# Page · Posting 보강 — 「지금 가능」 11개 (2026-11-12 사용자 요청)

2026-11-11 후보 보고서(서울 81상권 실측 · 23개 후보)의 「지금 가능」 11개를 넣었다. 새 데이터 · 새 서버 키 없이 된다.

## 무엇을 넣었나

| # | 트랙 | 내용 | 코드 |
|---|---|---|---|
| N1 | Posting | 인테리어 · 설비 견적 입력 → 세 가격대 모두 이 값(+ 권리금)을 투자비로 | `SimulateRequest.fitout_override` · `districts.tier_scenarios`(`unit.fitout`) · `posting._apply_fitout`(코파일럿 답) · `inputs_source.invest = user_input` |
| N3 | Posting | 계약 월세 입력(R-ONE 추정 대신) · 보증금 입력 → 상가임대차법 환산보증금 판정(서울 9억원) | `SimulateRequest.rent_override`(`inputs_source.rent = contract` · `resolved_inputs`) · `lib/founderChecks.leaseCheck` |
| N6 | Posting | 민감도 — 매출 −10/−20/−30% · 월세 +5% | `lib/founderChecks.sensitivity`(서버 식 그대로: 비용 = 월세 + 매출 × 비임차 비용률) |
| N7 | Posting | 인건비 도우미(2026 최저임금 10,320원 · 주휴 · 월 유급시간 반올림 — 주 40시간 = 209시간) | `lib/menuPlan.laborMonthly` · `MenuPlanner` |
| N9 | Posting | 위험 확인에 상권 분기 개업률 · 폐업률(서울시 상권분석 · 상권 평균 · 소수 둘째 자리) | `postingRisk` · Platform 응답 `identity.demand.open_rate/close_rate` |
| N10 | Posting | 카드 우대수수료(영세 신용 0.40% · 체크 0.15%, 2025-02-14~) · 간이과세 기준(1억 400만원 미만, 2024-07~) 안내 | `MenuPlanner` |
| N11 | Posting | 계약 전 확인 체크리스트 7항목(입력 · 판정 자동 채움, 체크는 브라우저에만) | `components/PostingDecideExtras` |
| N2 | Page | 층 용도로 본 음식점 영업 — 「음식점 용도 / 기재변경 필요 / 허가 · 신고 필요」(건축법 시행령 별표1 · §19, 휴게음식점 300㎡) | `lib/founderChecks.floorUseCheck` · `components/FloorUseBox` |
| N8 | Page | 건물 연식(사용승인일) | `/floor-vacancies` 유닛에 `use_apr`(Gold `building_floors.lots[pnu].use_apr`) |
| N5 | Page | 월세 상한(200 · 300 · 500 · 800만원) · 면적(10 · 20 · 30평) 필터 — 층별 필터와 함께 같은 빈 층에 건다 | `MapShell.rentMatch` |
| N4 | Page | 공실 이력 요약 — 거쳐 간 가게 · 닫은 곳 영업기간 중앙 · 3년 안에 닫은 곳(생존율 아님) | `lib/founderChecks.historySummary` · `BuildingViewer` |

## 경계

- 입력을 비우면 종전 계산 그대로다(투자비 계수 · 월세 R-ONE 추정 · 권리금 0 전제). 출처 칩이 어느 쪽인지 밝힌다.
- 법 · 세무 수치는 기준일과 「원문 · 관할 확인」을 함께 보인다 — 법률 · 세무 자문이 아니다. 지역 기준액은 서울만(사이트 범위 · `lib/siteScope`).
- 층 용도 · 사용승인일은 건축물대장 기재값이다. 용도 분류는 대장 문자열 키워드 근사이고, 정화조 · 주차 등 건축기준과 영업신고는 관할 구청이 정한다.
- 보증금은 회수기간에 넣지 않는다(판정에만 쓴다).
- 예시 자리의 추정 월매출이 높게 잡혀(상권 평균 매출의 면적 비례) 견적을 넣어도 회수가 짧게 나올 수 있다 — 매출 보정은 보고서의 A1(정보공개서) · D3(자리 단위 매출) 몫이다.

## 검증(2026-11-12)

프론트 build · lint 0 errors · vitest 667/667(새 테스트: `lib/founderChecks.test.ts` · `pages/PostingConsole.founder.test.tsx` · `postingRisk` · `MapShell` · `BuildingViewer`) ·
백엔드 pytest 1,009 passed · 7 skipped(새 `tests/test_posting_contract_inputs.py` 5건) · PPPP 실화면 보존 22/22 ·
로컬 실화면(경희대): 견적 6,000만원 · 계약 월세 320만원 → 기능중심 회수 1.6 → 3.4개월, 월 300만원 이하 필터 510 → 47동, 콘솔 오류 0.
