"""버스정류소 이용량 Gold(`data/gold/page_bus_stops.json`) 정적 서빙.

산출물은 `data/collectors/seoul_bus_stops.py` 가 서울열린데이터광장 두 서비스(정류소 위치 ·
일자별 승하차)를 조인해 만든다. 서빙은 외부 호출 없이 이 파일만 읽는다. 파일이 없거나 깨졌으면
**빈 목록이 아니라 None** 을 돌려준다 — 화면이 "주변에 정류장이 없다"로 읽지 않게 하려는 것이다.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[4] / "data" / "gold" / "page_bus_stops.json"
_EARTH_M = 6_371_000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_M * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def _load() -> dict[str, Any] | None:
    try:
        data = json.loads(_SRC.read_text(encoding="utf-8"))
        fields = data["fields"]
        index = {name: fields.index(name) for name in
                 ("stop_id", "name", "lat", "lng", "daily_total", "routes")}
        stops = [
            {"stop_id": str(row[index["stop_id"]]), "name": str(row[index["name"]]),
             "lat": float(row[index["lat"]]), "lng": float(row[index["lng"]]),
             "daily_total": int(row[index["daily_total"]]), "routes": int(row[index["routes"]])}
            for row in data["stops"]
        ]
        window = data.get("window") or {}
        return {"stops": stops, "window": {
            "start": str(window["start"]), "end": str(window["end"]), "days": int(window["days"])}}
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return None


def available() -> bool:
    return _load() is not None


def window() -> dict[str, str | int] | None:
    data = _load()
    return dict(data["window"]) if data else None


def busiest_within(lat: float, lng: float, radius_m: int, limit: int) -> list[dict[str, Any]] | None:
    """반경 안 정류소를 일평균 이용량 큰 순으로 `limit` 개. 데이터가 없으면 None."""
    data = _load()
    if data is None:
        return None
    dlat = radius_m / 111_000.0
    dlng = radius_m / (111_000.0 * max(math.cos(math.radians(lat)), 0.01))
    hits = []
    for stop in data["stops"]:
        if abs(stop["lat"] - lat) > dlat or abs(stop["lng"] - lng) > dlng:
            continue
        distance = haversine_m(lat, lng, stop["lat"], stop["lng"])
        if distance <= radius_m:
            hits.append({**stop, "straight_meters": distance})
    # 이용량이 같으면 가까운 쪽을 앞에 둔다.
    hits.sort(key=lambda s: (-s["daily_total"], s["straight_meters"]))
    return hits[:limit]
