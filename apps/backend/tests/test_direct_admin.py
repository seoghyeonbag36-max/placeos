"""직거래 관리자 창구 · 정액 상품 · 공실 진단 잠금 · 탈퇴 파기(2026-11-18). 합성값만 쓴다."""
from __future__ import annotations

from sqlalchemy import func, select

from app.models.direct import DirectInquiry, DirectListing, DirectMessage, ListingVerification, PurchaseIntent
from tests.conftest import DIRECT_REGISTRY


def test_rejected_listing_can_be_fixed_and_resubmitted(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.client.post(f"{env.base}/listings", headers=owner, json=env.listing_body()).json()["id"]
    sub = {"relation": "owner", "registry_number": DIRECT_REGISTRY, "owner_name": "홍길동"}
    env.client.post(f"{env.base}/listings/{lid}/submit", headers=owner, json=sub)
    vid = env.client.get("/api/v1/admin/direct/verifications", headers=env.admin).json()["items"][0]["id"]
    r = env.client.post(f"/api/v1/admin/direct/verifications/{vid}", headers=env.admin,
                        json={"decision": "rejected", "note": "등기 소유자와 이름이 달라요"})
    assert r.json()["listing_status"] == "rejected"
    mine = env.client.get(f"{env.base}/me/listings", headers=owner).json()["items"][0]
    assert mine["verification"]["reviewer_note"] == "등기 소유자와 이름이 달라요"
    assert env.client.post(f"{env.base}/listings/{lid}/submit", headers=owner, json=sub).status_code == 200


def test_purchase_needs_manual_payment_and_price_can_be_pending(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    req = env.client.post(f"{env.base}/purchases", headers=founder,
                          json={"product": "founder_precheck_report", "target_id": lid, "depositor_name": "김창업"})
    assert req.status_code == 201
    body = req.json()
    assert body["status"] == "requested" and body["amount_krw"] is None       # 가격 확정 전
    assert "계좌이체" in body["instructions"]["payment"]
    again = env.client.post(f"{env.base}/purchases", headers=founder,
                            json={"product": "founder_precheck_report", "target_id": lid, "depositor_name": "김창업"})
    assert again.json()["id"] == body["id"]                                      # 같은 신청을 겹쳐 만들지 않는다
    paid = env.client.post(f"/api/v1/admin/direct/purchases/{body['id']}", headers=env.admin,
                           json={"action": "confirm_paid"}).json()
    assert paid["status"] == "paid"                                              # 사람이 이행한 뒤 fulfilled
    assert env.client.post(f"/api/v1/admin/direct/purchases/{body['id']}", headers=env.admin,
                           json={"action": "fulfill"}).json()["status"] == "fulfilled"
    assert env.client.post(f"{env.base}/purchases", headers=founder,
                           json={"product": "founder_watch_30d", "target_id": lid,
                                 "depositor_name": "김창업"}).status_code == 409     # 준비 중 상품은 팔지 않는다
    assert env.client.post(f"{env.base}/purchases", headers=founder,
                           json={"product": "owner_promote_30d", "target_id": lid,
                                 "depositor_name": "김창업"}).status_code == 404     # 남의 매물 광고 금지


def test_diagnosis_detail_opens_after_paid_report(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner, vacant_since="2025-01-01")
    d = env.client.get(f"{env.base}/listings/{lid}/diagnosis", headers=owner).json()
    assert d["full"] is False and d["detail"] is None and d["locked_note"]
    assert d["preview"]["flags"]["long_vacancy"] is True
    assert d["preview"]["tradeoff"]["cheaper"] in ("cut", "vacant", "same")
    pid = env.client.post(f"{env.base}/purchases", headers=owner,
                          json={"product": "owner_diagnosis_report", "target_id": lid, "depositor_name": "홍길동"}).json()["id"]
    env.client.post(f"/api/v1/admin/direct/purchases/{pid}", headers=env.admin, json={"action": "confirm_paid"})
    full = env.client.get(f"{env.base}/listings/{lid}/diagnosis", headers=owner).json()
    assert full["full"] is True and set(full["detail"]) == {"signals", "nearby_vacant", "history"}


def test_account_delete_wipes_direct_rows_and_anonymises_payments(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder, json={"body": "문의"})
    pid = env.client.post(f"{env.base}/purchases", headers=owner,
                          json={"product": "owner_promote_30d", "target_id": lid, "depositor_name": "홍길동"}).json()["id"]
    assert env.client.delete("/api/v1/auth/me", headers=owner).status_code in (200, 204)
    with env.session() as db:
        assert db.execute(select(func.count()).select_from(DirectListing)).scalar_one() == 0
        assert db.execute(select(func.count()).select_from(ListingVerification)).scalar_one() == 0
        assert db.execute(select(func.count()).select_from(DirectInquiry)).scalar_one() == 0
        assert db.execute(select(func.count()).select_from(DirectMessage)).scalar_one() == 0
        p = db.get(PurchaseIntent, pid)
        assert p is not None and p.user_id is None and p.depositor_name == ""


def test_founder_delete_removes_sent_inquiries(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder, json={"body": "문의"})
    assert env.client.delete("/api/v1/auth/me", headers=founder).status_code in (200, 204)
    assert env.client.get(f"{env.base}/inbox", headers=owner).json()["as_owner"] == []
    assert env.client.get(f"{env.base}/listings/{lid}").status_code == 200       # 남의 매물은 그대로
