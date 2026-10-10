"""합성 제공사 응답으로 검색 계약을 검증한다. 실제 호출은 별도 확인한다."""
import asyncio
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services import benchmark as svc

CELL = dict(lat=37.5, lng=127., dlat=.001, dlng=.001)


def row(ident: str = "123", **over: str) -> dict:
    return dict(id=ident, place_name="테스트 카페", category_name="음식점 > 카페",
                x="127.0005", y="37.5005", phone="", address_name="테스트 주소", **over)


def test_scope_category_coordinates_and_duplicate_id():
    outside = row("2") | {"x": "127.002"}
    wrong = row("3") | {"category_name": "생활 > 미용실"}
    invalid = row("4") | {"y": "NaN"}
    gap = row("5") | {"x": "127.0015"}
    cells = [CELL, CELL | {"lng": 127.002}]
    result = svc.normalize([row(), row(), outside, wrong, invalid, gap], cells, [37.5, 127.], ("카페",))
    assert [p["id"] for p in result] == ["123", "2"]
    assert result[0]["phone"] is None
    assert result[0]["place_url"] == "https://place.map.kakao.com/123"


def test_izakaya_uses_verified_provider_category():
    japanese = row() | {"category_name": "음식점 > 술집 > 일본식주점"}
    assert svc.normalize([japanese], [CELL], [37.5, 127.], svc.MAPPINGS["izakaya"][2])


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(svc.settings, "kakao_rest_api_key", "test-only")
    monkeypatch.setattr(svc.districts, "PAGES_BY_ID", {"test": {"grid": {}, "center": [37.5, 127.]}})
    monkeypatch.setattr(svc.gold_vacancy, "build_cells", lambda *_: {"cells": [CELL]})


def transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(svc.httpx, "AsyncClient", lambda **kwargs: original(
        transport=httpx.MockTransport(handler), **kwargs))


def test_route_pagination_provenance_and_bounded_search(configured, monkeypatch):
    calls = []
    def reply(request):
        calls.append(request)
        return httpx.Response(200, json={"documents": [row()],
            "meta": {"is_end": False, "total_count": 100, "pageable_count": 45}})
    transport(monkeypatch, reply)
    response = TestClient(app).get("/api/v1/benchmark/places?district_id=test&industry_key=cafe")
    assert response.status_code == 200
    body = response.json()
    assert len(calls) == 3
    assert len(body["places"]) == 1
    assert body["truncated"] is True
    assert body["source"] == "kakao_local"
    assert body["scope"] == "measured_cells"
    assert "test-only" not in response.text
    assert "영업" in body["note"]


@pytest.mark.parametrize("status,expected", [(429, 429), (401, 503), (403, 503), (500, 502)])
def test_provider_errors_are_not_empty_success(configured, monkeypatch, status, expected):
    transport(monkeypatch, lambda _: httpx.Response(status))
    with pytest.raises(svc.SearchError) as exc:
        asyncio.run(svc.search("test", "cafe"))
    assert exc.value.status == expected


def test_missing_key_scope_and_unsupported_industry_fail(configured, monkeypatch):
    monkeypatch.setattr(svc.settings, "kakao_rest_api_key", "")
    with pytest.raises(svc.SearchError, match="키"):
        asyncio.run(svc.search("test", "cafe"))
    with pytest.raises(svc.SearchError, match="미지원"):
        asyncio.run(svc.search("test", "unknown"))
    monkeypatch.setattr(svc.settings, "kakao_rest_api_key", "test-only")
    monkeypatch.setattr(svc.gold_vacancy, "build_cells", lambda *_: None)
    with pytest.raises(svc.SearchError, match="측정 범위"):
        asyncio.run(svc.search("test", "cafe"))


def test_empty_result_is_valid_when_provider_search_succeeds(configured, monkeypatch):
    transport(monkeypatch, lambda _: httpx.Response(200, json={"documents": [],
        "meta": {"is_end": True, "total_count": 0, "pageable_count": 0}}))
    assert asyncio.run(svc.search("test", "cafe"))["places"] == []
