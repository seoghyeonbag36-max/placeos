"""외부 교통 API 어댑터. 실패를 수치로 대체하지 않고 각 수단별로 반환한다.

ODsay 도시간 응답은 터미널 전후 구간이 빠지므로 총 이동시간으로 쓰지 않는다.
요청량 상한은 프로세스별 24시간 외부 호출 수이며 재시작하면 초기화된다.
경로·좌표는 저장하지 않는다. 쿼터는 실패한 외부 호출도 포함한다.
"""
from __future__ import annotations

import asyncio
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.travel import TravelRequest, TravelResponse, TravelResult

DRIVING_URL = "https://apis-navi.kakaomobility.com/v1/directions"
TRANSIT_URL = "https://api.odsay.com/v1/api/searchPubTransPathT"
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


async def _lookup(mode: str, request: TravelRequest, client: httpx.AsyncClient) -> TravelResult:
    driving = mode == "driving"
    base = {
        "mode": mode, "provider": "kakao_mobility" if driving else "odsay",
        "time_basis": "current_departure" if driving else "standard_route",
    }
    key = settings.kakao_mobility_api_key if driving else settings.odsay_api_key
    if not key.strip():
        return TravelResult(**base, status="not_configured")
    if not _reserve_call():
        return TravelResult(**base, status="quota_exceeded")
    origin, destination = request.origin, request.destination
    try:
        if driving:
            response = await client.get(DRIVING_URL, headers={"Authorization": f"KakaoAK {key}"}, params={
                "origin": f"{origin.lng},{origin.lat}",
                "destination": f"{destination.lng},{destination.lat}",
                "priority": "RECOMMEND", "summary": "true", "alternatives": "false",
            })
        else:
            response = await client.get(TRANSIT_URL, params={
                "apiKey": key, "SX": origin.lng, "SY": origin.lat,
                "EX": destination.lng, "EY": destination.lat,
                "SearchType": 0, "SearchPathType": 0, "output": "json",
            })
        response.raise_for_status()
        payload = response.json()
        if driving:
            routes = payload["routes"]
            if not routes:
                return TravelResult(**base, status="no_route")
            route = routes[0]
            if route["result_code"] != 0:
                return TravelResult(**base, status="upstream_error")
            summary = route["summary"]
            return TravelResult(**base, status="ok", duration_seconds=_number(summary["duration"]),
                                distance_meters=_number(summary["distance"]))
        if "error" in payload:
            error = payload["error"]
            if isinstance(error, list):
                error = error[0]
            code = str(error.get("code"))
            status = "no_route" if code in {"3", "4", "5", "-98", "-99"} else (
                "unsupported_route" if code == "6" else "upstream_error")
            return TravelResult(**base, status=status)
        result = payload["result"]
        if result["searchType"] != 0:
            return TravelResult(**base, status="unsupported_route")
        paths = result["path"]
        if not paths:
            return TravelResult(**base, status="no_route")
        # 제공사가 반환한 도시내 경로 중 총 소요시간 최단 경로를 선택한다.
        path = min(paths, key=lambda item: _number(item["info"]["totalTime"]))
        info = path["info"]
        # 도보(3)를 제외한 지하철(1)·버스(2) 탑승 구간에서 환승 횟수를 구한다.
        boardings = sum(1 for leg in path["subPath"] if leg["trafficType"] in (1, 2))
        if boardings < 1:
            raise ValueError("교통 탑승 구간이 없습니다.")
        values: dict[str, float | int] = {
            "duration_seconds": _number(info["totalTime"]) * 60,
            "transfers": boardings - 1,
        }
        for external, internal, scale in (
            ("totalDistance", "distance_meters", 1), ("payment", "fare_won", 1),
        ):
            if info.get(external) is not None:
                values[internal] = _number(info[external]) * scale
        # totalWalkTime은 v1.8 공식 응답 계약에 없다. 실호출에서 -1도 반환되므로
        # 도보시간은 null로 유지하고, 문서화된 totalTime의 정상 결과를 보존한다.
        return TravelResult(**base, status="ok", **values)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, AttributeError):
        # 예외 원문에는 API 키·좌표가 포함될 수 있다. 응답이나 로그에 싣지 않는다.
        return TravelResult(**base, status="upstream_error")


async def get_travel_times(request: TravelRequest) -> TravelResponse:
    queried_at = datetime.now(timezone.utc)
    async with httpx.AsyncClient(timeout=httpx.Timeout(3.0), follow_redirects=False) as client:
        # 느린 한 수단이 다른 수단의 오류/성공 계약을 바꾸지 않는다.
        results = await asyncio.gather(*(_lookup(mode, request, client) for mode in ("driving", "transit")))
    return TravelResponse(origin=request.origin, destination=request.destination,
                          queried_at=queried_at, results=results)
