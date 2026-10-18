# 근거 인덱스 — 논문 본문에 쓸 수 있는 수치의 전부

**이 파일에 없는 숫자는 논문에 쓰지 않는다.** 새 수치가 필요하면 먼저 여기에
출처·재현 경로와 함께 등재한 뒤 본문에 쓴다. → [README.md](README.md) 작성 규칙

<a id="update-20261018"></a>
## 후속 실험·자료 품질 갱신 근거 — 2026-10-18

현재 네 Markdown 원고를 점검하고 Platform·Page·Posting에 후속 절을 추가한다. Program은 새 생성 품질·사업 성과 평가 근거가 확인되지 않아 기존 미검증 판정을 유지한다. 아래 수치는 보존 JSON에서 대조한 값이며 이번 집필에서 재학습·재수집하지 않았다. 10월의 세부 업종 실험은 조건 A/B/C/E/F와 별도인 **조건 H**로 표기한다. 조건 H 안에서도 전체 엣지 피처 실험과 공간 이웃 전용 비교는 별도 팔이며, 서로 다른 팔의 차이를 피처 효과로 계산하지 않는다.

| ID | 등재 값·계약 | 원천·재현 경로와 해석 제한 |
|---|---|---|
| PLATFORM-V01 | 조건 H: 81거점, 61,165노드·27클래스·test 12,243노드. 대조군 132열, 층 137열, 교통 136열, 시간대 142열, 전체 151열. 분할 시드 42, 초기화 시드 42·43·44, 최대 80에포크·patience 15·hidden 64, val Top-1 선택. 거점 군집 부트스트랩 2,000회·95% 구간 | `ml/reports/industry_detail_features_experiment_2026-10-16.json::parameters/overall/bundles`; 노드 수·클래스는 `ml/reports/industry_detail_experiment_2026-10-16.json`. 재현: `python -m ml.training.industry_detail_features run-all` 후 `report --output <새 경로>`. 같은 거점·건물의 점포가 분할에 섞이는 전이적 평가. 시드 평균 적중을 거점별 재표본하며 구간은 학습 시드 변동을 포함하지 않음 |
| PLATFORM-V02 | 시드 평균 Top-3: 대조 52.8%, 층 55.9%, 교통 53.2%, 시간대 53.2%, 전체 56.1%. 동일 표본 기준선 45.4%. 대조 대비 차이·95% 구간: 층 +3.1 [+2.5, +3.7]%p, 교통 +0.4 [+0.1, +0.7]%p, 시간대 +0.4 [+0.1, +0.7]%p, 전체 +3.3 [+2.6, +3.9]%p | 같은 JSON `overall::<arm>::model_top3/baseline_top3/vs_control`. 원값에 100을 곱해 소수 첫째 자리로 반올림. 교통·시간대의 구간은 양수지만 학습 변동 대비 견고한 효과는 미입증. 전체와 층의 직접 차이 검정 없음. `reproduces_prior_report.match=true`: 시드 42 대조 53.01%, 기준선 45.41%는 앞선 보고서와 일치 |
| PLATFORM-V03 | 층−대조: 요가·필라테스 +11.4 [+8.3, +14.2]%p, 미용실 −2.9 [−4.3, −1.6]%p. 네일숍 층 Top-3 8.1%. 의류 +0.9 [−0.3, +2.2]%p. 골프·PC방·기타 숙박은 층 팔에서도 Top-3 0%. 공연장·전시장·갤러리는 test 0·산출 불가 | 같은 JSON `per_class`; 업종별 다중비교 미보정. 기준선 대비 양의 차이는 서비스 효용 기준 충족이 아님. `docs/finding-industry-features-2026-10-16.md`의 표 A·한계도 대조 |
| PLATFORM-V04 | 공간 이웃 전용 비교: Top-1 29.94%→30.61%, Top-3 51.76%→51.72%, macro-F1 0.1078→0.1162, 기준선 Top-3 45.41% | `reports/industry_detail_spatial_comparison_2026-10-16.json::overall`; 두 원본 `ml/reports/industry_detail_spatial_{control,neighbor}_2026-10-16.json`. 재현: `python -m ml.training.industry_detail_compare <control> <neighbor> --output <새 경로>`. 같은 입력·분할 해시를 검사. 단일 분할·초기화, 유의성 검정 없음. 주변 업종은 학습 라벨만 사용. 추천 활성화 근거 아님 |
| PAGE-V01 | 부분 격리 검증: 원본 1,077,457행, 수용 1,077,224행, 격리 233행, `status=verified`. 원천 식별키별 연구 피처 740,919행·`status=partial_quarantined` | `reports/industry_public_partial_verified_2026-10-17.json`; `reports/industry_public_features_2026-10-17.json`. 검증 해시→부분 Silver·격리 파일→연구 Gold 연결을 대조. 재현 경로: `data/pipelines/build_industry_public_silver.py`의 부분 격리 CLI와 `data/pipelines/build_industry_public_features.py`의 검증 해시 게이트. 검증 JSON은 보존 대조 기록이며 독립 검증 스크립트가 아님. 점포·모델·API 미연결이며 공실 판정 성능 실험이 아님 |
| PAGE-V02 | 학교 식별자 공란으로 전체 Silver 승격은 `blocked`·`silver_written=false`. 부분 격리 승격과 전체 승격 실패를 구분. 학교 코드 임의 복원·손상 원문 추측 복원 없음 | `reports/industry_public_silver_2026-10-17.json`; `reports/industry_public_school_identity_audit_2026-10-17.json`; 부분 검증 `quarantined_identities_absent_from_datasets_and_links=true`. 상호·주소 후보는 확정 링크 아님. `SITEAREA`는 소재지면적이지 공실 가용면적이 아니며 학원 정원은 재원생 실측이 아님 |
| POSTING-V01 | 검증용 추정매출 분기 패널 142,984행·81거점, 2021Q1~2026Q2. 모델 입력·서빙 미연결, POS 실측 아님 | `reports/industry_outcome_panel_2026-10-16.json`; `data/gold/features/industry_outcome_panel_2026-10-16.parquet`. 재현: `python -m data.pipelines.build_industry_outcome_panel data/bronze/platform13/2026-09-24/seoul_trdar_selng.json --tag <새 태그>`. 같은 TRDAR의 거점 간 중복 합산 금지·누락 보간 금지·업종 자동 대응 금지. 과거 정정값의 당시 이용 가능성 미확인 |

이번 갱신은 보존 보고서·로컬 산출물과 코드 계약의 대조다. 기존 가설 판정·역사적 결과·문헌 확인 범위를 유지한다. Word 및 제출처별 파생 원고는 이 Markdown 갱신에 자동 동기화되지 않는다.

<a id="pppp-update-20261011"></a>
## 네 원고 갱신의 근거와 범위 — 2026-10-11

연구 동기의 출처는 이번 집필 요청에서 연구자가 제공한 현장 관찰이다. ‘공실은 창업·재창업 순환의 동맥경화’는 문제를 설명하는 은유다. 유동인구가 많은 곳의 폐업과 적은 곳의 배달 기반 유지라는 관찰에는 표집·관측 기간·성과 대조 자료가 제공되지 않았다. 디지털 접근성·IT/SNS/AI 검색의 상대적 영향은 미검증 연구 가설로만 사용한다. 이 관찰을 인과 추정치나 기존 실험의 결과로 바꾸지 않는다.

| ID | 확인한 근거 | 출처·재검증 경로·허용 범위 |
|---|---|---|
| COMMON-U01 | PPPP 대응: Place→Platform, Product→Page, Price→Posting, Promotion→Program | 루트 `AGENTS.md`. 현행 기능 대응이며 전통 마케팅 이론의 실증 검증 결과가 아님 |
| COMMON-U02 | 서빙 81거점. Page·Posting·Program 구현 게이트 충족과 Platform 잔여 게이트를 구분 | `data/config/page_hubs.py::ACTIVE_HUBS`; `python scripts/pppp_status.py`; `python scripts/chain_status.py --all`. 구현 진행률을 정확도·사업 성과로 해석하지 않음 |
| PLATFORM-U01 | 조건 F: 81거점, 노드 90,419·엣지 279,468·피처 132열·클래스 6·test 18,087. `group_mapped`, val 선택 `top1` | `data/gold/platform_industry_recommend.json::metrics`; `docs/finding-page-oct-refresh-2026-10-10.md` §7. 조건 E 및 A/B/C와 모집단·판본이 다르므로 개선 전후 비교 금지 |
| PLATFORM-U02 | 조건 F Top-3 92.03% 대 거점 사전분포 88.40%, 차이 +3.63%p; 거점 군집 부트스트랩 95% 구간 [+3.00, +4.25]%p; b=920·c=264, 쌍대 판정 `실력` | `python scripts/kpi_baseline.py --json`의 `gnn`; 원값 구간 [2.998887427935673, 4.246551822812339]. 본문은 위 기록과 같은 반올림. McNemar 자리 독립 가정과 새 거점 일반화의 한계를 유지 |
| PLATFORM-U03 | 조건 F off-prior Top-3 43.85%, 2,098자리; macro-F1 0.2504 | 같은 Gold의 `metrics`. 관측 전용. 창업 적합성·디지털 접근성 효과 아님 |
| PLATFORM-U04 | LSTM 방향·오차 게이트 `확인대기`, 확인 기준 이후 신규 표본 0건 | `kpi_baseline.py --json::lstm.confirmation` 및 `direction/error.gate_verdict`. 스크립트 종료코드 1은 이 게이트 미충족을 나타냄. 이번 갱신에서 재학습하지 않음 |
| PLATFORM-U05 | 검색 제목·링크·작성일·검색어·수집일과 행정동 소비의 조회 연결. 검색 본문·요약 재배포 없음, 소비를 점포 매출·소득으로 환산하지 않음 | `docs/finding-pppp-collected-context-2026-10-11.md`; `collected_context.py::for_district`; `platform_profile.py::identity`; `apps/backend/tests/test_collected_context.py`. 검색 표본의 지역 귀속·광고성은 미검증이며 감성 피처 경로를 되살린 결과가 아님 |
| PAGE-U01 | 조건 G: 81거점 보존 스냅샷. 정렬 격차 중앙 +9.6%p→+7.6%p, 절대 격차 >10%p 거점 39→31, 양의 격차 70→70, 앵커가 층 밴드 안인 거점 8→8 | `reports/page_accuracy_baseline_2026-10-10.json` 및 `reports/page_accuracy_after-licensing.json::summary`; `python scripts/page_accuracy_snapshot.py --compare reports/page_accuracy_baseline_2026-10-10.json`. 앵커 통계와의 대조이지 독립 현실 공실 정답 검증이 아님. 조건 D와 합산 금지 |
| PAGE-U02 | 현장 라벨 설계: 81거점의 고유 지번·층 78,511층, 8계층에서 458층·76거점 표본 | `data/validation/floor_sample_20261011/design.json`; `docs/finding-page-oct-refresh-2026-10-10.md` §8. 표본 설계·입력 페이지·채점기 구축은 라벨 수집 또는 정확도 평가 완료가 아님. `python -m data.validation.score_floor_labels --tag 20261011 --json reports/floor_labels_20261011.json`은 별도 라벨 입력 후 실행 |
| POSTING-U01 | 2026-10-04 매출 산출물: 분기 20262, 서빙 81거점 중 세 tier 완비 79거점. garak·bulgwang의 premium 재료 부족 | `data/gold/platform_posting_revenue.json::quarter/coverage`; `docs/feature-posting.md` §0-X. `python -m data.pipelines.build_posting_revenue --quarter 20262`는 재생성 경로이며 이번 집필에서는 실행하지 않음 |
| POSTING-U02 | `seoul` 기준점은 매핑된 352상권 풀이며 서울 전체가 아님. 서빙 모집단의 모델 커버리지와 임대료 수준별 부담 서열을 검사 | `docs/feature-posting.md` §0-X; `apps/backend/tests/test_posting_revenue.py::test_revenue_artifact_covers_served_hubs`, `test_premium_tracks_hub_rent_level`. 과거 §0-N의 ‘서울 전체’ 표현을 현행 사실로 전용하지 않음. 유닛 수는 후속 Page 재빌드로 바뀌므로 당시 수치를 현재 인벤토리로 옮기지 않음 |
| PROGRAM-U01 | 로그인/JWT·조직 키가 확인된 호출만 LLM 허용. 익명 Program은 `rule-stub`, 상권 콘텐츠는 `seed`. 잘못된 자격증명은 거부. 상권 콘텐츠 실패 캐시는 300초 | `apps/backend/app/api/v1/marketing.py`; `marketing.py`; `tests/test_program_llm_gate.py`; `docs/feature-program.md` §0-V 「LLM 문」. 300초는 선택한 운영 상수이지 효과 평가 결과가 아님. 로그인은 호출 허용이며 LLM 성공 보장 아님 |
| PROGRAM-U02 | 문화행사 Gold 갱신: 기준일 2026-10-11, 종료되지 않은 배정 749건(거점 간 중복 포함). TourAPI 응답 0건은 문화행사 부재로 치환하지 않음 | `data/gold/platform_events.json::as_of/districts`; `platform_collected_context.json::tourapi.rows`; `docs/finding-pppp-collected-context-2026-10-11.md`. 행사 배정 수는 고유 행사 수·참여 성과 아님. `python -m data.pipelines.promote_collected_context`는 해당 문서의 로컬 Bronze 경로와 인자를 필요로 함 |

현재 코드·Gold 읽기 대조와 보존 보고서 검산을 수행했다. 새 학습, 외부 API 재수집, 유료 LLM 실호출 및 독립 현장 성과 실험은 수행하지 않았다. 문헌은 기존 원고와 확인 기록의 범위에서 유지하며 새 인용을 추가하지 않는다.

**2026-09-20 가설 명시:** 네 원고의 RQ·H 식별자는 사후 분석 구조이며 새로운 실험 수치를 뜻하지 않는다. Platform H1/H2는 P1 및 PLATFORM-E01–E06, Page H1–H4는 PAGE-D03–D09, Posting H1–H4는 POSTING-E01–E05, Program H1–H3은 PROGRAM-E02–E05에 연결했다. 미검증 가설은 성과 자료가 없는 상태를 그대로 유지한다.

⚠ **모집단이 다른 값을 섞지 말 것.** 아래 표는 세 종류의 실험 조건을 담고 있고
서로 비교 가능하지 않다. 각 수치의 조건을 반드시 확인한다.

| 조건 | 그래프 | 라벨 | 피처 | 시점 |
|---|---|---|---|---|
| **A. 서빙본** | 66거점 47,442노드 | category_group 7종 | 117열 | 2026-09-05 |
| **B. 실험군(group)** | 54거점 | category_group 7종 | 105/115열 | 2026-08-19~26 |
| **C. 실험군(category2)** | 54거점 | category 2단계 32클래스 | 105/115열 | 2026-08-27 |
| **E. 서빙본(81거점 재학습)** | 81거점 88,238노드 | category_group 7종 중 사상분(`group_mapped` · 실제 6클래스) | 132열 | 2026-09-27 |

Page의 **조건 D(2026-09-06 동결 구조 감사)**는 아래 별도 절에 등재한다. 위 그래프 조건 A/B/C와 모집단·태스크가 다르며 합산하지 않는다.

⚠ B 의 off-prior 37.6% 와 A 의 33.8% 는 **성능 저하가 아니다** — 거점이 54→66 으로
늘며 모집단이 바뀐 것이다(`docs/feature-platform.md` §0 이 직접 경고한다).

---

## P1 · Platform — GNN 업종추천

### 집필 시 해석 정정 및 재현 범위 2026-09-19

아래 원래 기록의 수치는 보존하되 해석은 이 절을 우선한다. 기각 결과를 개선으로 바꾸는 정정이 아니라 과도한 통계적 단정을 제한하는 정정이다.

- PLATFORM-E01: `train_gnn.py::_split`, `_district_top3`, `_offprior_top3` 대조. 클래스별 60/20/20 노드 분할, train 라벨만으로 거점 Top-3 정의. 같은 그래프의 전이적 평가이며 새 거점·미래 시점 외부 검증이 아니다. off-prior는 사전분포 실패 부분집합이며 그래프 구조의 순수 인과 기여를 분리하지 않는다.
- PLATFORM-E02: `train_gnn.py`의 lift 계산은 Top-1 기준선 대비 상대 증가율이다. +5.3%를 Top-3 차이로 해석하지 않는다. `ml/models/gnn/industry_gnn.py`는 GCNConv 기반이다.
- PLATFORM-E03: 조건 B 표는 기준 포함 네 행으로, 서로 다른 시드·모집단의 독립 반복 네 번이 아니다. 단일 팔 SE 1.63%p와 차이 비교만으로 쌍대 유의성을 판정하지 않는다. 조건 C의 4.32배는 off-prior 표본 수 증가이며 검정력 자체의 배수가 아니다. p=1.0은 효과 영 또는 동등성의 증명이 아니다.
- PLATFORM-E04: §0-O의 MDE는 유의수준 0.05에서 `1.96√D/n`으로 계산한 근사 검출 경계다. 목표 검정력·대립가설 오차를 포함한 정식 표본설계가 아니다. 다른 라벨 과제의 경계를 비교해 같은 효과를 검출한다고 주장하지 않는다. 노드 간 공간 의존성도 반영하지 않았다.
- PLATFORM-E05: 2026-09-15 노드 소스 교체와 과거 Bronze 삭제로 현행 학습 명령은 옛 그래프의 재현을 보장하지 않는다. 출처 `ml/training/train_gnn.py` 머리말, `docs/finding-map-provider-google-2026-09-15.md`. 본 원고 조건 A/B/C는 역사적 보존 결과이며 현재 신규 학습의 성능이 아니다.
- PLATFORM-E06: `reports/gnn_category2_mcnemar_2026-08-27.json`은 노드별 덤프가 gitignore 대상이고 요약만 새 클론에서 검증 가능하다고 명시한다. 합계 741+2747+148+149=3785, 불일치 148+149=297, 두 팔 차이 +0.03pp, 연속성 보정 chi2=0.0·p=1.0을 요약에서 검산한다. 학습 재실행과 구별한다.
- PLATFORM-E07: Kipf, T. N. & Welling, M. (2017), *Semi-Supervised Classification with Graph Convolutional Networks*, ICLR, arXiv:1609.02907. [저자 PDF](https://arxiv.org/pdf/1609.02907)의 초록·서론·전파식 확인.
- PLATFORM-E08: Shchur, O., Mumme, M., Bojchevski, A. & Günnemann, S. (2018), *Pitfalls of Graph Neural Network Evaluation*, Relational Representation Learning Workshop, NeurIPS, arXiv:1811.05868. [저자 연구실 서지](https://www.cs.cit.tum.de/daml/gnn-benchmark/)와 [PDF](https://arxiv.org/pdf/1811.05868)의 초록·서론 확인. 원문 성능 숫자 전재 없음.

### 서빙본 성능 (조건 A)

| 값 | 수치 | 출처 |
|---|---|---|
| 그래프 규모 | 노드 47,442 · 엣지 188,673 · 피처 117열 | `feature-platform.md` §0 |
| Top-1 / Top-3 | **64.9% / 91.7%** | 홀드아웃 층화 60/20/20 |
| macro-F1 | 0.235 | 〃 |
| 거점 사전분포 기준선 | Top-1 61.7% / Top-3 89.4% | 〃 |
| **lift** | **+5.3%** | 〃 |
| off-prior Top-3 | **33.8%** (n=1,011) | `test_offprior_top3` |
| 태스크 | 업종을 가리고 입지만으로 대분류 7종 분류 | `feature-platform.md` §0 |

> 논문의 핵심 관찰: **Top-3 91.7% 는 높아 보이지만 기준선이 이미 89.4%다.**
> "어느 거점이냐"가 업종 대부분을 결정하고 그래프가 얹는 정보는 작다.
> off-prior(사전분포로는 정의상 맞힐 수 없는 자리)만이 그래프의 실제 기여를 잰다.

### 성능 천장 — 4회 독립 확인 (조건 B)

레버를 넷 바꿔 봤고 **전부 표준오차(약 1.63%p) 안**이었다.

| 시도 | off-prior Top-3 | 판정 | 출처 |
|---|---|---|---|
| 기준 (105열) | 37.63% | — | §0-D |
| 이웃 업종 분포 8열 추가 (113열) | 36.49% | 기각 | §0-I |
| 조기종료 기준 3종 ablation | 35.92 ~ 37.17% | 기각 | §0-E · `reports/gnn_selectby_ablation.json` |
| 행정동 24시간 축 10열 (115열) | 37.51% | 기각 | §0-J · `reports/gnn_adong_2026-08-25.json` |

> **§0-E 의 결정적 관찰**: 게이트 지표(off-prior)를 val 에서 **직접 최적화**한 팔이
> macro_f1 최적화 팔과 소수점까지 같은 값(37.17%)에 멈췄다. val 은 37.70%까지 올랐고
> test 는 37.17% — val 과잉적합도 아니다. **이 피처 집합의 천장이 37%대**라는 뜻이다.

### 진단 — 막는 것은 변동의 **양**이 아니라 **종류** (§0-J)

within-district 분산 0.221짜리 10열을 실제로 늘렸는데도 움직이지 않았다.
시간·유동 계열로는 **약국을 병원 옆에서 가릴 수 없다.** 필요한 것은 업종 자체에 대한
정보(감성·인접 구조)이고, 그 두 경로는 §0-K(감성)·§0-I(인접)가 각각 기각했다.

### 감성 경로 기각 (§0-K, 2026-08-25)

600ep 을 돌리지 않고 기각했다. 수집은 이미 끝나 있었고, 세 다리를 재 보니 셋 다 끊긴다.
리뷰 유사도 엣지 불가 사유: 네이버 블로그 검색 API 가 본문이 아닌 **약 150자 스니펫**만 준다
— 27거점 8,554건 중 점포명 2개 이상 동시 언급 **15건(0.2%)**. 점포 단위 리뷰 원문은 공식 API 부재.

### 라벨 세분화 — 검정력 4.32배 확보 후 "가를 차이 없음" 확인 (조건 C, §0-N)

출처: `reports/gnn_category2_mcnemar_2026-08-27.json` · 32클래스 · seed 42

| 표본 확대 | 값 |
|---|---|
| group off-prior n | 877 |
| **category2 off-prior n** | **3,785** (4.32배) |
| 표준오차 | 1.63pp → **0.78pp** |

| 팔 | 피처 | Top-1 | Top-3 | macro-F1 | off-prior Top-3 | lift |
|---|---|---|---|---|---|---|
| control_105 | 105 | 0.3267 | 0.6063 | 0.0733 | **0.2349** | 30.7% |
| adong_115 | 115 | 0.3229 | 0.6033 | 0.0719 | 0.2325 | 29.2% |
| jipgyegu_115 | 115 | 0.3272 | 0.6031 | 0.0710 | **0.2351** | 30.9% |

기준선: major_top1 0.2266 · district_prior_top1 0.2500 · district_prior_top3 0.5323

**McNemar (control_105 vs jipgyegu_115, n=3,785)**: both_hit 741 · both_miss 2,747 ·
a_only 148 · b_only 149 · discordant 297 · 델타 **+0.03pp** · chi2 = 0.0 · **p = 1.0**

> 검정력을 4.32배로 키운 뒤에도 p=1.0 이다. **표본이 부족해서 못 가른 것이 아니라
> 효과가 0 이다.**

### 수집을 사기 전에 기각 — 검정력 계산 (§0-O, 2026-08-27)

`reports/offprior_hub_yield_probe_2026-08-27.json` · `scripts/offprior_hub_yield_probe.py`
(학습 없이 `_split`/`_district_top3` 재사용)

거점별 off-prior 수율: 전체 **0.0217** · 중앙 0.0209 · 최소 0.0052(nokdu) ~ 최대 0.0429(gwangjang)
· **변동계수 CV 0.39** · 거점 크기 중앙 720노드
→ off-prior 2배에 필요한 신규 거점: 평균 수율 **56곳** · 상위 4분위만 골라도 **45곳**
(= 지금 프로젝트를 통째로 한 번 더 짓는 규모)

**McNemar 최소검출효과 MDE** (p<0.05, `|n01 - n10| = 1.96 * sqrt(D)`)

| 구성 | n | MDE |
|---|---|---|
| group 현재 | 877 | 2.25pp |
| **category2 현재 (이미 확보)** | **3,785** | **0.89pp** |
| group + 거점 2배 (신규 45~56곳 수집) | 1,754 | 1.59pp |
| category2 + 거점 2배 | 7,570 | 0.63pp |

> **거점을 2배로 늘려 얻는 MDE 1.59pp 는, 라벨 세분화로 공짜로 얻은 0.89pp 보다 나쁘다.**
> 45~56거점을 새로 수집해 이미 가진 것보다 낮은 해상도를 사는 셈이다.

실측 효과크기를 유의하게 가르는 데 필요한 표본:

| 비교 | 실측 델타 | 필요 n | = 거점 |
|---|---|---|---|
| jipgyegu vs adong | +0.26pp | 44,592 | 636곳 |
| adong vs control | −0.24pp | 52,334 | 747곳 |
| jipgyegu vs control | +0.03pp | 3,349,347 | 47,785곳 |

서울에 이 성격의 상권이 636곳 있지 않다. **표본으로 가를 수 있는 문제가 아니다.**

### 수요신호 주입 — 유일한 양성 결과 (2026-08-16)

| 지표 | 종전(58피처) | 수요신호(95피처) | 델타 |
|---|---|---|---|
| test_top1 | 0.6308 | 0.6384 | +0.0076 |
| test_top3 | 0.9050 | 0.9080 | +0.0030 |
| test_macro_f1 | 0.1887 | **0.2124** | +0.0237 (상대 **+12.6%**) |
| lift | 3.1 | **4.4** | +1.3 |

> 읽는 법: **macro-F1 +12.6% 가 top-1 +0.76%p 보다 중요하다.** 음식점 60% 편중 탓에
> top-1 은 다수 클래스가 지배한다. macro-F1 상승은 약국·문화시설 같은 희소 업종이
> 실제로 더 뽑히기 시작했다는 뜻이고, 추천 다양성은 제품 가치에 직결된다.

### 라벨 단계와 정확도의 교환 관계

라벨을 category 2단계(30클래스)로 내리면 **lift +22%로 커지나 Top-3 57%로 KPI 미달.**
세분 업종일수록 그래프 정보가 더 필요하지만 절대 정확도는 낮다.

---

### LSTM 공실 예측 — 서빙본 (2026-09-04 학습 · 66거점)

⚠ **GNN 의 조건 A/B/C 와 다른 모집단·태스크다.** 위 표들과 합산하거나 비교하지 않는다.
태스크는 분기 시계열의 **방향**(오르는가 내리는가) 예측이고, 공실률 값 자체의 정확도가
아니다. 인용할 때 "방향 정확도"라는 말을 떼지 않는다.

| 값 | 수치 | 출처 |
|---|---|---|
| 방향 정확도 | **70.8%** (46/65) | `feature-platform.md` §0 · 홀드아웃 |
| MAE / RMSE | **1.061** / **1.387** (vac_proxy 원단위) | 〃 |
| look_back | 8분기 (분기 데이터라 30개월이 아니다) | `feature-platform.md` §0 |
| 산출물 | `ml/artifacts/vacancy_lstm.pt` · `data/gold/platform_vacancy_forecast.json` · `ml/mlruns` | 〃 |
| 학습 | `ml/training/train_lstm.py` | 〃 |

**거점 확장에 따른 보수화** — 표본이 커질수록 지표가 내려간다. 앞의 값들보다 마지막 값을
인용한다(신뢰구간이 가장 좁다).

| 거점 | 방향 정확도 | MAE |
|---|---|---|
| 13 | 84.6% | 0.901 |
| 27 | 74.1% | 0.803 |
| 54 | 72.2% | 1.109 |
| **66 (서빙본)** | **70.8%** | **1.061** |

> **논문에서 쓸 수 있는 자리**: 이 곡선 자체가 재료다. 초기 표본에서 높게 나온 값이
> 모집단을 넓히며 어떻게 내려앉는지를 네 지점으로 보인 기록은 드물다. 목표선 70%를
> **0.8%p 차로** 넘고 있다는 사실도 함께 쓴다 — 거점이 더 늘면 내려갈 수 있는 자리다.

⚠ **알려진 취약점**: 신규 거점을 `data/config/rone_districts.py` 에 등재하지 않으면 해당
거점의 R-ONE 열이 전 분기 NaN 이 되고, **pooled LSTM 이 전 거점 NaN 으로 붕괴한다**
(`feature-platform.md` §0). 성능 수치를 재현할 때 이 매핑을 먼저 확인한다.

<a id="platform-condition-e"></a>

### GNN 81거점 재학습 — 조건 E (2026-09-27 학습 · 서빙본)

등재일: 2026-09-30. ⚠ **조건 A/B/C 와 모집단·원천·어휘가 모두 다르다.** 노드 원천은 2026-09-15 교체 뒤 그래프이고,
어휘 (b) `group_mapped` 는 7종에 사상되지 않는 점포를 **모집단에서 뺀다.** 위 표들과 한 표에 두거나 차이를 개선·저하로 읽지 않는다.
KIIT 원고(`kiit/paper-platform-kiit.md` · PR #74)의 `{{K1}}`~`{{K11}}` · `{{M1}}` 자리가 이 행들이다.

**재검증 명령:** 저장소 루트에서 `python scripts/kpi_baseline.py --json` (읽기 전용 · 네트워크 없음).
입력 `data/gold/platform_industry_recommend.json` 의 `metrics` · `test_top3_paired`. 2026-09-30 새 체크아웃에서 실행해 아래 값을 확인했다.
K3·K4·K6·K1 은 노드별 덤프 `reports/gnn_test_preds_group-mapped_2026-09-27.json` 의 `test_rows`(`hit_top3` · `prior_hit_top3` · `district`)로 **따로 다시 세어** 같은 값을 얻었다.
학습 재실행이 아니다 — 학습 명령과 경위는 `docs/finding-gnn-81hub-retrain-2026-09-27.md` 「재학습 (b)」.

| ID | 값 | 출처 필드 | 허용되는 해석 |
|---|---|---|---|
| K1 | **81거점** | `test_top3_paired.by_district` 81개 · 덤프 `district` 81종 | 서울 서빙 거점 전체. 경기 보류 거점 제외 |
| K2 | 노드 88,238 · 엣지 270,212 · 피처 132열 · 미사상 제외 91,052 · 클래스 6 · val 선택 `top1` | `metrics.nodes` · `edges_used` · `features` · `unmapped_nodes_dropped` · `classes` · `val_select_by` | 1점포 1행(겹침 제거) 뒤 규모. 클래스 6 은 7종 중 문화시설이 모집단에 없다는 뜻 |
| K3 | test **17,650**자리 | `metrics.test_nodes` · 덤프 `test_rows` 길이 | 모델 선택에 쓰지 않은 시험 집합. 같은 그래프의 전이적 평가 |
| K4 | Top-3 모델 **92.03%** · 거점 사전분포 **88.67%** · 차이 **+3.36%p** | `test_top3` 0.9203 · `baseline_district_prior_top3` 0.8867 | 같은 test 자리 위 쌍대 비교. 절대 정확도가 아니라 차이가 판정 대상 |
| K5 | 차이의 거점 군집 부트스트랩 95% 구간 **[+2.78, +3.95]%p** | kpi_baseline `skill_ci95_pp` | 거점을 재표본 단위로 둔 구간. 새 거점으로의 일반화 구간 아님 |
| K6 | McNemar b=**851** · c=**258** · 양측 정확 p=2.13×10⁻⁷⁴ · 판정 `실력` | `test_top3_paired.b_model_only/c_prior_only` · kpi_baseline `mcnemar` | 자리 독립 가정. 판정은 K5 구간과 둘 다 요구 |
| K7 | Top-1 모델 **66.96%** · 사전분포 **64.06%** · 차이 **+2.90%p** | `test_top1` 0.6696 · `baseline_district_prior_top1` 0.6406 | **관측.** Top-1 은 쌍대 표가 없어 구간·판정 미산출 |
| K8 | off-prior Top-3 **42.55%** · **2,000**자리 · 분해능 ≈**2.21**%p | `test_offprior_top3` · `offprior_nodes` · kpi_baseline `offprior_detectability` | 관측 전용(게이트 2026-08-26 폐기). 조건 A 의 33.8%(n=1,011)와 모집단이 달라 비교하지 않는다 |
| K9 | test SE **0.2**%p · 분해능(SE 의 2배) ≈**0.41**%p | kpi_baseline `detectability` | 검정이 아니라 눈금 |
| K10 | 어휘 점검 `합격` — 라벨 수준 `group_mapped` · 미분류 0 · 라벨 폭 6/7(기준 ≥6) · 빠진 라벨 문화시설 · [관측] 1순위 음식점 93.3%(88,238자리) | kpi_baseline `vocab` | 기준 ①②③ 은 창업자 승인(2026-09-28) 제품 기준이며 통계적 도출이 아님. 1순위 쏠림은 판정에 쓰지 않음 |
| K11 | **어휘 (a) 대조 — 서빙 불가 판본.** Top-3 91.44% vs 사전분포 89.56%(+1.88%p) · 구간 [+1.57, +2.20]%p · b=1,160 · c=486 · p=1.38×10⁻⁶³ · 판정 `실력` · test 35,861자리 중 미분류 18,211(50.8%) · 서빙 1순위 미분류 133,453/179,290(74.4%) | `reports/gnn_label_a_2026-09-27.json`(`metrics` · `test_top3_paired` · `serving_check`)에 `kpi_baseline.gnn_skill` 적용 · 덤프 `reports/gnn_test_preds_label-a_2026-09-27.json`(y=0 이 미분류) | **실험 근거일 뿐 서빙본 아님.** 통계 판정이 어휘의 쓸모를 보증하지 않는다는 사례로만 쓴다. K1~K10 과 모집단(노드 179,290)이 다르다 |
| M1 | 방법 상수: 구간 95% · 군집 부트스트랩 2,000회 · seed 42 · 유의수준 0.05 · 판정 = 구간 하한 > 0 **그리고** McNemar p < 0.05 일 때만 `실력` | `apps/backend/app/services/forecast_skill.py` `cluster_bootstrap_ratio_ci`(reps=2000, seed=42) · `ALPHA` · `verdict` | 코드 상수. 결과 수치가 아님 |

<!-- 확인필요: finding-gnn-81hub-retrain-2026-09-27 의 비교 열은 09-04 서빙본 사전분포 Top-3 를 89.3%(+2.32%p)로 적는다.
     이 인덱스 조건 A 는 89.4%. 어느 쪽도 이 절에서 고치지 않는다. 조건 E 와 조건 A 를 나란히 쓰지 않으므로 이 절의 값에는 영향이 없다. -->

---

## P2 · Page — 건물 단위 공실률 데이터셋

| 값 | 수치 | 출처 |
|---|---|---|
| Tier1(건축물대장 실측) 거점 | **66/66** | `scripts/pppp_status.py` |
| 대표 집계 커버리지 90% 이상 | 66/66 (최저 100.0%) | 〃 |
| R-ONE 앵커 대조 보유 | 66/66 | 〃 |
| 히트맵 레이어 | 공실 · 임대(R-ONE) · 유동 · 밀도 (동일 100m 격자) | 〃 |

### 공간 해상도 승격 — 상권 → 집계구 (2026-08-26)

| 값 | 수치 |
|---|---|
| 집계구 수 | 거점당 중앙 **26곳** (4~66) |
| 집계구 면적 중앙 | **22,407㎡** |
| 커버된 셀 | **3,699개 · 54/54거점 전부** (부분 커버 거점 0) |

> **한 화면에 두 눈금이 섞이면 색은 그럴듯한데 셀 간 비교가 거짓이 된다** — 그래서
> 거점 단위 전부-아니면-전무로 싣는다. 논문에서 방법론적 주장으로 쓸 수 있는 원칙이다.

### 승격이 실제로 무엇을 고쳤는가 — 검증 가능한 형태

종전 셀 값은 `(상권 총량) × (거점 공통 구성비)` 였다. 시각을 바꿔도 **모든 셀에 같은
상수가 곱해져** 거점 내 서열이 구조적으로 불변이었다(슬라이더가 밝기만 바꿨다).

| 검증 | 결과 |
|---|---|
| 시각에 따라 셀 서열이 바뀌는 거점 | **52/54** |
| 03시 vs 14시 Spearman rho | 중앙 **0.812** · 최소 0.498(kyunghee) |
| 대조군(상권 경로) rho | **1.000** (테스트가 고정) |

⚠ **입도가 올라간 것이지 격자 실측이 된 것은 아니다** (집계구 22,407㎡ > 셀 10,000㎡).
⚠ 점포 밀도(`stor`)는 집계구 원천이 없어 **상권 단위에 남았다** — 같은 레이어 안에서 눈금이 다르다.

### 시간 축

평일 24시간 66거점 · 주말 66거점 (표본 28일: 평일 20 / 주말 8).
미충족 거점은 응답이 `time_source:"trdar_band"` 로 6구간임을 밝히고 물러난다.

---

## P3 · Posting — 공개 데이터의 ROI 정밀도 한계

⚠ **이 편은 양성 결과가 적고 기각 기록이 많다.** 그것을 논문의 주장으로 삼는다:
"공개 데이터 범위에서 층·면적 축 ROI 정밀화는 닫혀 있다"를 **증명하는** 편이다.

| 근거 | 내용 | 출처 |
|---|---|---|
| 3-Tier 폴백 | 고급화/가성비/기능중심 + `roi_months` | `services/districts.tier_scenarios` |
| 감도 실험 | **32조합 전수** | §0-D |
| 유닛 면적 입도 | **50%** (게이트 폐기 2026-09-05, 관측 전용) | `pppp_status.py` |
| `prem`(권리금) | 수집 과제가 아니라 **입력 계약**으로 확정 | §0-K |
| 집합건물 전유부 편입 | 정량 조사 후 **기각** | §0-R |
| 호실 면적 공식 소스 | 공개 범위에서 **닫힘** | §0-S · `finding-posting-unit-area-sources-2026-08-29.md` |
| 상가정보 `flrNo` 로 면적 특정 | 재 보고 **기각** | §0-W · `finding-posting-unit-area-flrno-2026-09-06.md` · `reports/posting_unit_area_flrno_probe_2026-09-06.json` |
| 층 축 | 두 번(§0-M·§0-Q) 같은 벽에 부딪힘 — 균등분할 유지 | §0-M · §0-Q |
| R-ONE 서울 모집단 | **59~64 상권**뿐 (21분기 58 / 17분기 1 / 7분기 5) | §0-O · `rone_districts.py` 전수확인 2026-07-24 |

> **§0-N 의 특징적 기록**: 매출 앵커에서 버그를 하나 찾아 고쳤는데 **그래도 가설은 기각됐다.**
> 버그 수정이 결과를 바꾸지 않았다는 것을 남긴 기록은 드물다.

⚠ 3D 디지털 트윈은 2026-09-05 폐기(§0-V) — 절차적 박스가 실측 형상이 아니었다.
번들 832KB → 4KB. 논문에서 "시각화 충실도 ≠ 정보량" 사례로 쓸 수 있다.

---

## P4 · Program — LLM 마케팅 생성의 사실성 가드레일

⚠ **정량 평가가 없다.** 아래는 전부 설계·계약·테스트 통과 기록이고 성능 수치가 아니다.
실증 논문으로 쓰려면 평가 설계부터 새로 해야 한다 → README 의 경고 참조.

| 근거 | 내용 | 출처 |
|---|---|---|
| 생성 엔진 | `POST /marketing/generate` + ProgramStudio + `ha_guard` 후처리 | `services/marketing.py` · `services/ha_guard.py` |
| 입력 계약 3층 | 자리 · 상권 · 검증 브리프(2026-09-17 대상 재정의 — 예비창업자·팝업/가오픈/MVP 검증) | §0-V · `tests/test_posting_marketing.py` 브리프 배선 · `tests/test_ha_guard.py` 미검증 경험 |
| 출력 분리 | 퍼포먼스 / 상권활성화 | §0-F · `tests/test_program_output_split.py` (14건) |
| ~~상용 온보딩~~ | 2026-09-17 삭제 — 받을 점주 원문이 없다 | §0-K · §0-V |
| 검증 지표 | 지표 · 측정 방법 · 목표선 · 기각 조건 | §0-V · `tests/test_program_output_split.py` · `tests/test_ha_guard.py` 지표 검사 |
| 검색 트렌드 라벨 | 66/66거점 | `pppp_status.py` |
| 데이터 채널 타당성 | 채널별 가능/불가 전수 판정 (크롤링 금지선 포함) | §0 (2026-07-18) |

> **트렌드 라벨의 의미와 수정 이력**: 종전에는 라벨이 없으면 트렌드 검사가 조용히 통과했다.
> 현재 `_check_trend`는 컨텍스트·라벨 부재에 `trend_unverified` 경고를 반환한다.
> 아래 P3·P4 집필 보완 근거의 PROGRAM-E02를 따른다. 과거 실패를 현행 동작으로 서술하지 않는다.

---

## 교차 편 — 방법론 (어느 편에도 쓸 수 있다)

이 저장소가 반복적으로 실행한 절차. P1 에서 정식화하고 나머지 편에서 인용하는 것을 권한다.

1. **값싼 프로브를 먼저 산다** — 학습·수집 없이 기존 split 재사용으로 표본·수율만 잰다
2. **검정력을 먼저 계산한다** — MDE 가 실측 효과크기보다 크면 그 실험은 사지 않는다
3. **음성 결과를 지우지 않는다** — 지우면 다음 사람이 같은 것을 다시 시도한다(§0-I 가 명시)
4. **문서가 낡는 것을 구조로 막는다** — 진행률·거점 수의 단일 출처는 스크립트다

> 4번의 근거: 이 저장소의 문서는 실제로 두 번 낡았다(08-02 Tier1 13거점, 08-09 22거점에서 멈춤).
> `scripts/pppp_status.py` · `scripts/chain_status.py` 가 산출물에서 직접 센다.

---

## 등재 대기 (본문에 쓰기 전 확인 필요)

- [x] LSTM 공실 예측 성능 — 2026-09-09 등재 완료. [서빙본 절](#lstm-공실-예측--서빙본-2026-09-04-학습--66거점) 참조. GNN 조건 A/B/C 와 모집단·태스크가 다르므로 합산하지 않는다
- [x] GNN 81거점 09-27 재학습(조건 E) — 2026-09-30 등재. [조건 E 절](#platform-condition-e). 조건 A/B/C 와 합산·비교하지 않는다
- [ ] Page 공실률의 R-ONE 앵커 대비 **격차 수치** — "앵커 대조 보유 66/66"은 보유일 뿐 격차가 아니다
- [ ] Posting 감도 실험 32조합의 **결과 수치** — 조합 수만 인덱스에 있다
- [x] Page 핵심 문헌 Alsudais의 저자 공개본 v2: 8페이지 텍스트·시각 대조 완료. [읽기 장부](page-study/reading-ledger.md). 출판본·별도 부록·보조문헌 전체 본문은 미확인이고, 다른 P의 상태를 완료로 바꾸지 않는다.

---

## 알려진 문서 결함 (앵커를 걸기 전에 알아야 한다)

⚠ `docs/feature-platform.md` 에 **`0-M` 이 두 번** 있다 (line 305 "감성 구역을 행정동
실측 구역으로" · line 466 "집계구 배선 → 600ep → McNemar"). 앵커로 인용할 때 절 번호만
쓰면 어느 쪽인지 알 수 없다 — **제목까지 함께 적는다.**

---

<a id="page-condition-d"></a>

## P2 · Page — 조건 D: 동결 자료의 구조 감사·영향·계산 재현성

등재일: 2026-09-07. 원 실행은 `audits/page-analysis-20260906`, 입력 명세는 `audits/page-inventory-20260906/manifest.json`이다. 이 절의 수치는 특정 입력 묶음에 대한 결과이며 현재 운영 전체·서울 전체·실제 공실 정확도로 확대하지 않는다. [추가 검증 결과](page-study/evidence-verification.json)의 `summary` 및 참조 파일 해시로 재확인했다.

| 근거 ID | 수치·판정 | 원천 / 검증 경로 | 허용되는 해석 |
|---|---|---|---|
| PAGE-D01 | 66거점 · 52,642 마스터 폴리곤 | `structural-audit.json`의 `hubs`, `rules`; 추가 검증 `hubs/polygons` | 동결된 가공 마스터 검사 범위 |
| PAGE-D02 | 층 정보 검사 30,912 폴리곤 | `rules.floor_semantics`, `rules.floor_interval_formula` | 해당 분모에서 계산 일관성 확인 |
| PAGE-D03 | 원천 관측 시점 정렬 66거점 평가 불가 | `rules.temporal_observation_alignment` | 최신성·동시점 현실 검증 완료 아님 |
| PAGE-D04 | 별도 프로세스 반복에서 마스터·커버리지·서빙 66/66 일치 | `reproduction-comparison.json`; 커버리지는 `built_at`만 제외 | 동일 선택 입력 반복. 바이트 비교는 마스터에만 해당 |
| PAGE-D05 | 기존 행 순서 시험 198회 · 거점 집계 변경 0회 · 격자 소속 또는 분자·분모 영향 65거점 | `order-sensitivity.json`; 추가 검증 `order_*` | 동일 내용 순서 변형의 사후 탐색. 현실 위치 오차·독립 표본 수 아님 |
| PAGE-D06 | 층 배정 범위 폭 중앙값 16.235267101643892%p · 최댓값 34.38818565400844%p | `impact-intervals.json`; 추가 검증 `floor_interval_*` | 정보 부족에 따른 범위. 통계적 신뢰구간·현실 공실 오차 아님 |
| PAGE-D07 | 독립 검토 표본 211개 전부 `unresolved` | `sample-design.json`, `independent-review-sample.csv` | 사람 정답·오류율 미확보. 2026-09-07 사용자도 자료·검토자 부재 확인 |
| PAGE-D08 | 보존 서빙 사본 비교 66/66 · 독립 셀 재합산 66/66 통과 | 추가 검증 `stored_serving_comparisons_pass/cell_reaggregation_pass` | 기존 검사 결과 JSON의 주장만 재인용하지 않고 응답 객체·셀 합계를 대조 |
| PAGE-D09 | 새 Git 체크아웃 Gold→서빙 66/66 일치 | 추가 검증 `fresh_gold_to_serving_matches`와 거점별 의미 해시 | 새 로컬 체크아웃 실행. 원천부터 전체 파이프라인·클라우드 실행·독립 팀 재현 아님 |
| PAGE-D10 | 보존 감사 파일 224개 해시 일치 · 목록 중 미보유 537개 | 추가 검증 `archived_file_availability` | Git 보존 범위의 무결성. 모든 로컬 사본의 재배포·보존을 뜻하지 않음 |
| PAGE-D11 | 원본 인벤토리 946개 중 새 체크아웃 보유 265개 · 미보유 681개 | 추가 검증 `data_availability` | 현재 패키지로 Bronze→Gold 전체 재실행 불가. 원래 로컬 원본 소실을 뜻하지 않음 |
| PAGE-D12 | PC 재검증: 서빙 사본·셀 재합산·Gold→서빙 각각 66/66 통과. 감사 파일 761개 및 원본 인벤토리 946개 보유·해시 일치 | 추가 검증 `pc_session_recheck`; 전체 실행 출력은 Git 제외 `private/pc-evidence-verification.json`과 등록 SHA-256 | 기존 파일을 보유한 PC에서 같은 계산 결과를 확인. 새 체크아웃·전체 파이프라인 재현 아님. PAGE-D10·D11의 이전 체크아웃 보유량을 대체하지 않음 |

**재검증 명령:** 저장소 루트에서 `python docs/papers/page-study/verify_evidence.py`. 표의 원 실행 결과를 다시 집계하고, 실제 Gold 서빙 함수를 호출한다. 원래 대장 파이프라인을 실행하는 명령이 아니다. 사용한 체크아웃 커밋, 실행기 해시, Python 및 로드한 저장소 코드 해시는 검증 JSON에 있다. 최상위 기록은 이전 새 체크아웃 결과이며, `pc_session_recheck`는 2026-09-07 PC 실행을 별도로 보존한다. 입력 해시와 거점별 서빙 객체·의미 해시는 두 실행에서 일치했다. 파일 보유량·커밋·실행기 및 로드 코드 해시의 차이를 생성시각 차이로 지우지 않는다.

마스터 키·계산식 등의 통과를 현실 정답으로 승격하지 않는다. 같은 지번에 대한 넓은 검사에서 표시된 613행·428그룹은 [후속 분류](audits/page-analysis-20260906/same-lot-flag-qualification.json)에 따라 **확정 오류로 등재하지 않는다**. 기존 코드의 집계 제외 규칙과 출처 표기를 유지한다. 기존 릴리스 변경을 신규 개업·폐업·수집 오류로 해석하지 않는다.

문헌 근거: Alsudais, *Incorrect Data in the Widely Used Inside Airbnb Dataset*, 저자 공개본 `arXiv:2007.03019v2`, 관련 출판 DOI `10.1016/j.dss.2020.113453`, 출판연도 2021. [원문 등록·읽기 범위](page-study/source-register.json). 원문 내 수치 불일치는 읽기 장부에 남겼으며 원고에 해당 수치·검정 결과를 옮기지 않는다. 우리의 표집·해시·행 순서 검사가 원문에 그대로 있었던 것으로 서술하지 않는다.

## Page 문헌 보완의 서지 식별값

2026-09-19 확인. 아래는 문헌 식별용 연도·권호·쪽·DOI이며 조건 D의 실증 수치가 아니다. 실제 확인 위치와 적용 제한은 [문헌 검토 기록](page-study/literature-review-20260919.md)에 있다.

| 문헌 | 확인한 서지 | 일차 출처 |
|---|---|---|
| Alsudais | 2021 · Decision Support Systems 141 · 113453 · arXiv:2007.03019v2 · DOI 10.1016/j.dss.2020.113453 | https://www.sciencedirect.com/science/article/pii/S0167923620302086 |
| Marsden, J. R. & Pingry, D. E. | 2018 · Decision Support Systems 115 · A1–A7 · DOI 10.1016/j.dss.2018.10.007 | https://www.sciencedirect.com/science/article/pii/S0167923618301647 |
| National Academies of Sciences, Engineering, and Medicine | 2019 · Reproducibility and Replicability in Science · 제3장 정의 절 · DOI 10.17226/25303 | https://www.nationalacademies.org/read/25303/chapter/6 |
| Sandve, G. K., Nekrutenko, A., Taylor, J. & Hovig, E. | 2013 · PLOS Computational Biology 9(10) · e1003285 · DOI 10.1371/journal.pcbi.1003285 | https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003285 |
| Timmerman, Y. & Bronselaer, A. | 2019 · Decision Support Systems 126 · 113138 · DOI 10.1016/j.dss.2019.113138 | https://biblio.ugent.be/publication/8634924 |

<a id="posting-program-update"></a>

## P3·P4 집필 보완 근거

확인일 2026-09-19. 과거 프로브의 모집단과 이번 코드 계약 검사를 분리한다. 원천·Gold·제품 코드는 변경하지 않았다. 세부 검수와 문헌 확인 범위는 [집필 기록](posting-program-writing-20260919.md)에 있다.

| ID | 근거·판정 | 출처와 확인 범위 |
|---|---|---|
| POSTING-E01 | 역사적 공식 소스 조사: 54거점·528 후보행. 건축HUB·서울교통공사·LH·온비드의 면적·임대가능 상태·모집단·키 적격성 대조. 모든 공개 데이터의 불가능성 증명 아님 | `docs/finding-posting-unit-area-sources-2026-08-29.md`; `data/validation/posting_unit_area_sources.py` |
| POSTING-E02 | 층번호 프로브: 66거점·664유닛, 단일층 30개(4.5%), 해당 용량 분포 `{1: 30}`, 면적 차이 n=30·min=0·max=0·median=0.0평 | `reports/posting_unit_area_flrno_probe_2026-09-06.json`의 `served_hubs/units_total/single_floor_units/single_floor_pct/single_floor_capacity_dist/delta_pyeong_on_single` 직접 대조. 이번에 프로브 재실행 아님 |
| POSTING-E03 | 층번호 후속은 층별 유닛 분할에 종속되므로 독립 성공·실패 실험으로 중복 계수하지 않음 | `docs/finding-posting-unit-area-flrno-2026-09-06.md`의 「왜 §0-Q 와 같은 것인가」 |
| POSTING-E04 | 매출 앵커의 기준 모집단 오류는 수정됐지만 설명 가설은 기각. 후속 R-ONE 대조에서 ‘전부 프라임’ 전제도 반증 | `docs/feature-posting.md` §0-N 「매출 앵커」, §0-O 「진짜 소득」. 과거 운영 판정을 사실상 공실·ROI 정답으로 승격하지 않음 |
| POSTING-E05 | 현재 통계 기반 매출·비용 계산과 수기 계수 폴백은 `basis`로 구분. 초기 투자 계수와 유닛 면적 가정은 실제 계약·성과 정답이 아님 | `apps/backend/app/services/districts.py::tier_scenarios`, `posting_revenue.py`, `vacant_inventory.py` 읽기 대조 |
| POSTING-E06 | 공식 소스 적격성 계약 검사 3 passed | 저장소 루트 `python -m pytest data/tests/test_posting_unit_area_sources.py -q`. 외부 API 호출·실측 정확도 평가 아님 |
| PROGRAM-E01 | 현행 대상은 검증하려는 창업자. 입력 ProgramBrief, 출력 online/offline/signals. 점주 원문 온보딩은 삭제 | `docs/feature-program.md` §0-V; `program_brief.py`, `marketing.py` |
| PROGRAM-E02 | 트렌드 컨텍스트·라벨 부재는 `trend_unverified` warning. 상승 라벨 혼재 시 모순 검사 차단을 하지 않는 한계 유지 | `ha_guard.py::_check_trend`; `test_no_context_means_no_trend_check`, `test_context_without_trend_labels_is_also_unverified`, `test_mixed_trend_does_not_block` |
| PROGRAM-E03 | 미검증 경험 주장 차단과 앞으로 측정할 지표를 구별. 생성 조각은 줄바꿈으로 연결 | `ha_guard.py::check_program`, `_check_unproven_evidence`; `docs/feature-program.md` §0-V의 문장 경계 결함 |
| PROGRAM-E04 | violation이면 생성물을 버리고 규칙 스텁으로 폴백, warning이면 생성물을 유지하고 findings 표시. 빈 findings는 전 항목 검증 완료 아님 | `marketing.py::generate_program`; `test_violation_falls_back_to_stub`, `test_warning_keeps_llm_output`, `test_stub_without_llm_has_empty_findings` |
| PROGRAM-E05 | HA 가드·출력 계약 검사 합계 54 passed | `apps/backend`에서 `python -m pytest tests/test_ha_guard.py tests/test_program_output_split.py -q`. 고정 예시·목킹 검사이며 LLM 실호출·사실성 위반율·광고 효과 평가 아님 |
| PROGRAM-E06 | 지표명·측정 방법·목표선·기각 조건의 구조와 내용 경고를 구별 | `test_signal_requires_a_decision_rule`, `test_missing_signals_is_warning`, `test_signal_without_number_is_warning`, `test_signal_without_decision_rule_is_warning` |

### P4 문헌 서지 식별값

- Min 등, 2023, *FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation*. EMNLP, 12076–12100. DOI `10.18653/v1/2023.emnlp-main.741`. ACL 서지·PDF 초록·서론과 평가 정의를 확인. 원문 성능 수치를 본 원고로 옮기지 않는다.
- Gao, Yen, Yu, Chen, 2023, *Enabling Large Language Models to Generate Text with Citations*. EMNLP, 6465–6488. DOI `10.18653/v1/2023.emnlp-main.398`. ACL 서지·PDF 초록·평가 차원 설명을 확인. 전체 부록 정독·벤치마크 실행 완료를 뜻하지 않는다.

<a id="literature-q1-20261011"></a>

## 문헌 근거 — AI/MIS Q1 저널 탐색 반영 (2026-10-11)

네 원고(`논문 초안/paper-*.md`)의 서론·관련 연구·논의를 다시 쓰면서 추가한 인용의 확인 범위다. 위 2026-10-11 갱신 절의 ‘새 인용을 추가하지 않는다’는 그 갱신 당시의 범위이며, 이 절이 이후에 추가한 문헌 근거다. PlaceOS의 실험 수치와 가설 판정은 이 절에서 바꾸지 않았다. 아래 수치는 **문헌이 초록에서 보고한 값**이며 PlaceOS의 결과가 아니다.

**확인 방법.** (1) 서지: Crossref DOI 레코드의 제목·저자·권호·쪽을 대조했다. (2) 초록: OpenAlex·Semantic Scholar 또는 출판사·기관 페이지의 초록을 읽었다. 초록을 읽지 못한 문헌은 아래 표에 ‘초록 미확인’으로 적었고 원고에서도 서지 수준으로만 인용했다. (3) 저널 분류: SCImago Journal Rank 최신판(2026-10-11 조회, 자료 연도 2025)의 최고 사분위와 분야다. Clarivate JCR의 분야별 사분위는 확인하지 않았다. 학회·워크숍 문헌은 Q1 근거로 세지 않는다. **전문은 정독하지 않았다** — 원고는 초록이 말하는 범위 안에서만 각 문헌을 서술한다.

| ID | 서지 | 원고에서 쓴 내용(초록 범위) | 확인 범위 · 저널 분류 |
|---|---|---|---|
| LIT-01 | Baroudi & Orlikowski (1989). *MIS Quarterly* 13(1), 87–106. DOI 10.2307/248704 | MIS 연구는 통계적 검정력이 낮아 현상을 놓치기 쉽고, 표본 확대 외에도 검정력을 높일 방법이 있다 (P1) | 서지·초록 · Q1 정보시스템 |
| LIT-02 | de Reuver, Sørensen & Basole (2018). *Journal of Information Technology* 33(2), 124–135. DOI 10.1057/s41265-016-0033-3 | 디지털 플랫폼 연구는 분석 단위·디지털화 정도·사회기술적 성격을 명시해야 한다 (P1) | 서지·초록 · Q1 정보시스템 |
| LIT-03 | Dietterich (1998). *Neural Computation* 10(7), 1895–1923. DOI 10.1162/089976698300017197 | 한 번만 실행할 수 있는 알고리즘의 비교에서 McNemar 검정만이 허용 가능한 제1종 오류를 가진다 (P1) | 서지·초록 · 방법론 인용, AI/MIS Q1 근거로 세지 않음 |
| LIT-04 | Ferrari Dacrema, Boglio, Cremonesi & Jannach (2021). *ACM Transactions on Information Systems* 39(2), 1–49. DOI 10.1145/3434185 | 재현 가능한 신경망 추천 방법 12개 중 11개가 개념적으로 단순한 방법에 뒤질 수 있다; 기준선의 선택과 최적화가 문제 (P1) | 서지·초록 · Q1 정보시스템 |
| LIT-05 | Forman, Ghose & Goldfarb (2009). *Management Science* 55(1), 47–57. DOI 10.1287/mnsc.1080.0932 | 지역에 매장이 문을 열면 소비자가 온라인 구매에서 이탈한다 (P1–P4) | 서지·초록 · Q1 경영과학 |
| LIT-06 | Ghose, Goldfarb & Han (2013). *Information Systems Research* 24(3), 613–631. DOI 10.1287/isre.1120.0453 | 모바일 인터넷에서 사용자 집 가까이의 매장이 더 자주 클릭된다 (P1–P3) | 서지·초록 · Q1 정보시스템·경영정보 |
| LIT-07 | Guo, Li, Zheng, Wang & Yu (2018). *Proceedings of the ACM on IMWUT* 1(4), 1–23. DOI 10.1145/3161411 | 데이터가 부족한 새 도시의 체인점 입지 추천을 위해 다른 도시·유사 기업의 지식을 전이; 네 도시의 체인 호텔 자료로 검증 (P1) | 서지·초록 · 저널 분류 미확인 |
| LIT-08 | Kaufman, Rosset, Perlich & Stitelman (2012). *ACM TKDD* 6(4), 1–21. DOI 10.1145/2382577.2382579 | 누수(leakage)의 정의, 학습·예측 분리, i.i.d. 가정이 깨지는 사례 (P1) | 서지·초록 · Q1 컴퓨터과학 일반 |
| LIT-09 | Kumar, Qiu & Kumar (2018). *Information Systems Research* 29(4), 849–870. DOI 10.1287/isre.2017.0749 | 점주의 온라인 응답이 이웃 업소의 성과에 번지며 직접 경쟁 여부에 따라 다르다 (P1) | 서지·초록 · Q1 정보시스템·경영정보 |
| LIT-10 | Lan, Cheng, Wang & Wen (2022). *Remote Sensing* 14(15), 3579. DOI 10.3390/rs14153579 | 대중교통망 기반 GCN으로 싱가포르의 점포 입지 매력도를 예측; 지역 지리 특성만 쓰는 방법보다 우수 (P1) | 서지·DOAJ 초록 · Q1 지구과학(AI/MIS 아님) |
| LIT-11 | Li, Yu, Li & Gao (2023). *Tourism Management* 96, 104707. DOI 10.1016/j.tourman.2022.104707 | 측면 기반 감성이 전체 감성보다 식당 생존 예측을 개선 (P1) | 서지·기관 공개 요약, 초록 직접 대조 미완료 · Q1 관광·경영 |
| LIT-12 | Lin, Lucas & Shmueli (2013). *Information Systems Research* 24(4), 906–917. DOI 10.1287/isre.2013.0480 | 대표본에서 p값이 0에 가까워져 실용적 의미 없는 결과를 지지하게 되는 문제 (P1) | 서지·초록 · Q1 정보시스템·경영정보 |
| LIT-13 | Liu, Guo, Zhang, Zeghlache, Chen, Hu, Zhang, Zhou & Yu (2021). *ACM TKDD* 15(3), 1–27. DOI 10.1145/3442203 | 라벨 없는 목표 도시로의 적대적 전이학습과 전이 가능성 가중 (P1) | 서지·초록 · Q1 컴퓨터과학 일반 |
| LIT-14 | Luca & Zervas (2016). *Management Science* 62(12), 3412–3427. DOI 10.1287/mnsc.2015.2304 | Yelp 식당 리뷰의 상당 부분이 의심 리뷰로 필터링되며 경쟁이 심할수록 불리한 가짜 리뷰를 받을 가능성이 커진다 (P1) | 서지·초록 · Q1 경영과학 |
| LIT-15 | Martens, Provost, Clark & de Fortuny (2016). *MIS Quarterly* 40(4), 869–888. DOI 10.25300/MISQ/2016/40.4.04 | 전통적 구조화 데이터는 규모를 키워도 뚜렷한 개선이 없었고 세밀한 행동 데이터는 규모의 이득이 지속 (P1) | 서지·초록 · Q1 정보시스템 |
| LIT-16 | Shmueli & Koppius (2011). *MIS Quarterly* 35(3), 553–572. DOI 10.2307/23042796 | 예측 분석의 여섯 역할(현상의 예측 가능성 평가 포함); 설명력은 예측력을 함의하지 않는다 (P1) | 서지·초록 · Q1 정보시스템 |
| LIT-17 | Yu, Tian, Wang, Guo & Mei (2016). *ACM TKDD* 11(1), 1–21. DOI 10.1145/2930671 | 주어진 위치의 점포 유형 추천; 서빙 고객 수 극대화; 위치·이웃 점포 관계 피처 (P1) | 서지·초록 · Q1 컴퓨터과학 일반 |
| LIT-18 | Zhang & Luo (2023). *Management Science* 69(1), 25–50. DOI 10.1287/mnsc.2022.4359 | 소비자 게시 사진이 리뷰·업체 특성·경쟁 환경을 넘어 식당 생존을 예측; 사진은 최대 3년, 리뷰는 1년; 진입·퇴출 시점은 플랫폼 페이지·웹사이트·검색에서 수집 (P1–P3) | 서지·초록 · Q1 경영과학 |
| LIT-19 | Zheng, Capra, Wolfson & Yang (2014). *ACM TIST* 5(3), 1–55. DOI 10.1145/2629592 | 도시 데이터의 수집·관리·분석·서비스 제공을 잇는 도시 컴퓨팅의 틀과 응용 범주 (P1) | 서지·초록 · Q1 인공지능 |
| LIT-20 | Ballou, Wang, Pazer & Tayi (1998). *Management Science* 44(4), 462–484. DOI 10.1287/mnsc.44.4.462 | 정보 제조 시스템과 정보 산출물의 적시성·정확도·비용을 데이터 단위와 구성요소에 연결 (P2, P3) | 서지·초록 · Q1 경영과학 |
| LIT-21 | Burton-Jones & Grange (2013). *Information Systems Research* 24(3), 632–658. DOI 10.1287/isre.1120.0444 | 표상 이론에서 효과적 사용의 성격과 동인을 도출 (P2, P3) | 서지·초록 · Q1 정보시스템·경영정보 |
| LIT-22 | Du, Wang, Zou & Shi (2018). *Remote Sensing* 10(12), 1920. DOI 10.3390/rs10121920 | Jilin1-03 위성과 지리 자료로 census tract 단위 주택 공실률을 모델링 (P2) | 서지, 기존 후보표의 공개 원문 확인 기록 · Q1 지구과학(AI/MIS 아님) |
| LIT-23 | Fišar, Greiner, Huber, Katok, Ozkes & the Management Science Reproducibility Collaboration (2024). *Management Science* 70(3), 1343–1356. DOI 10.1287/mnsc.2023.03556 | 데이터 접근 등이 장애가 아닌 논문의 95% 이상이 완전·대부분 재현; 29%는 데이터 일부 접근 불가; 전체 재현 비율 68%; 분야 간 이질성은 주로 데이터 접근성 (P2) | 서지·초록 · Q1 경영과학 |
| LIT-24 | Hevner, March, Park & Ram (2004). *MIS Quarterly* 28(1), 75–106. DOI 10.2307/25148625 | 설계과학을 이해·수행·평가하는 지침 (P2, P4) | 서지·초록 · Q1 정보시스템 |
| LIT-25 | Law, Paige & Russell (2019). *ACM TIST* 10(5), 1–19. DOI 10.1145/3342240 | 거리뷰·위성 영상의 시각 피처가 런던 주택가격 추정을 개선하고 보지 못한 자치구에도 일반화 (P2) | 서지·초록 · Q1 인공지능 |
| LIT-26 | Li & Long (2024). *Computers, Environment and Urban Systems* 108, 102071. DOI 10.1016/j.compenvurbsys.2023.102071 | 이동 센싱 이미지와 컴퓨터 비전으로 점포 공실 추론; 공개 데이터셋 설명(Faster R-CNN, 시닝) (P2) | 서지·데이터셋 설명, 초록 미확인 · Q1 지리·도시(AI/MIS 아님) |
| LIT-27 | Parssian, Sarkar & Jacob (2004). *Management Science* 50(7), 967–982. DOI 10.1287/mnsc.1040.0237 | 원천 데이터의 정확도·완전성이 선택·투영·카테시안 곱을 거쳐 파생 데이터 품질에 반영되는 방식 (P2, P3) | 서지·초록 · Q1 경영과학 |
| LIT-28 | Recker, Indulska, Green, Burton-Jones & Weber (2019). *Journal of the Association for Information Systems*, 735–786. DOI 10.17705/1jais.00550 | 정보시스템의 기본 목적은 현실 현상의 충실한 표상; 이 이론이 데이터 품질 연구 등을 뒷받침 (P2, P3) | 서지·초록, 권호는 확인한 기록에 없음 · Q1 정보시스템 |
| LIT-29 | Venable, Pries-Heje & Baskerville (2016). *European Journal of Information Systems* 25(1), 77–89. DOI 10.1057/ejis.2014.36 | 평가 에피소드를 기능적 목적(형성/총괄)과 환경(인공/자연)으로 구분하는 FEDS (P2, P4) | 서지·초록 · Q1 정보시스템·경영정보 |
| LIT-30 | Vetrò, Canova, Torchiano, Minotas, Iemma & Morando (2016). *Government Information Quarterly* 33(2), 325–337. DOI 10.1016/j.giq.2016.02.001 | 공공 개방 데이터 품질을 가장 세밀한 수준에서 측정하는 지표 체계; 두 이탈리아 사례 적용 (P2) | 서지·초록 · Q1 문헌정보·법·사회과학(AI/MIS 아님) |
| LIT-31 | Wang & Strong (1996). *Journal of Management Information Systems* 12(4), 5–33. DOI 10.1080/07421222.1996.11518099 | 데이터 품질의 네 범주: 내재적·맥락적·표현적·접근성 (P2, P3) | 서지·초록 · Q1 경영정보 |
| LIT-32 | Han, Jia, Chen, Gupta, Kumar & Lin (2022). *Journal of Business Research* 144, 416–427. DOI 10.1016/j.jbusres.2022.01.049 | 기계학습 기반 수익 입지 탐색(제목·서지 수준) (P3) | 서지·검색 요약, 초록 미확인 · Q1 경영·마케팅 |
| LIT-33 | Kayande, De Bruyn, Lilien, Rangaswamy & van Bruggen (2009). *Information Systems Research* 20(4), 527–546. DOI 10.1287/isre.1080.0198 | 개선 여지와 교정 행동 피드백을 함께 줄 때 사용자의 정신 모형이 정렬되고 시스템 평가가 개선 (P3) | 서지·초록 · Q1 정보시스템·경영정보 |
| LIT-34 | Lu, Zheng, Nervino, Li, Xu & Xu (2024). *Journal of Retailing and Consumer Services* 77, 103620. DOI 10.1016/j.jretconser.2023.103620 | 기계학습 기반 점포 입지 선별(제목·서지 수준) (P3) | 서지·검색 요약, 초록 미확인 · Q1 마케팅 |
| LIT-35 | Nambisan (2017). *Entrepreneurship Theory and Practice* 41(6), 1029–1055. DOI 10.1111/etap.12254 | 디지털 기술이 창업 과정의 불확실성의 성격과 대처 방식을 바꾸었다 (P3) | 서지·초록 · Q1 경영·경제 |
| LIT-36 | Önüt, Efendigil & Soner Kara (2010). *Expert Systems with Applications* 37(3), 1973–1980. DOI 10.1016/j.eswa.2009.06.080 | 퍼지 AHP·TOPSIS로 이스탄불 쇼핑센터 입지 선택 (P3) | 서지, 저자 소속 대학 기록의 초록 · Q1 인공지능 |
| LIT-37 | Otis, Clarke, Delecourt, Holtz & Koning (2026). *Management Science*, 온라인 선공개. DOI 10.1287/mnsc.2024.06909 | GPT-4 사업 조언의 평균 효과는 영과 구분되지 않음; 기준 성과가 낮던 창업자는 거의 10% 나빠지고 높던 창업자는 15%를 넘게 개선되었을 수 있음; 차이는 실행한 조언에서 비롯 (P3, P4) | 서지·초록 · Q1 경영과학 |
| LIT-38 | Steininger (2019). *Information Systems Journal* 29(2), 363–407. DOI 10.1111/isj.12206 | 창업 운영에서 IT의 네 역할: 촉진자·매개자·산출물·편재 (P3) | 서지·초록 · Q1 정보시스템 |
| LIT-39 | Boussioux, Lane, Zhang, Jacimovic & Lakhani (2024). *Organization Science* 35(5), 1589–1607. DOI 10.1287/orsc.2023.18430 | 외부 평가자 300명이 234개 해결안 중 무작위 13개씩 평가(3,900 평가자-해결안 쌍); 사람 집단은 참신성, 사람-AI는 전략적 실행 가능성·재무·환경 가치에서 높음 (P4) | 서지·초록 · Q1 경영·조직 |
| LIT-40 | Camuffo, Cordova, Gambardella & Spina (2020). *Management Science* 66(2), 564–586. DOI 10.1287/mnsc.2018.3249 | 이탈리아 스타트업 116개, 16개 시점, 약 1년; 과학적 접근을 훈련받은 창업자가 성과가 좋고 피벗이 잦으며 중도 탈락은 늘지 않음 (P4) | 서지·초록 · Q1 경영과학 |
| LIT-41 | Camuffo, Gambardella, Messinese, Novelli, Paolucci & Spina (2024). *Strategic Management Journal* 45(6), 1209–1237. DOI 10.1002/smj.3580 | 759개 기업, 네 개의 무작위 실험; 아이디어 종료 증가, 피벗 횟수의 비선형 효과 (P4) | 서지·초록 · Q1 경영·전략 |
| LIT-42 | Feuerriegel, Hartmann, Janiesch & Zschech (2024). *Business & Information Systems Engineering* 66(1), 111–126. DOI 10.1007/s12599-023-00834-7 | 생성형 AI가 사람의 창작과 구별되지 않는 콘텐츠를 만들 수 있다는 도입부 (P4) | 서지·초록 도입부 · Q1 정보시스템 |
| LIT-43 | Gregor & Hevner (2013). *MIS Quarterly* 37(2), 337–355. DOI 10.25300/MISQ/2013/37.2.01 | 문제·해결 영역의 지식 상태에 따른 기여 틀과 산출물 기술을 결과 절 자리에 두는 소통 도식 (P4) | 서지·초록 · Q1 정보시스템 |
| LIT-44 | Heo, Son & Park (2025). *Expert Systems with Applications* 272, 126712. DOI 10.1016/j.eswa.2025.126712 | LLM 응답의 환각을 설명 가능·검증 가능하게 자동 탐지(제목·서지 수준) (P4) | 서지, 초록 미확인; 공개본과 출판본의 버전 차이 대조 필요 · Q1 인공지능 |
| LIT-45 | Huang, Yu, Ma, Zhong, Feng, Wang, Chen, Peng, Feng, Qin & Liu (2025). *ACM TOIS* 43(2), 1–55. DOI 10.1145/3703155 | LLM 환각의 분류, 탐지·완화 방법, 검색 증강 모형의 한계 (P4) | 서지·초록 · Q1 정보시스템 |
| LIT-46 | Ji, Lee, Frieske, Yu, Su, Xu, Ishii, Bang, Madotto & Fung (2023). *ACM Computing Surveys* 55(12), 1–38. DOI 10.1145/3571730 | 자연어 생성의 환각 측정·완화 연구 개관 (P4) | 서지·초록 · Q1 컴퓨터과학 일반 |
| LIT-47 | Koning, Hasan & Chatterji (2022). *Management Science* 68(9), 6434–6453. DOI 10.1287/mnsc.2021.4209 | A/B 테스트 도입 스타트업의 성과가 1년 뒤 30%–100% 개선; 부정적 신호에 더 빨리 접음 (P4) | 서지·초록 · Q1 경영과학 |
| LIT-48 | Leatherbee & Katila (2020). *Strategic Entrepreneurship Journal* 14(4), 570–593. DOI 10.1002/sej.1373 | 린 스타트업 팀 152개에서 가설 수립·탐색적 시험·아이디어 수렴의 구성요소가 예상대로 연결 (P4) | 서지·초록 · Q1 경영·전략 |
| LIT-49 | Lu, Ba, Huang & Feng (2013). *Information Systems Research* 24(3), 596–612. DOI 10.1287/isre.1120.0454 | 쿠폰은 리뷰 규모와 대체, 키워드 광고는 보완 관계 (P4) | 서지·초록 · Q1 정보시스템·경영정보 |
| LIT-50 | Reisenbichler, Reutterer, Schweidel & Dan (2022). *Marketing Science* 41(3), 441–452. DOI 10.1287/mksc.2022.1354 | 자연어 생성 검색 최적화 문구가 사람 편집을 거쳐 전문가 원고보다 높은 검색 순위; 사람 편집이 필수 (P4) | 서지·기관 공개 요약, 초록 직접 대조 미완료 · Q1 마케팅·경영 |

기존 근거 절이 이미 등재한 문헌은 다시 적지 않았다: Kipf & Welling(PLATFORM-E07), Shchur 등(PLATFORM-E08), Alsudais·Marsden & Pingry·National Academies·Sandve 등·Timmerman & Bronselaer([Page 문헌 보완의 서지 식별값](#page-condition-d)), Min 등·Gao 등([P4 문헌 서지 식별값](#posting-program-update)).

**해석 한계.** 위 문헌들의 성능 수치·방법은 PlaceOS의 기준이나 결과로 쓰지 않는다. 문헌과의 관계는 개념·범주·평가 설계의 대응이며, PlaceOS가 해당 문헌의 효과를 재현했다는 뜻이 아니다. 초록에 없는 내용(예: Huang 등의 분류 체계의 세부 범주, Wang & Strong의 차원별 정의)은 원고에서 서술하지 않았다.
