"""LSTM 무정보 베이스라인 — 거점 평균(climatology)과 '평균 쪽' 방향 규칙.

torch 없이 import 되도록 `train_lstm` 에서 떼어 냈다(`selection.py` · `lstm_grids.py` 와 같은
이유 — 기본 테스트 러너에서 수치로 시험할 수 있어야 한다). numpy 만 쓴다.

## 왜 (2026-09-30 사전등록 개정)

`vac_proxy` 는 평균으로 되돌아가는 지표라 **그 거점 train 기간 평균을 그대로 내미는 규칙**이
val 에서 지속성보다 MAE 가 32% 낮다(0.905 vs 1.338). 지속성만 기준으로 두면 조기종료 모델의
평균회귀가 `실력`으로 통과한다 → docs/finding-lstm-climatology-baseline-2026-09-28.md §2 · §3.
그래서 오차는 지속성·거점 평균 중, 방향은 다수방향 상수·'평균 쪽' 중 **강한 쪽**에 댄다
→ docs/finding-lstm-regularization-prereg-2026-09-28.md §개정.

⚠ 거점 평균은 **train 행에서만** 낸다 — val·test 타깃을 보면 그 자체가 누수다(표준화 통계와
같은 규약 · datasets.build_dataset).
"""
from __future__ import annotations

import numpy as np


def hub_climatology(sample_district: np.ndarray, level_target: np.ndarray,
                    train_mask: np.ndarray) -> np.ndarray:
    """샘플마다 그 거점의 train 행 타깃 평균(원단위 · level). 형태 (N,).

    `level_target` 은 **수준** 타깃이다 — Δ 모델이어도 변화량이 아니라 직전값 + 변화량을
    넘긴다(베이스라인은 모델 모수화와 무관해야 한다). train 행이 없는 거점은 NaN 이다
    (채우지 않는다 — 채우면 그 거점에 없는 정보를 있는 것처럼 쓴다).
    """
    sd = np.asarray(sample_district)
    y = np.asarray(level_target, dtype=np.float64)
    tr = np.asarray(train_mask, dtype=bool)
    out = np.full(len(y), np.nan)
    for d in np.unique(sd):
        rows = sd == d
        tr_rows = rows & tr
        if tr_rows.any():
            out[rows] = float(y[tr_rows].mean())
    return out


def climatology_block(clim: np.ndarray, actual: np.ndarray, prev: np.ndarray) -> dict:
    """한 분할에서 거점 평균 규칙의 지표 — MAE · '평균 쪽' 방향정확도.

    `clim` 에 NaN 이 하나라도 있으면 둘 다 None 이다(부분 표본으로 재지 않는다 —
    판정 쪽 `forecast_skill.lstm_skill` 도 한 행이라도 없으면 종전 기준으로 물러난다).
    """
    c = np.asarray(clim, dtype=np.float64)
    a = np.asarray(actual, dtype=np.float64)
    p = np.asarray(prev, dtype=np.float64)
    if c.size == 0 or not np.isfinite(c).all():
        return {"climatology_mae": None, "meanward_dir_acc": None}
    return {
        "climatology_mae": float(np.mean(np.abs(c - a))),
        # 방향 = sign(거점 평균 − 직전값). 모델 방향 판정(sign(pred − prev))과 같은 모양이다
        "meanward_dir_acc": float(np.mean(np.sign(c - p) == np.sign(a - p))),
    }
