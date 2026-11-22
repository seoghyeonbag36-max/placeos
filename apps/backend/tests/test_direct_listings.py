"""직거래 매물 — 필수 정보(L4) · 확인 뒤 공개(L3) · 마스킹(L5) · 광고 표시(L6) · 신고 자동 숨김(L9) (2026-11-18).

아래 주소·이름·번호는 테스트 전용 합성값이다.
"""
from __future__ import annotations

from tests.conftest import DIRECT_REGISTRY


def test_submit_requires_the_legal_fields(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.client.post(f"{env.base}/listings", headers=owner, json={}).json()["id"]
    r = env.client.post(f"{env.base}/listings/{lid}/submit", headers=owner,
                        json={"relation": "owner", "registry_number": DIRECT_REGISTRY, "owner_name": "홍길동"})
    assert r.status_code == 422
    missing = set(r.json()["detail"]["missing"])
    assert {"address", "area_m2", "use_type", "floor", "price"} <= missing


def test_agent_needs_delegation_and_registry_format(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.client.post(f"{env.base}/listings", headers=owner, json=env.listing_body()).json()["id"]
    bad = env.client.post(f"{env.base}/listings/{lid}/submit", headers=owner,
                          json={"relation": "owner", "registry_number": "abc", "owner_name": "홍길동"})
    assert bad.status_code == 422
    agent = env.client.post(f"{env.base}/listings/{lid}/submit", headers=owner,
                            json={"relation": "agent", "registry_number": DIRECT_REGISTRY, "owner_name": "홍길동"})
    assert agent.status_code == 422 and "delegation_note" in agent.json()["detail"]["missing"]


def test_not_public_until_owner_relation_is_verified(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.client.post(f"{env.base}/listings", headers=owner, json=env.listing_body()).json()["id"]
    env.client.post(f"{env.base}/listings/{lid}/submit", headers=owner,
                    json={"relation": "owner", "registry_number": DIRECT_REGISTRY, "owner_name": "홍길동"})
    assert env.client.get(f"{env.base}/listings/{lid}").status_code == 404
    assert env.client.get(f"{env.base}/listings", params={"district_id": "garosugil"}).json()["n"] == 0
    own = env.client.get(f"{env.base}/listings/{lid}", headers=owner).json()
    assert own["mine"] is True and own["status"] == "pending"

    vid = env.client.get("/api/v1/admin/direct/verifications", headers=env.admin).json()["items"][0]["id"]
    env.client.post(f"/api/v1/admin/direct/verifications/{vid}", headers=env.admin, json={"decision": "verified"})
    public = env.client.get(f"{env.base}/listings/{lid}")
    assert public.status_code == 200 and public.json()["verified"] is True
    assert env.client.get(f"{env.base}/listings", params={"district_id": "garosugil"}).json()["n"] == 1


def test_owner_identity_is_masked_outside_admin(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    public = env.client.get(f"{env.base}/listings/{lid}").text
    assert "홍길동" not in public and DIRECT_REGISTRY not in public and "012345" not in public
    own = env.client.get(f"{env.base}/me/listings", headers=owner).json()["items"][0]
    assert own["verification"]["registry_masked"].endswith("2345")
    assert DIRECT_REGISTRY not in str(own) and "홍길동" not in str(own)


def test_only_the_owner_can_edit_or_delete(direct_env):
    env = direct_env
    owner, other = env.signup("owner@example.com"), env.signup("other@example.com")
    lid = env.publish(owner)
    assert env.client.patch(f"{env.base}/listings/{lid}", headers=other,
                            json={"monthly_rent_manwon": 1}).status_code == 404
    assert env.client.delete(f"{env.base}/listings/{lid}", headers=other).status_code == 404
    assert env.client.delete(f"{env.base}/listings/{lid}", headers=owner).status_code == 204
    assert env.client.get(f"{env.base}/listings/{lid}").status_code == 404


def test_core_field_change_needs_reverification_but_price_does_not(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    price = env.client.patch(f"{env.base}/listings/{lid}", headers=owner, json={"monthly_rent_manwon": 230}).json()
    assert price["status"] == "published"
    moved = env.client.patch(f"{env.base}/listings/{lid}", headers=owner, json={"floor": 3}).json()
    assert moved["status"] == "pending"
    assert env.client.get(f"{env.base}/listings/{lid}").status_code == 404


def test_promoted_listing_is_labelled_ad_and_listed_first(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    plain = env.publish(owner, monthly_rent_manwon=100)
    promoted = env.publish(owner, monthly_rent_manwon=900, address="서울 강남구 신사동 000-1")
    pid = env.client.post(f"{env.base}/purchases", headers=owner,
                          json={"product": "owner_promote_30d", "target_id": promoted, "depositor_name": "홍길동"}).json()["id"]
    r = env.client.post(f"/api/v1/admin/direct/purchases/{pid}", headers=env.admin, json={"action": "confirm_paid"})
    assert r.status_code == 200 and r.json()["status"] == "fulfilled"
    items = env.client.get(f"{env.base}/listings", params={"district_id": "garosugil"}).json()["items"]
    assert [i["id"] for i in items] == [promoted, plain]
    assert items[0]["is_ad"] is True and items[1]["is_ad"] is False


def test_three_reporters_hide_listing_until_admin_review(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    for i in range(3):
        reporter = env.signup(f"r{i}@example.com")
        r = env.client.post(f"{env.base}/listings/{lid}/report", headers=reporter, json={"reason": "fake"})
        assert r.status_code == 201
    assert r.json()["auto_hidden"] is True
    assert env.client.get(f"{env.base}/listings/{lid}").status_code == 404
    # 건물주가 스스로 다시 게시할 수 없다 — 관리자 확인 뒤에만
    assert env.client.post(f"{env.base}/listings/{lid}/status", headers=owner,
                           json={"action": "resume"}).status_code == 409
    rid = env.client.get("/api/v1/admin/direct/reports", headers=env.admin).json()["items"][0]["id"]
    env.client.post(f"/api/v1/admin/direct/reports/{rid}", headers=env.admin, json={"action": "restore_listing"})
    assert env.client.get(f"{env.base}/listings/{lid}").status_code == 200


def test_filters_for_the_segments_brokers_skip(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    first = env.publish(owner, floor=1, address="서울 강남구 신사동 000-2")
    upper_popup = env.publish(owner, floor=3, deal_type="lease_popup", popup_daily_manwon=30, popup_min_days=3,
                              vacant_since="2025-01-01", address="서울 강남구 신사동 000-3")
    q = lambda **p: [i["id"] for i in env.client.get(f"{env.base}/listings",  # noqa: E731
                                                     params={"district_id": "garosugil", **p}).json()["items"]]
    assert q(floor_band="first") == [first]
    assert q(floor_band="upper") == [upper_popup]
    assert q(popup=True) == [upper_popup]
    assert q(long_vacancy=True) == [upper_popup]
    detail = env.client.get(f"{env.base}/listings/{upper_popup}", params={"industry": "education"}).json()
    assert detail["flags"]["long_vacancy"] is True and detail["flags"]["popup_ok"] is True
    assert any("반긴다" in r for r in detail["reasons"])
