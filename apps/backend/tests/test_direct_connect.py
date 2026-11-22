"""직거래 연결 — 참여자만 · 방문 제안/확정 · 하루 상한 · 결과 자기보고 · 알림(2026-11-18). 합성값만 쓴다."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services import direct_connect


def _future(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(microsecond=0).isoformat()


def test_question_thread_is_visible_only_to_the_two_parties(direct_env):
    env = direct_env
    owner, founder, stranger = (env.signup(e) for e in ("owner@example.com", "founder@example.com",
                                                        "stranger@example.com"))
    lid = env.publish(owner)
    r = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                        json={"kind": "question", "body": "주차가 되나요?", "industry_key": "education"})
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    assert "중개" in r.json()["notice"]
    inbox = env.client.get(f"{env.base}/inbox", headers=owner).json()
    assert [i["id"] for i in inbox["as_owner"]] == [iid]
    assert env.client.get(f"{env.base}/inquiries/{iid}", headers=stranger).status_code == 404
    reply = env.client.post(f"{env.base}/inquiries/{iid}/messages", headers=owner, json={"body": "2대 가능해요"})
    assert reply.status_code == 201
    seen = env.client.get(f"{env.base}/inquiries/{iid}", headers=founder).json()
    assert [m["from"] for m in seen["messages"]] == ["founder", "owner"]


def test_visit_proposed_by_founder_confirmed_by_owner(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    slots = [_future(48), _future(72)]
    r = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                        json={"kind": "visit", "body": "보러 가고 싶어요", "visit_slots": slots})
    iid = r.json()["id"]
    stored = r.json()["visit_slots"]
    assert env.client.post(f"{env.base}/inquiries/{iid}/visit", headers=founder,
                           json={"action": "confirm", "slot": stored[0]}).status_code == 403
    ok = env.client.post(f"{env.base}/inquiries/{iid}/visit", headers=owner, json={"action": "confirm", "slot": stored[1]})
    assert ok.status_code == 200 and ok.json()["status"] == "scheduled"
    past = env.client.post(f"{env.base}/inquiries/{iid}/visit", headers=founder,
                           json={"action": "propose", "slots": ["2020-01-01T10:00:00+00:00"]})
    assert past.status_code == 422


def test_no_inquiry_to_own_or_unpublished_listing(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    assert env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=owner,
                           json={"body": "자문"}).status_code == 400
    draft = env.client.post(f"{env.base}/listings", headers=owner, json=env.listing_body()).json()["id"]
    assert env.client.post(f"{env.base}/listings/{draft}/inquiries", headers=founder,
                           json={"body": "문의"}).status_code == 404


def test_daily_cap_on_new_inquiries(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    for _ in range(direct_connect.MAX_NEW_PER_DAY):
        assert env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                               json={"body": "문의"}).status_code == 201
    assert env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                           json={"body": "문의"}).status_code == 429


def test_outcome_self_report_closes_the_thread(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    iid = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder, json={"body": "문의"}).json()["id"]
    done = env.client.post(f"{env.base}/inquiries/{iid}/outcome", headers=founder, json={"outcome": "contracted"})
    assert done.status_code == 200 and done.json()["status"] == "closed"
    assert env.client.post(f"{env.base}/inquiries/{iid}/messages", headers=owner,
                           json={"body": "감사합니다"}).status_code == 409
    funnel = env.client.get("/api/v1/admin/direct/funnel", headers=env.admin).json()
    assert funnel["outcomes"]["contracted"] == 1 and funnel["inquiries_total"] == 1


def test_owner_notice_mail_is_disabled_without_smtp():
    assert direct_connect.notify_owner("owner@example.com") == "disabled"
    assert direct_connect.notify_owner(None) == "disabled"
