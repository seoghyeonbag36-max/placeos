# 세부 업종 서비스 구현·검증 (2026-10-09)

## 사용 흐름

내 사업 설정에서 기존 12개 상위 업종을 고른 뒤 세부 업종을 선택한다.
7개 대상 업종에 30개 세부 선택지를 추가했다. 기존 저장 key는 유지하며
`industryDetailKey`와 업종 전환용 `targetIndustryDetailKey`를 선택적으로 저장한다.

Platform에는 선택한 세부 업종의 경쟁점 집계가 나온다. 상위 업종 추천 점수는
상위 업종의 참고 비교임을 별도로 알린다. Posting에서는 세부 업종·운영 조건을
입력해 월 매출, 비용, 운영 잉여, 손익분기 매출, 단순 회수기간을 계산하고 저장한다.

## 원천·집계

- 분류: `config/industry_details.py`. 실제 Gold `inds_scls` 소분류를 완전 일치로 대응한다.
  주점을 음식점 점수로 대체하지 않고, 미술학원·필라테스·스터디카페를 중복 집계하지 않는다.
- 흐름: 기존 `bronze/{거점}/{수집일}/stores_raw.json` →
  `silver/{거점}/industry_detail_stores.json` → `gold/industry_detail/competition.json`.
- 재고는 수집 반경 안의 관측 자료다. 상권 경계 전수나 현재 영업 전수라고 말하지 않는다.
  수집일·반경·원천 SHA256·ID 중복·충돌·결손·층/건물 식별자 보유 수를 남긴다.
- 동일 점포 ID의 중복만 제거한다. 같은 좌표의 다른 점포는 유지한다.
  같은 ID의 업종·위치·층 정보 충돌은 제외한다. 거점 간 중복을 합산하지 않는다.
- 전시·공연 3종의 원천 매핑은 없다. 경쟁점 수는 0이 아니라 null이다.
- 생성 명령: `python -m data.pipelines.build_industry_detail`.
  기존 Gold가 있으면 덮어쓰지 않고 실패한다.
- 새 산출물의 배포 포함 규칙은 `data/.gitignore`에 있다. 기존 출처 필드의 규칙은 유지한다.

## 손익 계산의 의미

`GET /api/v1/ai/industry-details`가 업종별 입력 단위·범위를 제공한다.
`POST /api/v1/ai/simulate-revenue`에 `industry_detail_key`, `operating_inputs`를 전달한다.

좌석, 예약, 소매, 수강료, 회원, 객실, 티켓, 대관, 작품판매 수수료 모델을 구분한다.
운영 가정은 모두 사용자가 입력한다. 필수 값 누락은 `needs_inputs`, 금액은 null이다.
음수·비유한 값·범위 위반·업종과 맞지 않는 입력은 422로 거부한다.

결과의 `provenance=user_input`은 직접 입력을 뜻하며 실측 검증을 뜻하지 않는다.
순이익 대신 **월 운영 잉여**를 표시한다. 세금·금융비용·감가상각을 제외한다.
선납금은 월 귀속분, 초기 투자비는 회수 가능한 보증금을 제외한 금액을 입력한다.
매출 예측·입점 성공 확률·시설 입점 허가를 판단하는 기능은 아니다.

세부 조건 없는 비외식/주점 요청에는 기존 외식 평균 3-Tier를 반환하지 않는다.
기존 업종 미선택·카페·음식점의 3-Tier 계약은 유지한다.

## 추천 실험

`OMP_NUM_THREADS=1`과 `PYTHONIOENCODING=utf-8`을 설정한 뒤
`python -m ml.training.industry_detail_experiment`로 실행한다.
`business_detail`은 실험 전용 라벨이고 서빙 저장 허용 목록에 넣지 않았다.

실측 기록은 `ml/reports/industry_detail_experiment.json`에 있다. 같은 분할의
거점 사전분포와 비교한 업종별 정밀도·재현율·Top-3, 입력 그래프 SHA256을 기록한다.
기존 추천 JSON·체크포인트를 교체하지 않았다. 노드 분할 실험이므로 미관측 상권과
미래 시점 검증이 남아 있고, 매출·생존 성과 검증은 수행한 것이 아니다.

## 남은 자료

- 전시·공연: KOPIS·문화시설 및 상업 전시/대관 시설을 정규화하고 공간 식별자로 연결해야 한다.
- 모든 업종: 공개 자료의 수집일을 갱신하고 영업 상태, 가격, 실제 예약·판매·회원 자료를 보완해야 한다.
- 운영 입력의 실측 보정: 사업자의 동의하에 POS·예약·회원·객실 운영 자료가 필요하다.
- 추천 공개: 업종별 부진, 공간·시간 일반화와 실제 성과 검증을 검토한 뒤 별도 결정한다.

## 회귀 검증

`data/tests/test_industry_detail.py`, `test_store_taxonomy.py`, `test_gnn_label_levels.py`,
`test_industry_detail_metrics.py`; 백엔드 `test_industry_detail.py`, `test_business_fit.py`,
`test_posting_revenue.py`, `test_posting_copilot.py`, `test_posting_marketing.py`, `test_auth.py`;
프론트 build/lint/test로 분류·중복·계산·결측·설정 저장·입력 변경 시 결과 폐기를 확인한다.
테스트의 운영 입력과 API 목 응답은 합성 자료다. 실제 모델 성능은 위 실험 기록으로만 판단한다.
