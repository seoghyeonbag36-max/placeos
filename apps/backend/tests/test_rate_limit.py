"""요청량 제어 (2026-10-06 · services/rate_limit) — 비용 경로와 무차별 대입을 막는다.

## 여기서 고정하는 계약

  ① **로그인 실패는 이메일 단위로 막힌다.** 한도를 넘으면 맞는 비밀번호도 429 이고 `Retry-After` 가 실린다.
     다른 이메일은 영향이 없고, 성공하면 그 이메일의 실패가 지워진다. 창이 지나면 풀린다.
  ② **새 계정 생성은 전역 한도가 있다.** 비밀번호 가입과 구글 첫 로그인이 **같은** 한도를 쓴다.
     이미 있는 이메일(409)과 기존 계정의 로그인·구글 로그인은 세지도 막지도 않는다.
  ③ (2026-11-22: LLM 생성 조직·전역 한도는 `POST /marketing/generate` 와 함께 지웠다 → docs/decision-program-post-opening-2026-11-22.md.)
  ④ 카운터 표는 키 수가 유한하다 — 넘으면 가장 오래 손대지 않은 키부터 버린다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.db import Base, get_db
from app.main import app
from app.services import google_auth, rate_limit

client = TestClient(app)
V1 = "/api/v1"
PASSWORD = "hunter2hunter"


@pytest.fixture
def db():
    """SQLite 인메모리 계정층. `get_db` 오버라이드는 이전 값을 복원한다(conftest.signed_in 과 같은 이유)."""
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _db
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def clock(monkeypatch):
    """카운터 시계를 손으로 돌린다 — 창이 끝나기를 실제로 기다리지 않는다."""
    now = [1000.0]
    monkeypatch.setattr(rate_limit, "_clock", lambda: now[0])
    return now


def _signup(email: str, org: str = "한도 시험 조직"):
    return client.post(f"{V1}/auth/signup",
                       json={"org_name": org, "email": email, "password": PASSWORD})


def _login(email: str, password: str):
    return client.post(f"{V1}/auth/login", json={"email": email, "password": password})


def _bearer(resp) -> dict[str, str]:
    assert resp.status_code in (200, 201), resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── ① 로그인 실패 ─────────────────────────────────────────────────────────────


def test_login_locks_per_email_after_limit(db, monkeypatch):
    monkeypatch.setattr(settings, "login_failures_per_email", 3)
    assert _signup("owner@example.com").status_code == 201

    for _ in range(3):
        assert _login("owner@example.com", "wrong-password").status_code == 401
    locked = _login("owner@example.com", PASSWORD)
    assert locked.status_code == 429, "한도를 넘었는데 맞는 비밀번호가 통과했다 — 대입이 계속 된다"
    assert int(locked.headers["Retry-After"]) > 0

    # 대소문자만 바꾼 같은 이메일도 같은 키다.
    assert _login("OWNER@example.com", PASSWORD).status_code == 429
    # 다른 이메일은 영향이 없다.
    assert _login("someone@example.com", "wrong-password").status_code == 401


def test_successful_login_clears_failures(db, monkeypatch):
    monkeypatch.setattr(settings, "login_failures_per_email", 3)
    assert _signup("owner@example.com").status_code == 201

    for _ in range(2):
        assert _login("owner@example.com", "wrong-password").status_code == 401
    assert _login("owner@example.com", PASSWORD).status_code == 200
    # 성공이 실패를 지웠으므로 다시 두 번 틀려도 아직 401 이다(누적이면 세 번째에서 429).
    for _ in range(2):
        assert _login("owner@example.com", "wrong-password").status_code == 401


def test_login_lock_expires_with_window(db, monkeypatch, clock):
    monkeypatch.setattr(settings, "login_failures_per_email", 2)
    assert _signup("owner@example.com").status_code == 201
    for _ in range(2):
        _login("owner@example.com", "wrong-password")
    assert _login("owner@example.com", PASSWORD).status_code == 429

    clock[0] += rate_limit.LOGIN_WINDOW_S
    assert _login("owner@example.com", PASSWORD).status_code == 200


# ── ② 새 계정 생성 ────────────────────────────────────────────────────────────


def test_signup_cap_blocks_new_accounts_only(db, monkeypatch):
    monkeypatch.setattr(settings, "signup_hourly_cap_per_instance", 2)
    assert _signup("a@example.com").status_code == 201
    assert _signup("b@example.com").status_code == 201

    third = _signup("c@example.com")
    assert third.status_code == 429, third.text
    assert int(third.headers["Retry-After"]) > 0
    # 이미 있는 이메일은 한도 전에 409 로 끝난다 — 세지도 않는다.
    assert _signup("a@example.com").status_code == 409
    # 기존 계정 로그인은 막지 않는다.
    assert _login("a@example.com", PASSWORD).status_code == 200


def test_google_first_login_shares_signup_cap(db, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "test-client")
    monkeypatch.setattr(settings, "signup_hourly_cap_per_instance", 2)
    monkeypatch.setattr(google_auth, "verify_id_token", lambda credential, aud: credential)

    assert _signup("pw@example.com").status_code == 201                       # 비밀번호 가입 1
    first = client.post(f"{V1}/auth/google", json={"credential": "new@example.com"})
    assert first.status_code == 201, first.text                               # 구글 첫 로그인 2
    blocked = client.post(f"{V1}/auth/google", json={"credential": "other@example.com"})
    assert blocked.status_code == 429, "구글 첫 로그인이 가입 한도를 우회했다"

    # 이미 있는 계정의 구글 로그인은 새 계정이 아니므로 그대로 된다.
    again = client.post(f"{V1}/auth/google", json={"credential": "new@example.com"})
    assert again.status_code == 200, again.text


# ── ③ LLM 한도 ────────────────────────────────────────────────────────────────


# ── ④ 표 크기 ─────────────────────────────────────────────────────────────────


def test_window_evicts_least_recently_touched_key():
    w = rate_limit._Window(window_s=60, max_keys=2)
    w.add("a", 0.0)
    w.add("b", 0.0)
    w.add("a", 1.0)          # a 를 다시 건드린다 → 가장 오래된 것은 b
    w.add("c", 2.0)
    assert w.count("b", 3.0) == 0
    assert w.count("a", 3.0) == 2
    assert w.count("c", 3.0) == 1
