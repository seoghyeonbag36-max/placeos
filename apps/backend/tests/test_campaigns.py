"""캠페인 계약·실제 저장 경로 검증. 아래 상호·증빙은 테스트 전용 합성값이다."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "/api/v1/program/campaigns"
CONDITIONS = dict(store_name="검증 카페", address="테스트 주소", category="카페", goal="quiet_hours",
                  target_customer="지역 주민", time_window="평일 오후", capacity=5, budget_krw=50000,
                  offer="유휴 좌석 제공", constraints="소음 제한")


def proof(day="2020-01-01"):
    return dict(reference="https://example.org/proof", observed_on=day, note="테스트 전용 증빙")


class Flow:
    def __init__(self, headers):
        self.headers = headers
        response = client.post(BASE, headers=headers, json=CONDITIONS)
        assert response.status_code == 201, response.text
        self.data = response.json()

    def command(self, action, payload, status=200, version=None):
        response = client.post(f"{BASE}/{self.data['id']}/commands", headers=self.headers,
                               json=dict(version=version or self.data["version"], action=action, payload=payload))
        assert response.status_code == status, response.text
        if status == 200:
            self.data = response.json()
        return response

    def candidate(self):
        self.command("candidate", dict(name="테스트 모임", role="audience", source="official_reference",
            evidence=proof(), contact="공식 게시판", fit_reason="목표 시간대 모임", mutual_value="모임 좌석 제공"))
        return self.data["candidates"][-1]["id"]

    def run(self, day="2020-01-01", candidate_id=None):
        self.command("run", dict(candidate_id=candidate_id, starts_on=day, ends_on=day, terms="주문 조건 협의",
            next_action="담당자 확인", responsible="점주", due_on=day, measurement="구매 영수증 집계", stop_rule="예산 한도 초과 시 중단"))
        return self.data["runs"][-1]["id"]

    def complete(self, day="2020-01-01", candidate_id=None):
        run_id = self.run(day, candidate_id)
        parties = ["owner", "partner"] if candidate_id else ["owner"]
        for party in parties:
            self.command("consent", dict(run_id=run_id, party=party, evidence=proof(day)))
        self.command("transition", dict(run_id=run_id, status="agreed"))
        self.command("transition", dict(run_id=run_id, status="running"))
        for party in parties:
            self.command("participation", dict(run_id=run_id, party=party, evidence=proof(day)))
        self.command("result", dict(run_id=run_id, evidence=proof(day)))
        self.command("transition", dict(run_id=run_id, status="completed"))
        return run_id

    def payment(self, run_id, ref, day="2020-01-01", **kwargs):
        payload = dict(run_id=run_id, payer="owner", purpose="program_fee", status="paid", amount_krw=20000,
                       transaction_ref=ref, evidence=proof(day), refunded_krw=0)
        payload.update(kwargs)
        self.command("payment", payload)


@pytest.fixture
def flow(signed_in):
    return Flow(signed_in)


def test_missing_evidence_never_creates_candidate(flow):
    flow.command("candidate", dict(name="근거 없음"), status=422)
    assert flow.data["candidates"] == []
    assert len(flow.data["recommendations"]) == 1
    assert flow.data["summary"]["owner_participations"] == 0


def test_official_reference_is_not_independent_verification(flow):
    flow.candidate()
    assert flow.data["candidates"][0]["verification"] == "user_submitted_not_independently_verified"
    assert flow.data["summary"]["independently_verified"] is False
    assert flow.data["recommendations"][1]["source"] == "rule_proposal"


def test_agreement_requires_both_parties(flow):
    run_id = flow.run(candidate_id=flow.candidate())
    flow.command("consent", dict(run_id=run_id, party="owner", evidence=proof()))
    flow.command("transition", dict(run_id=run_id, status="agreed"), status=422)
    flow.command("transition", dict(run_id=run_id, status="running"), status=422)


def test_consent_does_not_count_as_participation(flow):
    run_id = flow.run()
    flow.command("consent", dict(run_id=run_id, party="owner", evidence=proof()))
    flow.command("transition", dict(run_id=run_id, status="agreed"))
    assert flow.data["summary"]["owner_participations"] == 0
    flow.command("transition", dict(run_id=run_id, status="running"))
    flow.command("result", dict(run_id=run_id, evidence=proof()))
    flow.command("transition", dict(run_id=run_id, status="completed"), status=422)


def test_missing_cost_keeps_balance_unknown(flow):
    run_id = flow.complete()
    assert flow.data["runs"][0]["recorded_balance_krw"] is None
    flow.command("result", dict(run_id=run_id, revenue_krw=0, variable_cost_krw=0, execution_cost_krw=0, evidence=proof()))
    assert flow.data["runs"][0]["recorded_balance_krw"] == 0
    assert "미판정" in flow.data["runs"][0]["effect_verdict"]


def test_same_partner_return_and_real_repayment(flow):
    partner = flow.candidate()
    first = flow.complete(candidate_id=partner)
    flow.payment(first, "txn-first")
    second = flow.complete("2020-01-02", partner)
    assert flow.data["summary"]["owner_returned"]
    assert flow.data["summary"]["returning_partner_ids"] == [partner]
    assert not flow.data["summary"]["owner_repaid"]
    flow.payment(second, "txn-second", "2020-01-02")
    assert flow.data["summary"]["both_returned_and_repaid"]


@pytest.mark.parametrize("state,purpose", [("intent", "program_fee"), ("cancelled", "program_fee"), ("paid", "campaign_expense")])
def test_intent_cancel_and_expenses_are_not_repayment(flow, state, purpose):
    first = flow.complete()
    flow.payment(first, "txn-first")
    second = flow.complete("2020-01-02")
    flow.payment(second, "txn-second", "2020-01-02", status=state, purpose=purpose)
    assert not flow.data["summary"]["owner_repaid"]


def test_full_refund_removes_repayment_and_preserves_history(flow):
    partner = flow.candidate()
    first = flow.complete(candidate_id=partner)
    flow.payment(first, "txn-first")
    second = flow.complete("2020-01-02", partner)
    flow.payment(second, "txn-second", "2020-01-02")
    flow.payment(second, "txn-second", "2020-01-03", status="refunded", refunded_krw=20000)
    assert not flow.data["summary"]["owner_repaid"]
    assert not flow.data["summary"]["both_returned_and_repaid"]
    assert flow.data["summary"]["program_fee_net_krw"] == 20000
    assert len([h for h in flow.data["history"] if h["action"] == "payment"]) == 3


def test_advance_installments_are_not_repeat_payment(flow):
    first = flow.complete()
    flow.payment(first, "txn-first")
    second = flow.complete("2020-01-02")
    flow.payment(second, "txn-second", "2020-01-01")
    assert not flow.data["summary"]["owner_repaid"]
    flow.payment(second, "txn-second", "2020-01-03", status="refunded", refunded_krw=1000)
    assert not flow.data["summary"]["owner_repaid"]


def test_different_partner_is_not_partner_return(flow):
    first = flow.complete(candidate_id=flow.candidate())
    flow.payment(first, "txn-first")
    second = flow.complete("2020-01-02", flow.candidate())
    flow.payment(second, "txn-second", "2020-01-02")
    assert flow.data["summary"]["owner_repaid"]
    assert flow.data["summary"]["returning_partner_ids"] == []
    assert not flow.data["summary"]["both_returned_and_repaid"]


def test_duplicate_transaction_across_runs_rejected(flow):
    first = flow.complete()
    flow.payment(first, "txn-first")
    second = flow.complete("2020-01-02")
    payload = deepcopy(flow.data["runs"][0]["payments"][0])
    payload.pop("source"); payload.pop("paid_on")
    flow.command("payment", dict(payload, run_id=second), status=422)


def test_foreign_candidate_and_overlapping_run_rejected(flow):
    flow.command("run", dict(candidate_id="invented", starts_on="2020-01-01", ends_on="2020-01-01", terms="테스트 조건",
        next_action="테스트", responsible="점주", due_on="2020-01-01", measurement="실적 기록", stop_rule="예산 중단"), status=422)
    flow.complete()
    payload = {k: v for k, v in flow.data["runs"][0].items() if k in (
        "candidate_id", "starts_on", "ends_on", "terms", "next_action", "responsible", "due_on", "measurement", "stop_rule")}
    flow.command("run", payload, status=422)


def test_stale_write_is_rejected_without_losing_records(flow):
    flow.candidate()
    flow.command("candidate", dict(name="덮어쓰기"), status=409, version=1)
    result = client.get(BASE, headers=flow.headers).json()
    assert result[0]["version"] == 2
    assert len(result[0]["candidates"]) == 1


def test_campaign_is_private_and_requires_login(flow):
    assert client.get(BASE).status_code == 401
    signup = client.post("/api/v1/auth/signup", json=dict(email="other-campaign@example.org", password="hunter2hunter", org_name="Other"))
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    assert client.get(BASE, headers=headers).json() == []
    response = client.post(f"{BASE}/{flow.data['id']}/commands", headers=headers, json=dict(version=1, action="candidate", payload={}))
    assert response.status_code == 404


def test_future_evidence_and_injected_results_are_rejected(flow):
    flow.command("candidate", dict(name="미래 모임", role="audience", source="user_record", evidence=proof("2099-01-01"),
        contact="공식 창구", fit_reason="목표 시간대", mutual_value="상호 가치"), status=422)
    assert client.post(BASE, headers=flow.headers, json=dict(CONDITIONS, owner_repaid=True)).status_code == 422


def test_account_deletion_removes_campaigns(flow):
    from sqlalchemy import select
    from app.core.db import get_db
    from app.models.campaign import Campaign
    assert client.delete("/api/v1/auth/me", headers=flow.headers).status_code == 200
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        assert db.scalar(select(Campaign).where(Campaign.id == flow.data["id"])) is None
    finally:
        generator.close()
