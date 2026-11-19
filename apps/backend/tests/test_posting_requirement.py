"""Posting 요구치(P2) — 산수와 근거 층위, 지어내지 않는 경계."""
from fastapi.testclient import TestClient

from app.main import app
from app.services import districts as svc
from app.services import posting_requirement as req

client = TestClient(app)


def test_required_sales_is_rent_over_margin():
    r = req.compute("garosugil", "value", 10000, rent_mn=500)
    nonrent = r["nonrent_rate"]
    assert r["available"] and r["rent_basis"] == "user"
    assert abs(r["monthly_sales_mn"] - 500 / (1 - nonrent)) < 0.1
    assert abs(r["daily_units"] - r["monthly_sales_mn"] * 10000 / (10000 * 26)) < 0.1


def test_user_cost_rate_is_a_floor_and_marked():
    r = req.compute("garosugil", "value", 10000, rent_mn=500, cost_rate=0.3)
    assert r["nonrent_floor"] is True and r["evidence"]["cost_rate"] == "사용자 입력"


def test_user_rent_beats_estimate():
    unit = svc.resolved_units("sungshin")[0]
    est = req.compute("sungshin", "value", 8000, unit_id=unit["id"])
    usr = req.compute("sungshin", "value", 8000, unit_id=unit["id"], rent_mn=1)
    assert est["rent_basis"] == "rone_estimate" and est["evidence"]["rent_mn"] == "추정"
    assert usr["rent_basis"] == "user" and usr["rent_mn"] == 1.0


def test_no_rent_is_unavailable_not_invented():
    r = req.compute("garosugil", "value", 8000)
    assert r["available"] is False and "월세" in r["reason"]


def test_benchmark_band_and_every_number_has_evidence():
    r = req.compute("garosugil", "value", 10000, rent_mn=500)
    bm = r["benchmark"]
    assert bm is None or (bm["share_pct"] > 0 and bm["band"])
    for k in ("monthly_sales_mn", "daily_units", "price_won"):
        assert k in r["evidence"]


def test_endpoint_and_validation():
    ok = client.post("/api/v1/ai/posting-requirement",
                     json={"district_id": "garosugil", "tier": "value", "price_won": 9000, "rent_mn": 400})
    assert ok.status_code == 200 and ok.json()["available"]
    assert client.post("/api/v1/ai/posting-requirement",
                       json={"district_id": "garosugil", "tier": "nope", "price_won": 9000, "rent_mn": 400}).status_code == 422
