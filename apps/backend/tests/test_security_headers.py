"""응답 보안 헤더 (2026-10-06 · core/security_headers) — 모든 응답에 같은 헤더가 붙는다.

## 여기서 고정하는 계약

  ① API·`/health`·없는 경로(404)까지 **모든 응답**에 nosniff · X-Frame-Options · Referrer-Policy ·
     Permissions-Policy · CSP(Report-Only) 가 붙는다 — 미들웨어가 가장 바깥에 있어야 정적 파일까지 덮는다.
  ② CSP 는 아직 **Report-Only** 다(강제 헤더가 없다). 네이버 지도가 통째로 막히는 종류라 운영 콘솔에서
     위반 0 을 본 뒤에 강제로 바꾼다 — 그때 이 테스트도 같이 바꾼다.
  ③ CSP 가 핵심 방어(frame-ancestors · object-src · base-uri)와 실측한 제3자 출처(네이버 SDK·구글 로그인)를 담는다.
  ④ 라우트가 이미 정한 헤더는 덮지 않는다(setdefault).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import MutableHeaders

from app.core import security_headers
from app.main import app

client = TestClient(app)

ENFORCED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}


@pytest.mark.parametrize("path", ["/health", "/api/v1/commercial-districts", "/api/v1/no-such-route"])
def test_every_response_carries_security_headers(path):
    r = client.get(path)
    for name, value in ENFORCED.items():
        assert r.headers.get(name) == value, f"{path} 에 {name} 가 없거나 다르다"
    assert r.headers.get("content-security-policy-report-only") == security_headers.CSP


def test_csp_is_report_only_for_now():
    r = client.get("/health")
    assert "content-security-policy" not in {k.lower() for k in r.headers.keys()}, \
        "CSP 를 강제로 바꿨다면 운영 콘솔 위반 0 을 확인했는지, 이 테스트의 계약을 같이 고쳤는지 볼 것"


def _directives() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part in security_headers.CSP.split(";"):
        name, *srcs = part.split()
        out[name] = srcs
    return out


def test_csp_keeps_core_guards():
    d = _directives()
    assert d["frame-ancestors"] == ["'none'"]
    assert d["object-src"] == ["'none'"]
    assert d["base-uri"] == ["'self'"]
    assert d["default-src"] == ["'self'"]
    assert "'unsafe-eval'" not in security_headers.CSP
    assert "'unsafe-inline'" not in d["script-src"], "인라인 스크립트를 열면 CSP 의 XSS 방어가 사라진다"


def test_csp_allows_measured_third_parties():
    """2026-10-06 실측 — 빠지면 강제 전환 때 지도·구글 로그인이 막힌다."""
    d = _directives()
    for src in ("https://oapi.map.naver.com", "https://nrbe.map.naver.net", "https://apis.naver.com",
                "https://accounts.google.com/gsi/client"):
        assert src in d["script-src"], src
    assert "https://accounts.google.com/gsi/style" in d["style-src"]
    assert "https://accounts.google.com/gsi/" in d["frame-src"]
    assert "https:" in d["img-src"]


def test_route_set_header_is_not_overridden():
    headers = MutableHeaders({"X-Frame-Options": "SAMEORIGIN"})
    security_headers.apply(headers)
    assert headers["X-Frame-Options"] == "SAMEORIGIN"
    assert headers["X-Content-Type-Options"] == "nosniff"
