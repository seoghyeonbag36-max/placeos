"""Posting 계약 입력 — 계약 월세 · 인테리어·설비 견적(2026-11-12 사용자 요청).

권리금(prem)과 같은 **입력 계약**이다. 주면 그 값으로 계산하고 `inputs_source` 가 어느 쪽인지 밝힌다.
견적은 업종 평균 계수(면적 × 평당 계수 + 고정분)를 갈아 끼운다 — 계수로는 서울 추천 전략 836곳 중 296곳이
회수 1개월 미만으로 나왔다(2026-11-11 실측).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
V1 = "/api/v1"


def _sim(**body):
    r = client.post(f"{V1}/ai/simulate-revenue", json={"district_id": "garosugil", **body})
    assert r.status_code == 200, r.text
    return r.json()


def _avail(res):
    return {k: s for k, s in res["scenarios"].items() if s.get("available", True) and s.get("month_net") is not None}


def test_fitout_override_replaces_coefficient_invest_for_every_tier():
    base = _sim()
    assert "invest" not in (base["inputs_source"] or {})
    given = _sim(unit_id=base["unit_id"], fitout_override=8000)
    assert given["inputs_source"]["invest"] == "user_input"
    tiers = _avail(given)
    assert tiers, "계산한 가격대가 하나는 있어야 한다"
    for s in tiers.values():
        # 8,000만원 = 80백만원 · 권리금 미입력(0)
        assert s["invest_mn"] == 80
        if s["month_net"] > 0:
            assert abs(s["roi_months"] - 80 * 100 / s["month_net"]) <= 0.1 + 80 * 100 / s["month_net"] * 0.01


def test_fitout_override_adds_premium_separately():
    base = _sim()
    given = _sim(unit_id=base["unit_id"], fitout_override=5000, prem=3000)
    for s in _avail(given).values():
        assert s["invest_mn"] == 80   # (3,000 + 5,000)만원 = 80백만원


def test_rent_override_is_contract_and_flows_to_cost_and_resolved_inputs():
    base = _sim()
    rent0 = base["resolved_inputs"]["rent_manwon"] if base.get("resolved_inputs") else None
    given = _sim(unit_id=base["unit_id"], rent_override=777)
    assert given["inputs_source"]["rent"] == "contract"
    assert given["resolved_inputs"]["rent_manwon"] == 777
    b, g = _avail(base), _avail(given)
    for k in g:
        # 월 비용 = 월세 + 매출 × 비임차 비용률 — 매출은 그대로라 비용 차이는 월세 차이다
        assert g[k]["month_rev"] == b[k]["month_rev"]
        if rent0 is not None:
            assert abs((g[k]["month_cost"] - b[k]["month_cost"]) - (777 - rent0)) <= 1


def test_overrides_are_validated():
    assert client.post(f"{V1}/ai/simulate-revenue", json={"district_id": "garosugil", "rent_override": 0}).status_code == 422
    assert client.post(f"{V1}/ai/simulate-revenue", json={"district_id": "garosugil", "fitout_override": -1}).status_code == 422


def test_floor_vacancies_carry_use_apr_when_ledger_has_it():
    r = client.get(f"{V1}/commercial-districts/garosugil/floor-vacancies?limit=50")
    assert r.status_code == 200
    units = r.json()["units"]
    dated = [u for u in units if u.get("use_apr")]
    assert dated, "가로수길 빈 층에는 사용승인일이 있는 지번이 있다(Gold building_floors)"
    for u in dated:
        assert len(u["use_apr"]) == 8 and u["use_apr"].isdigit()
