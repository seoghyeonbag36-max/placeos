"""회원 탈퇴 = 개인정보 파기 잠금 (2026-10-05) — docs/decision-lightweight-first-2026-10-05.md §2.

잠그는 것
1. **흔적이 남지 않는다** — 혼자 쓰던 조직이면 사용자·조직·키·피드백·사업 정보·감사로그까지 0행.
2. **남의 것은 안 지운다** — 다른 사용자, 다른 멤버가 남은 조직은 그대로다. 떠난 사람의 감사 행은
   익명(user_id 없음)으로만 남아 조직 사용량이 과거로 거슬러 줄지 않는다.
3. **지운 뒤에는 아무 자격도 안 통한다** — 그 토큰, 그 조직의 API 키 모두.

SQLite 는 외래키를 기본으로 안 본다. 프로덕션(Neon Postgres)은 보므로 여기서도 켠다 —
그래야 삭제 순서가 틀렸을 때 테스트가 먼저 운다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.models.auth import ApiKey, AuditLog, BusinessWorkspace, Membership, Org, User
from app.models.feedback import PilotFeedback
from app.services import auth_service

V1 = "/api/v1"

_engine = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(_engine, "connect")
def _foreign_keys_on(dbapi_connection, _record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _fresh_schema():
    Base.metadata.create_all(bind=_engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    Base.metadata.drop_all(bind=_engine)


client = TestClient(app)

_PROFILE = {"status": "set", "profile": {"goal": "start", "industryKey": "coffee",
                                         "homeDistrictId": None, "businessName": "내 카페",
                                         "description": "동네 주민을 위한 카페"}}


def _join(email: str, org_name: str = "Acme") -> dict[str, str]:
    r = client.post(f"{V1}/auth/signup", json={
        "org_name": org_name, "email": email, "password": "hunter2hunter"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _count(model) -> int:
    with _TestSession() as db:
        return db.execute(select(func.count()).select_from(model)).scalar_one()


def _fill(headers: dict[str, str]) -> str:
    """사업 정보·피드백·API 키를 남기고 키 원문을 돌려준다."""
    assert client.post(f"{V1}/auth/workspace", headers=headers, json=_PROFILE).status_code == 200
    assert client.post(f"{V1}/feedback", headers=headers, json={
        "nps_score": 9, "would_pay": "yes", "comment": "연락처 010-0000-0000"}).status_code == 201
    created = client.post(f"{V1}/auth/api-keys", headers=headers, json={"name": "pos"})
    assert created.status_code == 201
    return created.json()["key"]


def test_delete_requires_login():
    assert client.delete(f"{V1}/auth/me").status_code == 401


def test_delete_solo_account_leaves_nothing():
    h = _join("solo@acme.com")
    raw_key = _fill(h)

    r = client.delete(f"{V1}/auth/me", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}

    for model in (User, Org, Membership, ApiKey, AuditLog, PilotFeedback, BusinessWorkspace):
        assert _count(model) == 0, f"{model.__tablename__} 에 흔적이 남았다"
    assert client.get(f"{V1}/auth/me", headers=h).status_code == 401
    with _TestSession() as db:
        assert auth_service.resolve_api_key(db, raw_key) is None, "지운 조직의 키가 통과한다"


def test_delete_leaves_other_users_alone():
    me, other = _join("me@acme.com", "Mine"), _join("other@acme.com", "Theirs")
    _fill(other)
    before = {m: _count(m) for m in (ApiKey, PilotFeedback, BusinessWorkspace)}

    assert client.delete(f"{V1}/auth/me", headers=me).status_code == 200

    assert client.get(f"{V1}/auth/me", headers=other).status_code == 200
    assert client.get(f"{V1}/auth/workspace", headers=other).json()["profile"] == {
        **_PROFILE["profile"], "targetIndustryKey": None,
        "industryDetailKey": None, "targetIndustryDetailKey": None}
    assert {m: _count(m) for m in before} == before
    assert _count(User) == 1 and _count(Org) == 1


def test_delete_member_of_shared_org_keeps_org_and_anonymizes_trail():
    owner = _join("owner@acme.com", "Shared")
    member = _join("member@acme.com", "MemberSolo")
    owner_me = client.get(f"{V1}/auth/me", headers=owner).json()
    member_me = client.get(f"{V1}/auth/me", headers=member).json()
    shared_org = owner_me["org"]["id"]
    with _TestSession() as db:
        db.add(Membership(user_id=member_me["user_id"], org_id=shared_org, role="member"))
        # 2026-10-05 전의 가입 행처럼 이메일 사본이 든 detail 과, 공유 조직에서의 이용 기록 하나
        db.add(AuditLog(org_id=shared_org, user_id=member_me["user_id"],
                        action="login", detail="member@acme.com"))
        db.add(AuditLog(org_id=shared_org, user_id=member_me["user_id"],
                        action="access:jwt", detail="/api/v1/commercial-districts/"))
        db.commit()

    assert client.delete(f"{V1}/auth/me", headers=member).status_code == 200

    assert client.get(f"{V1}/auth/me", headers=owner).status_code == 200
    with _TestSession() as db:
        orgs = set(db.execute(select(Org.id)).scalars())
        assert orgs == {shared_org}, "혼자 쓰던 조직만 지우고 공유 조직은 남긴다"
        assert db.get(User, member_me["user_id"]) is None
        trail = db.execute(select(AuditLog).where(AuditLog.org_id == shared_org)).scalars().all()
        assert all(row.user_id != member_me["user_id"] for row in trail)
        assert not [row for row in trail if "@" in row.detail], "이메일 사본이 남았다"
        assert any(row.action == "access:jwt" and row.user_id is None for row in trail), \
            "조직 사용량은 익명으로 남아야 한다"
