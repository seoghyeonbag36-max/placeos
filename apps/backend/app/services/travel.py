"""공실 인근 교통 접근성 어댑터 — 지하철역·많이 이용하는 버스정류장까지의 도보시간, 인근 주차장.

- 지하철역·주차장: 카카오 Local 카테고리 검색(SW8·PK6). 좌표는 장소 대표점이며 출입구가 아니다.
- 버스정류장: 서울열린데이터 교통카드 승하차 Gold(`services/bus_stops`)에서 반경 안
  일평균 이용량 상위. 외부 호출 없음.
- 도보시간: TMAP 보행자 경로. 실패를 직선거리 환산으로 대체하지 않고 이유와 함께 null 로 둔다.

요청량 상한은 프로세스별 24시간 외부 호출 수이며 재시작하면 초기화된다. 좌표·경로는 저장하지
않는다. 한 번의 조회는 최대 8회(카카오 2 + TMAP 6)를 쓰고 실패 호출도 센다.
"""
from __future__ import annotations

import asyncio
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.core.config import settings
from app.schemas.travel import (
    AccessGroup, AccessPlace, AccessRequest, AccessResponse, TravelPoint, WalkTime,
)
from app.services import bus_stops

LOCAL_URL = "https://dapi.kakao.com/v2/local/search/category.json"
WALK_URL = "https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1"

SUBWAY_RADIUS_M, SUBWAY_LIMIT = 1000, 3
BUS_RADIUS_M, BUS_LIMIT = 500, 3
PARKING_RADIUS_M, PARKING_LIMIT = 500, 5

_lock = threading.Lock()
_started = 0.0
_calls = 0


def _reserve_call() -> bool:
    global _started, _calls
    with _lock:
        now = time.monotonic()
        if now - _started >= 86400:
            _started, _calls = now, 0
        if _calls >= settings.travel_daily_cap_per_instance:
            return False
        _calls += 1
        return True


def _number(value: Any) -> float:
    # bool·문자열·null은 암묵 변환하지 않는다 — 깨진 응답은 실패로 처리한다.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("교통 수치가 아닙니다.")
    if not math.isfinite(value) or value < 0:
        raise ValueError("교통 수치 범위 오류입니다.")
    return float(value)


def _coordinate(value: Any, low: float, high: float) -> float:
    # 카카오 Local 은 좌표를 문자열로 준다. 숫자로 바꿀 수 없거나 범위 밖이면 실패다.
    number = float(value)
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError("좌표 범위 오류입니다.")
    return number


def _local_key() -> str:
    # 카카오 REST 키는 한 앱의 키다. Platform 벤치마킹용(KAKAO_REST_API_KEY)을 먼저 보고,
    # 없으면 기존 길찾기용 이름(KAKAO_MOBILITY_API_KEY)을 쓴다.
    return settings.kakao_rest_api_key.strip() or settings.kakao_mobility_api_key.strip()


def _kakao_place_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if parsed.hostname != "place.map.kakao.com":
        return None
    return parsed._replace(scheme="https").geturl()


async def _kakao_category(client: httpx.AsyncClient, code: str, destination: TravelPoint,
                          radius: int, size: int) -> tuple[str, list[dict[str, Any]]]:
    """(status, documents). status 가 ok 가 아니면 documents 는 비어 있다."""
    key = _local_key()
    if not key:
        return "not_configured", []
    if not _reserve_call():
        return "quota_exceeded", []
    try:
        response = await client.get(LOCAL_URL, headers={"Authorization": f"KakaoAK {key}"}, params={
            "category_group_code": code, "x": destination.lng, "y": destination.lat,
            "radius": radius, "sort": "distance", "size": size,
        })
        response.raise_for_status()
        documents = response.json()["documents"]
        if not isinstance(documents, list):
            raise ValueError("장소 응답 형식 오류")
        return "ok", documents
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        # 예외 원문에는 API 키·좌표가 들어 있을 수 있다. 응답·로그에 싣지 않는다.
        return "upstream_error", []


async def _walk(client: httpx.AsyncClient, origin: TravelPoint, destination: TravelPoint) -> WalkTime:
    key = settings.tmap_app_key.strip()
    if not key:
        return WalkTime(status="not_configured")
    if not _reserve_call():
        return WalkTime(status="quota_exceeded")
    try:
        response = await client.post(WALK_URL, headers={"appKey": key, "Accept": "application/json"}, json={
            "startX": origin.lng, "startY": origin.lat, "endX": destination.lng, "endY": destination.lat,
            "reqCoordType": "WGS84GEO", "resCoordType": "WGS84GEO", "searchOption": "0",
            # TMAP 은 이름 필드를 필수로 받는다. 실제 이름이 아니라 자리표시이며 URL 인코딩한다.
            "startName": quote("출발"), "endName": quote("도착"),
        })
        if response.status_code == 429:
            return WalkTime(status="quota_exceeded")
        response.raise_for_status()
        features = response.json()["features"]
        if not features:
            return WalkTime(status="no_route")
        props = features[0]["properties"]
        return WalkTime(status="ok", duration_seconds=_number(props["totalTime"]),
                        distance_meters=_number(props["totalDistance"]))
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, AttributeError):
        return WalkTime(status="upstream_error")


def _group(status: str, radius: int, items: list[AccessPlace] | None = None) -> AccessGroup:
    if status == "ok" and not items:
        status = "no_results"
    return AccessGroup(status=status, radius_meters=radius, items=(items or []) if status == "ok" else [])


async def _subway(client: httpx.AsyncClient, destination: TravelPoint) -> AccessGroup:
    status, documents = await _kakao_category(client, "SW8", destination, SUBWAY_RADIUS_M, 15)
    if status != "ok":
        return _group(status, SUBWAY_RADIUS_M)
    try:
        # 같은 역이 노선마다 따로 온다("신사역 3호선" · "신사역 신분당선") — 역 이름으로 합친다.
        stations: dict[str, dict[str, Any]] = {}
        for doc in documents:
            parts = str(doc["place_name"]).split()
            if not parts:
                continue
            lat, lng = _coordinate(doc["y"], -90, 90), _coordinate(doc["x"], -180, 180)
            distance = bus_stops.haversine_m(destination.lat, destination.lng, lat, lng)
            line = " ".join(parts[1:])
            entry = stations.get(parts[0])
            if entry is None:
                stations[parts[0]] = entry = {"name": parts[0], "lat": lat, "lng": lng,
                                              "distance": distance, "lines": [],
                                              "url": _kakao_place_url(doc.get("place_url"))}
            elif distance < entry["distance"]:
                entry.update(lat=lat, lng=lng, distance=distance, url=_kakao_place_url(doc.get("place_url")))
            if line and line not in entry["lines"]:
                entry["lines"].append(line)
        nearest = sorted(stations.values(), key=lambda s: s["distance"])[:SUBWAY_LIMIT]
        points = [TravelPoint(lat=s["lat"], lng=s["lng"]) for s in nearest]
    except (ValueError, KeyError, TypeError, AttributeError):
        return _group("upstream_error", SUBWAY_RADIUS_M)
    walks = await asyncio.gather(*(_walk(client, point, destination) for point in points))
    items = [
        AccessPlace(kind="subway", name=s["name"], detail=", ".join(s["lines"]) or None, point=point,
                    straight_meters=s["distance"], walk=walk, source="kakao_local", place_url=s["url"])
        for s, point, walk in zip(nearest, points, walks)
    ]
    return _group("ok", SUBWAY_RADIUS_M, items)


async def _bus(client: httpx.AsyncClient, destination: TravelPoint) -> AccessGroup:
    stops = bus_stops.busiest_within(destination.lat, destination.lng, BUS_RADIUS_M, BUS_LIMIT)
    if stops is None:
        # 산출물이 없다 — "주변에 정류장이 없다"와 다른 상태다.
        return _group("unavailable", BUS_RADIUS_M)
    points = [TravelPoint(lat=s["lat"], lng=s["lng"]) for s in stops]
    walks = await asyncio.gather(*(_walk(client, point, destination) for point in points))
    items = [
        AccessPlace(kind="bus_stop", name=s["name"] or "이름 없는 정류장", point=point,
                    straight_meters=s["straight_meters"], walk=walk, daily_riders=s["daily_total"],
                    route_count=s["routes"], source="seoul_open_data")
        for s, point, walk in zip(stops, points, walks)
    ]
    return _group("ok", BUS_RADIUS_M, items)


async def _parking(client: httpx.AsyncClient, destination: TravelPoint) -> AccessGroup:
    status, documents = await _kakao_category(client, "PK6", destination, PARKING_RADIUS_M, PARKING_LIMIT)
    if status != "ok":
        return _group(status, PARKING_RADIUS_M)
    try:
        items = []
        for doc in documents:
            name = str(doc["place_name"]).strip()
            if not name:
                continue
            point = TravelPoint(lat=_coordinate(doc["y"], -90, 90), lng=_coordinate(doc["x"], -180, 180))
            address = str(doc.get("road_address_name") or doc.get("address_name") or "").strip()
            items.append(AccessPlace(
                kind="parking", name=name, detail=address or None, point=point,
                straight_meters=bus_stops.haversine_m(destination.lat, destination.lng, point.lat, point.lng),
                source="kakao_local", place_url=_kakao_place_url(doc.get("place_url"))))
    except (ValueError, KeyError, TypeError, AttributeError):
        return _group("upstream_error", PARKING_RADIUS_M)
    items.sort(key=lambda item: item.straight_meters)
    return _group("ok", PARKING_RADIUS_M, items[:PARKING_LIMIT])


async def get_transit_access(request: AccessRequest) -> AccessResponse:
    queried_at = datetime.now(timezone.utc)
    destination = request.destination
    async with httpx.AsyncClient(timeout=httpx.Timeout(3.0), follow_redirects=False) as client:
        # 한 종류의 지연·실패가 다른 종류의 결과를 바꾸지 않는다.
        subway, bus, parking = await asyncio.gather(
            _subway(client, destination), _bus(client, destination), _parking(client, destination))
    return AccessResponse(destination=destination, queried_at=queried_at, subway=subway,
                          bus_stops=bus, parking=parking, bus_window=bus_stops.window())
