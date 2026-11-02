"""주소 검색 계약: 테스트용 합성 응답만 사용하며 실주소를 만들지 않는다."""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import travel


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setattr(settings, "kakao_mobility_api_key", "test-key")
    monkeypatch.setattr(settings, "travel_daily_cap_per_instance", 1000)
    monkeypatch.setattr(travel, "_calls", 0)
    monkeypatch.setattr(travel, "_started", 0.0)
    original = httpx.AsyncClient

    def install(payload, status=200):
        def handler(request):
            assert request.url.path == "/v2/local/search/address.json"
            assert request.url.params["query"] == "서울 세종대로 110"
            assert request.headers["Authorization"] == "KakaoAK test-key"
            return httpx.Response(status, json=payload)
        monkeypatch.setattr(travel.httpx, "AsyncClient", lambda **kw: original(**kw, transport=httpx.MockTransport(handler)))
    return install


def test_address_coordinates_source_and_selection_candidates(adapter):
    adapter({"documents": [
        {"address_type": "ROAD_ADDR", "address_name": "서울 중구 세종대로 110", "x": "126.978", "y": "37.566"},
        {"address_type": "REGION", "address_name": "서울", "x": "126.978", "y": "37.566"},
    ]})
    response = TestClient(app).post("/api/v1/travel/addresses", json={"query": "서울 세종대로 110"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "candidates": [{"address": "서울 중구 세종대로 110",
        "point": {"lat": 37.566, "lng": 126.978}, "source": "kakao_local"}]}


@pytest.mark.parametrize("payload,status,expected", [
    ({"documents": []}, 200, "no_results"),
    ({"documents": [{"address_type": "ROAD_ADDR", "address_name": "주소", "x": "nan", "y": "37"}]}, 200, "upstream_error"),
    ({"documents": {}}, 200, "upstream_error"),
    ({}, 403, "upstream_error"),
])
def test_address_failure_never_fills_coordinates(adapter, payload, status, expected):
    adapter(payload, status)
    response = asyncio.run(travel.search_addresses("서울 세종대로 110"))
    assert response.status == expected
    assert response.candidates == []


def test_address_missing_key_and_quota(adapter, monkeypatch):
    monkeypatch.setattr(settings, "kakao_mobility_api_key", "")
    assert asyncio.run(travel.search_addresses("서울 세종대로 110")).status == "not_configured"
    monkeypatch.setattr(settings, "kakao_mobility_api_key", "test-key")
    monkeypatch.setattr(settings, "travel_daily_cap_per_instance", 0)
    assert asyncio.run(travel.search_addresses("서울 세종대로 110")).status == "quota_exceeded"


@pytest.mark.parametrize("query", ["", " ", "x" * 201])
def test_address_invalid_input(query):
    assert TestClient(app).post("/api/v1/travel/addresses", json={"query": query}).status_code == 422
