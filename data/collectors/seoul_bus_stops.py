"""[Page] 서울 버스정류소 이용량 수집기 — 공실 인근 「많이 이용하는 버스정류장」의 원천.

두 서울열린데이터광장 서비스를 정류소 ID 로 조인해 정류소별 일평균 승하차 인원을 만든다.

- `busStopLocationXyInfo` — 정류소 위치(WGS84 XCRD/YCRD). 전량 약 1.1만 건.
- `CardBusStatisticsServiceNew` — **일자·노선·정류소별** 교통카드 승하차. 하루 약 4.1만 행.
  월 단위 인자(`202509`)는 `INFO-200 데이터 없음` 이다 — 일자(`20250901`)로만 응답한다(2026-10-14 실측).

일평균 = 최근 7일(요일 편향을 줄이려 주말 포함) 승차+하차 합 ÷ 7. 한 정류소를 지나는
**모든 노선**을 합친 값이다. 교통카드 기록이라 현금·무임 외 이용은 빠질 수 있고,
**정류소 단위 이용량이지 인근 점포 방문자 수가 아니다.**

산출물: `data/gold/page_bus_stops.json` — 서빙(`app/services/transit_access.py`)이 정적으로 읽는다.
Bronze: `data/bronze/seoul_bus_stops/<오늘>/` 에 위치 원본과 정류소별 합계를 둔다.

실행: python -m data.collectors.seoul_bus_stops [--days 7]
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import GOLD, load_env, save_json

LOCATION_SERVICE = "busStopLocationXyInfo"
RIDERSHIP_SERVICE = "CardBusStatisticsServiceNew"
SLUG = "seoul_bus_stops"
GOLD_NAME = "page_bus_stops.json"
_PAGE = 1000
_MAX_ROWS = 80_000
# 서울 경계 상자 — 좌표 단위 오류(경위도 뒤바뀜·0)를 걸러 내는 용도다.
_LAT = (37.40, 37.72)
_LNG = (126.70, 127.25)

FIELDS = ["stop_id", "name", "lat", "lng", "daily_total", "daily_boardings", "daily_alightings", "routes"]


def _decode(content: bytes) -> str:
    """이 API 는 일부 응답을 CP949 로 보낸다 — UTF-8 을 먼저 엄격하게 시도하고 실패하면 CP949."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp949", errors="replace")


def _get(key: str, service: str, start: int, end: int, tail: str = "") -> dict:
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/{service}/{start}/{end}/{tail}"
    last: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=40)
            resp.raise_for_status()
            return json.loads(_decode(resp.content))
        except Exception as exc:  # 네트워크·JSON 오류 — 키가 URL 에 있어 원문을 싣지 않는다
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{service} {tail or ''} 조회 실패: {type(last).__name__}")


def _pages(key: str, service: str, tail: str = "") -> list[dict]:
    rows: list[dict] = []
    start = 1
    while start <= _MAX_ROWS:
        body = _get(key, service, start, start + _PAGE - 1, tail)
        if service not in body:
            return rows   # INFO-200(데이터 없음) 등 — 호출자가 빈 결과를 판정한다
        payload = body[service]
        page = payload.get("row", [])
        rows.extend(page)
        total = int(payload.get("list_total_count", 0))
        start += _PAGE
        if not page or start > total:
            break
    return rows


def latest_available_day(key: str, today: date | None = None) -> date:
    """오늘에서 거꾸로 짚어 승하차 데이터가 있는 가장 최근 일자(등록은 사용일+3일 안팎)."""
    today = today or date.today()
    for back in range(2, 15):
        day = today - timedelta(days=back)
        body = _get(key, RIDERSHIP_SERVICE, 1, 1, day.strftime("%Y%m%d"))
        if RIDERSHIP_SERVICE in body and body[RIDERSHIP_SERVICE].get("row"):
            return day
    raise RuntimeError("최근 14일 안에 승하차 데이터가 없다")


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def collect(days: int = 7) -> dict:
    if requests is None:
        raise RuntimeError("requests 가 필요하다")
    load_env()
    key = os.environ.get("SEOUL_OPENAPI_KEY", "").strip()
    if not key:
        raise RuntimeError("SEOUL_OPENAPI_KEY 가 없다 (data/.env)")

    last_day = latest_available_day(key)
    window = [last_day - timedelta(days=i) for i in range(days - 1, -1, -1)]
    print(f"[window] {window[0]} ~ {window[-1]} ({days}일)")

    locations = _pages(key, LOCATION_SERVICE)
    print(f"[location] {len(locations)}건")

    boardings: dict[str, float] = defaultdict(float)
    alightings: dict[str, float] = defaultdict(float)
    routes: dict[str, set] = defaultdict(set)
    day_rows: dict[str, int] = {}
    for day in window:
        ymd = day.strftime("%Y%m%d")
        rows = _pages(key, RIDERSHIP_SERVICE, ymd)
        day_rows[ymd] = len(rows)
        print(f"[ridership] {ymd} {len(rows)}행")
        for row in rows:
            stop = str(row.get("STOPS_ID", "")).strip()
            if not stop:
                continue
            boardings[stop] += _num(row.get("GTON_TNOPE"))
            alightings[stop] += _num(row.get("GTOFF_TNOPE"))
            routes[stop].add(str(row.get("RTE_ID", "")))
    empty_days = [d for d, n in day_rows.items() if n == 0]
    if empty_days:
        # 빈 날을 0 으로 평균에 넣으면 일평균이 조용히 깎인다 — 실패로 멈춘다.
        raise RuntimeError(f"승하차 행이 없는 날이 있다: {empty_days}")

    stops, no_coord, out_of_box = [], 0, 0
    located = set()
    for loc in locations:
        stop = str(loc.get("STOPS_NO", "")).strip()
        if stop not in boardings:
            continue
        located.add(stop)
        lat, lng = _num(loc.get("YCRD")), _num(loc.get("XCRD"))
        if not lat or not lng:
            no_coord += 1
            continue
        if not (_LAT[0] <= lat <= _LAT[1] and _LNG[0] <= lng <= _LNG[1]):
            out_of_box += 1
            continue
        b, a = boardings[stop] / days, alightings[stop] / days
        stops.append([stop, str(loc.get("STOPS_NM", "")).strip(), round(lat, 6), round(lng, 6),
                      round(b + a), round(b), round(a), len(routes[stop])])
    stops.sort(key=lambda s: -s[4])

    unmatched = len(set(boardings) - located)
    stats = {
        "ridership_stops": len(boardings), "location_rows": len(locations),
        "joined": len(located), "ridership_without_location": unmatched,
        "dropped_no_coord": no_coord, "dropped_out_of_seoul": out_of_box,
        "kept": len(stops),
    }
    gold = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metric": "일평균 승차+하차 인원(교통카드 · 정류소를 지나는 모든 노선 합)",
        "window": {"start": window[0].isoformat(), "end": window[-1].isoformat(), "days": days},
        "source": {
            "location": f"서울열린데이터광장 {LOCATION_SERVICE}",
            "ridership": f"서울열린데이터광장 {RIDERSHIP_SERVICE}",
        },
        "stats": stats,
        "fields": FIELDS,
        "stops": stops,
    }
    GOLD.mkdir(parents=True, exist_ok=True)
    path = GOLD / GOLD_NAME
    path.write_text(json.dumps(gold, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[gold] {path.name} {path.stat().st_size / 1024:.0f}KB · {stats}")
    save_json(locations, SLUG, "location.json")
    save_json({"window": gold["window"], "day_rows": day_rows, "stats": stats}, SLUG, "ridership_meta.json")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="서울 버스정류소 이용량 Gold 빌드")
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    collect(args.days)


if __name__ == "__main__":
    main()
