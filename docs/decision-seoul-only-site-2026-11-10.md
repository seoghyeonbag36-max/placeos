# 사이트는 서울만 보인다 — 서울 밖 데이터는 그대로 (2026-11-10 사용자 결정)

> 「PlaceOS 지역 서울을 제외한 나머지는 데이터는 가지고 있되 PlaceOS 홈페이지에는 서울쪽 데이터만 보일 수 있도록 설정」

## 1. 무엇을 바꿨나 — 화면만

| 자리 | 전 | 후 |
|---|---|---|
| 상권 목록(`lib/api.listDistricts`) | 158곳 | 서울 81곳 |
| 업종 순위(`getIndustryFit` → `scopeIndustryFit`) | 서울 · 경기 · 광주 묶음 + 전주 미순위 줄 | 서울 묶음 · 줄만(순위 숫자는 그대로 — 묶음마다 1 부터 센다) |
| 상권 외곽선(`getHubOutlines`) | 158곳 | 서울 81곳 |
| 지역 고르기 · 순위 지역 단추 · 상권 묶음 탭 | 서울 · 경기 · 광주 · 전주 | 서울(`districtMapModel.siteRankGroups`) |
| 손님 흐름(파주 → 고양 → 서울) | 홈 · R1 · 상권 소개에 링크 | 링크 없음 · 옛 주소는 「손님 흐름은 지금 쉬고 있어요」(`CorridorClosed`) |
| 광주·전주 조사 위치 | 상권 지도 광주 · 전주 탭 | 닫음 |
| 랜딩 | 「서울·경기·광주·전주 158개 상권」 | 「서울 81개 상권」 |
| 저장된 지역 선택(`startupRegion`) | 네 지역 되살림 | 보이는 지역만 — 「경기」 등은 비운다 |

보이는 범위는 **`apps/frontend/src/lib/siteScope.ts` 한 곳**이 정한다. 화면 · API 는 그 파일의 함수(`isSiteCity` ·
`isSiteRegion` · `isSiteSido` · `isSiteRankGroup` · `showsCrossRegion`)로만 묻는다.

## 2. 무엇을 안 바꿨나 — 데이터

- 백엔드 서빙 목록(`measured_pages.SERVED_CITIES` 25개 도시 · `page_hubs.ACTIVE_HUBS` 158곳)과 서버 코드는 그대로다.
  API 는 서울 밖 77곳을 계속 서빙한다(2026-11-10 로컬 · 프로덕션 모두 상권 목록 158곳).
- Gold(서울 밖 77곳 coverage.json 전부) · 업종 모델 · KPI 계산은 손대지 않았다.
- PPPP 네 구현 화면 · 레일 · 진입로는 그대로다(실화면 보존 검사 22/22).

처음에는 백엔드 `SERVED_CITIES` 를 서울로 줄이는 안(09-03 경기 일시 중단의 선례)을 시험했다. 서빙 · KPI · 업종 모델 · 테스트가
서빙 목록에 묶여 있어 「데이터는 가지고 있되」와 어긋나 되돌리고, 화면으로 오는 길목에서 거르는 쪽으로 갔다.

## 3. 경계 · 함정

- 업종 순위 줄에는 도시가 없다. 그래서 범위 밖 상권 id(상권 목록에서 뽑는다)와 순위 묶음 열쇠(`잣대/시도`) 두 단서로 거른다.
  목록을 못 읽으면 묶음 열쇠로만 거른다(순위 없는 줄은 남을 수 있다 — 그때는 화면도 목록 오류를 띄운다).
- 서울 밖 상권 주소(`#/explore?district=gj-usan`)로 들어오면 지도 탐색 화면들은 첫 서울 상권으로 떨어지고, 흐름의 상권 소개는
  「지금 서비스하는 상권이 아니에요」를 띄운다(종전 그대로의 분기). 목록이 오기 전 잠깐은 그 상권 값을 부를 수 있다.
- 랜딩 숫자 가드 `apps/backend/tests/test_landing_facts.py` 는 이제 `siteScope.SITE_CITIES` 를 읽어 **보이는 도시의** 서빙 거점 수와
  `LANDING_HUBS` 를 대조한다.

## 4. 다시 열 때

1. `lib/siteScope.ts` 의 `SITE_CITIES` · `SITE_SIDO` · `SITE_REGION_NAMES` 를 늘리고, 흐름 · 조사 위치를 열려면 `CROSS_REGION` 을 켠다.
2. `lib/landingFacts.ts` 의 `LANDING_HUBS` · `LANDING_REGION` 을 고친다(백엔드 테스트가 알려 준다).
3. 닫아 둔 화면의 테스트(손님 흐름 · 경기 순위 · 조사 위치 · 상권 지도 · 흐름 지역 선택)는 지금도 범위를 넓혀(`src/test/siteScopeWide.ts`)
   돈다 — 그대로 안전망이다. 서울만 보이는 기본 동작은 `src/siteScope.test.tsx` 가 지킨다(열면 그 파일을 고친다).
