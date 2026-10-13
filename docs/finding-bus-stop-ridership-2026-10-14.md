# 버스정류소 이용량 원천 실측 (2026-10-14)

「많이 이용하는 버스정류장」을 가르려면 정류소별 이용량이 필요한데 저장소에는 없었다(승하차·정류소 0건).
서울열린데이터광장 두 서비스를 1콜씩 재서 확인했다.

| 서비스 | 결과 |
|---|---|
| `busStopLocationXyInfo/1/3/` | 200 · 전량 **11,236** · 필드 STOPS_NO·STOPS_NM·XCRD·YCRD |
| `CardBusStatisticsServiceNew/1/3/202509` | **INFO-200 데이터 없음** — 월 단위 인자는 안 된다 |
| `CardBusStatisticsServiceNew/1/3/20250901` | 200 · **41,305행/일** · USE_YMD·RTE_ID·STOPS_ID·GTON_TNOPE·GTOFF_TNOPE |
| `CardBusStatisticsService`(구) | ERROR-500 — 서비스 종료 |

수집(2026-10-04~10, 7일): 승하차 정류소 12,515 · 위치 조인 **10,651** · 위치 없음 1,864.
수요일 1일 대조(20261007)에서 위치 없는 정류소가 **일 이용량의 4.8%**, ID 접두 2xx(경기권 인덕원·성남·석수 등)가
대부분이고 서울은 `홍대입구역(가상)` 같은 가상 정류소뿐 — 서울 커버리지는 충분하다.
이용량 중앙값 362/일 · 상위 10% 1,952/일 · 최대 18,624/일(고속터미널).

카카오 Local 카테고리 검색(SW8·PK6)은 `KAKAO_REST_API_KEY`·`KAKAO_MOBILITY_API_KEY` 모두 200
(가로수길 u1 기준 지하철역 3곳·주차장 207곳 중 5건).
응답 인코딩은 CP949 가 섞여 있어 수집기가 UTF-8 → CP949 순으로 디코딩한다.

## 프로브 명령
```bash
http://openapi.seoul.go.kr:8088/<KEY>/json/busStopLocationXyInfo/1/3/
http://openapi.seoul.go.kr:8088/<KEY>/json/CardBusStatisticsServiceNew/1/3/20250901
https://dapi.kakao.com/v2/local/search/category.json?category_group_code=SW8&x=127.02312&y=37.52082&radius=1000&sort=distance
python -m data.collectors.seoul_bus_stops --days 7
```
