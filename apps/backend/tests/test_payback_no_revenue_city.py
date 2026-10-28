"""매출 재료가 없는 도시(고양·파주)에서는 본전 시점을 답하지 않는다 — 2026-10-27 · 10-28 갱신.

고양·파주 서빙 거점에는 서울 상권분석 추정매출이 서지 않는다. 10-27 까지는 세 tier 를 손으로 적은 계수
(`rent+fitout`)로 채웠고 그 값은 원가·인건비가 빠져 회수 1개월 안팎으로 나왔다(금촌 가성비 0.9개월). 10-28
사용자 결정 (b) 로 계수 폴백을 없앴다 — 재료가 없는 tier 는 계산하지 않는다. 지키는 것:

  · `/postings` 유닛에 사유가 실린다 — 자리(건축물대장 실측)는 남기고 답만 거둔다. 세 tier 는 모두
    「자료 부족」(`available: False` · 숫자 None)이고 각자 그 도시를 사유로 든다
  · `/ai/simulate-revenue` 가 「계산 불가」와 같은 사유로 답한다
  · 서울 거점에는 사유가 없다 — 서울 안에서 일부 tier 만 표본이 모자란 거점(가락·불광)은 선 tier 로 답한다
    (그 판단은 tests/test_posting_revenue.test_partial_hubs_compute_only_the_measured_tiers)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.data import cities
from app.main import app
from app.services import districts as D

client = TestClient(app)
V1 = "/api/v1"


def _city(slug: str) -> cities.City:
    d = D.PAGES_BY_ID[slug]
    return cities.by_id(d["city"]) if d.get("city") else cities.of_gu(d.get("gu"))


NO_REVENUE = [s for s in D.PAGES_BY_ID if not _city(s).has_trdar]
pytestmark = pytest.mark.skipif(not NO_REVENUE, reason="매출 재료가 없는 도시의 서빙 거점이 없다")


def _with_units(slugs: list[str]) -> list[str]:
    return [s for s in slugs if D.resolved_units(s)]


def test_postings_carry_the_reason_in_cities_without_revenue_material():
    hubs = _with_units(NO_REVENUE)
    assert hubs, "고양·파주 거점에 공실 유닛이 하나도 없다 — 이 테스트가 아무것도 못 본다"
    for slug in hubs:
        r = client.get(f"{V1}/commercial-districts/{slug}/postings")
        assert r.status_code == 200, (slug, r.text)
        units = r.json()
        assert units and all(u["payback_unavailable_reason"] for u in units), slug
        assert _city(slug).short in units[0]["payback_unavailable_reason"], slug
        # 자리는 그대로다. 시나리오의 세 tier 는 모두 자료 부족이고 숫자를 지어내지 않는다(2026-10-28 (b))
        for u in units:
            assert set(u["scenarios"]) == {"premium", "value", "factory"}, slug
            for t, sc in u["scenarios"].items():
                assert sc["available"] is False and sc["basis"] is None, (slug, t)
                assert sc["roi_months"] is None and sc["month_net"] is None, (slug, t)
                assert _city(slug).short in sc["unavailable_reason"], (slug, t)


def test_simulate_refuses_instead_of_answering_from_coefficients():
    slug = _with_units(NO_REVENUE)[0]
    unit = D.resolved_units(slug)[0]
    r = client.post(f"{V1}/ai/simulate-revenue",
                    json={"district_id": slug, "unit_id": unit["id"], "industry_type": "카페"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["calculation_status"] == "unavailable"
    assert body["scenarios"] == {}, "계수 폴백 시나리오가 새어 나갔다"
    assert body["unavailable_reason"] == D.payback_unavailable_reason(slug)


def test_seoul_hubs_have_no_reason_even_when_a_tier_is_missing():
    seoul = [s for s in D.PAGES_BY_ID if _city(s).has_trdar]
    assert all(D.payback_unavailable_reason(s) is None for s in seoul)
    measured = next(s for s in _with_units(seoul) if all(
        sc["basis"] == D.COST_BASIS for sc in D.tier_scenarios(D.resolved_units(s)[0], s).values()))
    unit = D.resolved_units(measured)[0]
    r = client.post(f"{V1}/ai/simulate-revenue",
                    json={"district_id": measured, "unit_id": unit["id"], "industry_type": "카페"})
    assert r.status_code == 200, r.text
    assert r.json()["calculation_status"] == "calculated" and r.json()["scenarios"], measured
