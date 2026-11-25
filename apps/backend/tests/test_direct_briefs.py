"""입점 희망서 — 단계별 공개 · 건물주 게이트 · 묶음 수요 n≥3 · 건물주 제안 · 조건표 · 요구 판매량 · 탈퇴 · 신용 점수 없음
(2026-11-21 · docs/decision-founder-brief-2026-11-21.md). 값은 전부 합성이다.

이 파일이 빨개지면 「누가 무엇을 보나」가 깨진 것이다 — ③ 비공개 칸(객단가 등)이 건물주에게 새거나, 희망서가 매물 없는
건물주에게 보이거나, 3명 미만 묶음이 숫자로 나가거나, 신용 점수 같은 칸이 생겼다.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from app.models.direct import BriefDisclosure, DirectBrief, DirectInquiry, DirectOffer
from app.services import direct_briefs, direct_connect, direct_matching
from app.services import districts as districts_svc

PRIVATE_KEYS = ("unit_price_won", "variable_cost_pct", "other_fixed_manwon", "open_days", "target_daily_units",
                "required_sales")
CONSENT_KEYS = ("summary", "funding_total_manwon", "funding_own_manwon")
SCORE_WORDS = ("score", "credit", "grade", "rating", "rank")


def _soon(days: int = 30) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def brief_body(**over) -> dict:
    body = dict(industry_key="cafe", area_min_m2=40, area_max_m2=90, floor_bands=["first", "upper"],
                needs_exhaust=True, needs_water=True, rent_cap_manwon=240, deposit_cap_manwon=3000,
                desired_start=_soon(), district_ids=["garosugil"], popup_first=True,
                summary="합성 사업 개요 — 디저트 카페", business_stage="pre", funding_total_manwon=8000,
                funding_own_manwon=5000, unit_price_won=6000, variable_cost_pct=35, other_fixed_manwon=300,
                open_days=26, target_daily_units=70)
    body.update(over)
    return body


def _post_brief(env, headers, **over) -> dict:
    r = env.client.patch(f"{env.base}/me/brief", headers=headers, json=brief_body(**over))
    assert r.status_code == 200, r.text
    r = env.client.post(f"{env.base}/me/brief/status", headers=headers, json={"action": "activate"})
    assert r.status_code == 200, r.text
    return r.json()["brief"]


def _keys(obj) -> set[str]:
    out: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            out |= _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _keys(v)
    return out


def _other_district() -> str:
    return next(d for d in districts_svc.PAGES_BY_ID if d != "garosugil")


# ── 쓰기 ───────────────────────────────────────────────────────────────────

def test_draft_then_activate_requires_every_required_field(direct_env):
    env = direct_env
    founder = env.signup("founder@example.com")
    r = env.client.patch(f"{env.base}/me/brief", headers=founder, json={"industry_key": "cafe"})
    assert r.status_code == 200 and r.json()["brief"]["status"] == "draft"
    assert set(r.json()["brief"]["missing"]) == {"area", "floor_bands", "rent_cap", "deposit_cap", "desired_start",
                                                 "district_ids"}
    r = env.client.post(f"{env.base}/me/brief/status", headers=founder, json={"action": "activate"})
    assert r.status_code == 422 and "district_ids" in r.json()["detail"]["missing"]
    brief = _post_brief(env, founder)
    assert brief["status"] == "active" and brief["visible"] is True
    expires = datetime.fromisoformat(brief["expires_at"])
    assert timedelta(days=89) < expires - datetime.now(timezone.utc) <= timedelta(days=direct_briefs.BRIEF_TTL_DAYS)


def test_validation_rejects_unknown_values_and_credit_fields(direct_env):
    env = direct_env
    founder = env.signup("founder@example.com")
    bad = [
        {"industry_key": "casino"},
        {"district_ids": ["not-a-district"]},
        {"district_ids": ["garosugil", "a", "b", "c"]},          # 최대 3곳
        {"area_min_m2": 90, "area_max_m2": 40},
        {"funding_total_manwon": 100, "funding_own_manwon": 500},
        {"credit_score": 700},                                   # 신용 점수 칸은 받지 않는다(extra=forbid)
        {"floor_bands": ["rooftop"]},
    ]
    for body in bad:
        assert env.client.patch(f"{env.base}/me/brief", headers=founder, json=body).status_code == 422, body


def test_losing_a_required_field_hides_an_active_brief(direct_env):
    env = direct_env
    founder = env.signup("founder@example.com")
    _post_brief(env, founder)
    r = env.client.patch(f"{env.base}/me/brief", headers=founder, json={"district_ids": []})
    assert r.json()["brief"]["status"] == "draft" and r.json()["brief"]["visible"] is False


# ── 건물주 게이트 · 단계별 공개 ─────────────────────────────────────────────

def test_owner_without_a_verified_listing_in_that_district_sees_nothing(direct_env):
    env = direct_env
    founder, owner, far_owner = (env.signup(e) for e in ("founder@example.com", "owner@example.com", "far@example.com"))
    brief = _post_brief(env, founder)
    # 매물이 아예 없는 건물주 → 403
    r = env.client.get(f"{env.base}/me/owner/briefs", headers=owner)
    assert r.status_code == 403
    # 다른 상권에만 확인 매물이 있는 건물주 → 목록에 없고, 한 장 보기는 있는지도 모르게 404
    env.publish(far_owner, district_id=_other_district())
    assert env.client.get(f"{env.base}/me/owner/briefs", headers=far_owner).json()["n"] == 0
    assert env.client.get(f"{env.base}/me/owner/briefs/{brief['id']}", headers=far_owner).status_code == 404
    # 확인 전(제출만 한) 매물은 게이트를 열지 않는다
    draft = env.client.post(f"{env.base}/listings", headers=owner, json=env.listing_body()).json()["id"]
    env.client.post(f"{env.base}/listings/{draft}/submit", headers=owner,
                    json={"relation": "owner", "registry_number": "1101-2026-099999", "owner_name": "합성"})
    assert env.client.get(f"{env.base}/me/owner/briefs", headers=owner).status_code == 403


def test_owner_sees_only_stage_one_until_the_founder_discloses(direct_env):
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    brief = _post_brief(env, founder)
    lid = env.publish(owner)
    listing = env.client.get(f"{env.base}/me/owner/briefs", headers=owner).json()
    assert listing["n"] == 1
    item = listing["items"][0]
    text = json.dumps(listing, ensure_ascii=False)
    assert "founder@example.com" not in text
    assert not set(PRIVATE_KEYS + CONSENT_KEYS) & _keys(listing)
    assert item["industry_label"] and item["rent_cap_manwon"] == 240 and item["my_listings"][0]["listing_id"] == lid
    assert "required_sales" not in item["my_listings"][0]["fit"]
    one = env.client.get(f"{env.base}/me/owner/briefs/{brief['id']}", headers=owner).json()
    assert one["disclosed"] is False and one["consent"] is None

    # 창업자가 먼저 문의한 대화에는 희망서를 말없이 붙이지 않는다(협상 상대에게 예산 상한을 동의 없이 넘기지 않게)
    iid = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                          json={"body": "배기 덕트가 있나요?", "industry_key": "cafe"}).json()["id"]
    t_owner = env.client.get(f"{env.base}/inquiries/{iid}", headers=owner).json()
    assert t_owner["brief"] is None
    # 창업자가 그 대화에서 직접 열면 → 그 건물주에게만 ① + ② 가 보인다(③ 은 끝까지 없다)
    assert env.client.post(f"{env.base}/inquiries/{iid}/disclose", headers=owner).status_code == 403
    opened = env.client.post(f"{env.base}/inquiries/{iid}/disclose", headers=founder)
    assert opened.status_code == 200 and opened.json()["brief_disclosed"] is True
    t_owner = env.client.get(f"{env.base}/inquiries/{iid}", headers=owner).json()
    assert t_owner["brief"]["consent"]["summary"].startswith("합성 사업 개요")
    assert not set(PRIVATE_KEYS) & _keys(t_owner)
    one = env.client.get(f"{env.base}/me/owner/briefs/{brief['id']}", headers=owner).json()
    assert one["disclosed"] is True and one["consent"]["funding_own_manwon"] == 5000
    assert not set(PRIVATE_KEYS) & _keys(one)
    # 거두면 다시 닫힌다 — 대화에서도, 희망서 한 장에서도
    env.client.delete(f"{env.base}/inquiries/{iid}/disclose", headers=founder)
    assert env.client.get(f"{env.base}/me/owner/briefs/{brief['id']}", headers=owner).json()["consent"] is None
    assert env.client.get(f"{env.base}/inquiries/{iid}", headers=owner).json()["brief"] is None


def test_owner_invite_thread_carries_stage_one_only(direct_env):
    """건물주가 희망서를 보고 먼저 제안한 대화에는 ① 이 붙는다(그 건물주는 이미 그 희망서를 볼 수 있다). ② 는 창업자가 열 때만."""
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    brief = _post_brief(env, founder)
    lid = env.publish(owner)
    t = env.client.post(f"{env.base}/me/owner/briefs/{brief['id']}/invite", headers=owner,
                        json={"listing_id": lid, "body": "제안"}).json()
    assert t["brief"]["code"] == brief["code"] and t["brief"]["consent"] is None
    assert not set(PRIVATE_KEYS + CONSENT_KEYS) & _keys(t["brief"])


def test_founder_inquiry_outside_desired_districts_never_attaches_the_brief(direct_env):
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    _post_brief(env, founder)                                         # 희망 상권 = garosugil
    far = env.publish(owner, district_id=_other_district())
    iid = env.client.post(f"{env.base}/listings/{far}/inquiries", headers=founder, json={"body": "문의"}).json()["id"]
    assert env.client.get(f"{env.base}/inquiries/{iid}", headers=owner).json()["brief"] is None


def test_consent_closes_with_the_conversation_and_can_always_be_revoked(direct_env):
    """리뷰 반영(2026-11-21) — 대화가 끝나거나 매물이 지워지면 ② 가 닫히고, 대화가 없어도 창업자가 거둘 수 있다."""
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    brief = _post_brief(env, founder)
    lid = env.publish(owner)
    iid = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder, json={"body": "문의"}).json()["id"]
    env.client.post(f"{env.base}/inquiries/{iid}/disclose", headers=founder)
    # 건물주가 대화를 끝내면(결과 자기보고) 공개 동의도 닫힌다
    env.client.post(f"{env.base}/inquiries/{iid}/outcome", headers=owner, json={"outcome": "not_contracted"})
    with env.session() as db:
        assert db.query(BriefDisclosure).count() == 0
    assert env.client.get(f"{env.base}/me/owner/briefs/{brief['id']}", headers=owner).json()["consent"] is None
    # 끝난 대화에서는 새로 열 수 없고, 거두기는 된다
    assert env.client.post(f"{env.base}/inquiries/{iid}/disclose", headers=founder).status_code == 409
    assert env.client.delete(f"{env.base}/inquiries/{iid}/disclose", headers=founder).status_code == 200

    # 매물이 지워져 대화가 사라져도 동의가 남지 않는다
    lid2 = env.publish(owner, unit_label="202호")
    iid2 = env.client.post(f"{env.base}/listings/{lid2}/inquiries", headers=founder, json={"body": "문의"}).json()["id"]
    env.client.post(f"{env.base}/inquiries/{iid2}/disclose", headers=founder)
    assert env.client.delete(f"{env.base}/listings/{lid2}", headers=owner).status_code == 204
    with env.session() as db:
        assert db.query(BriefDisclosure).count() == 0

    # 대화 없이도 희망서 화면에서 거둔다
    lid3 = env.publish(owner, unit_label="203호")
    iid3 = env.client.post(f"{env.base}/listings/{lid3}/inquiries", headers=founder, json={"body": "문의"}).json()["id"]
    env.client.post(f"{env.base}/inquiries/{iid3}/disclose", headers=founder)
    mine = env.client.get(f"{env.base}/me/brief", headers=founder).json()["brief"]
    assert mine["disclosed_n"] == 1 and mine["disclosures"][0]["open_threads"] == 1
    assert mine["disclosures"][0]["listings"] and "founder@example.com" not in json.dumps(mine["disclosures"])
    did = mine["disclosures"][0]["id"]
    stranger = env.signup("stranger@example.com")
    assert env.client.delete(f"{env.base}/me/brief/disclosures/{did}", headers=stranger).status_code == 404
    r = env.client.delete(f"{env.base}/me/brief/disclosures/{did}", headers=founder)
    assert r.status_code == 200 and r.json()["brief"]["disclosed_n"] == 0
    assert env.client.get(f"{env.base}/inquiries/{iid3}", headers=owner).json()["brief"] is None


def test_expired_or_paused_briefs_disappear_for_owners(direct_env):
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    brief = _post_brief(env, founder)
    env.publish(owner)
    env.client.post(f"{env.base}/me/brief/status", headers=founder, json={"action": "pause"})
    assert env.client.get(f"{env.base}/me/owner/briefs", headers=owner).json()["n"] == 0
    env.client.post(f"{env.base}/me/brief/status", headers=founder, json={"action": "activate"})
    assert env.client.get(f"{env.base}/me/owner/briefs", headers=owner).json()["n"] == 1
    with env.session() as db:
        row = db.get(DirectBrief, brief["id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    assert env.client.get(f"{env.base}/me/owner/briefs", headers=owner).json()["n"] == 0
    mine = env.client.get(f"{env.base}/me/brief", headers=founder).json()["brief"]
    assert mine["expired"] is True and mine["visible"] is False


# ── 묶음 수요(공개) ─────────────────────────────────────────────────────────

def test_public_demand_hides_counts_below_three_and_never_names_small_groups(direct_env):
    env = direct_env
    founders = [env.signup(f"f{i}@example.com") for i in range(4)]
    for h in founders[:2]:
        _post_brief(env, h)
    d = env.client.get(f"{env.base}/demand", params={"district_id": "garosugil"}).json()
    assert d["total"] is None and d["suppressed"] is True and d["by_industry"] == [] and d["rent_cap_median_manwon"] is None
    _post_brief(env, founders[2])
    _post_brief(env, founders[3], industry_key="bar", rent_cap_manwon=400)
    d = env.client.get(f"{env.base}/demand", params={"district_id": "garosugil"}).json()
    assert d["total"] == 4
    assert [(r["industry_key"], r["founders"]) for r in d["by_industry"]] == [("cafe", 3)]   # 술집 1명은 이름도 없다
    assert d["popup_first"] == 4
    # 공개 경로에는 예산 상한 중앙값이 없다(리뷰 반영 — n=3 이면 한 사람의 상한 그대로 · 계정 하나로 캐낼 수 있다)
    assert d["rent_cap_median_manwon"] is None and d["deposit_cap_median_manwon"] is None and d["caps_shown"] is False
    assert d["notice"].startswith("PlaceOS는 부동산 중개를 하지 않으며")
    assert "f0@example.com" not in json.dumps(d, ensure_ascii=False)
    assert env.client.get(f"{env.base}/demand", params={"district_id": "nowhere"}).status_code == 404


def test_cap_medians_only_reach_owners_with_a_verified_listing_there(direct_env):
    env = direct_env
    for i in range(3):
        _post_brief(env, env.signup(f"f{i}@example.com"), rent_cap_manwon=200 + i * 20)
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    diag = env.client.get(f"{env.base}/listings/{lid}/diagnosis", headers=owner).json()
    assert diag["preview"]["brief_demand"]["rent_cap_median_manwon"] == 220
    # 확인 전(작성 중) 매물로 상권만 적어서는 중앙값을 받지 못한다
    draft = env.client.post(f"{env.base}/listings", headers=owner, json=env.listing_body(unit_label="301호")).json()["id"]
    diag = env.client.get(f"{env.base}/listings/{draft}/diagnosis", headers=owner).json()
    assert diag["preview"]["brief_demand"]["total"] == 3 and diag["preview"]["brief_demand"]["rent_cap_median_manwon"] is None
    # 공개 /listings/{id}/fit 의 희망서 묶음에도 중앙값이 없다
    fit = env.client.get(f"{env.base}/listings/{lid}/fit").json()
    assert fit["for_owner"]["briefs"]["rent_cap_median_manwon"] is None


def test_demand_threshold_matches_inquiry_signal_threshold():
    assert direct_briefs.DEMAND_MIN_N == direct_matching.DEMAND_MIN_N


# ── 건물주 제안(invite) ─────────────────────────────────────────────────────

def test_owner_invite_opens_a_thread_without_spending_the_founders_cap(direct_env):
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    brief = _post_brief(env, founder)
    lid = env.publish(owner)
    r = env.client.post(f"{env.base}/me/owner/briefs/{brief['id']}/invite", headers=owner,
                        json={"listing_id": lid, "body": "2층 66㎡, 렌트프리 2개월 가능해요"})
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["kind"] == "invite" and t["initiated_by"] == "owner" and t["role"] == "owner"
    # 같은 매물·같은 창업자에게 두 번은 안 된다
    again = env.client.post(f"{env.base}/me/owner/briefs/{brief['id']}/invite", headers=owner,
                            json={"listing_id": lid, "body": "다시"})
    assert again.status_code == 409
    # 창업자 문의함에 보이고, 창업자 하루 문의 상한은 그대로다
    box = env.client.get(f"{env.base}/inbox", headers=founder).json()
    assert [i["kind"] for i in box["as_founder"]] == ["invite"]
    other_owner = env.signup("owner2@example.com")
    lid2 = env.publish(other_owner)
    for _ in range(direct_connect.MAX_NEW_PER_DAY):
        assert env.client.post(f"{env.base}/listings/{lid2}/inquiries", headers=founder,
                               json={"body": "문의"}).status_code == 201


def test_invite_respects_founder_choice_and_desired_districts(direct_env):
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    brief = _post_brief(env, founder, accept_invites=False)
    lid = env.publish(owner)
    r = env.client.post(f"{env.base}/me/owner/briefs/{brief['id']}/invite", headers=owner,
                        json={"listing_id": lid, "body": "제안"})
    assert r.status_code == 409
    env.client.patch(f"{env.base}/me/brief", headers=founder, json={"accept_invites": True})
    # 희망 상권 밖 매물로는 제안하지 못한다(같은 건물주라도)
    far = env.publish(owner, district_id=_other_district())
    assert env.client.post(f"{env.base}/me/owner/briefs/{brief['id']}/invite", headers=owner,
                           json={"listing_id": far, "body": "다른 상권 매물"}).status_code == 409
    # 남의 매물로는 제안하지 못한다
    stranger = env.signup("stranger@example.com")
    env.publish(stranger)
    assert env.client.post(f"{env.base}/me/owner/briefs/{brief['id']}/invite", headers=stranger,
                           json={"listing_id": lid, "body": "남의 매물"}).status_code == 404
    assert env.client.post(f"{env.base}/me/owner/briefs/{brief['id']}/invite", headers=owner,
                           json={"listing_id": lid, "body": "제안"}).status_code == 201


def test_invites_do_not_count_as_founder_inquiry_demand(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    for i in range(3):
        f = env.signup(f"f{i}@example.com")
        b = _post_brief(env, f)
        env.client.post(f"{env.base}/me/owner/briefs/{b['id']}/invite", headers=owner,
                        json={"listing_id": lid, "body": "제안"})
    fit = env.client.get(f"{env.base}/listings/{lid}/fit").json()
    assert fit["for_owner"]["demand"]["rows"] == []                       # 건물주가 연 대화는 문의 수요가 아니다
    assert fit["for_owner"]["briefs"]["by_industry"][0]["founders"] == 3  # 희망서 수요는 따로 센다


# ── 조건표 · 요구 판매량 ─────────────────────────────────────────────────────

def test_fit_table_is_conditions_not_a_score_and_required_sales_is_founder_only(direct_env):
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    _post_brief(env, founder)
    lid = env.publish(owner, exhaust_ok=True, water_ok=None)
    fit = env.client.get(f"{env.base}/me/brief/fit/{lid}", headers=founder).json()
    status = {r["key"]: r["status"] for r in fit["rows"]}
    assert status["district"] == "ok" and status["floor"] == "ok" and status["area"] == "ok"
    assert status["rent"] == "ok"            # 명목 250 > 상한 240 이지만 렌트프리 반영 실질 229.2 ≤ 240
    assert status["exhaust"] == "ok" and status["water"] == "unknown" and status["popup"] == "gap"
    assert status["timing"] == "unknown"     # 건물주가 입주 가능일을 적지 않았다
    assert not SCORE_WORDS_IN(fit)
    rs = fit["required_sales"]
    # (실질 월세 229.2 + 관리비 20 + 기타 고정비 300) ÷ (1 − 0.35) = 844.92만원 → ÷ (6,000원 × 26일) = 54.2 → 55개
    assert rs["status"] == "calculated" and rs["monthly_revenue_manwon"] == 844.92 and rs["daily_units"] == 55
    assert "70개는 필요한 55개보다 15개 많아요" in rs["target_text"]
    # 비공개 입력이 비면 계산하지 않는다(자료 부족)
    env.client.patch(f"{env.base}/me/brief", headers=founder, json={"unit_price_won": None})
    rs = env.client.get(f"{env.base}/me/brief/fit/{lid}", headers=founder).json()["required_sales"]
    assert rs["status"] == "needs_inputs" and "unit_price_won" in rs["missing"]


def SCORE_WORDS_IN(obj) -> list[str]:  # noqa: N802 — 테스트 안의 작은 도우미
    return [k for k in _keys(obj) if any(w in k.lower() for w in SCORE_WORDS)]


def test_no_credit_score_anywhere_in_brief_tables_or_responses(direct_env):
    """⛔ 신용 점수·등급·순위를 만들지 않는다 — 칼럼에도 응답 키에도 없다(신용정보법 · KPI 규칙)."""
    for model in (DirectBrief, BriefDisclosure, DirectOffer):
        cols = set(model.__table__.columns.keys())
        assert not [c for c in cols if any(w in c for w in SCORE_WORDS)], (model.__tablename__, cols)
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    brief = _post_brief(env, founder)
    env.publish(owner)
    for body in (env.client.get(f"{env.base}/me/owner/briefs", headers=owner).json(),
                 env.client.get(f"{env.base}/me/owner/briefs/{brief['id']}", headers=owner).json(),
                 env.client.get(f"{env.base}/me/brief", headers=founder).json(),
                 env.client.get(f"{env.base}/demand", params={"district_id": "garosugil"}).json()):
        assert not SCORE_WORDS_IN(body)
    owner_list = env.client.get(f"{env.base}/me/owner/briefs", headers=owner).json()
    assert "점수" in owner_list["order_note"] and "점수" in owner_list["trust_note"]   # 「점수가 아니에요」를 밝힌다


# ── 탈퇴 ───────────────────────────────────────────────────────────────────

def test_account_deletion_removes_brief_disclosures_and_offers(direct_env):
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    brief = _post_brief(env, founder)
    lid = env.publish(owner, deal_type="lease_popup", popup_daily_manwon=30, popup_min_days=3, popup_max_days=30)
    iid = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder,
                          json={"kind": "offer", "body": "이 조건 어떠세요", "offer": {"rent_manwon": 220}}).json()["id"]
    env.client.post(f"{env.base}/inquiries/{iid}/disclose", headers=founder)
    with env.session() as db:
        assert db.query(DirectOffer).count() == 1 and db.query(BriefDisclosure).count() == 1
    assert env.client.delete("/api/v1/auth/me", headers=founder).status_code in (200, 204)
    with env.session() as db:
        assert db.get(DirectBrief, brief["id"]) is None
        assert db.query(BriefDisclosure).count() == 0
        assert db.query(DirectOffer).count() == 0
        assert db.query(DirectInquiry).count() == 0


def test_owner_deletion_removes_disclosures_made_to_them(direct_env):
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    _post_brief(env, founder)
    lid = env.publish(owner)
    iid = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder, json={"body": "문의"}).json()["id"]
    env.client.post(f"{env.base}/inquiries/{iid}/disclose", headers=founder)
    assert env.client.delete("/api/v1/auth/me", headers=owner).status_code in (200, 204)
    with env.session() as db:
        assert db.query(BriefDisclosure).count() == 0
        assert db.query(DirectBrief).count() == 1          # 창업자의 희망서는 남는다


def test_founder_can_delete_their_brief_and_its_disclosures(direct_env):
    env = direct_env
    founder, owner = env.signup("founder@example.com"), env.signup("owner@example.com")
    _post_brief(env, founder)
    lid = env.publish(owner)
    iid = env.client.post(f"{env.base}/listings/{lid}/inquiries", headers=founder, json={"body": "문의"}).json()["id"]
    env.client.post(f"{env.base}/inquiries/{iid}/disclose", headers=founder)
    assert env.client.delete(f"{env.base}/me/brief", headers=founder).status_code == 204
    assert env.client.get(f"{env.base}/me/brief", headers=founder).json()["brief"] is None
    with env.session() as db:
        assert db.query(BriefDisclosure).count() == 0
    assert env.client.get(f"{env.base}/inquiries/{iid}", headers=owner).json()["brief"] is None
