"""양쪽 공용 임대 조건 계산 — 순수 산술 · R-ONE 은 1층만 · 비교 표본 n≥3 · 인하 vs 공실 (2026-11-18)."""
from __future__ import annotations

from app.models.direct import DirectListing
from app.services import direct_pricing, posting_inputs


def _listing(**kw) -> DirectListing:
    base = dict(id="l1", owner_user_id="u1", status="published", district_id="garosugil", address="합성 주소",
                floor=1, area_m2=50.0, use_type="제1종 근린생활시설", deal_type="lease", deposit_manwon=3000,
                monthly_rent_manwon=300, maintenance_manwon=20, rent_free_months=2, min_term_months=24,
                preferred_industries=[], excluded_industries=[])
    base.update(kw)
    return DirectListing(**base)


def test_effective_rent_and_first_year_cash(direct_env, monkeypatch):
    monkeypatch.setattr(posting_inputs, "for_district", lambda _d: None)
    with direct_env.session() as db:
        t = direct_pricing.terms(db, _listing())
    assert t["effective_monthly_rent_manwon"] == 275.0          # 300 × (24 − 2) / 24
    assert t["monthly_occupancy_manwon"] == 295.0
    assert t["first_year_cash_manwon"] == 3000 + 300 * 10 + 20 * 12
    assert t["term_assumed"] is False
    assert t["rent_per_m2_thousand"] == 60.0                     # 300만원 × 10 ÷ 50㎡


def test_term_is_marked_when_assumed(direct_env, monkeypatch):
    monkeypatch.setattr(posting_inputs, "for_district", lambda _d: None)
    with direct_env.session() as db:
        t = direct_pricing.terms(db, _listing(min_term_months=None))
    assert t["term_assumed"] is True and t["term_months"] == direct_pricing.DEFAULT_TERM_MONTHS
    assert any("계약 기간을 적지 않아" in n for n in t["notes"])


def test_rone_ratio_only_on_the_first_floor(direct_env, monkeypatch):
    monkeypatch.setattr(posting_inputs, "for_district", lambda _d: {"rent_per_m2_krw_thousand": 50.0})
    with direct_env.session() as db:
        first = direct_pricing.terms(db, _listing(floor=1))
        upper = direct_pricing.terms(db, _listing(floor=3))
    assert first["rone"]["ratio"] == 1.2
    assert upper["rone"]["ratio"] is None and "1층 기준" in upper["rone"]["note"]


def test_peer_median_needs_three_verified_listings(direct_env, monkeypatch):
    env = direct_env
    monkeypatch.setattr(posting_inputs, "for_district", lambda _d: None)
    owner = env.signup("owner@example.com")
    target = env.publish(owner, floor=2, monthly_rent_manwon=200, area_m2=50.0)
    assert env.client.get(f"{env.base}/listings/{target}/terms").json()["peers"]["median_rent_per_m2_thousand"] is None
    for rent in (100, 150, 250):
        env.publish(owner, floor=3, monthly_rent_manwon=rent, area_m2=50.0, address=f"합성 주소 {rent}")
    peers = env.client.get(f"{env.base}/listings/{target}/terms").json()["peers"]
    assert peers["n"] == 3 and peers["median_rent_per_m2_thousand"] == 30.0


def test_vacancy_tradeoff_is_plain_arithmetic():
    t = direct_pricing.vacancy_tradeoff(300, 10, 3)
    assert t["loss_if_cut_12m_manwon"] == 360.0 and t["loss_if_vacant_manwon"] == 900.0 and t["cheaper"] == "cut"
    assert direct_pricing.vacancy_tradeoff(300, 50, 1)["cheaper"] == "vacant"
