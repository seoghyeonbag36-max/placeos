"""교통 API 계약 검증. 기본 스위트는 외부 호출 대신 HTTP 경계만 목킹한다."""
import asyncio
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import settings
from app.main import app
from app.schemas.travel import TravelRequest, TravelResult
from app.services import travel

# 테스트 전용 합성 응답. TODO: 실제 응답 검증은 test_travel_live.py에서 수행한다.
REQUEST = {"origin": {"lat": 37.55, "lng": 126.97},
           "destination": {"lat": 37.52, "lng": 127.02}}
DRIVING = {"routes": [{"result_code": 0, "summary": {"duration": 901, "distance": 8000}}]}
TRANSIT = {"result": {"searchType": 0, "path": [
    {"info": {"totalTime": 38, "payment": 1550, "totalDistance": 9200},
     "subPath": [{"trafficType": 3}, {"trafficType": 1}, {"trafficType": 3}, {"trafficType": 2}]},
    {"info": {"totalTime": 50, "payment": 1700}, "subPath": [{"trafficType": 1}]},
]}}


@pytest.fixture(autouse=True)
def isolated_travel(monkeypatch):
    monkeypatch.setattr(settings, "kakao_mobility_api_key", "test-driving-key")
    monkeypatch.setattr(settings, "odsay_api_key", "test-transit-key")
    monkeypatch.setattr(settings, "travel_daily_cap_per_instance", 1000)
    monkeypatch.setattr(travel, "_calls", 0)
    monkeypatch.setattr(travel, "_started", 0.0)
    original = httpx.AsyncClient

    def install(handler):
        monkeypatch.setattr(travel.httpx, "AsyncClient", lambda **kw: original(
            **kw, transport=httpx.MockTransport(handler)))

    # 목킹을 빠뜨리면 외부 호출하지 말고 즉시 실패한다.
    def blocked(_request):
        pytest.fail("교통 테스트가 실제 외부 API를 호출하려 했습니다.")

    install(blocked)
    return install


def respond(request):
    return httpx.Response(200, json=DRIVING if request.url.host == "apis-navi.kakaomobility.com" else TRANSIT)


def test_provider_units_coordinates_and_provenance(isolated_travel):
    calls = []

    def handler(request):
        calls.append(request)
        return respond(request)

    isolated_travel(handler)
    response = TestClient(app).post("/api/v1/travel/times", json=REQUEST)
    assert response.status_code == 200
    body = response.json()
    driving, transit = body["results"]
    assert driving["duration_seconds"] == 901
    assert transit["duration_seconds"] == 38 * 60
    assert transit["transfers"] == 1
    assert transit["fare_won"] == 1550
    assert transit["walk_seconds"] is None
    assert body["origin"] == REQUEST["origin"]
    assert body["destination"] == REQUEST["destination"]
    assert body["queried_at"].endswith("Z")
    assert all(r["source"] == "provider_estimate" for r in body["results"])
    assert driving["time_basis"] == "current_departure"
    assert transit["time_basis"] == "standard_route"
    car = next(r for r in calls if r.url.host == "apis-navi.kakaomobility.com")
    bus = next(r for r in calls if r.url.host == "api.odsay.com")
    assert car.url.params["origin"] == "126.97,37.55"
    assert car.headers["Authorization"] == "KakaoAK test-driving-key"
    assert bus.url.path.endswith("searchPubTransPathT")
    assert bus.url.params["SX"] == "126.97"
    assert bus.url.params["EY"] == "37.52"
    assert "test-driving-key" not in response.text
    assert "test-transit-key" not in response.text


def test_missing_keys_never_call_or_fabricate(monkeypatch):
    monkeypatch.setattr(settings, "kakao_mobility_api_key", "")
    monkeypatch.setattr(settings, "odsay_api_key", "")
    result = asyncio.run(travel.get_travel_times(TravelRequest(**REQUEST)))
    assert [r.status for r in result.results] == ["not_configured", "not_configured"]
    assert all(r.duration_seconds is None for r in result.results)
    assert travel._calls == 0


@pytest.mark.parametrize("failure", ["timeout", "http", "json", "missing", "negative", "null", "bool"])
def test_one_provider_failure_preserves_other_result(isolated_travel, failure):
    def handler(request):
        if request.url.host != "apis-navi.kakaomobility.com":
            return respond(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("비밀 키를 포함할 수 있는 메시지", request=request)
        if failure == "http":
            return httpx.Response(403)
        if failure == "json":
            return httpx.Response(200, text="깨진 JSON")
        data = deepcopy(DRIVING)
        summary = data["routes"][0]["summary"]
        if failure == "missing":
            del summary["duration"]
        else:
            summary["duration"] = {"negative": -1, "null": None, "bool": True}[failure]
        return httpx.Response(200, json=data)

    isolated_travel(handler)
    result = asyncio.run(travel.get_travel_times(TravelRequest(**REQUEST)))
    assert result.results[0].status == "upstream_error"
    assert result.results[0].duration_seconds is None
    assert result.results[1].status == "ok"


@pytest.mark.parametrize("payload,status", [
    ({"error": {"code": "-99"}}, "no_route"),
    ({"error": [{"code": -98}]}, "no_route"),
    ({"error": {"code": 6}}, "unsupported_route"),
    ({"error": {"code": 500}}, "upstream_error"),
    ({"result": {"searchType": 1, "path": [{"info": {"totalTime": 10}}]}}, "unsupported_route"),
    ({"result": {"searchType": 0, "path": []}}, "no_route"),
])
def test_transit_errors_and_intercity_do_not_supply_partial_times(isolated_travel, payload, status):
    isolated_travel(lambda req: httpx.Response(200, json=payload) if req.url.host == "api.odsay.com" else respond(req))
    result = asyncio.run(travel.get_travel_times(TravelRequest(**REQUEST)))
    assert result.results[1].status == status
    assert result.results[1].duration_seconds is None


def test_zero_boardings_is_invalid_not_zero_transfers(isolated_travel):
    data = deepcopy(TRANSIT)
    data["result"]["path"][0]["subPath"] = [{"trafficType": 3}]
    isolated_travel(lambda req: httpx.Response(200, json=data) if req.url.host == "api.odsay.com" else respond(req))
    result = asyncio.run(travel.get_travel_times(TravelRequest(**REQUEST)))
    assert result.results[1].status == "upstream_error"
    assert result.results[1].transfers is None


@pytest.mark.parametrize("walk_time", [-1, 10, None])
def test_undocumented_walk_time_does_not_discard_valid_transit_route(isolated_travel, walk_time):
    data = deepcopy(TRANSIT)
    data["result"]["path"][0]["info"]["totalWalkTime"] = walk_time
    isolated_travel(lambda req: httpx.Response(200, json=data) if req.url.host == "api.odsay.com" else respond(req))
    result = asyncio.run(travel.get_travel_times(TravelRequest(**REQUEST)))
    assert result.results[1].status == "ok"
    assert result.results[1].duration_seconds == 38 * 60
    assert result.results[1].walk_seconds is None


@pytest.mark.parametrize("point", [{"lat": 91, "lng": 127}, {"lat": 37, "lng": -181},
                                  {"lat": 37}, {"lat": True, "lng": 127}])
def test_invalid_coordinates_rejected_before_lookup(point):
    response = TestClient(app).post("/api/v1/travel/times", json={**REQUEST, "origin": point})
    assert response.status_code == 422
    assert travel._calls == 0


def test_daily_cap_includes_failed_calls_and_resets(isolated_travel, monkeypatch):
    monkeypatch.setattr(settings, "travel_daily_cap_per_instance", 1)
    clock = [100000.0]
    monkeypatch.setattr(travel.time, "monotonic", lambda: clock[0])
    isolated_travel(lambda req: httpx.Response(503))
    request = TravelRequest(**REQUEST)
    first = asyncio.run(travel.get_travel_times(request))
    assert sorted(r.status for r in first.results) == ["quota_exceeded", "upstream_error"]
    second = asyncio.run(travel.get_travel_times(request))
    assert all(r.status == "quota_exceeded" for r in second.results)
    clock[0] += 86400
    third = asyncio.run(travel.get_travel_times(request))
    assert any(r.status == "upstream_error" for r in third.results)


def test_failed_response_cannot_carry_a_duration():
    with pytest.raises(ValidationError):
        TravelResult(mode="driving", provider="kakao_mobility", time_basis="current_departure",
                     status="no_route", duration_seconds=0)
