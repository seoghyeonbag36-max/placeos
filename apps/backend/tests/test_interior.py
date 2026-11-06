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


# ── 실패 경로 재현 (2026-11-06) — 공급자를 MockTransport 로 흉내 낸다. 실호출·과금 없음 ──────────
import asyncio
import logging

ENDPOINT = "/api/v1/ai/interior-preview"


def _provider(monkeypatch, respond):
    """OpenAI 를 흉내 낸다. respond(request) → httpx.Response 또는 예외."""
    monkeypatch.setattr(settings, "interior_images_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-only-key")
    original = httpx.AsyncClient
    monkeypatch.setattr(interior.httpx, "AsyncClient",
                        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    interior.log.propagate = True  # caplog 가 보게 — 운영에서는 자체 핸들러로 stderr 에 쓴다(_restore_propagate 가 되돌린다)


@pytest.fixture(autouse=True)
def _restore_propagate():
    yield
    interior.log.propagate = False


def _err(status, code=None, etype=None, param=None):
    def respond(request):
        body = {"error": {"message": "USER-TEXT-SHOULD-NOT-BE-LOGGED", "code": code, "type": etype, "param": param}}
        return httpx.Response(status, json=body, headers={"x-request-id": "req_test"})
    return respond


def test_interior_success_returns_image(client, monkeypatch):
    _provider(monkeypatch, lambda r: httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(PNG).decode()}]}))
    r = client.post(ENDPOINT, json=BODY)
    assert r.status_code == 200 and r.json()["image_data_url"].startswith("data:image/png;base64,")


@pytest.mark.parametrize("status,code,etype,param,expect,word", [
    (401, "invalid_api_key", "invalid_request_error", None, 503, "키"),          # 키 거부 — 401 로 새면 화면이 로그인 토큰을 지운다
    (403, None, "invalid_request_error", None, 403, "조직 인증"),                  # gpt-image 조직 인증 미완료
    (404, "model_not_found", None, None, 503, "모델"),
    (429, "rate_limit_exceeded", "requests", None, 429, "잠시 뒤"),
    (429, "insufficient_quota", "insufficient_quota", None, 503, "크레딧"),        # 11-02 실측 사례
    (400, "moderation_blocked", "image_generation_user_error", None, 422, "안전 정책"),
    (400, "invalid_image", "invalid_request_error", "image", 422, "첨부"),
    (400, "unknown_parameter", "invalid_request_error", "quality", 502, "거부"),
    (413, None, None, None, 413, "용량"),
    (500, None, "server_error", None, 502, "장애"),
    (503, None, "server_error", None, 503, "장애"),
])
def test_interior_provider_errors_map_to_status_and_korean_detail(client, monkeypatch, caplog, status, code, etype, param, expect, word):
    _provider(monkeypatch, _err(status, code, etype, param))
    caplog.set_level(logging.INFO, logger="placeos.interior")
    r = client.post(ENDPOINT, json=BODY)
    assert r.status_code == expect, r.json()
    assert word in r.json()["detail"]
    text = caplog.text
    assert f"upstream_status={status}" in text and "request_id=req_test" in text
    # 비밀값·사용자 입력·공급자 message 는 로그에 없다
    assert "test-only-key" not in text and "USER-TEXT" not in text and BODY["style"] not in text


def test_interior_slow_provider_times_out_before_hosting_limit(client, monkeypatch, caplog):
    """60초 넘는 공급자 — 이쪽 한도(여기선 0.2초로 줄임)에서 504 와 한국어 사유를 먼저 낸다."""
    async def slow(request):
        await asyncio.sleep(5)
        return httpx.Response(200, json={})
    _provider(monkeypatch, slow)
    monkeypatch.setattr(interior, "timeout_s", lambda: 0.2)
    caplog.set_level(logging.INFO, logger="placeos.interior")
    r = client.post(ENDPOINT, json=BODY)
    assert r.status_code == 504 and "초 안에 끝나지 않았습니다" in r.json()["detail"]
    assert "reason=provider_timeout" in caplog.text


def test_interior_timeout_is_below_hosting_60s(monkeypatch):
    assert interior.timeout_s() < 60
    monkeypatch.setattr(settings, "interior_image_timeout_s", 180)
    assert interior.timeout_s() <= interior.MAX_TIMEOUT_S < 60


def test_interior_unreachable_provider_is_502(client, monkeypatch):
    def down(request):
        raise httpx.ConnectError("boom", request=request)
    _provider(monkeypatch, down)
    r = client.post(ENDPOINT, json=BODY)
    assert r.status_code == 502 and "연결하지 못했습니다" in r.json()["detail"]


def test_interior_bad_provider_payload_is_502(client, monkeypatch):
    _provider(monkeypatch, lambda r: httpx.Response(200, json={"data": []}))
    assert client.post(ENDPOINT, json=BODY).status_code == 502


def test_interior_missing_key_is_503(client, monkeypatch):
    monkeypatch.setattr(settings, "interior_images_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "")
    r = client.post(ENDPOINT, json=BODY)
    assert r.status_code == 503 and "설정되지 않았습니다" in r.json()["detail"]


def test_interior_bad_reference_is_422_without_provider_call(client, monkeypatch):
    """전에는 첨부 형식 오류가 공급자 실패와 같은 502 로 나갔다."""
    calls = []
    _provider(monkeypatch, lambda r: calls.append(r) or httpx.Response(200, json={}))
    ref = {"kind": "photo", "mime": "image/png", "data": base64.b64encode(b"not-an-image").decode()}
    r = client.post(ENDPOINT, json={**BODY, "references": [ref]})
    assert r.status_code == 422 and "3MB" in r.json()["detail"] and calls == []


def test_interior_oversize_reference_rejected(client, monkeypatch):
    """3MB 넘는 첨부 — 스키마 한도(base64 4,000,000자)에서 422, 공급자 호출 없음."""
    calls = []
    _provider(monkeypatch, lambda r: calls.append(r) or httpx.Response(200, json={}))
    big = base64.b64encode(PNG + b"0" * 3_100_000).decode()
    r = client.post(ENDPOINT, json={**BODY, "references": [{"kind": "plan", "mime": "image/png", "data": big}]})
    assert r.status_code == 422 and calls == []


def test_interior_two_max_references_reach_provider(client, monkeypatch):
    """도면·사진 각 3MB(본문 약 8MB) — 서버는 받아 edits 로 보낸다(Hosting·Cloud Run 본문 한도는 운영에서 확인)."""
    seen = []
    def respond(request):
        seen.append(len(request.content))
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(PNG).decode()}]})
    _provider(monkeypatch, respond)
    data = base64.b64encode(PNG + b"0" * (3_000_000 - len(PNG))).decode()
    refs = [{"kind": "plan", "mime": "image/png", "data": data}, {"kind": "photo", "mime": "image/png", "data": data}]
    r = client.post(ENDPOINT, json={**BODY, "references": refs})
    assert r.status_code == 200 and seen and seen[0] > 6_000_000
