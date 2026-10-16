# 5개 업종 확장 작업 결과: 공간 이웃 비교·검증 패널

## 완료한 것

1. 세부 업종 실험에 공간 이웃 전용(`--spatial-only`)과 학습 점포의 이웃 업종
   피처(`--neighbor`) 옵션을 연결했다.
2. 입력 그래프·수요·건물 테이블 해시, 코드 해시, 점포·정답·학습/검증/테스트 분할 해시를
   실험 보고서에 기록한다. 다른 입력·분할의 보고서는 비교 도구가 실패시킨다.
3. 비저장 실험이 기존 학습 재개 체크포인트를 삭제하던 부작용을 수정했다.
4. 기존 추정매출 원천을 Bronze→Silver→Gold 검증용 분기 패널로 정리했다.
   142,984행, 81거점, 2021Q1~2026Q2. 원천 코드 유지, 중복 충돌 거부, 결손·실제 0 구분,
   기존 파일 덮어쓰기 거부를 구현했다. 모델 입력과 서빙에는 연결하지 않았다.

## 비교 실험

두 팔 모두 공간 거리 이웃(`spatial_knn`)만 사용해 업종과 직접 연관된 같은 체인·같은 건물
엣지 효과를 분리했다. 같은 61,165노드 중 테스트 12,243노드, 27개 세부 업종.
선택 기준은 기존 val Top-1, 최대 80회·patience 15·hidden 64. 후보는 41회에서 조기 종료했다.
이웃 피처는 학습 라벨만 집계하며 자기 자신과 검증·테스트 라벨을 집계하지 않는다.

| 지표 | 공간 이웃 기준 모델 | 주변 업종 피처 추가 |
|---|---:|---:|
| Top-1 | 29.94% | 30.61% |
| Top-3 | 51.76% | 51.72% |
| macro-F1 | 0.1078 | 0.1162 |
| 같은 표본의 거점 사전분포 Top-3 | 45.41% | 45.41% |

단일 분할·단일 초기화의 관측이며 통계적 유의성이나 상권 추천 정확도를 의미하지 않는다.
큰 업종으로 점수를 임의 합산하지 않았고 서빙 승격 기준도 새로 만들지 않았다.

| 세부 업종 | 기준 Top-3 | 주변 업종 추가 Top-3 |
|---|---:|---:|
| 요리 주점 | 80.30% | 77.24% |
| 생맥주 전문점 | 5.96% | 7.72% |
| 미용실 | 93.11% | 87.83% |
| 네일숍 | 0.00% | 6.85% |
| 피부 관리실 | 31.27% | 45.92% |
| 의류 | 85.61% | 86.41% |
| 입시·교과학원 | 65.10% | 61.33% |
| 헬스장 | 1.00% | 2.67% |
| 요가·필라테스 | 8.71% | 14.59% |
| 골프·PC방 | 각 0.00% | 각 0.00% |

전체 Top-3 개선은 관측되지 않았고 업종별 개선·악화가 섞였다. 주변 업종 피처 하나로
5개 업종을 일괄 활성화할 근거가 되지 않는다. 다른 작업에서 생성된
`industry_detail_features.py` 및 층·교통·시간대 보고서는 이번 작업에서 수정하지 않았다.

## 산출물과 재현

- `ml/reports/industry_detail_spatial_control_2026-10-16.json`
- `ml/reports/industry_detail_spatial_neighbor_2026-10-16.json`
- `reports/industry_detail_spatial_comparison_2026-10-16.json`
- `reports/industry_outcome_panel_2026-10-16.json`

```powershell
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:PYTHONIOENCODING='utf-8'
python -m ml.training.industry_detail_experiment --spatial-only --output ml/reports/control-new.json
python -m ml.training.industry_detail_experiment --spatial-only --neighbor --output ml/reports/neighbor-new.json
python -m ml.training.industry_detail_compare ml/reports/control-new.json ml/reports/neighbor-new.json --output reports/comparison-new.json
```

통과: `test_industry_detail_experiment.py`, `test_industry_detail_metrics.py`,
`test_gnn_label_levels.py`, `test_industry_outcome_panel.py` 합계 25개.
검증용 합성 입력과 실제 학습 결과는 구분했다. `git diff --check` 통과.

## 남은 조건

추천 활성화·프로덕션 배포는 완료하지 않았다. 학습 정답인 현재 업종과 추천 정답인 미래의
적합한 상권은 같지 않으며, 분기 패널도 평가 후보가 준비된 단계다.
업종 코드 대응, 시점별 공백·당시 이용 가능성, 시간 분리 평가와 상권 순위 검증이 남아 있다.
추가 데이터의 필드·입도·확보 경로는
[데이터 요구사항](industry-recommendation-data-requirements-2026-10-16.md)에 정리했다.

`ml/AGENTS.md`의 「실험은 --no-save로 돌리고 결과를 보고」 원칙에 따라 기존 서빙 JSON과
모델은 교체하지 않았다. 점수 미지원 상태를 임의로 해제하거나 출처 계약을 바꾸지 않았다.
