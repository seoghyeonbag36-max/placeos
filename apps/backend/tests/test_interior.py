"""외부 호출 없이 계약·실패 닫힘·편집 입력 전송을 검증한다. 실호출 증거가 아니다."""
import base64

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.security import get_current_user
from app.schemas.interior import InteriorRequest
from app.services import interior, program_site, floor_vacancy

BODY = {"district": "가로수길", "industry": "카페", "style": "따뜻함", "strategy": "가성비", "consent": True}
PNG = b"\x89PNG\r\n\x1a\n" + b"test-only"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: object()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user, None)


def test_interior_requires_authentication():
    with TestClient(app) as c:
        assert c.post("/api/v1/ai/interior-preview", json=BODY).status_code == 401


def test_interior_disabled_has_no_fake_image(client, monkeypatch):
    monkeypatch.setattr(settings, "interior_images_enabled", False)
    response = client.post("/api/v1/ai/interior-preview", json=BODY)
    assert response.status_code == 503
    assert "image_data_url" not in response.json()


@pytest.mark.parametrize("change", [{"consent": False}, {"area_py": 0}, {"strategy": "없는 전략"},
                                    {"references": [{"kind": "plan", "mime": "image/svg+xml", "data": "12345678"}]}])
def test_interior_rejects_invalid_contract(client, change):
    assert client.post("/api/v1/ai/interior-preview", json={**BODY, **change}).status_code == 422


def test_interior_edits_send_reference_bytes_and_no_secrets(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-only-key")
    requests = []

    def respond(request):
        requests.append(request)
        assert request.url.path == "/v1/images/edits"
        assert PNG in request.content
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(PNG).decode()}]})

    original = httpx.AsyncClient
    monkeypatch.setattr(interior.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    import asyncio
    req = InteriorRequest(**BODY, references=[{"kind": "plan", "mime": "image/png", "data": base64.b64encode(PNG).decode()}])
    result = asyncio.run(interior.generate(req))
    assert result["source"] == "ai_generated" and "실측 도면·시공안 아님" in result["note"]
    assert "test-only-key" not in str(result)
    assert len(requests) == 1


def test_interior_invalid_reference_rejected_before_provider():
    with pytest.raises(ValueError):
        interior.decode_reference(base64.b64encode(b"not-an-image").decode(), "image/png")


def test_program_floor_site_keeps_floor_area_and_basis(monkeypatch):
    monkeypatch.setattr(floor_vacancy, "load", lambda _: {"units": [{"id": "vfu-test", "n": "합성 테스트 층",
        "floor_label": "3F", "area": 18, "was": "", "lat": 37.5, "lng": 127.0}]})
    context = program_site.site_context("test", "vfu-test")
    assert "3F" in context and "18평" in context and "층 전체 면적" in context
    assert "건물 상업면적 ÷ 호실 수" not in context and "현장 미확인" in context
    assert program_site.site_context("test", "vfu-missing") is None
