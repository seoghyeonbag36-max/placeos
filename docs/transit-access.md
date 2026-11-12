# 공실 인근 교통 접근성 (지하철·버스·주차장)

Platform의 상권 중심, Page의 실측 건물 상세, Posting의 선택 매물에서 「주변 지하철·버스·주차장」을
펼친다. 이 기능(`/travel/access`)은 출발지를 받지 않는다 — 공실 좌표만 서버로 간다.
「출발지 → 공실 차량·대중교통 소요시간」은 2026-10-14 에 이 기능으로 교체했다가 **2026-11-02 에 나란히 되살렸다**
(`/travel/times` · `/travel/addresses`, 메모 1-4). 둘은 대신하지 않고 공존한다 → [travel-times.md](travel-times.md).

| 칸 | 내용 | 원천 |
|---|---|---|
| 지하철역에서 걸어서 | 반경 1km 안 가까운 3개 역, 역→공실 **도보시간·걷는 거리** | 카카오 Local `SW8` + 보행 경로(TMAP 키가 있으면 TMAP, 없으면 OSM — 아래 §도보시간 공급자) |
| 많이 이용하는 버스정류장에서 걸어서 | 반경 500m 안 **일평균 승하차 상위 3개** 정류소, 도보시간 | 서울열린데이터 교통카드 승하차 Gold + 보행 경로(위와 같음) |
| 인근 주차장 | 반경 500m 안 가까운 5곳 이름·주소·직선거리·카카오맵 링크 | 카카오 Local `PK6` |

## API

`POST /api/v1/travel/access` — body `{destination:{lat,lng}}`(WGS84, 범위 밖·누락은 422).
응답은 `subway`·`bus_stops`·`parking` 세 그룹과 `bus_window`(버스 이용량 산출 기간)다.
한 그룹이 실패해도 다른 그룹을 숨기지 않는다. 그룹 `status`:
`ok · no_results · not_configured · upstream_error · quota_exceeded · unavailable`
(`unavailable` = 버스 Gold 파일이 서버에 없다. "주변에 없다"와 다른 상태다.)
항목의 `walk.status` 가 `ok` 가 아니면 시간·거리는 모두 null 이다 — **직선거리 ÷ 보행속도로
시간을 채우지 않는다.** 직선거리(`straight_meters`)는 좌표에서 계산한 값이라 항상 있다.

## 데이터와 한계

- **버스 이용량** `data/gold/page_bus_stops.json` — `python -m data.collectors.seoul_bus_stops`
  (SEOUL_OPENAPI_KEY). 정류소 위치 `busStopLocationXyInfo` 와 일자별 승하차
  `CardBusStatisticsServiceNew` 를 정류소 ID 로 조인, 최근 7일 승차+하차 일평균(모든 노선 합).
  **정류소 이용량이지 점포 방문자 수가 아니다.** 서울 정류소만 있다(경기권 정류소 ID 는 위치
  데이터에 없어 빠진다 — 일 이용량의 약 4.8%). 갱신은 수동이며 낡으면 `bus_window` 가 그 사실을 보여 준다.
- **역·정류소 좌표**는 대표점이다. 출입구·출구까지의 거리는 도보시간에 들어 있지 않다.
- **도보시간**은 제공사 예상값이다(TMAP 또는 OSRM 도보 프로필 · 약 4.5km/h). 신호·경사·혼잡은 반영되지 않는다.
- **주차장**은 위치만 안내한다. 빈자리·요금·운영시간은 제공하지 않는다.
- 외부 호출 상한은 프로세스별 24시간(`TRAVEL_DAILY_CAP_PER_INSTANCE`, 기본 1000). 한 번의 조회는
  카카오 2회 + TMAP 최대 6회 = **최대 8회**(OSM 이면 카카오 2회 + OSRM 1회)이고 실패 호출도 센다. 지도 초기 로딩에서는 부르지 않고,
  패널을 **펼칠 때만** 한 번 조회한다. 좌표·경로는 디스크에 저장하지 않는다(OSM 도보시간만 24시간 메모리 캐시 — 아래).
- **Posting 「찾아오는 길」(2026-11-10 사용자 요청)** — 공실까지 역 · 정류장에서 걸어서 몇 분인지 보인다(`showWalking`).
  그 쪽을 연 것이 곧 조회 요청이라 패널을 펼친 채 바로 한 번 조회하고(`openOnMount`), 맨 위에 「지하철역에서 · 버스정류장에서
  걸어서 약 N분」(TMAP 보행 시간이 가장 짧은 곳) 한 줄을 단다(`walkSummary`). 도보시간이 없으면 「도보시간 없음」과 직선거리 ·
  사유만 쓴다 — 시간으로 바꾸지 않는다. Platform(상권 중심)은 여전히 도보시간을 보이지 않는다.
- ⚠ **2026-11-10 프로덕션 실측: `TMAP_APP_KEY` 가 비어 있다** — 그래서 같은 날 OSM 보행 경로(FOSSGIS OSRM)를 기본 공급자로 더했다(§도보시간 공급자).

## 도보시간 공급자 (2026-11-10 사용자 선택)

TMAP 키(`TMAP_APP_KEY`)가 있으면 TMAP 보행자 경로(곳마다 1회), **없으면 OpenStreetMap 보행 경로**
— FOSSGIS 가 운영하는 OSRM 도보 서버(`routing.openstreetmap.de/routed-foot`, 키 · 가입 없음) — 를 쓴다. 둘 다 없으면 「준비 중」.
무료 대안 가운데 OpenRouteService · GraphHopper 무료판은 비상업 전용이라, Google 은 한국 도보 길찾기를 제공하지 않아서,
카카오 · 네이버는 도보 경로 공개 API 가 없어서 뺐다.

**FOSSGIS 이용 조건**(fossgis.de/arbeitsgruppen/osm-server/nutzungsbedingungen — 2026-11-10 원문 확인)과 지키는 방법:

| 조건 | 이 코드 |
|---|---|
| 라우팅 서버 **초당 1회 이하** | 한 조회의 역 · 정류장(최대 6곳)을 OSRM `table` **한 번**으로 묻는다. 프로세스 안에서 요청 간격 1초(`_OSRM_MIN_INTERVAL_S`), 5초 넘게 줄 서야 하면 묻지 않고 「조회 한도」 |
| 앱을 밝히는 User-Agent(라이브러리 기본값 안 됨) · Referer | `PlaceOS/1.0 (+https://placeos.co.kr)` · `https://placeos.co.kr/` |
| OSM 출처 + 「지도 오류 신고」(openstreetmap.org/fixthemap) 링크 표시 | `TransitAccessPanel` 이 도보시간 출처가 `osrm_foot` 이면 단다 |
| 운영자 이메일이 사이트에서 쉽게 보일 것 | 랜딩 바닥글 「문의」(mailto) |
| 서비스 주소를 박아 두지 말 것(권고) | `WALK_ROUTING_URL` 설정값 |
| 상업적 이용은 그 서비스가 **온라인 서비스의 본질적 부분이 아닐 때만**(예: 웹사이트의 찾아오는 길 약도) · **고트래픽 사이트 금지** · 예고 없이 중단 가능 | 도보시간은 Posting · Page 한 칸의 보조 정보다. 트래픽이 늘면 TMAP 키를 넣거나 OSRM 을 직접 띄운다(같은 API) |

같은 출발(역 · 정류장) → 공실 좌표는 **24시간 메모리 캐시**(최대 4,096쌍)로 다시 묻지 않는다 — 사용자 위치가 아니라 공공 장소와
공실 좌표다. 실패는 캐시하지 않는다. 2026-11-10 실측(샌드박스 → FOSSGIS): 회기로10길 → 경성빌딩 앞 **482초 · 602m**, 두 곳을
`table` 한 번에 받았다.

## 서버 설정

```dotenv
KAKAO_REST_API_KEY=      # 비면 KAKAO_MOBILITY_API_KEY 를 쓴다(같은 앱의 REST 키)
TMAP_APP_KEY=            # SK Open API(openapi.sk.com) 보행자 경로. 비우면 아래 OSM 보행 경로를 쓴다
WALK_ROUTING_URL=https://routing.openstreetmap.de/routed-foot   # 비우면 도보시간을 묻지 않는다("준비 중")
TRAVEL_DAILY_CAP_PER_INSTANCE=1000
```

Cloud Run 에는 `--update-env-vars TMAP_APP_KEY=…` 로 **부분 갱신**한다(`--set-env-vars` 는 기존 값을 지운다).
키는 PR·로그·명령 출력에 싣지 않는다. TMAP 은 IP 허용 목록이 아니라 앱키 방식이다.

> ⚠ **미검증:** TMAP 보행자 경로의 실응답은 이 작업 시점에 키가 없어 확인하지 못했다. 어댑터는
> 공식 계약(`POST /tmap/routes/pedestrian`, 헤더 `appKey`, 응답 `features[0].properties.totalTime/
> totalDistance`)에 맞췄고 합성 응답으로만 테스트했다. 키를 넣은 뒤 운영 사이트에서 도보시간이
> 실제로 나오는지 먼저 확인할 것. 실패하면 화면에 「도보시간을 조회하지 못함」이 뜨고 위치·직선거리는 그대로다.

> ODsay 연동과 `/travel/times`·`/travel/addresses` 는 제거했다. ODsay 허용 IP 때문에 만든
> Cloud Run 고정 송신 IP·Cloud NAT(`placeos-egress-*`, docs 이전판 참조)는 이제 이 기능에 필요 없다.
> 다른 외부 연동이 의존하지 않으면 **고정 IP·NAT 비용이 계속 나가므로** 정리 여부를 판단할 것.

## 통과 조건

```powershell
cd apps/backend ; python -m pytest tests/test_travel_access.py -q
cd apps/frontend ; npm run test -- src/components/TransitAccessPanel.test.tsx ; npm run build
```
