"""Platform·LSTM 공실 예측 서빙 — gold/platform_vacancy_forecast.json 직접 로드.

ml/inference/predictor.py 와 같은 배치 산출물을 읽지만, 배포 이미지(Cloud Run ·
apps/backend/requirements.txt)에 torch/ml 의존을 싣지 않으므로 백엔드는 json 정적
서빙이 기본 경로다.
Redis 를 실제로 쓰는 코드가 아직 없다 — 인메모리 TTL 캐시로 파일 재읽기를 줄인다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.services import forecast_skill

# repo/data/gold/platform_vacancy_forecast.json (services → app → backend → apps → repo)
_GOLD = Path(__file__).resolve().parents[4] / "data" / "gold"
_FORECAST_JSON = _GOLD / "platform_vacancy_forecast.json"
_CALIBRATION_JSON = _GOLD / "garosugil" / "calibration.json"
_TTL_SECONDS = 300.0

# 지상검증 실측 앵커 보유 거점 (garosugil PoC exit 통과분)
_ANCHOR_DISTRICTS = {"garosugil"}

_cache: dict[str, Any] = {}

# 응답 `metrics` 에서 빼는 키 — **종전 기준**(다수방향 상수 · 지속성)에 댄 실력 값이다.
# 2026-09-30 개정 뒤 판정 기준은 "두 무정보 규칙 중 강한 쪽"이라, 거점 평균·'평균 쪽'이
# 더 강하면 이 값은 실력을 부풀린다(reg-0928: 방향 +25.0%p vs 판정 +11.3%p · 오차
# +30.9% vs 판정 +17.6%). 판정 값은 같은 응답의 `skill` 에 있다. 산출물(JSON)은 그대로
# 두고 응답에서만 뺀다 — 옛 키(09-29 서빙본)와 train_lstm 이 다음 학습부터 쓰는 키 둘 다.
_LEGACY_SKILL_KEYS = frozenset({
    "direction_skill_pp", "mae_skill",                                  # 09-29 서빙본까지
    "direction_skill_pp_vs_constant", "mae_skill_vs_persistence",       # 다음 학습부터
    "legacy_skill_basis",
})


def _public_metrics(metrics: dict | None) -> dict | None:
    """산출물 metrics 에서 종전 기준 실력 값을 뺀 사본 — 원본(캐시)은 건드리지 않는다."""
    if metrics is None:
        return None
    return {k: v for k, v in metrics.items() if k not in _LEGACY_SKILL_KEYS}


def _anchor(district_id: str) -> dict | None:
    """building_vacancy PoC 실측 보정값을 참조 앵커로 부착 (단일 시점 스냅샷)."""
    if district_id not in _ANCHOR_DISTRICTS or not _CALIBRATION_JSON.exists():
        return None
    if "anchor" not in _cache:
        import datetime

        cal = json.loads(_CALIBRATION_JSON.read_text(encoding="utf-8"))
        # 대표값은 rone_aligned.mid — R-ONE 과 같은 모집단(일반건축물·상가 주용도·
        # 중대형 규모)·단위(면적 기준)로 잰 값이다(2026-08-01). primary 는 집합건물이
        # 섞여 있어 앵커 대조 시 과대추정된다. combined 는 방법 구성비에 흔들린다.
        mid = (cal.get("rone_aligned") or {}).get("mid") or {}
        primary = cal.get("primary") or {}
        _cache["anchor"] = {
            "estimated_vacancy_pct": mid.get("vacancy_area_pct")
                                     or primary.get("estimated_vacancy_pct")
                                     or cal.get("estimated_vacancy_pct"),
            "vacancy_band_pct": ([mid["vacancy_floor_hi_pct"], mid["vacancy_floor_lo_pct"]]
                                 if "vacancy_floor_lo_pct" in mid else None),
            "anchor_street_pct": cal.get("anchor_pct"),
            "buildings_used": mid.get("buildings") or primary.get("buildings")
                              or cal.get("buildings_used"),
            "as_of": datetime.date.fromtimestamp(
                _CALIBRATION_JSON.stat().st_mtime).isoformat(),
            "source": "building_vacancy PoC 지상검증(정확도 75%) — 단일 시점 스냅샷",
        }
    return _cache["anchor"]


def _load() -> dict | None:
    now = time.monotonic()
    if _cache.get("data") is not None and now - _cache.get("at", 0.0) < _TTL_SECONDS:
        return _cache["data"]
    if not _FORECAST_JSON.exists():
        return None
    _cache["data"] = json.loads(_FORECAST_JSON.read_text(encoding="utf-8"))
    _cache["at"] = now
    return _cache["data"]


def get_forecast(district_id: str, quarters: int = 1) -> dict | None:
    """거점의 다음 분기 공실 프록시 예측. 미지원 거점 또는 파일 부재 시 None.

    quarters(1~4): 재귀 예측 horizon 선택. h2+ 는 외생 피처를 마지막 관측값으로
    고정한 근사라 불확실성이 커진다 (검증 지표는 h1 기준 — 응답 metrics 참조).
    """
    fc = _load()
    if fc is None:
        return None
    item = fc.get("forecasts", {}).get(district_id)
    if item is None:
        return None
    out = {
        "district_id": district_id,
        **item,
        "metrics": _public_metrics(fc.get("metrics")),
        "model": fc.get("model", "vacancy-lstm-pooled-v2"),
        "trained_at": fc.get("trained_at"),
        "source": "forecast_json",
    }
    horizons = item.get("horizons") or []
    q = max(1, min(quarters, len(horizons) or 1))
    if horizons and q > 1:
        sel = horizons[q - 1]
        out.update({
            "forecast_vac_proxy": sel["forecast_vac_proxy"],
            "forecast_quarter": sel["quarter"],
            # delta·direction 은 마지막 관측 분기 대비로 재계산
            "delta": round(sel["forecast_vac_proxy"] - item.get("last_vac_proxy", 0.0), 3),
            "direction": "up" if sel["forecast_vac_proxy"] > item.get("last_vac_proxy", 0.0) else "down",
        })
    out["horizon_quarters"] = q
    # 베이스라인 대비 실력 판정 — 화면이 예측 옆에 성능 숫자를 **박지 않고** 여기서 읽는다.
    out["skill"] = skill_summary()
    # 이 거점의 홀드아웃 — 전체 MAE 옆에 붙여 "이 거점에서 실제로 얼마나 틀렸나"를
    # 같이 보여준다. 평균만 내놓으면 거점별 오차가 평균 뒤에 숨는다.
    #
    # ⚠ **2026-09-24 키 형식이 바뀌었다.** 누수 차단 재학습이 롤링 오리진
    # (`protocol.split == "rolling_origin"`)으로 가면서 거점당 홀드아웃이 1점 → **3점**
    # (test_quarters)이 됐고, 키도 `anam` → **`anam@20254`** 로 갈렸다. 종전처럼
    # `.get(district_id)` 로 집으면 **전 거점이 조용히 None** 이 된다 — 에러가 아니라
    # `district_holdout` 키가 통째로 빠져서, 화면이 "이 거점 오차"를 못 그린다.
    # 옛 형식(거점 키 = 1점)도 계속 받는다.
    rows = fc.get("holdout") or {}
    if district_id in rows:                      # 옛 형식
        out["district_holdout"] = rows[district_id]
    else:                                        # 롤링 오리진 — 분기 오름차순
        mine = {k.split("@", 1)[1]: v for k, v in rows.items()
                if k.split("@", 1)[0] == district_id and "@" in k}
        if mine:
            out["district_holdout_points"] = [mine[q] for q in sorted(mine)]
            # 하위호환: 가장 최근 분기 1점을 종전 키로도 준다
            out["district_holdout"] = out["district_holdout_points"][-1]
    anchor = _anchor(district_id)
    if anchor:
        out["ground_anchor"] = anchor
    return out


def skill_summary() -> dict | None:
    """LSTM 이 베이스라인을 이기는가 — `scripts/kpi_baseline.py` 와 같은 판정(같은 코드).

    화면용으로 줄인 요약이다. 두 축(오차 · 방향)을 **둘 다** 준다 —
    하나만 인용하면 어느 쪽이든 거짓이 된다(`forecast_skill.lstm_skill` 독스트링).
    `verdict` 는 전체 holdout 의 **참고** 판정, `gate_verdict` 는 `protocol.confirm_after`
    이후(본 적 없는) 분기로만 낸 판정이다 — 그런 표본이 0건이면 `확인대기`.
    균형정확도·MCC 는 관측 전용이라 싣지 않는다(판정에 쓰지 않는다).
    기준은 축마다 두 무정보 규칙 중 **강한 쪽**이고(오차: 지속성·거점 평균 · 방향: 다수방향
    상수·'평균 쪽'), 어느 쪽이었는지 `baseline_label` 로 싣는다. 거점 평균(`clim`)이 없는
    산출물(09-27 서빙본)은 종전 기준(지속성 · 상수)이고 `baseline_basis = legacy_no_clim`.

    산출물이 없거나 holdout 이 비면 None — 화면은 그때 문구를 **숨긴다**(옛 값 폴백 없음).
    부트스트랩(2000회)이 있어 산출물을 다시 읽을 때만 새로 계산한다.
    """
    fc = _load()
    if fc is None:
        return None
    if _cache.get("skill_for") is fc:
        return _cache.get("skill")
    res = forecast_skill.lstm_skill(fc)
    summary: dict | None = None
    if res.get("available"):
        forecast_skill.apply_confirmation(res, fc)
        e, d = res["error"], res["direction"]
        cf = res.get("confirmation") or {}
        summary = {
            "n": res["n"],
            "n_hubs": res["n_hubs"],
            "n_forecast_hubs": len(fc.get("forecasts") or {}),
            "confirm_after": cf.get("after"),
            "n_fresh": cf.get("n_fresh"),
            # 2026-09-30: 두 기준 중 강한 쪽(strongest_of_two) · `clim` 없는 산출물은
            # 종전 기준으로 물러난다(legacy_no_clim). 화면은 아래 `baseline_label` 을 읽는다
            "baseline_basis": res["baseline_basis"],
            "error": {
                "model_mae": e["model_mae"],
                "persistence_mae": e["persistence_mae"],
                "baseline_label": e["baseline_label"],
                "baseline_mae": e["baseline_mae"],
                "mae_skill": e["mae_skill"],
                "mae_skill_ci95": e["mae_skill_ci95"],
                "verdict": e["verdict"],
                "gate_verdict": e["gate_verdict"],
            },
            "direction": {
                "model_acc": d["model_acc"],
                "baseline_acc": d["baseline_acc"],
                "baseline_label": d["baseline_label"],
                "skill_pp": d["skill_pp"],
                "skill_ci95_pp": d["skill_ci95_pp"],
                "mcnemar_p": d["mcnemar"]["p_two_sided"],
                "verdict": d["verdict"],
                "gate_verdict": d["gate_verdict"],
            },
        }
    _cache["skill_for"], _cache["skill"] = fc, summary
    return summary


def all_forecasts() -> dict[str, dict]:
    """전 거점 forecast 맵 — heatmap/대시보드 predicted_rate 조인용(D단계)."""
    fc = _load() or {}
    return fc.get("forecasts", {})


def is_available() -> bool:
    return _load() is not None
