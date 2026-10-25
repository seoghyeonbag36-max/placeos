"""실제 제출 저장·입력 검증·메일 실패·관리자 접근 계약."""
import json
from pathlib import Path
from typing import get_args
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.db import Base, get_db
from app.core.config import settings
from app.models.visitor_feedback import VisitorFeedback
from app.schemas.visitor_feedback import CATEGORY_LABELS, VISITOR_ROLES, VisitorFeedbackIn, VisitorRole
from app.services import visitor_feedback as service

FORM = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "visitorFeedbackForm.json"

@pytest.fixture()
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    def dependency():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = dependency
    monkeypatch.setattr(service, "SessionLocal", sessions)
    monkeypatch.setattr(service, "_count", 0)
    monkeypatch.setattr(settings, "feedback_smtp_host", "")
    monkeypatch.setenv("ADMIN_TOKEN", "visitor-test")
    with TestClient(app) as c:
        yield c, sessions
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()

BODY = {"category": "suggestion", "message": "지도 검색 개선", "page": "/#page"}
HEADERS = {"X-Admin-Token": "visitor-test"}

def test_feedback_create(client):
    c, sessions = client
    r = c.post("/api/v1/visitor-feedback", json=BODY)
    assert r.status_code == 201
    with sessions() as db:
        row = db.get(VisitorFeedback, r.json()["id"])
        assert row.message == BODY["message"]
        assert row.contact is None and row.notification_status == "disabled"
    assert c.get("/api/v1/visitor-feedback").status_code == 403
    data = c.get("/api/v1/visitor-feedback", headers=HEADERS).json()
    assert len(data) == 1 and data[0]["status"] == "received"
    url = "/api/v1/visitor-feedback/" + r.json()["id"]
    assert c.patch(url, json={"status": "completed"}).status_code == 403
    assert c.patch(url, json={"status": "completed"}, headers=HEADERS).json()["status"] == "completed"

@pytest.mark.parametrize("changes", [{"message": "   "}, {"message": "a" * 2001}, {"category": "other"}, {"page": "/?token=secret"}, {"page": ""}, {"contact": " "}, {"nps_score": 10},
    {"role": "founder"},                                           # 없는 입장
    {"answers": {"stage": "touring_listings"}},                    # 입장 없이 선택 응답
    {"role": "dev", "answers": {"stage": "touring_listings"}},     # 다른 입장의 질문
    {"role": "start", "answers": {"stage": "매물 보러 다녀요 그리고 자유 서술"}},  # 선택지 밖 값 — 자유 서술이 새는 길
    {"role": "start", "answers": {"stage": 3}}])
def test_feedback_validation(client, changes):
    c, sessions = client
    assert c.post("/api/v1/visitor-feedback", json=BODY | changes).status_code == 422
    with sessions() as db:
        assert list(db.scalars(select(VisitorFeedback))) == []

def test_feedback_role_and_answers(client):
    """입장·선택 응답을 저장하고, 관리자 목록은 입장으로 거른다. 입장 없는 옛 화면의 제출도 그대로 받는다."""
    c, sessions = client
    founder = BODY | {"role": "start", "answers": {"stage": "touring_listings", "found": "partly"}}
    r = c.post("/api/v1/visitor-feedback", json=founder)
    assert r.status_code == 201
    with sessions() as db:
        row = db.get(VisitorFeedback, r.json()["id"])
        assert (row.role, row.answers) == ("start", {"stage": "touring_listings", "found": "partly"})
    assert c.post("/api/v1/visitor-feedback", json=BODY | {"role": "other", "answers": {}}).status_code == 201
    assert c.post("/api/v1/visitor-feedback", json=BODY).status_code == 201
    with sessions() as db:  # 응답 없음 = SQL NULL(옛 의견과 같게). JSON 'null' 문자열로 저장되면 둘이 섞인다
        assert db.scalar(text("SELECT count(*) FROM visitor_feedback WHERE answers IS NULL")) == 2
    everyone = c.get("/api/v1/visitor-feedback", headers=HEADERS).json()
    assert sorted((x["role"] or "", x["answers"] is None) for x in everyone) == [("", True), ("other", True), ("start", False)]
    only = c.get("/api/v1/visitor-feedback", params={"role": "start"}, headers=HEADERS).json()
    assert [x["answers"] for x in only] == [founder["answers"]]
    assert c.get("/api/v1/visitor-feedback", params={"role": "dev"}, headers=HEADERS).json() == []
    assert c.get("/api/v1/visitor-feedback", params={"role": "founder"}, headers=HEADERS).status_code == 422

def test_form_definition_matches_frontend():
    """서버의 입장·질문·선택지 사본 == 화면의 원본(visitorFeedbackForm.json). 한쪽만 고치면 제출이 422 로 막힌다."""
    form = json.loads(FORM.read_text(encoding="utf-8"))
    assert {c["key"]: c["label"] for c in form["categories"]} == CATEGORY_LABELS
    assert set(get_args(VisitorFeedbackIn.model_fields["category"].annotation)) == set(CATEGORY_LABELS)
    frontend = {r["key"]: {"label": r["label"], "questions": {
        q["key"]: {"label": q["label"], "options": {o["key"]: o["label"] for o in q["options"]}} for q in r["questions"]}}
        for r in form["roles"]}
    assert frontend == VISITOR_ROLES
    assert list(get_args(VisitorRole)) == [r["key"] for r in form["roles"]]

def test_feedback_notification_failure(client, monkeypatch):
    c, sessions = client
    monkeypatch.setattr(settings, "feedback_smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "feedback_mail_from", "sender@example.com")
    def fail(*args, **kwargs):
        raise OSError("offline")
    monkeypatch.setattr(service.smtplib, "SMTP", fail)
    r = c.post("/api/v1/visitor-feedback", json=BODY)
    assert r.status_code == 201
    with sessions() as db:
        assert db.get(VisitorFeedback, r.json()["id"]).notification_status == "failed"

def test_feedback_rate_limit(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(settings, "visitor_feedback_hourly_cap", 1)
    assert c.post("/api/v1/visitor-feedback", json=BODY).status_code == 201
    assert c.post("/api/v1/visitor-feedback", json=BODY).status_code == 429

def test_feedback_notification_success(client, monkeypatch):
    c, sessions = client
    monkeypatch.setattr(settings, "feedback_smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "feedback_mail_from", "sender@example.com")
    sent = []
    class SMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def starttls(self, **kwargs): pass
        def login(self, *args): pass
        def send_message(self, message): sent.append(message)
    monkeypatch.setattr(service.smtplib, "SMTP", SMTP)
    r = c.post("/api/v1/visitor-feedback", json=BODY | {"contact": "reply@example.com", "role": "design", "answers": {"blocker": "mobile"}})
    assert r.status_code == 201
    assert len(sent) == 1 and sent[0]["To"] == "seoghyeonbag36@gmail.com"
    assert sent[0]["Subject"].startswith("[PlaceOS 의견] 디자이너 · 개선 요청 · ")
    content = sent[0].get_content()
    assert BODY["message"] in content and "입장: 디자이너" in content and "가장 걸린 것은? 모바일" in content
    with sessions() as db:
        assert db.get(VisitorFeedback, r.json()["id"]).notification_status == "sent"
    url = "/api/v1/visitor-feedback/" + r.json()["id"]
    assert c.delete(url).status_code == 403
    assert c.delete(url, headers=HEADERS).status_code == 204
    assert c.get("/api/v1/visitor-feedback", headers=HEADERS).json() == []
