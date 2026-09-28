"""LSTM 하이퍼파라미터 선택 규칙 — val 지표만 보고 한 시행을 고른다.

torch 없이 import 되도록 `train_lstm` 에서 떼어 냈다 — 기본 러너에 torch 가 없어도
규칙을 수치로 시험할 수 있어야 한다(data/tests/test_lstm_leakage.py).

## 규칙 (2026-09-27 사전등록 · docs/finding-lstm-delta-target-2026-09-26.md §0-B ①)

1. **val MAE < 같은 val 분할의 지속성 MAE** 인 시행만 후보로 남긴다.
2. 후보 중 **val 방향정확도 최대**, 동률이면 val MAE 최소.
3. 후보가 없으면 **val MAE 최소**, 동률이면 val 방향 최대 — 그리고 `fallback=True`
   로 "val 단계에서 이미 지속성 미달"을 산출물에 남긴다.

종전 규칙(val 방향 최대 하나)은 09-24 에 val MAE 1.574 를 두고 1.728 을 골랐다.
한 기준으로 두 게이트를 노리다 오차 축을 버린 것이다. 제품이 파는 것은 공실 압력의
**크기**라 지속성 대비 오차를 먼저 거른다.

## 개정 (2026-09-30 · docs/finding-lstm-regularization-prereg-2026-09-28.md §개정)

`baseline="strongest"` 면 1. 의 기준이 **지속성과 거점 평균 중 val MAE 가 낮은 쪽**이다.
거점 평균만 내밀어도 val 에서 지속성을 크게 이기므로(0.905 vs 1.338), 지속성만 넘은 시행은
평균회귀만으로 후보가 될 수 있다. `reg-0928` 그리드가 이것을 쓰고, `default` 그리드는 09-26
사전등록 그대로 `persistence` 다(`lstm_grids.GRIDS[*]["selection_baseline"]`).
2.·3. 은 바뀌지 않는다.

⚠ test 지표는 **절대 읽지 않는다**(선택 ≠ 보고, KPI 규칙 3). 인자는 val 블록뿐이다.
"""
from __future__ import annotations

RULE = "val_mae_beats_persistence_then_val_direction"
RULE_STRONGEST = "val_mae_beats_strongest_baseline_then_val_direction"
BASELINES = ("persistence", "strongest")


def filter_mae(v: dict, baseline: str = "persistence") -> tuple[float, str]:
    """후보 필터가 댈 val MAE 와 그 기준 이름.

    `strongest` 인데 val 블록에 `climatology_mae` 가 없으면 **멈춘다** — 조용히 지속성으로
    물러나면 개정한 기준이 한 시행에서만 빠져도 알아챌 수 없다.
    """
    if baseline == "persistence":
        return v["persistence_mae"], "persistence"
    if baseline != "strongest":
        raise ValueError(f"알 수 없는 기준: {baseline!r} — {BASELINES}")
    clim = v.get("climatology_mae")
    if clim is None:
        raise ValueError("strongest 기준인데 val 블록에 climatology_mae 가 없다")
    # 동률이면 지속성(종전 기준) — forecast_skill.lstm_skill 과 같은 규칙
    return (clim, "climatology") if clim < v["persistence_mae"] else (
        v["persistence_mae"], "persistence")


def select_trial(vals: list[dict], baseline: str = "persistence") -> tuple[int, dict]:
    """시행별 val 지표 목록 → (고른 인덱스, 선택 기록).

    각 원소는 `_score` 가 내는 val 블록이다: `mae` · `persistence_mae` · `dir_acc`
    (`baseline="strongest"` 면 `climatology_mae` 도).
    """
    if not vals:
        raise ValueError("시행이 없다")
    bars = [filter_mae(v, baseline) for v in vals]
    eligible = [i for i, v in enumerate(vals) if v["mae"] < bars[i][0]]
    if eligible:
        # 방향 최대 → 동률이면 MAE 최소. 인덱스를 마지막 키로 둬 먼저 나온 시행이 이긴다.
        idx = max(eligible, key=lambda i: (vals[i]["dir_acc"], -vals[i]["mae"], -i))
        fallback = False
    else:
        idx = min(range(len(vals)), key=lambda i: (vals[i]["mae"], -vals[i]["dir_acc"], i))
        fallback = True
    return idx, {
        "rule": RULE_STRONGEST if baseline == "strongest" else RULE,
        "baseline": baseline,
        # 고른 시행의 val 에서 어느 기준이 강했는가(필터가 실제로 댄 쪽)
        "baseline_label": bars[idx][1],
        "baseline_mae": bars[idx][0],
        "eligible": len(eligible),
        "trials": len(vals),
        "fallback": fallback,
        "chosen": idx,
    }
