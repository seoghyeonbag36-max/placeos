"""LSTM 하이퍼파라미터 그리드 — 어떤 시행을 몇 번 도는지를 한 자리에 박는다.

torch·numpy 없이 import 되도록 `train_lstm` 에서 떼어 냈다(`selection.py` 와 같은 이유) —
기본 테스트 러너에서도 "사전등록한 시행 수와 값 그대로인가"를 시험할 수 있어야 한다
(data/tests/test_lstm_leakage.py).

## 그리드

- `default` — 기존 8 조합 × `target_mode ∈ TARGET_MODES` = 16 시행(2026-09-26 사전등록).
  **바꾸지 않는다.** 조기종료·가중치감쇠 없이 400 epoch 고정이라 09-24 · 09-27 을 재현한다.
- `reg-0928` — 기존 8 조합 × `weight_decay ∈ {0, 1e-3}` = 16 시행, `level` 고정 ·
  val 손실 조기종료(patience 20 · 상한 400) 공통(2026-09-28 사전등록 §2).
  → docs/finding-lstm-regularization-prereg-2026-09-28.md

⚠ 결과를 본 뒤 여기 값을 바꾸는 것은 그 사전등록의 연장이 아니다 — 새 그리드 이름과
새 사전등록을 쓴다(§3 시행 수 상한).
"""
from __future__ import annotations

# 기존 8 조합. 연혁(train_lstm.main 에 있던 주석을 옮겼다):
# hidden=64/layers=1 은 2026-07-22 19거점 확장 때 추가. 기존 그리드에 32/1 과 64/2 는
# 있었으나 그 사이 조합이 비어 있었고, 19거점에서는 이 조합이 MAE(0.937 vs 1.073)와
# 방향정확도(78.9% vs 68.4%) 양쪽 모두에서 우위라 정식 후보로 편입한다.
# look_back 10/12 와 hidden 96 은 2026-07-22 27거점(Phase 2) 확장 때 추가.
# 27거점에서는 기존 4-trial 그리드가 전부 66.7% 로 묶여 목표 미달이었다 — 거점이 늘어
# 홀드아웃 표본도 27개가 되면서 더 긴 문맥·넓은 은닉이 필요해진 것으로 보인다.
BASE_TRIALS: tuple[dict, ...] = (
    {"hidden": 32, "layers": 1, "look_back": None},
    {"hidden": 64, "layers": 1, "look_back": None},
    {"hidden": 64, "layers": 2, "look_back": None},
    {"hidden": 32, "layers": 1, "look_back": 6},
    {"hidden": 64, "layers": 1, "look_back": 10},
    {"hidden": 96, "layers": 1, "look_back": None},
    {"hidden": 96, "layers": 1, "look_back": 10},
    {"hidden": 64, "layers": 1, "look_back": 12},
)

GRIDS: dict[str, dict] = {
    "default": {
        "target_modes": None,          # None = 호출부가 넘기는 TARGET_MODES 전부
        "weight_decays": (0.0,),
        "patience": None,              # None = 조기종료 없음(400 epoch 고정)
        # 09-27 은 후보 0 이어도 fallback 시행으로 서빙을 교체했다 — 그 동작을 유지한다
        "serve_on_fallback": True,
        "prereg": "docs/finding-lstm-delta-target-2026-09-26.md",
    },
    "reg-0928": {
        "target_modes": ("level",),    # Δ 는 09-27 에 기각됐다(delta-target §2)
        "weight_decays": (0.0, 1e-3),  # 0 팔 = 조기종료만의 효과
        "patience": 20,
        # §4: 후보 0/16 이면 레버 기각 — 기각된 레버의 산출물을 서빙에 올리지 않는다
        "serve_on_fallback": False,
        "prereg": "docs/finding-lstm-regularization-prereg-2026-09-28.md",
    },
}


def build_trials(grid: str, target_modes: tuple[str, ...]) -> list[dict]:
    """그리드 이름 → `_train_once` 에 넘길 시행 목록(순서 고정).

    순서는 바깥이 `weight_decay` → `target_mode`, 안쪽이 `BASE_TRIALS` 다. 선택 규칙의
    마지막 동률 키가 인덱스라, 순서를 바꾸면 동률일 때 고르는 시행이 바뀐다.
    """
    if grid not in GRIDS:
        raise ValueError(f"알 수 없는 그리드: {grid!r} — {sorted(GRIDS)}")
    g = GRIDS[grid]
    modes = g["target_modes"] or target_modes
    unknown = set(modes) - set(target_modes)
    if unknown:
        raise ValueError(f"datasets.TARGET_MODES 에 없는 타깃: {sorted(unknown)}")
    return [{**hp, "target_mode": tm, "weight_decay": wd, "patience": g["patience"]}
            for wd in g["weight_decays"] for tm in modes for hp in BASE_TRIALS]


def serves(grid: str, selection: dict) -> bool:
    """이 선택 결과로 서빙 산출물(`vacancy_lstm.pt` · forecast json)을 바꾸는가."""
    return not selection["fallback"] or GRIDS[grid]["serve_on_fallback"]
