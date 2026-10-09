"""공식 API 응답은 mock이다. 서명 state·HTTP 교환·DB 가입과 파기는 실제 코드를 탄다."""
from urllib.parse import parse_qs
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.db import Base, get_db
from app.main import app
from app.models.auth import SocialIdentity, User, Org
from app.services import social_auth, auth_service

V1 = "/api/v1/auth"


@pytest.fixture
def social(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    factory = sessionmaker(engine)
    Base.metadata.create_all(engine)
    def db():
        with factory() as session:
            yield session
    old = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = db
    for provider in ("naver", "kakao"):
        monkeypatch.setattr(settings, f"{provider}_login_client_id", f"mock-{provider}-client")
        monkeypatch.setattr(settings, f"{provider}_login_client_secret", "mock-secret")
        monkeypatch.setattr(settings, f"{provider}_login_redirect_uri", f"https://placeos.web.app/?social={provider}")
    replies = {"naver": {"resultcode": "00", "response": {"id": "naver-user", "email": "naver@example.com"}},
               "kakao": {"id": 12345, "kakao_account": {"email": "kakao@example.com", "is_email_valid": True, "is_email_verified": True}}}
    replies["token"] = {"access_token": "mock-provider-token"}
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.path.endswith("token"):
            assert request.method == "POST"
            body = parse_qs(request.content.decode())
            assert body["client_secret"] == ["mock-secret"]
            assert "client_secret" not in str(request.url)
            return httpx.Response(200, json=replies["token"])
        assert request.headers["Authorization"] == "Bearer mock-provider-token"
        return httpx.Response(200, json=replies["naver" if request.url.host == "openapi.naver.com" else "kakao"])
    real_client = httpx.Client
    monkeypatch.setattr(social_auth.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    with TestClient(app) as client:
        yield client, factory, replies, calls
    if old is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = old
    Base.metadata.drop_all(engine)
    engine.dispose()


def attempt(client, provider):
    result = client.post(f"{V1}/social/{provider}/start", json={"org_name": "직접 입력 공간"})
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    body = result.json()
    assert body["verifier"] not in body["authorization_url"]
    payload = jwt.decode(body["state"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert "org_name" not in payload
    return {"code": "mock-code", "state": body["state"], "verifier": body["verifier"], "org_name": "직접 입력 공간"}


def count(factory, model):
    with factory() as db:
        return db.scalar(select(func.count()).select_from(model))


def _assert_new_identity(social, provider):
    client, factory, _, _ = social
    r = client.post(f"{V1}/social/{provider}/callback", json=attempt(client, provider))
    assert r.status_code == 201, r.text
    me = client.get(f"{V1}/me", headers={"Authorization": "Bearer " + r.json()["access_token"]}).json()
    assert me["email"] == f"{provider}@example.com"
    assert me["org"]["name"] == "직접 입력 공간"
    with factory() as db:
        assert db.scalar(select(SocialIdentity)).provider == provider


def test_naver_login_creates_user_with_verified_identity(social):
    _assert_new_identity(social, "naver")


def test_kakao_login_creates_user_with_verified_identity(social):
    _assert_new_identity(social, "kakao")


@pytest.mark.parametrize("provider", ["naver", "kakao"])
def test_social_login_existing_identity_reuses_user(social, provider):
    client, factory, replies, _ = social
    first = client.post(f"{V1}/social/{provider}/callback", json=attempt(client, provider))
    account = replies[provider]["response" if provider == "naver" else "kakao_account"]
    account.pop("email")
    again = client.post(f"{V1}/social/{provider}/callback", json=attempt(client, provider))
    assert first.status_code == 201 and again.status_code == 200
    assert count(factory, User) == count(factory, Org) == count(factory, SocialIdentity) == 1


@pytest.mark.parametrize("provider", ["naver", "kakao"])
def test_social_login_missing_email_does_not_fabricate_value(social, provider):
    client, factory, replies, _ = social
    replies[provider]["response" if provider == "naver" else "kakao_account"].pop("email")
    r = client.post(f"{V1}/social/{provider}/callback", json=attempt(client, provider))
    assert r.status_code == 422
    assert count(factory, User) == count(factory, Org) == 0


@pytest.mark.parametrize("bad", ["state", "verifier", "provider", "expired"])
def test_social_login_invalid_state_is_rejected(social, bad):
    client, factory, _, calls = social
    body = attempt(client, "naver")
    provider = "naver"
    if bad == "state": body["state"] = "forged"
    if bad == "verifier": body["verifier"] = "x" * 43
    if bad == "provider": provider = "kakao"
    if bad == "expired":
        payload = jwt.decode(body["state"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
        body["state"] = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    r = client.post(f"{V1}/social/{provider}/callback", json=body)
    assert r.status_code == 401
    assert not calls and count(factory, User) == 0


def test_social_login_invalid_token_does_not_create_user(social):
    client, factory, replies, _ = social
    replies["token"] = {"error": "invalid_grant"}
    r = client.post(f"{V1}/social/naver/callback", json=attempt(client, "naver"))
    assert r.status_code == 401 and count(factory, User) == 0


def test_social_login_matching_email_does_not_auto_merge(social):
    client, factory, _, _ = social
    signup = client.post(f"{V1}/signup", json={"org_name": "기존 공간", "email": "naver@example.com", "password": "mock-password"})
    assert signup.status_code == 201
    r = client.post(f"{V1}/social/naver/callback", json=attempt(client, "naver"))
    assert r.status_code == 409
    assert count(factory, User) == 1 and count(factory, SocialIdentity) == 0
    assert client.post(f"{V1}/login", json={"email": "naver@example.com", "password": "mock-password"}).status_code == 200


@pytest.mark.parametrize("provider", ["naver", "kakao"])
def test_social_login_missing_credentials_fails_explicitly(social, monkeypatch, provider):
    client, _, _, _ = social
    monkeypatch.setattr(settings, f"{provider}_login_client_secret", "")
    assert client.get(f"{V1}/providers").json()[f"{provider}_enabled"] is False
    assert client.post(f"{V1}/social/{provider}/start", json={}).status_code == 404
    assert client.post(f"{V1}/social/{provider}/callback", json={"code": "mock", "state": "mock", "verifier": "v" * 43}).status_code == 404


def test_social_identity_is_deleted_with_account(social):
    client, factory, _, _ = social
    r = client.post(f"{V1}/social/naver/callback", json=attempt(client, "naver"))
    assert client.delete(f"{V1}/me", headers={"Authorization": "Bearer " + r.json()["access_token"]}).status_code == 200
    assert count(factory, SocialIdentity) == count(factory, User) == 0


def test_google_does_not_link_social_identity_by_email(social):
    client, factory, _, _ = social
    client.post(f"{V1}/social/naver/callback", json=attempt(client, "naver"))
    with factory() as db, pytest.raises(auth_service.InvalidCredentials):
        auth_service.login_with_google(db, "naver@example.com")


def test_kakao_unverified_email_does_not_create_user(social):
    client, factory, replies, _ = social
    replies["kakao"]["kakao_account"]["is_email_verified"] = False
    r = client.post(f"{V1}/social/kakao/callback", json=attempt(client, "kakao"))
    assert r.status_code == 422 and count(factory, User) == 0


@pytest.mark.parametrize("provider", ["naver", "kakao"])
def test_invalid_provider_subject_does_not_create_user(social, provider):
    client, factory, replies, _ = social
    account = replies[provider]["response"] if provider == "naver" else replies[provider]
    account["id"] = None
    assert client.post(f"{V1}/social/{provider}/callback", json=attempt(client, provider)).status_code == 401
    assert count(factory, User) == 0


def test_provider_timeout_is_reported_without_creating_user(social, monkeypatch):
    client, factory, _, _ = social
    def unavailable(*args):
        raise social_auth.SocialAuthUnavailable()
    monkeypatch.setattr(social_auth, "exchange", unavailable)
    assert client.post(f"{V1}/social/naver/callback", json=attempt(client, "naver")).status_code == 503
    assert count(factory, User) == 0


def test_pre_migration_schema_keeps_google_and_delete_working(social):
    client, factory, _, _ = social
    SocialIdentity.__table__.drop(factory.kw["bind"])
    with factory() as db:
        token, created = auth_service.login_with_google(db, "legacy@example.com")
        assert created
        again, created = auth_service.login_with_google(db, "legacy@example.com")
        assert again and not created
    assert client.delete(f"{V1}/me", headers={"Authorization": "Bearer " + token}).status_code == 200
    assert count(factory, User) == 0


def test_pre_migration_social_login_fails_explicitly(social):
    client, factory, _, _ = social
    SocialIdentity.__table__.drop(factory.kw["bind"])
    r = client.post(f"{V1}/social/naver/callback", json=attempt(client, "naver"))
    assert r.status_code == 503 and "마이그레이션" in r.json()["detail"]
    assert count(factory, User) == 0
