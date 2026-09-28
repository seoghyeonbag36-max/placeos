# [사전등록] LSTM 정규화·조기종료 — 결과를 보기 전에 시행 수와 기준을 박는다 (2026-09-28)

> 학습은 **아직 돌리지 않았다.** 이 문서는 규칙만 적는다. 결과는 학습 뒤 §결과 절에 덧붙인다.
> 앞선 사전등록: [finding-lstm-delta-target-2026-09-26.md](finding-lstm-delta-target-2026-09-26.md) §0 · §0-B.

## 배경

Δ 타깃 가설은 기각됐다 — 16 시행 전부 val 에서 지속성(val MAE 1.338)에 졌다
(delta-target §2). 같은 절의 해석: Δ 모델은 출력 0 이 곧 지속성인데도 **큰 변화량을
자신 있게 틀리게** 낸다. train 윈도우가 거점당 몇 개뿐이라(`n_train` 396~) 변화량의 잡음을
외우고 있다는 쪽과 맞는다. 그래서 다음 레버 1 이 정규화·조기종료다. 같은 절이 "val 을 또
보며 고르는 것이라 **시행 수를 사전에 정할 것**"이라고 적어 두었다. 이 문서가 그것이다.

## 1. 가설

Δ·level 모델이 분기 잡음을 외우는 것이라면, **가중치감쇠(weight decay)와 val 손실 기반
조기종료(early stopping)** 가 val 에서 지속성과의 격차를 줄인다.

## 2. 바꾸는 축과 값

### 학습 스크립트에 이미 있는 인자 — 이것뿐이다

`ml/training/train_lstm.py::_train_once(hidden, layers, look_back, epochs=400, lr=1e-3,
test_quarters, val_quarters, target_mode)`. CLI 는 `--test-quarters` · `--val-quarters` 둘뿐이다.

- 드롭아웃은 인자가 아니다 — `dropout=0.2 if layers > 1 else 0.0` 으로 박혀 있고, `nn.LSTM`
  의 층간 드롭아웃이라 **1층에서는 효과가 없다**(8 기본설정 중 7개가 1층).
- 가중치감쇠는 없다 — `torch.optim.Adam(model.parameters(), lr=lr)`.
- 조기종료는 없다 — 400 epoch 고정, full-batch.

### 코드 추가 필요 (이 문서에서는 구현하지 않는다)

| # | 무엇 | 자리 |
|---|---|---|
| a | `weight_decay` 인자 → `Adam(..., weight_decay=wd)` | `_train_once` |
| b | val 손실 조기종료 — 매 epoch 뒤 val MSE(표준화 단위 · 학습 손실과 같은 것)를 재고, 최선 `state_dict` 를 보관, **patience 20** 동안 개선이 없으면 멈추고 최선으로 복원. 상한 400 epoch | `_train_once` |
| c | 이번 16 시행만 도는 그리드 전환 인자(예: `--grid reg-0928`). **기본 그리드(level×delta 16)는 바꾸지 않는다** | `main` · argparse |
| d | 산출물 `params` 에 `weight_decay` · `patience` · `stopped_epoch` 기록 | `main` |
| e | **후보 0 이면 서빙 산출물을 쓰지 않는 분기** — 지금은 `vacancy_lstm.pt` · `platform_vacancy_forecast.json` 을 무조건 덮어쓴다(§4 서빙 규칙) | `main` |

드롭아웃은 **이번 시행에서 뺀다.** 1층 모델에 넣으려면 모델 구조(`ml/models/lstm/vacancy_lstm.py`)
를 바꿔야 하고, 축을 하나 더 넣으면 시행 수가 늘어난다(§3 상한).

### 그리드 — 16 시행

- 기본설정 8개: `base_trials` 그대로(h32/L1 · h64/L1 · h64/L2 · h32/L1/lb6 · h64/L1/lb10 ·
  h96/L1 · h96/L1/lb10 · h64/L1/lb12).
- `weight_decay ∈ {0, 1e-3}` — 0 팔은 **조기종료만의 효과**를 떼어 본다.
- 조기종료: 전 시행 공통(patience 20 · 상한 400).
- `target_mode = level` 고정 — Δ 는 §배경대로 기각됐다. `lr = 1e-3` 고정.

8 × 2 = **16 시행.**

## 3. 시행 수 · 시드 · 선택 규칙 — **승인 2026-09-28**

- **시행 수 상한 16.** 결과를 본 뒤 patience·weight_decay 값을 바꿔 다시 도는 것은 이
  사전등록의 연장이 아니다 — 새 사전등록을 쓴다.
- **시드 42 고정**(`_SEED`). 09-27 의 level 8 시행이 09-24 를 소수점까지 재현했으므로 같은
  코드·시드에서 비교가 선다. 시드 간 분산은 재지 않는다(§한계).
- **선택 규칙: §0-B ① 그대로.**
  1. val MAE < 같은 val 분할의 지속성 MAE 인 시행만 후보.
  2. 후보 중 val 방향정확도 최대(동률이면 val MAE 최소).
  3. 후보가 없으면 val MAE 최소를 고르고 `selection.fallback = true`.
  구현은 `ml/training/selection.py::select_trial` 을 그대로 쓴다.
- **선택 풀은 이번 16 시행뿐이다.** 09-27 의 16 시행은 대조로만 옆에 적는다(전부 후보 0 이라
  풀에 넣어도 후보는 늘지 않고, fallback 비교만 흐려진다).

## 4. 성공 기준 · 서빙 규칙 — **승인 2026-09-28**

판정은 `kpi_baseline` 의 verdict(`apps/backend/app/services/forecast_skill.py::verdict`)로만 한다.

| 결과 | 뜻 | 서빙 |
|---|---|---|
| 후보 **0/16** | **레버 기각** — 정규화·조기종료로도 val 에서 지속성을 못 넘는다 → §6 | **교체하지 않는다** — 09-27 trial 7 유지 |
| 후보 ≥1 · test 참고 오차 `실력` | val·test 둘 다에서 지속성 위 — 그래도 **참고**(§5) | 교체 |
| 후보 ≥1 · test 참고 오차 `구분불가` | val 에서는 넘고 test 에서는 못 가른다 | 교체 |
| 후보 ≥1 · test 참고 오차 `열위` | val 에서만 넘었다 — 선택 편향 쪽 증거(§한계) | 교체 |

- 후보 0 에서 fallback 시행이 골라져도 **서빙 산출물은 바꾸지 않는다.** 기각된 레버의
  산출물을 서빙에 올리지 않는다는 뜻이다(09-27 은 fallback 도 교체했다 — 이번에는 다르다).
- 방향 축 판정은 §0-B ② 그대로(원시 정확도 vs 무정보 상수). 균형정확도·MCC 는 관측만.

## 5. 확정 규칙 — §0-B ③ 그대로

이미 본 test 분기(2025Q4 · 2026Q1 · 2026Q2)의 결과는 **참고 판정**이다. 게이트는
`protocol.confirm_after = "20262"` **이후 분기** holdout 으로만 판정하고, 그런 표본이 없으면
`확인대기`다. 이번 시행이 어떻게 나와도 Platform 진행률은 2026Q3 데이터 전에는 바뀌지 않는다.

## 6. 레버 2 와의 분기점

**§4 에서 레버 기각(후보 0/16)이면 레버 2 로 간다** — 목표 `vac_proxy`(폐업률−개업률−점포증감)
자체의 분기 잡음이 커서 지속성이 이기는 것이 정상일 수 있다. 그 경우 모델을 더 돌리기
전에 ⑥(지속성을 못 넘을 때 화면에 무엇을 보일지)을 먼저 정한다.

## 7. 노트북에서 돌릴 명령 — **초안** (§2 코드 추가 뒤에만 돈다)

```bash
cd spaceos
OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8 python -u -m ml.training.train_lstm --grid reg-0928 \
  > logs/lstm_reg_0928.log 2>&1
python scripts/kpi_baseline.py
python scripts/pppp_status.py
```

- 예상 시간: 09-26 실측으로 시행당 약 5분(400 epoch) → **상한 약 80분.** 조기종료로 멈추는
  시행은 그보다 짧다.
- 재시도 래퍼: `scripts/run_gnn_retry.py` 는 GNN 전용이다. LSTM 은 체크포인트 재개가 없어
  중단되면 16 시행을 처음부터 다시 돈다(delta-target §1 과 같다). 세그폴트 기록은 GNN 쪽에만
  있다 — 래퍼는 필요해지면 만든다.
- 무인 실행이면 `autorun` 스킬 규칙(절전 억제 · UTF-8 · 로그)을 따른다.

## ⚠ 공개해 둘 한계

- **val 을 두 번 쓴다.** 조기종료가 val 손실로 멈추고, 후보 필터도 val MAE 다. 그래서 val MAE
  가 낙관적으로 나오고 후보 필터가 그만큼 느슨해진다. 거점당 val 원점이 2 라 val 을 둘로 나눌
  여유가 없다. 게이트는 §5 때문에 이 편향의 영향을 받지 않는다.
- **test 를 세 번째로 본다**(09-24 · 09-27 · 이번). 선택은 val 로만 하지만 "무엇을 시도할지"가
  앞선 test 결과에 조건부라는 사실은 남는다.
- **단일 시드.** 후보가 경계에서 1~2개 나오면 시드 우연일 수 있다. 그 경우도 확정은 §5 가 한다.
