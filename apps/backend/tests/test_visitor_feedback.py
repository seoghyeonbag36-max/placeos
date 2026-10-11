"""실제 제출 저장·입력 검증·메일 실패·관리자 접근 계약."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.db import Base, get_db
from app.core.config import settings
from app.models.visitor_feedback import VisitorFeedback
from app.services import visitor_feedback as service

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

@pytest.mark.parametrize("changes", [{"message": "   "}, {"message": "a" * 2001}, {"category": "other"}, {"page": "/?token=secret"}, {"page": ""}, {"contact": " "}, {"nps_score": 10}])
def test_feedback_validation(client, changes):
    c, sessions = client
    assert c.post("/api/v1/visitor-feedback", json=BODY | changes).status_code == 422
    with sessions() as db:
        assert list(db.scalars(select(VisitorFeedback))) == []

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
    r = c.post("/api/v1/visitor-feedback", json=BODY | {"contact": "reply@example.com"})
    assert r.status_code == 201
    assert len(sent) == 1 and sent[0]["To"] == "seoghyeonbag36@gmail.com"
    assert BODY["message"] in sent[0].get_content()
    with sessions() as db:
        assert db.get(VisitorFeedback, r.json()["id"]).notification_status == "sent"
    url = "/api/v1/visitor-feedback/" + r.json()["id"]
    assert c.delete(url).status_code == 403
    assert c.delete(url, headers=HEADERS).status_code == 204
    assert c.get("/api/v1/visitor-feedback", headers=HEADERS).json() == []
