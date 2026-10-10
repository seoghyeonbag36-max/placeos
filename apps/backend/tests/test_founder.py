"""미확인 금액·예산 판정·API 입력 검증의 회귀 검사."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.founder import CandidateCosts
from app.services.founder import assess_costs


def test_missing_costs_never_become_zero_total():
    result = assess_costs(CandidateCosts(rent=100))
    assert result.required_cash is None
    assert result.budget_remaining is None
    assert result.known_monthly == 100
    assert result.status == "incomplete"


def test_confirmed_zero_and_reserve_are_counted():
    result = assess_costs(CandidateCosts(deposit=1000, premium=0, fitout=0,
        equipment=0, rent=100, maintenance=10, other_monthly=0, reserve_months=3, budget=1300))
    assert result.required_cash == 1330
    assert result.budget_remaining == -30
    assert result.status == "over_budget"
    assert result.source == "user_input"


@pytest.mark.parametrize("value", [-1, 1.5, "100", True, 10**13])
def test_cost_api_rejects_invalid_money(value):
    response = TestClient(app).post("/api/v1/founder/costs", json={"rent": value})
    assert response.status_code == 422


def test_cost_api_reports_incomplete_contract():
    response = TestClient(app).post("/api/v1/founder/costs", json={})
    assert response.status_code == 200
    assert response.json()["required_cash"] is None
