# 광주·전주 조사 위치 레이어 (2026-11-09)

## 1. 결정

2026-11-09 사용자가 「광주·전주 전유부 수집이 끝났으면 Gold 작업을 진행해서 수집한 상권이 나오게」를 지시했다.
선택지 셋(조사 위치 레이어 · 레이어 + 상위 몇 곳 정식 거점 · 206곳 전부 정식 거점) 중 사용자가 **조사 위치 레이어**를 골랐다.

광주·전주 탐색 위치 206곳(광주 121 · 전주 82 · 전주권 3)을 Platform 「상권 지도」의 광주·전주 묶음 아래에
**조사 위치**로 보여 준다. 서빙 거점 목록(`page_hubs.ACTIVE_HUBS`)·공실 산출물·순위 묶음은 바꾸지 않는다.

## 2. 왜 거점이 아니라 레이어인가

- 이 206곳은 정식 상권이 아니다. 일반음식점 인허가 주소에서 찾은 700m 조사 원이고 서로 겹친다
  (docs/regional-hub-candidates-2026-11-03.md §신규 탐색 조사).
- 대장 Gold(`data/pipelines/build_regional_ledger_gold.py`)는 **상가정보 점포가 확인된 지번만** 받았다. 빈 건물이 없으니
  공실률의 분모가 없다. 그래서 그 파이프라인이 스스로 `serving_eligible: false` ·
  `page_gold_status: requires_boundary_polygon_anchor_validation` 을 단다.
- R-ONE 표본은 이미 공개된 광주 13 · 전주 5 거점에만 있어 앵커 대조 기준이 없다.

## 3. 무엇을 보여 주고 무엇을 안 보여 주나

| 보여 준다(관측) | 안 보여 준다 |
|---|---|
| 700m 점포 수 · 건물 수(상가정보 실호출) | 공실률 · 빈 층 |
| 점포가 있는 지번 수 · 그중 상업층이 확인된 지번(층별개요) | 순위 · 업종 적합도 |
| 상업용 전유 호수(전유부 — 집합건물 호실 수이지 빈 호실 수가 아님) | 임대료 · 본전 시점 |
| 많은 업종 상위 5 · 가장 가까운 등록 거점 | 상권 경계(원을 경계로 주장하지 않는다) |

화면에서는 거점과 갈리게 그린다 — 중립색 · 속이 빈 점 · 고르면 점선 칩, 「정식 상권 아님」 배지. 거점 목록·색칠에는 섞지 않는다.
「가까운 거점」을 누르면 그 거점을 고를 뿐 조사 위치를 거점으로 바꾸지 않는다.

## 4. 경로

- 빌더: `python -m data.pipelines.build_research_locations --root <원천이 있는 체크아웃>` — 대장 Gold 보고서가
  `checked` 이고 위치마다 `ledger_gold_complete` 이며 산출물 sha256 이 맞을 때만 만든다. 네트워크 호출 없음.
- 산출물: `data/gold/platform_research_locations.json`(추적 · `.gitignore` 예외). 입력 해시는 파일의 `inputs` 에 남는다.
  원천 대장 Gold(`data/gold/regional_research_ledgers/`)와 그 보고서의 커밋은 자동 공개 작업(`run_regional_research_release.py`) 몫이다.
- API: `GET /api/v1/commercial-districts/research-locations?group=gwangju|jeonju` (`services/research_locations`)
- 화면: `components/ResearchLocationsLayer.tsx` — `DistrictMapExplorer` 가 광주·전주 묶음에서만 그린다.

## 5. 다음 단계(이 결정 밖)

조사 위치를 정식 거점으로 올리려면 hub-chain 을 탄다: 겹침 정리 → 범위 확정 → V-World 건물 폴리곤 → 빈 건물 대장 추가 수집
→ Page Gold → 앵커 규칙(R-ONE 표본 없음 — 사용자 결정 필요). 그때도 이 레이어는 지우지 않고, 승격한 위치만 빠지게 한다.

## 통과 조건

`apps/backend/tests/test_research_locations.py` · `apps/frontend/src/components/ResearchLocationsLayer.test.tsx` ·
`DistrictMapExplorer.test.tsx` · `ppppScreens.test.tsx` · 프론트 빌드·린트 · 실화면(Platform → 광주 묶음).
