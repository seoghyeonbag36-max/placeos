"""합성 사용자 입력으로 금액·결측·업종 혼동을 검증한다. 예측 성능 시험이 아니다."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import industry_detail as detail, posting, districts

client = TestClient(app)
COMMON = dict(variable_cost_rate=.2, rent=100, fixed_cost=200, investment=1000)


def test_lodging_uses_room_nights_and_explicit_costs():
    out = detail.calculate("lodging_hotel", COMMON | dict(capacity=10, utilization=.5, days=30, price=10))
    assert out["monthly_revenue"] == 1500
    assert out["monthly_cost"] == 600
    assert out["monthly_surplus"] == 900
    assert out["payback_months"] == 1.1
    assert set(out["provenance"].values()) == {"user_input"}


@pytest.mark.parametrize("key,values,expected", [
    ("bar_beer", dict(capacity=20, cycles=2, utilization=.5, days=25, price=3), 1500),
    ("beauty_nail", dict(capacity=2, cycles=4, utilization=.5, days=20, price=5), 400),
    ("fashion_clothes", dict(transactions=10, days=20, price=5, return_rate=.1), 900),
    ("education_subject", dict(capacity=50, utilization=.6, price=30), 900),
    ("fitness_gym", dict(capacity=100, utilization=.5, price=5), 250),
    ("culture_performance", dict(capacity=100, cycles=10, utilization=.5, price=3), 1500),
    ("culture_exhibition", dict(days=20, utilization=.5, price=30), 300),
    ("culture_gallery", dict(sales=1000, commission_rate=.3), 300),
])
def test_each_business_model_uses_its_own_units(key, values, expected):
    assert detail.calculate(key, COMMON | values)["monthly_revenue"] == expected


def test_missing_inputs_never_become_zero_or_seed():
    out = detail.calculate("beauty_hair", {"capacity": 2})
    assert out["status"] == "needs_inputs"
    assert out["monthly_revenue"] is None
    assert "rent" in {f["key"] for f in out["required_inputs"]}
    assert "rent" not in out["assumptions"]


@pytest.mark.parametrize("values", [{"utilization": 1.1}, {"rent": -1}, {"days": 2.5}, {"capacity": True}, {"price": float("inf")}, {"unexpected": 1}])
def test_invalid_or_foreign_inputs_fail(values):
    with pytest.raises(ValueError):
        detail.calculate("lodging_hotel", values)


def test_loss_has_no_payback():
    out = detail.calculate("lodging_hotel", COMMON | dict(capacity=1, utilization=0, days=30, price=10))
    assert out["payback_months"] is None
    assert out["monthly_surplus"] == -300


def test_non_food_cannot_receive_food_fallback(monkeypatch):
    monkeypatch.setattr(districts, "resolved_units", lambda _: [{"id": "u"}])
    monkeypatch.setattr(posting, "_call_copilot", lambda *a: pytest.fail("미지원 업종을 기존 계산으로 보내면 안 됨"))
    for industry in ("숙박", "미용실", "주점", "학원", "운동시설", "문화시설", "의류", "알 수 없음"):
        out = posting.simulate("d", "u", industry)
        assert out["calculation_status"] == "unavailable"
        assert out["scenarios"] == {}


def test_missing_unit_does_not_calculate_another_unit(monkeypatch):
    monkeypatch.setattr(districts, "resolved_units", lambda _: [{"id": "u"}])
    assert posting.simulate("d", "missing") is None


def test_detail_api_exposes_inputs_and_does_not_invent_recommendations(monkeypatch):
    options = client.get("/api/v1/ai/industry-details").json()["details"]
    assert {i["parent"] for i in options} == {"bar", "beauty", "fashion", "education", "fitness", "lodging", "culture"}
    assert all(not i["recommendation_available"] and i["fields"] for i in options)
    monkeypatch.setattr(detail, "_competition", lambda: {})
    out = client.get("/api/v1/ai/industry-competition?district_id=garosugil&detail_key=beauty_nail").json()
    assert out["count"] is None and out["fit"] is None
    assert out["unavailable_reason"]


def test_simulation_api_returns_missing_inputs_and_rejects_invalid_values(monkeypatch):
    monkeypatch.setattr(districts, "resolved_units", lambda _: [{"id": "u"}])
    body = dict(district_id="d", unit_id="u", industry_detail_key="lodging_hotel")
    r = client.post("/api/v1/ai/simulate-revenue", json=body)
    assert r.status_code == 200
    assert r.json()["calculation_status"] == "needs_inputs"
    assert r.json()["economics"]["monthly_revenue"] is None
    assert client.post("/api/v1/ai/simulate-revenue", json=body | {"operating_inputs": {"utilization": 2}}).status_code == 422
    assert client.post("/api/v1/ai/simulate-revenue", json=body | {"industry_type": "네일숍"}).status_code == 422


def test_workspace_subtype_must_belong_to_selected_parent():
    from pydantic import ValidationError
    from app.schemas.auth import BusinessProfile
    profile = BusinessProfile(goal="start", industryKey="lodging", industryDetailKey="lodging_hotel")
    assert profile.industryDetailKey == "lodging_hotel"
    with pytest.raises(ValidationError):
        BusinessProfile(goal="start", industryKey="beauty", industryDetailKey="lodging_hotel")
