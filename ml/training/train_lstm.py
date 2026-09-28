"""VacancyLSTM 33거점 pooled 학습 + 다음 분기 공실률 예측.

타깃: vac_proxy(대리 지표) 유지. v2 = R-ONE 실측(공실률 소규모/중대형·임대료)을 피처로
추가 — v1 대비 MAE 0.941→0.901, RMSE 1.361→1.147, 방향정확도 84.6% 동일.
실측(vac_small)을 타깃으로 쓰는 실험은 46.2%로 실패(표본개편 노이즈) — datasets.py 참조.

전략 (분기 데이터 → look_back 자동 조정, /platform-autorun B단계):
  - 거점당 분기 수가 적어(≈20) 단일 거점 학습 불가 → 전 거점 통합(pooled) + 거점 원핫.
  - 분할 = 거점별 **끝에서 두 번째 분기 = val**(선택용) · **마지막 분기 = test**(보고용).
    시계열이므로 무작위가 아니라 시간 순서를 지킨다.
  - 지표는 항상 **같은 분할의 베이스라인과 함께** 낸다: 방향은 무정보 상수(다수 방향),
    오차는 지속성(예측=직전값). 베이스라인 없는 정확도는 판정 근거가 아니다.

⚠ 2026-09-16 누수 차단 — 그 전 규약으로 학습한 산출물은 지표가 위로 편향돼 있다:
  ① 표준화 통계(mu/sd/y_mu/y_sd)를 홀드아웃 포함 전체 행에서 냈다(datasets.py).
  ② 하이퍼파라미터를 **보고와 같은 홀드아웃**에서 골랐고, 방향정확도가 0.70 을 넘는
     순간 멈췄다 — 즉 KPI 임계값이 곧 멈춤 규칙이었다.
  그렇게 나온 70.8% 는 같은 홀드아웃의 무정보 상수(항상 하락 78.5%)보다 낮다.
  → scripts/kpi_baseline.py · docs/finding-kpi-leak-2026-09-16.md
  산출물의 `protocol` 블록이 어느 규약으로 잰 값인지 밝힌다. 블록이 없으면 옛 규약이다.

산출:
  ml/artifacts/vacancy_lstm.pt              모델 + 전처리 메타 (predictor 가 로드)
  data/gold/platform_vacancy_forecast.json  거점별 다음 분기 예측 (서빙 폴백·정적 서빙용)
  ml/mlruns                                 MLflow 로컬 파일 스토어

실행: python -m ml.training.train_lstm
"""
from __future__ import annotations

import copy
import datetime
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

# 파이프라인이 출력을 파이프로 받으면 Windows 기본 인코딩이 cp949 로 잡혀
# 로그의 '—' 하나에 UnicodeEncodeError 로 죽는다(2026-07-22 refresh_platform 오탐 원인).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # 재설정 불가 스트림이면 그대로 둔다
    pass

from ml.models.lstm.vacancy_lstm import VacancyLSTM  # noqa: E402
from ml.training.lstm_grids import GRIDS, build_trials, serves  # noqa: E402
from ml.training.selection import select_trial  # noqa: E402
from ml.training.datasets import (  # noqa: E402
    SEQ_FEATURES,
    TARGET,
    TARGET_MODES,
    TEST_QUARTERS,
    VAL_QUARTERS,
    build_dataset,
    load_gold,
)

ARTIFACT = _REPO / "ml" / "artifacts" / "vacancy_lstm.pt"
FORECAST_JSON = _REPO / "data" / "gold" / "platform_vacancy_forecast.json"
MLRUNS = _REPO / "ml" / "mlruns"
# 시행 전체 기록 — 서빙 여부와 무관하게 매 실행 남긴다. 09-27 의 16 시행은 로그와 문서
# 표에만 남아, 서빙하지 않은 시행의 test 참고 판정을 다시 낼 방법이 없었다.
# 형식은 forecast json 과 같아 `kpi_baseline.check(forecast_path=…)` 가 그대로 읽는다.
REPORTS = _REPO / "reports"

_SEED = 42


def _train_once(hidden: int, layers: int, look_back: int | None, epochs: int = 400,
                lr: float = 1e-3, test_quarters: int = TEST_QUARTERS,
                val_quarters: int = VAL_QUARTERS, target_mode: str = "level",
                weight_decay: float = 0.0, patience: int | None = None) -> dict:
    """한 시행. `patience=None` 이면 조기종료 없이 `epochs` 를 다 돈다(종전 경로 그대로).

    `patience` 가 있으면 매 epoch 뒤 val MSE(표준화 단위 — 학습 손실과 같은 것)를 재고,
    가장 낮았던 epoch 의 가중치를 보관한다. `patience` epoch 동안 개선이 없으면 멈추고,
    상한까지 돈 경우에도 **보관한 최선으로 복원**한다(2026-09-28 사전등록 §2 b).
    ⚠ 그래서 이 모드에서는 val 이 두 번 쓰인다 — 멈춤과 후보 필터. 사전등록 §한계.
    """
    torch.manual_seed(_SEED)
    np.random.seed(_SEED)
    ds = build_dataset(look_back=look_back, test_quarters=test_quarters,
                       val_quarters=val_quarters, target_mode=target_mode)
    # 2026-09-16 누수 차단: 학습에서 val·test 를 **둘 다** 뺀다. 종전에는 test 만 빼고
    # 그 test 로 하이퍼파라미터까지 골랐다(main 참조) — 보고값이 test 가 아니었다.
    holdout = ds.sample_is_last
    val = ds.sample_is_val
    train = ~(holdout | val)
    Xtr, ytr = torch.from_numpy(ds.X[train]), torch.from_numpy(ds.y[train])
    Xte, yte = torch.from_numpy(ds.X[holdout]), torch.from_numpy(ds.y[holdout])
    Xva, yva = torch.from_numpy(ds.X[val]), torch.from_numpy(ds.y[val])

    model = VacancyLSTM(num_features=ds.X.shape[2], hidden=hidden, layers=layers,
                        dropout=0.2 if layers > 1 else 0.0)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    lossf = nn.MSELoss()
    # val 평가는 eval 모드·no_grad 라 난수를 소비하지 않는다 — 조기종료 팔도 멈추기 전까지는
    # 같은 시드의 400 epoch 경로와 가중치가 한 자리도 다르지 않다(wd=0 팔이 대조군인 이유).
    best_val, best_epoch, best_state = float("inf"), epochs, None
    stopped_epoch = epochs
    for ep in range(1, epochs + 1):
        model.train()
        opt.zero_grad()
        loss = lossf(model(Xtr).squeeze(-1), ytr)
        loss.backward()
        opt.step()
        if patience is None:
            continue
        model.eval()
        with torch.no_grad():
            vloss = float(lossf(model(Xva).squeeze(-1), yva))
        if vloss < best_val:
            best_val, best_epoch = vloss, ep
            best_state = copy.deepcopy(model.state_dict())
        elif ep - best_epoch >= patience:
            stopped_epoch = ep
            break
    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()

    def _score(X: torch.Tensor, ytrue: torch.Tensor, mask: np.ndarray) -> dict:
        """한 분할의 지표. 방향 기준값 prev = 그 윈도우 마지막 분기의 vac_proxy."""
        with torch.no_grad():
            pred = model(X).squeeze(-1).numpy() * ds.y_sd + ds.y_mu   # 원단위 복원
        actual = ytrue.numpy() * ds.y_sd + ds.y_mu
        if ds.target_mode == "delta":
            # Δ 모델 — 직전 원값에 더해 수준으로 되돌린다. 채점은 level 과 같은 단위다.
            prev = ds.y_prev[mask]
            pred, actual = prev + pred, prev + actual
        else:
            prev = ds.X[mask][:, -1, 0] * ds.sd[0] + ds.mu[0]
        # 베이스라인: 같은 분할에서 **입력을 안 보는** 상수 규칙(다수 방향)과 지속성.
        # 이것을 같이 내지 않으면 "70% 넘었다"가 실력인지 쏠림인지 구분할 수 없다
        # (2026-09-16 실측 — scripts/kpi_baseline.py).
        d_actual = np.sign(actual - prev)
        n = max(len(d_actual), 1)
        base_dir = max((d_actual > 0).sum(), (d_actual < 0).sum()) / n
        return {
            "pred": pred, "actual": actual, "prev": prev,
            "mae": float(np.mean(np.abs(pred - actual))),
            "rmse": float(np.sqrt(np.mean((pred - actual) ** 2))),
            "dir_acc": float(np.mean(np.sign(pred - prev) == d_actual)),
            "baseline_dir_acc": float(base_dir),
            "persistence_mae": float(np.mean(np.abs(prev - actual))),
            "n": int(n),
        }

    te = _score(Xte, yte, holdout)
    va = _score(Xva, yva, val)
    return {
        "model": model, "ds": ds,
        "pred": te["pred"], "actual": te["actual"], "prev": te["prev"],
        "mae": te["mae"], "rmse": te["rmse"], "dir_acc": te["dir_acc"],
        "test": te, "val": va,
        "params": {"hidden": hidden, "layers": layers, "look_back": int(ds.X.shape[1]),
                   "epochs": epochs, "lr": lr, "train_loss": float(loss.item()),
                   "test_quarters": test_quarters, "val_quarters": val_quarters,
                   "n_train": int(train.sum()), "target_mode": target_mode,
                   # 2026-09-28 사전등록 §2 d — 조기종료가 없으면 patience None ·
                   # stopped_epoch = best_epoch = epochs 로 남는다
                   "weight_decay": weight_decay, "patience": patience,
                   "stopped_epoch": stopped_epoch, "best_epoch": best_epoch,
                   "best_val_loss": None if best_state is None else round(best_val, 6)},
    }


def _log_mlflow(res: dict, run_name: str) -> None:
    try:
        import mlflow
        mlflow.set_tracking_uri(f"file:///{MLRUNS.as_posix()}")
        mlflow.set_experiment("platform_vacancy_lstm")
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params(res["params"])
            mlflow.log_metrics({"holdout_mae": res["mae"], "holdout_rmse": res["rmse"],
                                "holdout_dir_acc": res["dir_acc"]})
    except Exception as exc:  # MLflow 실패가 학습을 막지 않도록
        print(f"[mlflow] 기록 실패(무시): {exc}")


# 학습 규약 표기 — 산출물을 읽는 쪽이 **어느 규약으로 잰 값인지** 알 수 있어야 한다.
# 이 블록이 없는 산출물은 2026-09-16 이전 규약(표준화·선택 모두 홀드아웃 포함)이다.
_PROTOCOL = {
    "version": "2026-09-27",
    "scaling": "train_only",       # mu/sd/y_mu/y_sd 를 train 행에서만 적합
    "selection": "val",            # 하이퍼파라미터는 val 로 고른다
    "test_used_once": True,        # test 는 보고에만 쓴다(임계값 조기중단 없음)
    "baselines": ["majority_direction", "persistence"],
    "split": "rolling_origin",     # 거점마다 뒤쪽 K분기를 차례로 홀드아웃 원점으로
    # 2026-09-27 사전등록(docs/finding-lstm-delta-target-2026-09-26.md §0-B):
    # ① 선택 규칙 — ml/training/selection.py
    "selection_rule": "val_mae_beats_persistence_then_val_direction",
    # ③ 이미 본 test 분기의 마지막. kpi_baseline 은 이 **이후** 분기 holdout 만으로
    #   게이트를 판정하고, 그런 표본이 없으면 `확인대기` 다. 이 값은 올리지 않는다 —
    #   올리면 본 분기를 다시 확정 표본으로 쓰게 된다.
    "confirm_after": "20262",
}

_MAX_HORIZON = 4  # 재귀 예측 최대 분기 수


def _next_quarter(q: str) -> str:
    """'20261' → '20262', '20264' → '20271'."""
    y, qq = int(q[:4]), int(q[4])
    return f"{y + 1}1" if qq == 4 else f"{y}{qq + 1}"


def _forecast_next(res: dict) -> dict:
    """거점별 최신 look_back 분기 윈도우로 1~4분기 앞 vac_proxy 재귀 예측.

    h2+ 는 예측 타깃값(피처 0)을 윈도우에 되먹이고 나머지 외생 피처는 마지막 관측값으로
    고정(persistence)한다 — 외생 피처의 미래값을 모르는 상태의 보수적 근사. 검증된
    홀드아웃 지표(방향 84.6%)는 h1 기준이며 h2+ 는 불확실성이 커진다(응답에 명시).
    """
    ds, model = res["ds"], res["model"]
    df = load_gold()
    lb = res["params"]["look_back"]
    out: dict[str, dict] = {}
    skipped: list[str] = []
    model.eval()
    for di, did in enumerate(ds.district_ids):
        g = df[df["district_id"] == did]
        z = (g[list(SEQ_FEATURES)].to_numpy(dtype=np.float64) - ds.mu) / ds.sd
        if len(z) < lb:
            continue
        onehot = np.zeros(len(ds.district_ids))
        onehot[di] = 1.0
        win = z[-lb:].copy()
        if not np.isfinite(win).all():
            # 마지막 윈도우에 결측이 있으면 예측을 **내지 않는다**(채워서 내지 않는다).
            # 2026-09-04 현재 해당 거점 0곳 — R-ONE 결측은 전부 시계열 앞쪽이다.
            skipped.append(did)
            continue
        last = float(g[TARGET].iloc[-1])
        q = str(g["quarter"].iloc[-1])
        horizons: list[dict] = []
        prev = last
        for _ in range(_MAX_HORIZON):
            x = np.hstack([win, np.tile(onehot, (lb, 1))]).astype(np.float32)
            with torch.no_grad():
                p = float(model(torch.from_numpy(x[None])).item()) * ds.y_sd + ds.y_mu
            if ds.target_mode == "delta":
                p = prev + p        # Δ̂ → 수준. 재귀라 h2+ 는 앞 예측 위에 쌓인다
            q = _next_quarter(q)
            horizons.append({
                "quarter": q,
                "forecast_vac_proxy": round(p, 3),
                "delta": round(p - prev, 3),
                "direction": "up" if p > prev else "down",
            })
            # 되먹임: 마지막 관측 피처행을 복제하되 타깃(0열)만 예측값으로 교체
            nxt = win[-1].copy()
            nxt[0] = (p - ds.mu[0]) / ds.sd[0]
            win = np.vstack([win[1:], nxt])
            prev = p
        h1 = horizons[0]
        out[did] = {
            "forecast_vac_proxy": h1["forecast_vac_proxy"],
            "last_vac_proxy": round(last, 3),
            "delta": h1["delta"],
            "direction": h1["direction"],
            "last_quarter": str(g["quarter"].iloc[-1]),
            "n_quarters": int(len(g)),
            "horizons": horizons,
        }
    if skipped:
        print(f"[forecast] 결측으로 예측 제외 {len(skipped)}거점: {skipped}")
    return out


def main(test_quarters: int = TEST_QUARTERS, val_quarters: int = VAL_QUARTERS,
         grid: str = "default") -> None:
    now = datetime.datetime.now().isoformat(timespec="seconds")
    # 하이퍼파라미터 후보 — **전부 끝까지 돈다.** 종전의 "미달 시 재시도" 서술은
    # 임계값 조기중단을 전제한 것이라 2026-09-16 에 걷었다(아래 선택 블록 참조).
    # 기존 8 조합과 그 연혁은 `ml/training/lstm_grids.py::BASE_TRIALS` 로 옮겼다.
    # 2026-09-26: 타깃 모수화(level/delta)를 그리드의 한 축으로 넣는다. 선택 기준은
    # **그대로**다(val 방향 → val MAE). Δ 가 val MAE 로 이겨도 val 방향에서 지면 채택되지
    # 않는다 — 기준을 결과 보고 바꾸면 metric shopping 이다.
    # → docs/finding-lstm-delta-target-2026-09-26.md §0 사전등록
    # 2026-09-28: 그리드를 이름으로 고른다. `default` 는 위 16 시행 그대로이고,
    # `reg-0928` 은 가중치감쇠 × 조기종료 16 시행이다(사전등록 §2 c).
    trials = build_trials(grid, TARGET_MODES)
    print(f"[grid] {grid} — {len(trials)} 시행 · 사전등록 {GRIDS[grid]['prereg']}")
    # ── 선택은 val, 보고는 test (2026-09-16 누수 차단) ─────────────────────
    # 종전 코드는 ① test 로 8개 조합을 고르고 ② `dir_acc >= 0.70` 이면 즉시 멈췄다.
    # 그러면 보고되는 방향정확도는 "이 모델의 성능"이 아니라 **"8번 뽑아 목표를 넘긴
    # 값"** 이다. 최댓값 편향이고, 멈춤 규칙이 KPI 임계값이라 사실상 목표 달성을
    # 보장하는 절차였다. 실제로 그렇게 나온 70.8% 는 같은 홀드아웃의 무정보 상수
    # 규칙(항상 하락 78.5%)보다 낮다 — scripts/kpi_baseline.py.
    #
    # 그래서: ① 선택 기준을 val 로 옮기고 ② 임계값 조기중단을 없앤다. 모든 조합을
    # 끝까지 돌려야 test 가 **한 번만** 쓰인다.
    # 2026-09-27: 선택 규칙을 `ml/training/selection.py` 로 옮겼다(사전등록 §0-B ①) —
    # val 에서 지속성을 이긴 시행 중 방향 최대, 없으면 val MAE 최소. test 는 안 읽는다.
    results: list[dict] = []
    for i, hp in enumerate(trials):
        res = _train_once(**hp, test_quarters=test_quarters, val_quarters=val_quarters)
        v, p = res["val"], res["params"]
        stop = (f" · epoch {p['stopped_epoch']}(최선 {p['best_epoch']})"
                if p["patience"] is not None else "")
        print(f"[trial {i}] {hp} → val MAE {v['mae']:.3f} (지속성 {v['persistence_mae']:.3f}) "
              f"방향 {v['dir_acc']:.1%} (상수 {v['baseline_dir_acc']:.1%}){stop}", flush=True)
        _log_mlflow(res, run_name=f"trial{i}")
        results.append(res)

    chosen, selection = select_trial([r["val"] for r in results])
    best = results[chosen]
    bt, bv = best["test"], best["val"]
    print(f"[best] trial {chosen} {best['params']} — 후보 {selection['eligible']}/"
          f"{selection['trials']} (val MAE {bv['mae']:.3f} vs 지속성 "
          f"{bv['persistence_mae']:.3f} · val 방향 {bv['dir_acc']:.1%})")
    if selection["fallback"]:
        print("  ⚠ val 단계에서 이미 지속성 미달 — 지속성을 이긴 시행이 없어 val MAE 최소로 골랐다")
    print(f"  test MAE {bt['mae']:.3f} (지속성 {bt['persistence_mae']:.3f}) · "
          f"RMSE {bt['rmse']:.3f} · 방향 {bt['dir_acc']:.1%} "
          f"(무정보 상수 {bt['baseline_dir_acc']:.1%})")
    if bt["dir_acc"] <= bt["baseline_dir_acc"]:
        print("  ⚠ 방향 축에 실력이 없다 — 상수 규칙 이하다. "
              "임계값(70%)을 넘더라도 '달성'으로 적지 말 것.")
    if bt["mae"] >= bt["persistence_mae"]:
        print("  ⚠ 오차 축도 지속성 베이스라인 이하다.")

    # 홀드아웃 상세 — 키는 **거점@분기** 다. 롤링 오리진이면 한 거점이 여러 건을
    # 내므로 거점명만 키로 쓰면 dict 가 덮어써져 표본이 조용히 1/K 로 준다.
    # `hub` 필드를 따로 실어 `scripts/kpi_baseline.py` 가 **거점 단위로 군집**해
    # 부트스트랩 구간을 낼 수 있게 한다(같은 거점의 이웃 분기는 독립이 아니다).
    ds = best["ds"]
    hold_dids = [ds.district_ids[d] for d in ds.sample_district[ds.sample_is_last]]
    hold_qs = list(ds.sample_quarter[ds.sample_is_last])
    per_district = {
        f"{did}@{q}": {"hub": did, "quarter": str(q),
                       "pred": round(float(p), 3), "actual": round(float(a), 3),
                       "prev": round(float(v), 3),
                       "direction_hit": bool(np.sign(p - v) == np.sign(a - v))}
        for did, q, p, a, v in zip(hold_dids, hold_qs, best["pred"], best["actual"],
                                   best["prev"])
    }
    for key, m in per_district.items():
        print(f"  {key}: pred {m['pred']} vs actual {m['actual']} "
              f"({'O' if m['direction_hit'] else 'X'})")

    fc = _forecast_next(best)
    payload = {
        "model": "vacancy-lstm-pooled-v2",
        "target": "vac_proxy(공실 프록시) — R-ONE 실측(vac_small/vac_mid/rent_small)은 피처",
        "target_mode": ds.target_mode,
        "trained_at": now,
        "metrics": {"holdout_mae": round(bt["mae"], 3), "holdout_rmse": round(bt["rmse"], 3),
                    "holdout_direction_acc": round(bt["dir_acc"], 3),
                    # 베이스라인을 **지표와 같은 칸에** 싣는다. 따로 두면 인용할 때
                    # 떨어져 나가고, 떨어지는 순간 그 지표는 다시 판정 근거가 못 된다.
                    "baseline_direction_acc": round(bt["baseline_dir_acc"], 3),
                    "persistence_mae": round(bt["persistence_mae"], 3),
                    "direction_skill_pp": round((bt["dir_acc"] - bt["baseline_dir_acc"]) * 100, 1),
                    "mae_skill": round(1 - bt["mae"] / bt["persistence_mae"], 3)
                    if bt["persistence_mae"] else None,
                    "holdout_n": bt["n"],
                    "val_direction_acc": round(bv["dir_acc"], 3),
                    "val_mae": round(bv["mae"], 3)},
        "protocol": {**_PROTOCOL, "test_quarters": test_quarters,
                     "val_quarters": val_quarters,
                     "target_modes_searched": list(dict.fromkeys(t["target_mode"] for t in trials)),
                     "grid": grid,
                     # 조기종료가 켜지면 val 이 멈춤에도 쓰인다 — 읽는 쪽이 알게 밝힌다
                     "early_stopping": ("val_loss" if GRIDS[grid]["patience"] is not None
                                        else None)},
        "params": best["params"],
        "selection": selection,
        "holdout": per_district,
        "forecasts": fc,
    }

    # 시행 전체 기록 — val 은 전 시행, test 는 **고른 시행 하나만**(위 payload).
    # 고르지 않은 시행의 test 를 남기면 사후에 골라 인용할 수 있게 된다(KPI 규칙 3).
    served = serves(grid, selection)
    report = {**payload, "served": served,
              "trials": [{"trial": i, "params": r["params"],
                          "val": {k: r["val"][k] for k in
                                  ("mae", "persistence_mae", "dir_acc", "baseline_dir_acc", "n")}}
                         for i, r in enumerate(results)]}
    REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS / f"lstm_trials_{grid}_{now[:10]}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[report] {report_path}")

    # 2026-09-28 사전등록 §4 — 후보 0 이면 레버 기각이고, 기각된 레버의 fallback 시행을
    # 서빙에 올리지 않는다. `default` 그리드는 09-27 처럼 fallback 도 교체한다.
    if not served:
        print(f"⛔ 후보 0/{selection['trials']} — 사전등록({GRIDS[grid]['prereg']}) §4: "
              "레버 기각. 서빙 산출물(vacancy_lstm.pt · platform_vacancy_forecast.json)을 "
              "바꾸지 않는다. 고른 시행의 참고 판정은 위 리포트로 낸다")
        return

    # 모델 아티팩트
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "state_dict": best["model"].state_dict(),
        "num_features": ds.X.shape[2],
        "params": best["params"],
        "district_ids": ds.district_ids,
        "mu": ds.mu.tolist(), "sd": ds.sd.tolist(),
        "y_mu": ds.y_mu, "y_sd": ds.y_sd,
        # 서빙(ml/inference/predictor.py)이 이 값으로 복원 방식을 고른다 — 빠지면 Δ 모델
        # 출력을 수준으로 읽어 **조용히** 틀린 값을 낸다(09-24 holdout 키 결함과 같은 모양).
        "target_mode": ds.target_mode,
        "protocol": _PROTOCOL,
    }, ARTIFACT)
    print(f"[artifact] {ARTIFACT}")

    # 서빙용 forecast json
    FORECAST_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[forecast] {FORECAST_JSON} — {len(fc)}거점")


if __name__ == "__main__":
    import argparse

    _ap = argparse.ArgumentParser(description="VacancyLSTM 학습 — 롤링 오리진 분할")
    _ap.add_argument("--test-quarters", type=int, default=TEST_QUARTERS,
                     help="거점당 test 원점 수(보고용). 1 이면 2026-09-16 이전 규약과 같은 분할")
    _ap.add_argument("--val-quarters", type=int, default=VAL_QUARTERS,
                     help="거점당 val 원점 수(하이퍼파라미터 선택용)")
    _ap.add_argument("--grid", choices=sorted(GRIDS), default="default",
                     help="시행 그리드(ml/training/lstm_grids.py). default = level×delta 16 · "
                          "reg-0928 = 가중치감쇠×조기종료 16(2026-09-28 사전등록)")
    _a = _ap.parse_args()
    main(test_quarters=_a.test_quarters, val_quarters=_a.val_quarters, grid=_a.grid)
