"""W4 판정 잠금 — docs/pilot-outreach-founders-2026-10.md §W4 판정 규칙(사전등록 2026-09-28).

잠그는 성질:
1. **시계는 조직마다 가입일부터 28일** — W4 가 안 끝난 조직은 분모에 없다.
2. **활성 = 서로 다른 2주 이상 접근** — 데모 날 한 번은 파일럿이 아니다. 28일 뒤 접근은 안 센다.
3. **무응답은 빼되 응답률 60% 미만이면 `판정보류`**.
4. **"아마"는 합격선 밖** — 따로 보고한다.
5. 내부·테스트 조직은 빠진다(`kpi_scope`).
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.models.auth import AuditLog, Org
from app.models.feedback import PilotFeedback
from app.services import pilot_w4

_engine = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
AFTER_W4 = T0 + timedelta(days=40)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    s = _TestSession()
    yield s
    s.close()
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=_engine)


def _org(db, name, signup=T0, access_days=(), feedback=None):
    """조직 1곳. access_days = 가입일로부터 며칠째에 접근했나. feedback = (점수, 의향)."""
    org = Org(name=name, created_at=signup)
    db.add(org)
    db.flush()
    for d in access_days:
        db.add(AuditLog(org_id=org.id, action="access:session", detail="/api/v1/x",
                        created_at=signup + timedelta(days=d, hours=1)))
    if feedback:
        score, pay = feedback
        db.add(PilotFeedback(org_id=org.id, nps_score=score, would_pay=pay,
                             created_at=signup + timedelta(days=29)))
    db.commit()
    return org


ACTIVE = (0, 8)  # 1주차 · 2주차


def test_not_ended_orgs_are_not_counted(db) -> None:
    for i in range(5):
        _org(db, f"p{i}", access_days=ACTIVE, feedback=(10, "yes"))
    r = pilot_w4.w4_summary(db, now=T0 + timedelta(days=27))
    assert r["orgs_in_progress"] == 5
    assert r["orgs_ended_active"] == 0
    assert r["verdict"] == "표본부족"


def test_one_week_or_late_access_is_not_active(db) -> None:
    """같은 주에 여러 번 · 28일 뒤 접근은 활성 2주를 채우지 못한다."""
    _org(db, "same-week", access_days=(0, 1, 6))
    _org(db, "late", access_days=(3, 28, 35))
    _org(db, "two-weeks", access_days=(6, 7))
    r = pilot_w4.w4_summary(db, now=AFTER_W4)
    status = {o["name"]: o["status"] for o in r["orgs"]}
    assert status == {"same-week": "비활성", "late": "비활성", "two-weeks": "활성"}
    assert {o["name"]: o["active_weeks"] for o in r["orgs"]}["two-weeks"] == [1, 2]


def test_low_response_rate_holds_verdict(db) -> None:
    """활성 5곳 중 2곳만 답하면(40%) 두 곳이 모두 10점이어도 판정하지 않는다."""
    for i in range(5):
        _org(db, f"p{i}", access_days=ACTIVE, feedback=(10, "yes") if i < 2 else None)
    r = pilot_w4.w4_summary(db, now=AFTER_W4)
    assert r["response_rate_pct"] == 40.0
    assert r["verdict"] == "판정보류"
    assert r["nps"] is None


def test_enough_rate_but_few_answers_is_insufficient(db) -> None:
    """활성 6곳 · 응답 4곳(66.7%) — 응답률은 넘었지만 n<5 라 표본부족."""
    for i in range(6):
        _org(db, f"p{i}", access_days=ACTIVE, feedback=(10, "yes") if i < 4 else None)
    r = pilot_w4.w4_summary(db, now=AFTER_W4)
    assert r["verdict"] == "표본부족"


def test_maybe_does_not_count_toward_pay_target(db) -> None:
    """NPS 는 넘어도 '예'가 20% 면 미달. '아마'는 따로 나온다."""
    pays = ["yes", "maybe", "maybe", "maybe", "no"]
    for i, p in enumerate(pays):
        _org(db, f"p{i}", access_days=ACTIVE, feedback=(10, p))
    r = pilot_w4.w4_summary(db, now=AFTER_W4)
    assert r["nps"] == 100.0
    assert r["would_pay_pct"] == 20.0
    assert r["would_pay_maybe_pct"] == 60.0
    assert r["verdict"] == "미달"


def test_meets_targets_and_inactive_feedback_ignored(db) -> None:
    for i in range(5):
        _org(db, f"p{i}", access_days=ACTIVE, feedback=(9, "yes") if i < 2 else (7, "no"))
    # 비활성 조직의 0점은 분모에 들어가지 않는다.
    _org(db, "drive-by", access_days=(0,), feedback=(0, "no"))
    r = pilot_w4.w4_summary(db, now=AFTER_W4)
    assert r["orgs_ended_active"] == 5 and r["orgs_ended_inactive"] == 1
    assert r["nps"] == 40.0 and r["would_pay_pct"] == 40.0
    assert r["verdict"] == "충족"
    assert r["one_response_swing_nps"] == 40.0


def test_internal_orgs_excluded(db) -> None:
    for i in range(5):
        _org(db, f"p{i}", access_days=ACTIVE, feedback=(10, "yes"))
    _org(db, "[내부] 창업자 시험", access_days=ACTIVE, feedback=(0, "no"))
    r = pilot_w4.w4_summary(db, now=AFTER_W4)
    assert r["excluded_orgs"] == 1
    assert r["orgs_ended_active"] == 5
    assert r["verdict"] == "충족"


def test_endpoint_requires_admin(db, monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setenv("ADMIN_TOKEN", "t")
    assert client.get("/api/v1/admin/pilot-w4").status_code == 403
    r = client.get("/api/v1/admin/pilot-w4", headers={"X-Admin-Token": "t"})
    assert r.status_code == 200
    assert r.json()["verdict"] == "표본부족"
    assert r.json()["rules"]["min_active_weeks"] == 2
