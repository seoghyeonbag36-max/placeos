"""캠페인 실행 원장. 추천·의향은 실적이 아니며 제출 증빙을 독립 검증으로 승격하지 않는다."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.schemas.campaign import (
    Candidate, Command, Conditions, PartyEvidence, PaymentInput, Progress, ResultInput,
    RunInput, Transition,
)


class CampaignError(ValueError):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone(timedelta(hours=9))).date().isoformat()


def _row(db: Session, user_id: str, campaign_id: str) -> Campaign:
    row = db.scalar(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id))
    if row is None:
        raise CampaignError("캠페인을 찾을 수 없습니다", 404)
    return row


def recommendations(data: dict) -> list[dict]:
    """사용자 근거만 연결하는 규칙 제안. 후보가 없으면 자체 실행만 제안한다."""
    c = data["conditions"]
    goal_plans = {
        "quiet_hours": ("목표 시간대 방문 활동", "목표 요일·시간에 한정한 방문 조건을 안내"),
        "first_purchase": ("첫 구매 안내 활동", "첫 구매 고객에게 상품·이용 방법을 현장에서 안내"),
        "revisit": ("후속 방문 안내 활동", "다음 방문 조건을 안내하고 동일 고객 식별이 가능한 범위에서 기록"),
        "group_order": ("단체·정기 주문 제안", "주문 수량·수령 시간·취소 조건을 정리"),
    }
    title, step = goal_plans[c["goal"]]
    own = {
        "candidate_id": None, "title": title, "source": "rule_proposal",
        "reason": f"입력한 목표 시간대 {c['time_window']}에 매장 자체 접점을 활용합니다.",
        "steps": [step, f"제공 조건 확인: {c['offer']}",
                  f"추가 수용 {c['capacity']} 이내, 실행 예산 {c['budget_krw']}원 이내로 운영",
                  "직원 안내와 방문 경로 기록 준비", "비용·구매를 기록하고 다음 실행 결정"],
        "unconfirmed": ["구매 증가 효과", "혜택의 실제 원가"],
    }
    options = [own]
    for candidate in data["candidates"]:
        options.append({
            "candidate_id": candidate["id"], "title": f"{candidate['name']} 협업 제안",
            "source": "rule_proposal", "reason": candidate["fit_reason"],
            "steps": [f"상호 가치 협의: {candidate['mutual_value']}",
                      f"{candidate['contact']}에서 일정·역할·비용 확인", "양측 합의 후 실행, 각자의 참여 증빙 기록"],
            "unconfirmed": ["현재 참여 의사", "매장 시간대·수용 인원과의 적합성", "성과"],
        })
    return options


def _net(payment: dict) -> int:
    if payment["status"] not in ("paid", "refunded"):
        return 0
    return payment["amount_krw"] - payment["refunded_krw"]


def summary(data: dict) -> dict:
    completed = [r for r in data["runs"] if r["status"] == "completed"]
    owner_runs = [r for r in completed if "owner" in r["participation"]]
    partner_counts: dict[str, int] = {}
    paid_runs: list[dict] = []
    combined = False
    for index, run in enumerate(completed):
        candidate_id = run["candidate_id"]
        if candidate_id and "partner" in run["participation"]:
            partner_counts[candidate_id] = partner_counts.get(candidate_id, 0) + 1
        # 점주가 Program 이용료를 실제 납부한 서로 다른 회차만 센다. 행사비는 제외한다.
        payments = [p for p in run["payments"] if p["payer"] == "owner"
                    and p["purpose"] == "program_fee" and _net(p) > 0
                    and (index == 0 or p.get("paid_on", "") > completed[index - 1]["ends_on"])]
        if payments:
            paid_runs.append(run)
            for prior in paid_runs[:-1]:
                if candidate_id and prior["candidate_id"] == candidate_id:
                    combined = True
    return {
        "evidence_source": "user_submitted_manual", "independently_verified": False,
        "completed_runs": len(completed), "owner_participations": len(owner_runs),
        "owner_returned": len(owner_runs) >= 2,
        "returning_partner_ids": [k for k, v in partner_counts.items() if v >= 2],
        "owner_paid_runs": len(paid_runs), "owner_repaid": len(paid_runs) >= 2,
        "both_returned_and_repaid": combined,
        "program_fee_net_krw": sum(_net(p) for r in data["runs"] for p in r["payments"]
                                   if p["purpose"] == "program_fee"),
    }


def _view(row: Campaign) -> dict:
    data = deepcopy(row.data)
    for run in data["runs"]:
        result = run.get("result")
        fields = ("revenue_krw", "variable_cost_krw", "execution_cost_krw")
        run["recorded_balance_krw"] = (
            result[fields[0]] - result[fields[1]] - result[fields[2]]
            if result and all(result.get(k) is not None for k in fields) else None
        )
        run["effect_verdict"] = "인과 효과 미판정 — 기록된 매출·비용만 집계"
    return {"id": row.id, "version": row.version, **data,
            "recommendations": recommendations(row.data), "summary": summary(row.data)}


def list_campaigns(db: Session, user_id: str) -> list[dict]:
    rows = db.scalars(select(Campaign).where(Campaign.user_id == user_id).order_by(Campaign.id)).all()
    return sorted([_view(r) for r in rows], key=lambda r: r["created_at"], reverse=True)


def create(db: Session, user_id: str, conditions: Conditions) -> dict:
    row = Campaign(id=uuid4().hex, user_id=user_id, version=1, data={
        "conditions": conditions.model_dump(mode="json"), "conditions_source": "user_input",
        "created_at": _now(), "candidates": [], "runs": [], "history": [],
    })
    db.add(row)
    db.commit()
    return _view(row)


def _run(data: dict, run_id: str) -> dict:
    for run in data["runs"]:
        if run["id"] == run_id:
            return run
    raise CampaignError("실행 회차를 찾을 수 없습니다", 404)


def mutate(db: Session, user_id: str, campaign_id: str, command: Command) -> dict:
    row = _row(db, user_id, campaign_id)
    if row.version != command.version:
        raise CampaignError("다른 창에서 변경됐습니다. 새로고침 후 다시 저장하세요", 409)
    data = deepcopy(row.data)
    action, payload = command.action, command.payload
    if len(data["history"]) >= 1000:
        raise CampaignError("캠페인 기록 상한에 도달했습니다. 새 캠페인을 시작하세요")
    if action == "candidate":
        candidate = Candidate.model_validate(payload).model_dump(mode="json")
        if len(data["candidates"]) >= 50:
            raise CampaignError("후보는 캠페인당 50건까지 등록합니다")
        candidate.update(id=uuid4().hex, verification="user_submitted_not_independently_verified")
        data["candidates"].append(candidate)
    elif action == "run":
        run = RunInput.model_validate(payload).model_dump(mode="json")
        if run["candidate_id"] and not any(c["id"] == run["candidate_id"] for c in data["candidates"]):
            raise CampaignError("출처를 등록한 후보만 선택할 수 있습니다")
        if any(r["status"] not in ("completed", "cancelled") for r in data["runs"]):
            raise CampaignError("이전 실행을 완료하거나 취소한 뒤 다음 회차를 만드세요")
        completed = [r for r in data["runs"] if r["status"] == "completed"]
        if completed and run["starts_on"] <= max(r["ends_on"] for r in completed):
            raise CampaignError("재실행은 이전 완료 회차의 종료일 이후여야 합니다")
        run.update(id=uuid4().hex, status="draft", consent={}, participation={}, result=None, payments=[])
        data["runs"].append(run)
    elif action in ("consent", "participation"):
        entry = PartyEvidence.model_validate(payload).model_dump(mode="json")
        run = _run(data, entry["run_id"])
        if entry["party"] == "partner" and not run["candidate_id"]:
            raise CampaignError("자체 실행에는 협업 상대가 없습니다")
        if action == "consent" and run["status"] not in ("draft", "proposed"):
            raise CampaignError("합의 이후 증빙은 변경할 수 없습니다")
        if action == "participation":
            if run["status"] != "running":
                raise CampaignError("진행 중인 회차의 실제 참여만 기록합니다")
            if not run["starts_on"] <= entry["evidence"]["observed_on"] <= run["ends_on"]:
                raise CampaignError("참여 증빙 날짜는 실행 기간 안이어야 합니다")
        run[action][entry["party"]] = entry["evidence"]
    elif action == "transition":
        entry = Transition.model_validate(payload)
        run = _run(data, entry.run_id)
        allowed = {"draft": {"proposed", "agreed", "cancelled"}, "proposed": {"agreed", "cancelled"},
                   "agreed": {"running", "cancelled"}, "running": {"completed", "cancelled"}}
        if entry.status not in allowed.get(run["status"], set()):
            raise CampaignError("허용되지 않는 진행 상태 변경입니다")
        parties = {"owner", "partner"} if run["candidate_id"] else {"owner"}
        if entry.status == "agreed" and not parties.issubset(run["consent"]):
            raise CampaignError("필요한 당사자의 합의 증빙을 먼저 기록하세요")
        if entry.status == "running" and run["starts_on"] > _today():
            raise CampaignError("시작일 이전에는 진행 상태로 바꿀 수 없습니다")
        if entry.status == "completed":
            if run["ends_on"] > _today():
                raise CampaignError("종료일 이전에는 완료할 수 없습니다")
            if not parties.issubset(run["participation"]):
                raise CampaignError("실제 참여 증빙을 당사자별로 기록하세요")
            if run["result"] is None:
                raise CampaignError("결과 기록이 필요합니다. 모르는 수치는 비워 두세요")
        run["status"] = entry.status
    elif action == "progress":
        entry = Progress.model_validate(payload).model_dump(mode="json")
        run = _run(data, entry.pop("run_id"))
        if run["status"] in ("completed", "cancelled"):
            raise CampaignError("종료된 회차의 진행 내용을 바꿀 수 없습니다")
        run.update(entry)
    elif action == "result":
        entry = ResultInput.model_validate(payload).model_dump(mode="json")
        run = _run(data, entry.pop("run_id"))
        if run["status"] not in ("running", "completed"):
            raise CampaignError("진행 또는 완료 회차에서 결과를 기록하세요")
        if entry["evidence"]["observed_on"] < run["starts_on"]:
            raise CampaignError("결과 확인일이 실행일보다 빠릅니다")
        run["result"] = entry
    elif action == "payment":
        entry = PaymentInput.model_validate(payload).model_dump(mode="json")
        run = _run(data, entry.pop("run_id"))
        if entry["payer"] == "partner" and not run["candidate_id"]:
            raise CampaignError("협업 상대가 없는 회차입니다")
        # 동일 거래를 여러 회차로 복제해 재결제로 세지 못하게 한다.
        old = None
        for other in data["runs"]:
            for p in other["payments"]:
                if p["transaction_ref"] == entry["transaction_ref"]:
                    if other["id"] != run["id"] or p["payer"] != entry["payer"] or p["purpose"] != entry["purpose"]:
                        raise CampaignError("이미 사용한 거래 식별자입니다")
                    old = p
        if old:
            allowed = {"intent": {"paid", "cancelled"}, "paid": {"refunded"}, "refunded": {"refunded"}}
            if entry["status"] not in allowed.get(old["status"], set()):
                raise CampaignError("결제 상태를 되돌릴 수 없습니다")
            if entry["amount_krw"] != old["amount_krw"] or entry["refunded_krw"] < old["refunded_krw"]:
                raise CampaignError("기존 결제액 변경이나 환불액 감소는 허용하지 않습니다")
            if entry["evidence"]["observed_on"] < old["evidence"]["observed_on"]:
                raise CampaignError("거래 상태 변경일이 이전 확인일보다 빠릅니다")
            run["payments"].remove(old)
        elif entry["status"] == "refunded":
            raise CampaignError("실제 납부 기록을 먼저 등록한 뒤 환불을 기록하세요")
        # 환불 확인일이 결제일을 덮으면 선결제가 재결제로 둔갑하므로 원 결제일을 보존한다.
        entry["paid_on"] = (old or {}).get("paid_on") or (
            entry["evidence"]["observed_on"] if entry["status"] == "paid" else None)
        entry["source"] = "manual_evidence"
        run["payments"].append(entry)
    data["history"].append({"at": _now(), "action": action, "payload": payload, "recorded_by": user_id})
    result = db.execute(update(Campaign).where(Campaign.id == campaign_id,
                        Campaign.user_id == user_id, Campaign.version == command.version)
                        .values(data=data, version=command.version + 1), execution_options={"synchronize_session": False})
    if result.rowcount != 1:
        db.rollback()
        raise CampaignError("동시에 수정되었습니다. 새로고침하세요", 409)
    db.commit()
    db.expire_all()
    return _view(_row(db, user_id, campaign_id))
