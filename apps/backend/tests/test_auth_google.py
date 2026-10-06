"""구글 로그인 잠금 (2026-10-05) — docs/decision-lightweight-first-2026-10-05.md §1.

잠그는 것은 성질이다:
1. **서명·대상·발급자·만료·이메일 확인** 중 하나라도 어긋나면 거절한다.
2. **꺼져 있으면 흔적이 없다** — GOOGLE_CLIENT_ID 가 비면 버튼도 엔드포인트도 없다.
3. **선점 차단** — 같은 이메일의 비밀번호 계정은 구글 로그인 순간 비밀번호가 끊기고,
   그 전에 발급된 토큰도 함께 무효가 된다(이메일을 확인하지 않은 가입이었으므로).
   조직 API 키도 그 순간 폐기된다(2026-10-06) — 연결 뒤 새로 만든 키는 다음 로그인에서 살아남는다.
4. **감사로그에 이메일 사본이 없다**(수집 최소화).

구글 공개키 대신 로컬 RSA 키로 서명한다 — 네트워크를 타지 않는다.
"""
from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models.auth import AuditLog, Org, User
from app.services import google_auth

V1 = "/api/v1"
CLIENT_ID = "test-client.apps.googleusercontent.com"

_engine = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _fresh_schema():
    """스키마를 새로 만들고, 끝나면 **이전 오버라이드를 되돌린다** — test_auth.py 는 모듈 최상단에서
    전역으로 걸어 두므로 지워 버리면 뒤에 도는 테스트가 진짜 DB 를 찾는다(conftest.signed_in 과 같은 이유)."""
    Base.metadata.create_all(bind=_engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture()
def google_on(monkeypatch):
    """구글 로그인을 켜고, 공개키 조회를 로컬 키로 바꾼다."""
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(google_auth, "_signing_key", lambda _cred: _KEY.public_key())


client = TestClient(app)


def _id_token(key=_KEY, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "1180000000001",
        "email": "Founder@Gmail.com", "email_verified": True,
        "name": "저장하지 않는 이름", "picture": "https://example.com/p.png",
        "iat": now, "exp": now + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


def _verify(token: str) -> str:
    return google_auth.verify_id_token(token, CLIENT_ID, key_for=lambda _c: _KEY.public_key())


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── 1. 토큰 검증 ────────────────────────────────────────────────────────────

def test_valid_token_yields_lowercased_email():
    assert _verify(_id_token()) == "founder@gmail.com"


def test_issuer_without_scheme_is_accepted():
    """구글 문서가 두 표기를 모두 쓴다."""
    assert _verify(_id_token(iss="accounts.google.com")) == "founder@gmail.com"


@pytest.mark.parametrize("overrides", [
    {"aud": "someone-elses-client"},                 # 다른 앱용으로 발급된 토큰
    {"iss": "https://evil.example.com"},             # 구글이 발급하지 않았다
    {"exp": int(time.time()) - 3600},                # 만료
    {"email_verified": False},                       # 구글이 소유를 확인하지 않은 주소
    {"email": None},                                 # 이메일 없음
])
def test_bad_claims_are_rejected(overrides):
    with pytest.raises(google_auth.GoogleTokenInvalid):
        _verify(_id_token(**overrides))


def test_token_signed_by_another_key_is_rejected():
    with pytest.raises(google_auth.GoogleTokenInvalid):
        _verify(_id_token(key=_OTHER_KEY))


def test_unconfigured_client_id_rejects_everything():
    with pytest.raises(google_auth.GoogleTokenInvalid):
        google_auth.verify_id_token(_id_token(), "", key_for=lambda _c: _KEY.public_key())


# ── 2. 꺼져 있으면 흔적이 없다 ────────────────────────────────────────────────

def test_providers_hides_google_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    assert client.get(f"{V1}/auth/providers").json() == {"google_client_id": None}
    assert client.post(f"{V1}/auth/google", json={"credential": _id_token()}).status_code == 404


def test_providers_exposes_public_client_id(google_on):
    assert client.get(f"{V1}/auth/providers").json() == {"google_client_id": CLIENT_ID}


# ── 3. 가입·로그인 ──────────────────────────────────────────────────────────

def test_first_google_login_creates_account(google_on):
    r = client.post(f"{V1}/auth/google", json={"credential": _id_token()})
    assert r.status_code == 201, r.text
    me = client.get(f"{V1}/auth/me", headers=_bearer(r.json()["access_token"])).json()
    assert me["email"] == "founder@gmail.com"
    assert me["org"]["name"] == "내 작업 공간"
    assert me["role"] == "admin"


def test_org_name_is_optional_but_used(google_on):
    r = client.post(f"{V1}/auth/google", json={"credential": _id_token(), "org_name": "  ○○커피  "})
    me = client.get(f"{V1}/auth/me", headers=_bearer(r.json()["access_token"])).json()
    assert me["org"]["name"] == "○○커피"


def test_second_google_login_returns_same_account(google_on):
    first = client.post(f"{V1}/auth/google", json={"credential": _id_token()})
    second = client.post(f"{V1}/auth/google", json={"credential": _id_token()})
    assert second.status_code == 200
    ids = [client.get(f"{V1}/auth/me", headers=_bearer(r.json()["access_token"])).json()["user_id"]
           for r in (first, second)]
    assert ids[0] == ids[1]


def test_invalid_google_token_is_401(google_on):
    r = client.post(f"{V1}/auth/google", json={"credential": _id_token(aud="other")})
    assert r.status_code == 401


def test_google_keys_unavailable_is_503_not_401(google_on, monkeypatch):
    """구글 공개키를 못 받은 것은 사용자 잘못이 아니다 — 401 로 말하면 '로그인 실패'로 읽힌다."""
    def down(_cred):
        raise google_auth.GoogleKeysUnavailable("network")
    monkeypatch.setattr(google_auth, "_signing_key", down)
    assert client.post(f"{V1}/auth/google", json={"credential": _id_token()}).status_code == 503


def test_google_account_has_no_usable_password(google_on):
    """비밀번호 자리는 어떤 입력과도 일치하지 않는다 — '!' 를 넣어도 마찬가지다."""
    client.post(f"{V1}/auth/google", json={"credential": _id_token()})
    for guess in ("!", "", "anything-at-all"):
        r = client.post(f"{V1}/auth/login", json={"email": "founder@gmail.com", "password": guess})
        assert r.status_code == 401


# ── 4. 선점 차단 ────────────────────────────────────────────────────────────

def test_google_login_takes_over_unverified_password_account(google_on):
    """누군가 남의 주소로 비밀번호 가입을 해 두었다(이메일 확인 없음). 진짜 주인이 구글로 들어오면
    그 계정은 주인 것이 되고, 선점자는 비밀번호로도 **이미 받은 토큰으로도** 못 들어온다."""
    squat = client.post(f"{V1}/auth/signup", json={
        "org_name": "선점", "email": "founder@gmail.com", "password": "squatter-pass"})
    assert squat.status_code == 201
    squat_token = squat.json()["access_token"]
    assert client.get(f"{V1}/auth/me", headers=_bearer(squat_token)).status_code == 200

    owner = client.post(f"{V1}/auth/google", json={"credential": _id_token()})
    assert owner.status_code == 200
    assert client.get(f"{V1}/auth/me", headers=_bearer(owner.json()["access_token"])).status_code == 200

    assert client.get(f"{V1}/auth/me", headers=_bearer(squat_token)).status_code == 401, \
        "선점자가 쥐고 있던 토큰이 살아 있으면 비밀번호를 끊은 의미가 없다"
    assert client.get(f"{V1}/auth/workspace", headers=_bearer(squat_token)).status_code == 401
    assert client.post(f"{V1}/auth/login", json={
        "email": "founder@gmail.com", "password": "squatter-pass"}).status_code == 401
    with _TestSession() as db:
        actions = set(db.execute(select(AuditLog.action)).scalars())
    assert "auth.google_link" in actions


def test_google_link_revokes_api_keys_issued_before_link(google_on):
    """(2026-10-06) 선점자가 비밀번호·토큰과 별개로 **조직 API 키**를 미리 발급해 두었다. 진짜 주인이
    구글로 들어오는 순간 그 키도 죽어야 한다 — 살아 있으면 주인 조직 명의로 피드백·사용 기록이 계속 쌓인다."""
    squat = client.post(f"{V1}/auth/signup", json={
        "org_name": "선점", "email": "founder@gmail.com", "password": "squatter-pass"})
    issued = client.post(f"{V1}/auth/api-keys", json={"name": "선점자 연동"},
                         headers=_bearer(squat.json()["access_token"]))
    assert issued.status_code == 201, issued.text
    key = {"X-API-Key": issued.json()["key"]}
    assert client.get(f"{V1}/commercial-districts", headers=key).status_code == 200

    owner = client.post(f"{V1}/auth/google", json={"credential": _id_token()})
    assert owner.status_code == 200, owner.text

    assert client.get(f"{V1}/commercial-districts", headers=key).status_code == 401, \
        "선점자의 API 키가 구글 연결 뒤에도 살아 있다"
    keys = client.get(f"{V1}/auth/api-keys", headers=_bearer(owner.json()["access_token"])).json()
    assert keys and all(k["revoked_at"] for k in keys), "폐기 기록(revoked_at)이 남아야 한다 — 삭제가 아니다"
    with _TestSession() as db:
        details = list(db.execute(select(AuditLog.detail)
                                  .where(AuditLog.action == "api_key.revoke")).scalars())
    assert details == ["선점자 연동 (google_link)"]


def test_keys_issued_after_link_survive_later_google_logins(google_on):
    """폐기는 **비밀번호를 끊는 그 한 번**뿐이다. 연결 뒤 주인이 새로 만든 키는 다음 구글 로그인에서 살아남는다."""
    client.post(f"{V1}/auth/signup", json={
        "org_name": "선점", "email": "founder@gmail.com", "password": "squatter-pass"})
    owner = client.post(f"{V1}/auth/google", json={"credential": _id_token()})
    fresh = client.post(f"{V1}/auth/api-keys", json={"name": "주인 연동"},
                        headers=_bearer(owner.json()["access_token"]))
    assert fresh.status_code == 201, fresh.text

    again = client.post(f"{V1}/auth/google", json={"credential": _id_token()})
    assert again.status_code == 200
    assert client.get(f"{V1}/commercial-districts",
                      headers={"X-API-Key": fresh.json()["key"]}).status_code == 200


def test_token_without_cv_stays_valid():
    """cv 검사 이전에 발급된 토큰(클레임 없음)은 통과한다 — 배포 순간 전원 로그아웃을 피한다."""
    r = client.post(f"{V1}/auth/signup", json={
        "org_name": "Acme", "email": "legacy@acme.com", "password": "hunter2hunter"})
    me = client.get(f"{V1}/auth/me", headers=_bearer(r.json()["access_token"])).json()
    legacy = create_access_token(me["user_id"], me["org"]["id"])
    assert client.get(f"{V1}/auth/me", headers=_bearer(legacy)).status_code == 200


# ── 5. 감사로그에 이메일 사본이 없다 ─────────────────────────────────────────

def test_audit_log_keeps_no_email_copy(google_on):
    client.post(f"{V1}/auth/signup", json={
        "org_name": "Acme", "email": "pw@acme.com", "password": "hunter2hunter"})
    client.post(f"{V1}/auth/login", json={"email": "pw@acme.com", "password": "hunter2hunter"})
    client.post(f"{V1}/auth/google", json={"credential": _id_token()})
    with _TestSession() as db:
        rows = db.execute(select(AuditLog.action, AuditLog.detail)).all()
        assert db.execute(select(Org)).scalars().first() is not None
        assert db.execute(select(User)).scalars().first() is not None
    assert rows, "가입·로그인 행이 남아야 한다"
    assert not [r for r in rows if "@" in (r.detail or "")], rows
    assert {r.detail for r in rows if r.action in ("signup", "login")} == {"password", "google"}
