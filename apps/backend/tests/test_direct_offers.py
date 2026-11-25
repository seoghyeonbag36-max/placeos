"""조건 제안서 · 팝업·단기 신청 · 계약 진행 방법 (2026-11-21 · docs/decision-founder-brief-2026-11-21.md). 합성값만 쓴다.

잠그는 것: 제안은 창업자가 적고 건물주가 받거나 거절한다(PlaceOS 는 값을 권하지 않는다 · L2) · 받음은 계약이 아니다 ·
제안·수락·계약 진행 방법 어디에도 돈이 붙지 않는다(L1) · 제휴 공인중개사는 정액 제휴만.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.services import direct_connect, direct_purchases


def _soon(days: int = 14) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _popup_listing(env, owner, **over) -> str:
    return env.publish(owner, deal_type="lease_popup", popup_daily_manwon=30, popup_min_days=3, popup_max_days=30,
                       **over)


def test_lease_offer_is_proposed_by_founder_and_answered_by_owner(direct_env):
    env = direct_env
    owner, founder, stranger = (env.signup(e) for e in ("owner@example.com", "founder@example.com", "s@example.com"))
    lid = env.publish(owner)
    r = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                        json={"kind": "offer", "body": "월세 220에 렌트프리 3개월이면 바로 계약 이야기하고 싶어요",
                              "offer": {"rent_manwon": 220, "rent_free_months": 3, "term_months": 36,
                                        "start_date": _soon()}})
    assert r.status_code == 201, r.text
    t = r.json()
    iid, oid = t["id"], t["offers"][0]["id"]
    assert t["kind"] == "offer" and t["offers"][0]["status"] == "proposed" and t["offers"][0]["rent_manwon"] == 220
    path = f"{env.base}/inquiries/{iid}/offers/{oid}"
    assert env.client.post(path, headers=founder, json={"action": "accept"}).status_code == 403   # 창업자는 못 받는다
    assert env.client.post(path, headers=stranger, json={"action": "accept"}).status_code == 404
    ok = env.client.post(path, headers=owner, json={"action": "accept"})
    assert ok.status_code == 200 and ok.json()["offers"][0]["status"] == "accepted"
    assert "계약 아님" in ok.json()["offers"][0]["status_label"]
    assert env.client.post(path, headers=owner, json={"action": "decline"}).status_code == 409      # 이미 답했다
    # 건물주는 조건 제안서를 쓰지 않는다
    assert env.client.post(f"{env.base}/inquiries/{iid}/offers", headers=owner,
                           json={"kind": "lease", "offer": {"rent_manwon": 230}}).status_code == 403


def test_new_offer_supersedes_the_pending_one_but_not_an_answered_one(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    t = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                        json={"kind": "offer", "body": "제안", "offer": {"rent_manwon": 200}}).json()
    iid = t["id"]
    t = env.client.post(f"{env.base}/inquiries/{iid}/offers", headers=founder,
                        json={"kind": "lease", "offer": {"rent_manwon": 210}}).json()
    assert [o["status"] for o in t["offers"]] == ["superseded", "proposed"]
    withdrawn = env.client.post(f"{env.base}/inquiries/{iid}/offers/{t['offers'][1]['id']}", headers=founder,
                                json={"action": "withdraw"}).json()
    assert [o["status"] for o in withdrawn["offers"]] == ["superseded", "withdrawn"]


def test_popup_request_follows_the_owners_popup_terms(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lease_only = env.publish(owner)
    popup_ok = _popup_listing(env, owner, unit_label="202호")
    base = {"kind": "popup", "body": "주말 팝업으로 먼저 해 보고 싶어요"}
    assert env.client.post(f"{env.base}/listings/{lease_only}/inquiries", headers=founder,
                           json={**base, "offer": {"popup_days": 5, "start_date": _soon()}}).status_code == 409
    assert env.client.post(f"{env.base}/listings/{popup_ok}/inquiries", headers=founder,
                           json={**base, "offer": {"popup_days": 2, "start_date": _soon()}}).status_code == 422
    past = (date.today() - timedelta(days=1)).isoformat()
    assert env.client.post(f"{env.base}/listings/{popup_ok}/inquiries", headers=founder,
                           json={**base, "offer": {"popup_days": 5, "start_date": past}}).status_code == 422
    r = env.client.post(f"{env.base}/listings/{popup_ok}/inquiries", headers=founder,
                        json={**base, "offer": {"popup_days": 5, "start_date": _soon()}})
    assert r.status_code == 201, r.text
    o = r.json()["offers"][0]
    assert o["kind"] == "popup" and o["popup_daily_manwon"] == 30 and o["popup_total_manwon"] == 150


def test_lease_offer_on_a_popup_only_listing_is_refused(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner, deal_type="popup", monthly_rent_manwon=0, popup_daily_manwon=25)
    r = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                        json={"kind": "offer", "body": "장기로", "offer": {"rent_manwon": 100}})
    assert r.status_code == 409


def test_offers_carry_no_fee_fields(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    for extra in ({"fee": 10}, {"commission_rate": 0.009}, {"success_fee_manwon": 50}):
        r = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                            json={"kind": "offer", "body": "제안", "offer": {"rent_manwon": 200, **extra}})
        assert r.status_code == 422, extra


def test_contract_path_is_a_record_and_partner_brokers_are_flat_only(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    iid = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder, json={"body": "문의"}).json()["id"]
    t = env.client.post(f"{env.base}/inquiries/{iid}/contract-path", headers=owner, json={"path": "broker"}).json()
    assert t["contract_path"] == "broker" and t["brokers"] == [] and "정액 제휴만" in t["brokers_note"]
    assert len(t["contract_guide"]) >= 4 and any("확정일자" in g for g in t["contract_guide"])
    assert env.client.post(f"{env.base}/inquiries/{iid}/contract-path", headers=owner,
                           json={"path": "platform"}).status_code == 422
    for b in direct_connect.PARTNER_BROKERS:
        assert b.get("deal_model") == "flat_partnership", b
        assert not [k for k in b if any(w in k for w in ("fee", "commission", "share", "rate"))], b


def test_no_product_is_tied_to_offers_or_contracts(direct_env):
    """L1 — 제안·수락·성사에 붙는 상품이 없다. 상품의 대상은 매물뿐이다."""
    for key, p in direct_purchases.PRODUCTS.items():
        assert not any(w in key for w in ("offer", "contract", "deal", "brief", "lead", "invite")), key
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    t = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                        json={"kind": "offer", "body": "제안", "offer": {"rent_manwon": 200}}).json()
    r = env.client.post(f"{env.base}/purchases", headers=founder,
                        json={"product": "founder_precheck_report", "target_id": t["offers"][0]["id"],
                              "depositor_name": "합성"})
    assert r.status_code == 404


def test_closed_threads_take_no_offers(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    lid = env.publish(owner)
    t = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                        json={"kind": "offer", "body": "제안", "offer": {"rent_manwon": 200}}).json()
    env.client.post(f"{env.base}/inquiries/{t['id']}/outcome", headers=founder, json={"outcome": "not_contracted"})
    assert env.client.post(f"{env.base}/inquiries/{t['id']}/offers", headers=founder,
                           json={"kind": "lease", "offer": {"rent_manwon": 190}}).status_code == 409
    assert env.client.post(f"{env.base}/inquiries/{t['id']}/offers/{t['offers'][0]['id']}", headers=owner,
                           json={"action": "accept"}).status_code == 409


def test_funnel_counts_floor_bands_briefs_offers_and_paths(direct_env):
    env = direct_env
    owner, founder = env.signup("owner@example.com"), env.signup("founder@example.com")
    env.publish(owner)                                    # 2층
    lid1 = env.publish(owner, floor=1, unit_label="101호")
    t = env.client.post(f"{env.base}/listings/{lid1}/inquiries", headers=founder,
                        json={"kind": "offer", "body": "제안", "offer": {"rent_manwon": 200}}).json()
    env.client.post(f"{env.base}/inquiries/{t['id']}/contract-path", headers=founder, json={"path": "direct"})
    f = env.client.get("/api/v1/admin/direct/funnel", headers=env.admin).json()
    assert f["public_listings_by_floor_band"] == {"first": 1, "upper": 1, "basement": 0}
    assert {"kind": "lease", "status": "proposed", "n": 1} in f["offers"]
    assert f["contract_paths"]["direct"] == 1 and f["inquiries_by_initiator"] == {"founder": 1}
    assert f["briefs"]["live"] == 0
