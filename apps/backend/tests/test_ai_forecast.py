"""AI 공실 예측 API 테스트 — platform_vacancy_forecast.json 서빙 검증 (C단계)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data.measured_pages import MEASURED_BY_ID
from app.main import app
from tests.test_districts import SEOUL_DISTRICT_IDS

client = TestClient(app)
V1 = "/api/v1"
_GOLD = Path(__file__).resolve().parents[3] / "data" / "gold"


def test_predict_vacancy_all_districts():
    for did in SEOUL_DISTRICT_IDS:
        r = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": did})
        assert r.status_code == 200, did
        body = r.json()
        assert body["district_id"] == did
        assert isinstance(body["forecast_vac_proxy"], (int, float)), did
        assert body["direction"] in ("up", "down"), did
        assert body["model"].startswith("vacancy-lstm-pooled")
        # 게이트 재설계(2026-07-25, 43거점): 방향정확도를 하드 KPI 에서 내리고 MAE 를 주지표로.
        # 이유 — 홀드아웃이 거점당 1분기(43점)뿐이라 방향정확도는 한 거점 뒤집힘에 ±2.3%p 흔들리는
        # 노이즈 지표다. 최적 조합을 시드 10개로 돌린 결과 평균 67.0%·표준편차 3.9%·범위 58~72%,
        # 70% 도달은 1/10 이었다(38거점의 81.6%가 오히려 예외적 상단이었다). 반면 MAE 는 시드 전반
        # 1.1~1.36 으로 안정적이다. "70%"는 Phase 1(13거점·동질적)에서 정한 값이라 43개 이질적
        # Page(오피스 teheran·도매 garak·패션 namdaemun)에는 하드 게이트로 맞지 않는다.
        m = body["metrics"]
        # 주지표: MAE.
        #
        # ⚠ **2026-09-24 절대 임계 1.5 를 베이스라인 상대로 바꿨다.** 그 값은 홀드아웃이
        # 거점당 **1분기**(43점)일 때 시드 최악치 1.36 에 여유를 둔 것이었는데, 누수 차단
        # 재학습이 롤링 오리진으로 가며 거점당 **3분기**(240점)가 됐다. 더 먼 분기까지
        # 예측하니 MAE 가 커지는 것은 파손이 아니라 **재는 대상이 달라진 것**이고,
        # 실제로 1.061 → 2.224 가 됐다. 낡은 절대선을 그대로 두면 정상 산출물이 매번 깨진다.
        #
        # 이 단언은 **붕괴 감지기**이지 KPI 판정이 아니다. "지속성보다 나은가"라는 실력
        # 판정은 `scripts/kpi_baseline.py` 와 `pppp_status` 의 `KPI 공실예측 오차 실력`
        # 게이트가 맡는다 — 그 게이트는 2026-09-24 현재 **0% 로 열려 있고**, 그게 맞다
        # (모델 2.224 vs 지속성 1.190). 여기서 같은 것을 두 번 재면 한쪽을 완화하려는
        # 압력이 판정 지표까지 흔든다.
        #
        # 그래서 여기서는 **같은 산출물이 들고 있는 지속성 값의 3배**를 상한으로 둔다.
        # NaN 붕괴·전 거점 동일값·스케일 파손처럼 자릿수가 틀어지는 것만 잡는 느슨한 선이다.
        persistence = m.get("persistence_mae")
        cap = persistence * 3 if persistence else 5.0
        assert m["holdout_mae"] <= cap, (
            f"{did}: MAE {m['holdout_mae']} > 지속성×3 {cap:.3f} — 모델 붕괴 의심. "
            f"실력 판정은 scripts/kpi_baseline.py 를 볼 것")
        # 하한: 방향정확도. NaN 붕괴(전 거점 동일값 → 0%)·랜덤(≈50%) 같은 실제 파손만 잡는
        # 느슨한 바닥. 시드 스터디 최저(58%)보다 아래로 두어 시드 변동에 오탐하지 않는다.
        assert m["holdout_direction_acc"] >= 0.55, did


def test_predict_vacancy_unknown_district_404():
    r = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": "nope"})
    assert r.status_code == 404


def test_predict_vacancy_horizon_selection():
    """horizon_months → 분기 환산(올림, 1~4 클램프) + horizons 재귀 예측 선택."""
    r1 = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": "garosugil"})
    r6 = client.post(f"{V1}/ai/predict-vacancy",
                     json={"district_id": "garosugil", "horizon_months": 6})
    b1, b6 = r1.json(), r6.json()
    assert b1["horizon_quarters"] == 1
    assert b6["horizon_quarters"] == 2
    assert len(b1["horizons"]) == 4
    assert b6["forecast_vac_proxy"] == b1["horizons"][1]["forecast_vac_proxy"]
    # 12개월(4분기) 초과분은 4로 클램프
    b24 = client.post(f"{V1}/ai/predict-vacancy",
                      json={"district_id": "garosugil", "horizon_months": 24}).json()
    assert b24["horizon_quarters"] == 4


def test_predict_vacancy_garosugil_ground_anchor():
    """garosugil 은 PoC 지상검증 실측 앵커가 응답에 부착돼야 한다."""
    body = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": "garosugil"}).json()
    anchor = body.get("ground_anchor")
    # 값을 박제하지 않는다 — 파이프라인이 재산출할 때마다 바뀌므로 산출물과 대조한다
    # (2026-08-01: 39.1 로 박제돼 있어 07-28 재산출 이후 계속 실패하고 있었다).
    cal = json.loads((_GOLD / "garosugil" / "calibration.json").read_text(encoding="utf-8"))
    expected = ((cal.get("rone_aligned") or {}).get("mid") or {}).get("vacancy_area_pct")
    assert anchor and anchor["estimated_vacancy_pct"] == expected
    assert 0 < anchor["estimated_vacancy_pct"] < 100
    # 앵커 미보유 거점에는 없어야 한다
    body2 = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": "hongdae"}).json()
    assert "ground_anchor" not in body2


def test_predict_vacancy_carries_this_districts_holdout():
    """거점별 홀드아웃 1점이 응답에 실려야 한다 — 전체 MAE 뒤에 거점 오차를 숨기지 않는다.

    값은 박제하지 않는다(재학습마다 바뀐다). 산출물과 대조하고 전 거점 보유를 센다.

    ⚠ **2026-09-24 키 형식이 바뀌었다.** 누수 차단 재학습이 롤링 오리진으로 가며
    홀드아웃이 거점당 1점 → **3점**(test_quarters)이 됐고, 키가 `anam` → `anam@20254`
    로 갈렸다. 종전처럼 키 집합을 거점 id 와 직접 비교하면 **전 거점이 미보유로 잡힌다.**
    거점 부분만 떼어 비교한다(옛 형식도 그대로 통과한다).
    """
    fc = json.loads((_GOLD / "platform_vacancy_forecast.json").read_text(encoding="utf-8"))
    expected = {k.split("@", 1)[0] for k in fc["holdout"]}
    missing = set(SEOUL_DISTRICT_IDS) - expected
    assert not missing, f"홀드아웃 미보유 거점: {sorted(missing)}"
    rows = fc["holdout"]
    for did in SEOUL_DISTRICT_IDS:
        body = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": did}).json()
        h = body.get("district_holdout")
        assert h is not None, did
        assert isinstance(h["pred"], (int, float)) and isinstance(h["actual"], (int, float))
        assert isinstance(h["direction_hit"], bool), did

        # 산출물과 대조 — 롤링 오리진이면 **가장 최근 분기 1점**이 이 키로 온다.
        mine = {k.split("@", 1)[1]: v for k, v in rows.items()
                if "@" in k and k.split("@", 1)[0] == did}
        if mine:
            assert h == mine[max(mine)], did
            # 전 분기는 별도 키로 순서대로 함께 온다 — 거점 오차 추이를 화면이 그릴 수 있어야 한다.
            pts = body.get("district_holdout_points")
            assert pts == [mine[q] for q in sorted(mine)], did
        else:                                    # 옛 형식(거점 키 = 1점)
            assert h == rows[did], did


def test_district_summaries_carry_predicted_rate():
    """D단계 — 대시보드 응답에 다음 분기 예측 필드가 실려야 한다."""
    r = client.get(f"{V1}/commercial-districts")
    assert r.status_code == 200
    for d in r.json():
        assert "predicted_rate" in d, d["id"]
        assert "predicted_direction" in d, d["id"]
        # None 이 정상인 자리는 둘이다.
        #   ① 서울 pooled LSTM 범위 밖인 실측 거점(경기)
        #   ② 거점 대표 공실률을 내린 거점 — predicted_rate 는 대표값 + delta 라,
        #      이것만 남기면 화면이 내린 수를 되계산한다(app/data/hub_caveats).
        if d["predicted_rate"] is None:
            assert d["id"] in MEASURED_BY_ID or d["vacancy_withheld"], d["id"]
            assert d["predicted_direction"] is None, d["id"]
            continue
        if d["id"] not in MEASURED_BY_ID:
            assert d["predicted_rate"] is not None, d["id"]
        assert 0 <= d["predicted_rate"] <= 100
        assert d["predicted_direction"] in ("up", "down")


def test_heatmap_carries_predicted_rate():
    r = client.get(f"{V1}/heatmap/vacancy", params={"district": "garosugil"})
    assert r.status_code == 200
    hm = r.json()
    assert hm["predicted_rate"] is not None
    assert hm["predicted_direction"] in ("up", "down")


def test_forecast_skill_matches_kpi_baseline():
    """화면이 읽는 판정(`skill`)은 `scripts/kpi_baseline.py` 와 **같은 값**이어야 한다.

    2026-09-28: 화면에 07-25 MAE 1.109 가 박혀 있었다(실제 2.065, 지속성 1.190).
    판정을 백엔드가 kpi_baseline 과 같은 코드로 내고, 화면은 그 값만 읽는다.
    두 출처가 갈리면 그 자체가 이 테스트가 막으려는 실패다.
    """
    import importlib.util

    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("kpi_baseline_t", root / "scripts" / "kpi_baseline.py")
    kb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kb)
    ref = kb.check()["lstm"]

    r = client.get(f"{V1}/ai/forecast-skill")
    assert r.status_code == 200
    s = r.json()["skill"]
    assert s is not None
    assert s["n"] == ref["n"]
    for axis in ("error", "direction"):
        assert s[axis]["verdict"] == ref[axis]["verdict"], axis
        assert s[axis]["gate_verdict"] == ref[axis]["gate_verdict"], axis
    assert s["error"]["mae_skill_ci95"] == ref["error"]["mae_skill_ci95"]
    assert s["direction"]["skill_ci95_pp"] == ref["direction"]["skill_ci95_pp"]
    # 판정 어휘는 네 가지뿐이다 — 임계값 문구("정확도 70%")가 끼어들 자리가 없다
    allowed = {"실력", "구분불가", "열위", "확인대기", "검정불가"}
    assert {s["error"]["gate_verdict"], s["direction"]["gate_verdict"]} <= allowed
    # 관측 전용 지표(균형정확도·MCC)는 화면 요약에 싣지 않는다 — 판정에 쓰지 않는다
    assert "observed" not in s["direction"]


def test_forecast_skill_on_the_reg0928_artifact_uses_the_strongest_baselines():
    """reg-0928 서빙본(2026-09-29 · trial 10)은 `clim` 을 싣는다 → 두 기준 중 강한 쪽으로 판정한다.

    09-27 서빙본(`clim` 없음 · 종전 기준 · 참고 열위/구분불가)의 잠금을 이 산출물로 옮겼다.
    종전 기준으로 물러나는 경로는 data/tests/test_kpi_baseline.py 의 합성 테스트가 잠근다.
    화면(`lib/forecastSkill.ts`)이 읽는 값 — 판정 네 칸 · 기준 이름 · 기준 MAE — 을 잠근다.
    참고 판정이 두 축 모두 `실력`이어도 게이트는 `확인대기`라 LSTM 은 접힌 채다(B안 · #48).
    ⚠ 서빙 산출물이 다시 학습되면 이 테스트는 **skip 된다** — 그 산출물로 잠금을 옮길 것.
    """
    fc = json.loads((_GOLD / "platform_vacancy_forecast.json").read_text(encoding="utf-8"))
    if (fc.get("protocol") or {}).get("grid") != "reg-0928":
        pytest.skip("서빙 산출물이 reg-0928 학습본이 아니다 — 이 잠금은 그 서빙본 전용")
    s = client.get(f"{V1}/ai/forecast-skill").json()["skill"]
    assert s["baseline_basis"] == "strongest_of_two"
    assert s["error"]["baseline_label"] == "거점 평균"
    # 화면 요약에는 거점 평균 MAE 칸이 따로 없다 — 기준 값(baseline_mae)이 지속성보다 강한지만 본다.
    # baseline_mae == 거점 평균 MAE 는 data/tests/test_kpi_baseline.py 가 잠근다
    assert s["error"]["baseline_mae"] < s["error"]["persistence_mae"]
    assert s["direction"]["baseline_label"] == "평균 쪽"
    # 2026-09-29 kpi_baseline 으로 확인한 판정 — 참고 실력 · 게이트 확인대기(20262 이후 0건)
    assert (s["error"]["verdict"], s["error"]["gate_verdict"]) == ("실력", "확인대기")
    assert (s["direction"]["verdict"], s["direction"]["gate_verdict"]) == ("실력", "확인대기")
    assert s["n"] == 240 and s["n_fresh"] == 0


def test_predict_vacancy_carries_skill():
    r = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": "garosugil"})
    assert r.status_code == 200
    s = r.json()["skill"]
    assert s["n_forecast_hubs"] == len(json.loads(
        (_GOLD / "platform_vacancy_forecast.json").read_text(encoding="utf-8"))["forecasts"])
    assert s["error"]["persistence_mae"] > 0


def test_predict_vacancy_metrics_drop_legacy_skill_values():
    """응답 `metrics` 에 종전 기준(상수·지속성) 실력 값이 새지 않는다 — 판정은 `skill` 이다.

    2026-09-30: reg-0928 산출물의 `direction_skill_pp` 는 +25.0%p(vs 상수)인데 판정 값은
    +11.3%p(vs '평균 쪽')다. 같은 응답에 두 값이 있으면 앞의 것이 판정으로 인용된다.
    """
    from app.services import vacancy_forecast as vf

    r = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": "garosugil"})
    assert r.status_code == 200
    m = r.json()["metrics"]
    assert m and "holdout_mae" in m                       # 나머지 지표는 그대로 나간다
    assert not (vf._LEGACY_SKILL_KEYS & set(m)), sorted(vf._LEGACY_SKILL_KEYS & set(m))
    # 원본(캐시)은 건드리지 않는다 — 산출물 수정 금지
    raw = json.loads((_GOLD / "platform_vacancy_forecast.json").read_text(encoding="utf-8"))
    assert vf._LEGACY_SKILL_KEYS & set(raw["metrics"])      # 옛 키든 개명본이든 원본엔 있다
    assert vf._LEGACY_SKILL_KEYS & set(vf._load()["metrics"])
