"""공실 인근 교통 접근성 계약 — 외부 호출은 HTTP 경계만 목킹하고 합성 응답만 쓴다."""
import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import settings
from app.main import app
from app.schemas.travel import AccessGroup, AccessRequest, WalkTime
from app.services import bus_stops, travel

# 테스트 전용 합성 좌표·응답. TODO: 실제 응답 검증은 PLACEOS_LIVE_TRAVEL=1 인 test_travel_access_live.py.
DEST = {"lat": 37.52082, "lng": 127.02312}
REQUEST = {"destination": DEST}


def doc(name, lat, lng, **extra):
    return {"place_name": name, "y": str(lat), "x": str(lng), "distance": "0",
            "address_name": "서울 강남구 신사동 1", "road_address_name": "", **extra}


SUBWAY = {"documents": [
    doc("신사역 3호선", 37.51638, 127.02021, place_url="http://place.map.kakao.com/1"),
    doc("신사역 신분당선", 37.51650, 127.02050, place_url="http://place.map.kakao.com/2"),
    doc("압구정역 3호선", 37.52630, 127.02850),
    doc("학동역 7호선", 37.51450, 127.03190),
    doc("논현역 7호선", 37.51110, 127.02150),
]}
PARKING = {"documents": [
    doc("먼 주차장", 37.5230, 127.0260, road_address_name="서울 강남구 압구정로 10"),
    doc("가까운 공영주차장", 37.5210, 127.0233, road_address_name="서울 강남구 가로수길 3",
        place_url="http://place.map.kakao.com/9"),
    doc("   ", 37.5215, 127.0231),
]}
WALK = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"totalDistance": 640, "totalTime": 520}}]}


def write_gold(path, rows):
    fields = ["stop_id", "name", "lat", "lng", "daily_total", "daily_boardings", "daily_alightings", "routes"]
    path.write_text(json.dumps({
        "fields": fields, "window": {"start": "2026-10-04", "end": "2026-10-10", "days": 7},
        "stops": [list(r) for r in rows]}, ensure_ascii=False), encoding="utf-8")


BUS_ROWS = [
    ("1", "조용한 정류장", 37.5209, 127.0231, 150, 80, 70, 2),     # 아주 가깝지만 이용량 적음
    ("2", "큰 정류장", 37.5170, 127.0210, 4200, 2100, 2100, 9),    # ~470m
    ("3", "중간 정류장", 37.5230, 127.0260, 1800, 900, 900, 5),
    ("4", "범위 밖 큰 정류장", 37.5000, 127.0500, 90000, 1, 1, 30),
    ("5", "다음 정류장", 37.5190, 127.0250, 900, 450, 450, 3),
]


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "kakao_rest_api_key", "test-local-key")
    monkeypatch.setattr(settings, "kakao_mobility_api_key", "")
    monkeypatch.setattr(settings, "tmap_app_key", "test-tmap-key")
    monkeypatch.setattr(settings, "travel_daily_cap_per_instance", 1000)
    monkeypatch.setattr(travel, "_calls", 0)
    monkeypatch.setattr(travel, "_started", 0.0)
    gold = tmp_path / "page_bus_stops.json"
    write_gold(gold, BUS_ROWS)
    monkeypatch.setattr(bus_stops, "_SRC", gold)
    bus_stops._load.cache_clear()
    original = httpx.AsyncClient

    def install(handler):
        monkeypatch.setattr(travel.httpx, "AsyncClient", lambda **kw: original(
            **kw, transport=httpx.MockTransport(handler)))

    def blocked(_request):
        pytest.fail("교통 테스트가 실제 외부 API를 호출하려 했습니다.")

    install(blocked)
    yield install
    bus_stops._load.cache_clear()


def respond(request):
    if request.url.host == "dapi.kakao.com":
        code = request.url.params["category_group_code"]
        return httpx.Response(200, json=SUBWAY if code == "SW8" else PARKING)
    return httpx.Response(200, json=WALK)


def run(**_):
    return asyncio.run(travel.get_transit_access(AccessRequest(**REQUEST)))


def test_groups_provenance_and_provider_requests(isolated):
    calls = []

    def handler(request):
        calls.append(request)
        return respond(request)

    isolated(handler)
    response = TestClient(app).post("/api/v1/travel/access", json=REQUEST)
    assert response.status_code == 200
    body = response.json()
    assert body["destination"] == DEST and body["queried_at"].endswith("Z")

    subway = body["subway"]["items"]
    # 같은 역은 노선을 합쳐 한 줄이고, 직선거리 가까운 3개 역만 나온다(신사 ≈0.6km · 압구정 ≈0.7km ·
    # 학동 ≈1.0km · 논현 ≈1.1km 는 밀려난다).
    assert [s["name"] for s in subway] == ["신사역", "압구정역", "학동역"]
    assert [s["straight_meters"] for s in subway] == sorted(s["straight_meters"] for s in subway)
    assert subway[0]["detail"] == "3호선, 신분당선"
    # 노선을 합칠 때 좌표·링크는 공실에 더 가까운 쪽(신분당선 문서)을 따른다. http 는 https 로 올린다.
    assert subway[0]["place_url"] == "https://place.map.kakao.com/2"
    assert all(s["walk"]["duration_seconds"] == 520 and s["walk"]["distance_meters"] == 640 for s in subway)
    assert all(s["source"] == "kakao_local" for s in subway)

    bus = body["bus_stops"]["items"]
    # 반경 500m 안에서 이용량 큰 순 — 범위 밖 큰 정류장은 빠지고 가까운 한산한 정류장은 뒤로 간다.
    assert [b["name"] for b in bus] == ["큰 정류장", "중간 정류장", "다음 정류장"]
    assert bus[0]["daily_riders"] == 4200 and bus[0]["route_count"] == 9
    assert all(b["source"] == "seoul_open_data" and b["walk"]["status"] == "ok" for b in bus)
    assert body["bus_window"] == {"start": "2026-10-04", "end": "2026-10-10", "days": 7}

    parking = body["parking"]["items"]
    assert [p["name"] for p in parking] == ["가까운 공영주차장", "먼 주차장"]   # 이름 없는 항목 제외
    assert parking[0]["detail"] == "서울 강남구 가로수길 3"
    assert all(p["walk"] is None for p in parking)
    assert parking[0]["straight_meters"] < parking[1]["straight_meters"]

    local = [r for r in calls if r.url.host == "dapi.kakao.com"]
    walks = [r for r in calls if r.url.host == "apis.openapi.sk.com"]
    assert sorted(r.url.params["category_group_code"] for r in local) == ["PK6", "SW8"]
    assert all(r.headers["Authorization"] == "KakaoAK test-local-key" for r in local)
    assert all(r.url.params["x"] == "127.02312" and r.url.params["y"] == "37.52082" for r in local)
    assert len(walks) == 6          # 지하철 3 + 버스 3. 주차장은 도보시간을 묻지 않는다.
    sent = json.loads(walks[0].content)
    assert walks[0].headers["appKey"] == "test-tmap-key"
    assert sent["endX"] == DEST["lng"] and sent["endY"] == DEST["lat"]
    assert sent["reqCoordType"] == "WGS84GEO"
    assert "test-local-key" not in response.text and "test-tmap-key" not in response.text


def test_without_tmap_key_keeps_places_and_never_fabricates_time(isolated, monkeypatch):
    monkeypatch.setattr(settings, "tmap_app_key", "")
    seen = []
    isolated(lambda r: (seen.append(r), respond(r))[1])
    result = run()
    assert all(r.url.host == "dapi.kakao.com" for r in seen)       # TMAP 을 부르지 않는다
    for item in result.subway.items + result.bus_stops.items:
        assert item.walk.status == "not_configured"
        assert item.walk.duration_seconds is None and item.walk.distance_meters is None
        assert item.straight_meters > 0                            # 직선거리는 좌표 계산값이라 남는다
    assert len(result.parking.items) == 2


def test_missing_local_key_only_drops_kakao_groups(isolated, monkeypatch):
    monkeypatch.setattr(settings, "kakao_rest_api_key", "")
    isolated(respond)
    result = run()
    assert result.subway.status == "not_configured" and result.parking.status == "not_configured"
    assert result.subway.items == [] and result.parking.items == []
    assert result.bus_stops.status == "ok" and len(result.bus_stops.items) == 3


def test_legacy_kakao_key_name_is_used_when_rest_key_empty(isolated, monkeypatch):
    monkeypatch.setattr(settings, "kakao_rest_api_key", "")
    monkeypatch.setattr(settings, "kakao_mobility_api_key", "legacy-key")
    headers = []
    isolated(lambda r: (headers.append(r.headers.get("Authorization")), respond(r))[1])
    run()
    assert "KakaoAK legacy-key" in headers


def test_missing_bus_gold_is_unavailable_not_empty(isolated, monkeypatch, tmp_path):
    monkeypatch.setattr(bus_stops, "_SRC", tmp_path / "없는파일.json")
    bus_stops._load.cache_clear()
    isolated(respond)
    result = run()
    assert result.bus_stops.status == "unavailable" and result.bus_stops.items == []
    assert result.bus_window is None
    assert result.subway.status == "ok" and result.parking.status == "ok"


def test_no_busy_stop_in_radius_is_no_results(isolated, monkeypatch, tmp_path):
    far = tmp_path / "far.json"
    write_gold(far, [("9", "먼 정류장", 37.45, 127.10, 5000, 1, 1, 3)])
    monkeypatch.setattr(bus_stops, "_SRC", far)
    bus_stops._load.cache_clear()
    isolated(respond)
    assert run().bus_stops.status == "no_results"


@pytest.mark.parametrize("failure", ["timeout", "http", "json", "missing", "negative", "null", "bool"])
def test_one_walk_failure_preserves_other_results(isolated, failure):
    first = {"count": 0}

    def handler(request):
        if request.url.host != "apis.openapi.sk.com":
            return respond(request)
        first["count"] += 1
        if first["count"] != 1:
            return httpx.Response(200, json=WALK)
        if failure == "timeout":
            raise httpx.ReadTimeout("비밀 키를 포함할 수 있는 메시지", request=request)
        if failure == "http":
            return httpx.Response(500)
        if failure == "json":
            return httpx.Response(200, text="깨진 JSON")
        data = deepcopy(WALK)
        props = data["features"][0]["properties"]
        if failure == "missing":
            del props["totalTime"]
        else:
            props["totalTime"] = {"negative": -1, "null": None, "bool": True}[failure]
        return httpx.Response(200, json=data)

    isolated(handler)
    result = run()
    walks = [i.walk for i in result.subway.items + result.bus_stops.items]
    assert sorted(w.status for w in walks) == ["ok"] * 5 + ["upstream_error"]
    failed = next(w for w in walks if w.status != "ok")
    assert failed.duration_seconds is None and failed.distance_meters is None
    assert len(result.parking.items) == 2


def test_walk_quota_and_no_route_statuses(isolated):
    def handler(request):
        if request.url.host == "dapi.kakao.com":
            return respond(request)
        return httpx.Response(429)

    isolated(handler)
    assert {i.walk.status for i in run().subway.items} == {"quota_exceeded"}
    isolated(lambda r: respond(r) if r.url.host == "dapi.kakao.com" else httpx.Response(200, json={"features": []}))
    assert {i.walk.status for i in run().subway.items} == {"no_route"}


@pytest.mark.parametrize("failure", ["http", "json", "documents", "bad_coordinate"])
def test_kakao_failure_hides_only_that_group(isolated, failure):
    def handler(request):
        if request.url.host != "dapi.kakao.com" or request.url.params["category_group_code"] != "PK6":
            return respond(request)
        if failure == "http":
            return httpx.Response(403)
        if failure == "json":
            return httpx.Response(200, text="깨진 JSON")
        if failure == "documents":
            return httpx.Response(200, json={"documents": {}})
        return httpx.Response(200, json={"documents": [doc("주차장", "nan", 127.0)]})

    isolated(handler)
    result = run()
    assert result.parking.status == "upstream_error" and result.parking.items == []
    assert result.subway.status == "ok" and result.bus_stops.status == "ok"


def test_daily_cap_counts_every_external_call_and_resets(isolated, monkeypatch):
    monkeypatch.setattr(settings, "travel_daily_cap_per_instance", 3)
    clock = [100000.0]
    monkeypatch.setattr(travel.time, "monotonic", lambda: clock[0])
    calls = []
    isolated(lambda r: (calls.append(r), respond(r))[1])
    first = run()
    assert len(calls) == 3                       # 상한을 넘어 외부로 나가지 않는다
    statuses = [first.subway.status, first.parking.status]
    statuses += [i.walk.status for i in first.subway.items + first.bus_stops.items]
    assert "quota_exceeded" in statuses
    assert all(i.walk.duration_seconds is None for i in first.bus_stops.items
               if i.walk.status == "quota_exceeded")
    clock[0] += 86400
    calls.clear()
    run()
    assert len(calls) == 3                       # 24시간 뒤 다시 센다


@pytest.mark.parametrize("point", [{"lat": 91, "lng": 127}, {"lat": 37, "lng": -181},
                                  {"lat": 37}, {"lat": True, "lng": 127}])
def test_invalid_destination_rejected_before_lookup(point):
    response = TestClient(app).post("/api/v1/travel/access", json={"destination": point})
    assert response.status_code == 422
    assert travel._calls == 0


def test_previous_origin_based_endpoints_are_gone():
    client = TestClient(app)
    assert client.post("/api/v1/travel/times", json={}).status_code in (404, 405)
    assert client.post("/api/v1/travel/addresses", json={}).status_code in (404, 405)


def test_response_models_reject_numbers_on_failed_states():
    with pytest.raises(ValidationError):
        WalkTime(status="no_route", duration_seconds=0)
    with pytest.raises(ValidationError):
        WalkTime(status="ok")
    with pytest.raises(ValidationError):
        AccessGroup(status="upstream_error", radius_meters=500, items=[{
            "kind": "parking", "name": "x", "point": DEST, "straight_meters": 1, "source": "kakao_local"}])


def test_bus_stops_corrupt_file_returns_none_not_empty(monkeypatch, tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{ 깨짐", encoding="utf-8")
    monkeypatch.setattr(bus_stops, "_SRC", broken)
    bus_stops._load.cache_clear()
    assert bus_stops.busiest_within(37.5, 127.0, 500, 3) is None
    assert bus_stops.available() is False
    bus_stops._load.cache_clear()
