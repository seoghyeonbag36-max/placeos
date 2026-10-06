"""관리자 API 의 문 — 모든 `/admin/*` 가 같은 가드를 같은 방식으로 지킨다 (2026-10-06).

종전에는 거부 테스트가 라우트마다 들쭉날쭉했다 — `/admin/usage` 는 0건, 토큰 오답은 `coverage` 만,
미설정은 `latency`·`pmf` 만 봤다(docs/finding-project-review-4roles-2026-10-06.md §4-3). 그리고
새 라우트가 가드 없이 붙어도 잡는 테스트가 없었다.

## 여기서 고정하는 계약

  ① `/api/v1/admin/*` 의 **모든** 라우트가 `require_admin` 의존성을 단다 — 앱에서 라우트를 뽑아 순회한다.
  ② 모든 라우트가 헤더 없음 · 오답 · 서버 `ADMIN_TOKEN` 미설정에서 403 이다.
  ③ 오답이 한도를 넘으면 429(`Retry-After`) — 그동안은 **맞는 토큰도** 막힌다. 창이 지나면 풀린다.
     헤더가 아예 없는 요청은 대입 시도가 아니므로 세지 않는다.
  ④ 비교는 `hmac.compare_digest` 를 거친다(응답 시간으로 한 글자씩 맞혀 가지 못하게).
"""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.v1 import admin
from app.core.config import settings
from app.main import app
from app.services import rate_limit

client = TestClient(app)
V1 = "/api/v1"
TOKEN = "correct-admin-token"

ADMIN_ROUTES = sorted(
    r.path for r in app.routes
    if isinstance(r, APIRoute) and r.path.startswith(f"{V1}/admin/")
)


def _dependency_calls(route: APIRoute) -> set:
    return {d.call for d in route.dependant.dependencies}


def test_admin_routes_are_discovered():
    """순회가 빈 목록을 돌면 아래 검사가 전부 공허하게 통과한다 — 개수부터 확인한다."""
    assert len(ADMIN_ROUTES) >= 5, ADMIN_ROUTES


def test_every_admin_route_depends_on_require_admin():
    unguarded = [r.path for r in app.routes
                 if isinstance(r, APIRoute) and r.path.startswith(f"{V1}/admin/")
                 and admin.require_admin not in _dependency_calls(r)]
    assert unguarded == [], f"가드 없는 관리자 라우트: {unguarded}"


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_admin_route_rejects_missing_wrong_or_unset_token(path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    assert client.get(path).status_code == 403
    assert client.get(path, headers={"X-Admin-Token": "wrong"}).status_code == 403

    monkeypatch.delenv("ADMIN_TOKEN")
    # 미설정이면 맞는 값을 보내도 열리지 않는다(fail-closed).
    assert client.get(path, headers={"X-Admin-Token": TOKEN}).status_code == 403


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(rate_limit, "_clock", lambda: now[0])
    return now


def test_admin_throttle_blocks_even_correct_token_until_window_ends(monkeypatch, clock):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setattr(settings, "admin_failures_per_instance", 3)
    path = f"{V1}/admin/latency"

    for _ in range(3):
        assert client.get(path, headers={"X-Admin-Token": "guess"}).status_code == 403
    blocked = client.get(path, headers={"X-Admin-Token": "guess"})
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert client.get(path, headers={"X-Admin-Token": TOKEN}).status_code == 429

    clock[0] += rate_limit.ADMIN_WINDOW_S
    assert client.get(path, headers={"X-Admin-Token": TOKEN}).status_code == 200


def test_missing_header_is_not_counted_as_attempt(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setattr(settings, "admin_failures_per_instance", 2)
    path = f"{V1}/admin/latency"

    for _ in range(5):
        assert client.get(path).status_code == 403            # 화면을 토큰 없이 연 것 — 세지 않는다
    assert client.get(path, headers={"X-Admin-Token": TOKEN}).status_code == 200
    for _ in range(2):
        assert client.get(path, headers={"X-Admin-Token": "guess"}).status_code == 403
    assert client.get(path, headers={"X-Admin-Token": "guess"}).status_code == 429


def test_token_comparison_goes_through_compare_digest(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    seen: list[tuple[bytes, bytes]] = []
    real = admin.hmac.compare_digest

    def spy(a, b):
        seen.append((a, b))
        return real(a, b)

    monkeypatch.setattr(admin.hmac, "compare_digest", spy)
    assert client.get(f"{V1}/admin/latency", headers={"X-Admin-Token": TOKEN}).status_code == 200
    assert seen, "토큰을 일반 비교(==/!=)로 확인했다"
