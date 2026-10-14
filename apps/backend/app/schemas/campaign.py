"""오프라인 캠페인 입력 계약. 빈 실적은 None, 증빙은 사용자 제출로 표시한다."""
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Evidence(Input):
    reference: HttpUrl
    note: str = Field(min_length=3, max_length=1000)
    observed_on: date

    @model_validator(mode="after")
    def past_only(self) -> "Evidence":
        if self.observed_on > datetime.now(timezone(timedelta(hours=9))).date():
            raise ValueError("미래 날짜를 확인 실적으로 기록할 수 없습니다")
        return self


class Conditions(Input):
    store_name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=300)
    category: str = Field(min_length=1, max_length=100)
    district_id: str | None = Field(default=None, max_length=100)
    goal: Literal["quiet_hours", "first_purchase", "revisit", "group_order"]
    target_customer: str = Field(min_length=1, max_length=200)
    time_window: str = Field(min_length=1, max_length=200)
    capacity: int = Field(gt=0, le=100000)
    budget_krw: int = Field(ge=0, le=1000000000)
    offer: str = Field(min_length=1, max_length=500)
    constraints: str = Field(default="", max_length=1000)


class Candidate(Input):
    name: str = Field(min_length=1, max_length=120)
    role: Literal["audience", "capability", "space"]
    source: Literal["official_reference", "user_record"]
    evidence: Evidence
    contact: str = Field(min_length=1, max_length=300)
    fit_reason: str = Field(min_length=3, max_length=500)
    mutual_value: str = Field(min_length=3, max_length=500)


class RunInput(Input):
    candidate_id: str | None = None
    starts_on: date
    ends_on: date
    terms: str = Field(min_length=3, max_length=1500)
    next_action: str = Field(min_length=1, max_length=500)
    responsible: str = Field(min_length=1, max_length=120)
    due_on: date
    measurement: str = Field(min_length=3, max_length=500)
    stop_rule: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def dates(self) -> "RunInput":
        if self.ends_on < self.starts_on:
            raise ValueError("종료일은 시작일보다 빠를 수 없습니다")
        return self


class Result(Input):
    purchases: int | None = Field(default=None, ge=0, le=100000000)
    revenue_krw: int | None = Field(default=None, ge=0, le=100000000000)
    variable_cost_krw: int | None = Field(default=None, ge=0, le=100000000000)
    execution_cost_krw: int | None = Field(default=None, ge=0, le=100000000000)
    operator_minutes: int | None = Field(default=None, ge=0, le=10000000)
    evidence: Evidence


class Payment(Input):
    payer: Literal["owner", "partner"]
    purpose: Literal["program_fee", "campaign_expense"]
    status: Literal["intent", "paid", "cancelled", "refunded"]
    amount_krw: int = Field(gt=0, le=1000000000)
    refunded_krw: int = Field(default=0, ge=0, le=1000000000)
    transaction_ref: str = Field(min_length=3, max_length=200)
    evidence: Evidence

    @model_validator(mode="after")
    def refund(self) -> "Payment":
        if self.refunded_krw > self.amount_krw:
            raise ValueError("환불액이 결제액을 초과합니다")
        if self.status == "refunded" and self.refunded_krw == 0:
            raise ValueError("환불 금액이 필요합니다")
        if self.status != "refunded" and self.refunded_krw:
            raise ValueError("환불 상태에서만 환불 금액을 기록합니다")
        return self


class Command(Input):
    version: int = Field(ge=1)
    action: Literal["candidate", "run", "consent", "participation", "transition", "progress", "result", "payment"]
    payload: dict


class PartyEvidence(Input):
    run_id: str
    party: Literal["owner", "partner"]
    evidence: Evidence


class Transition(Input):
    run_id: str
    status: Literal["proposed", "agreed", "running", "completed", "cancelled"]


class Progress(Input):
    run_id: str
    next_action: str = Field(min_length=1, max_length=500)
    responsible: str = Field(min_length=1, max_length=120)
    due_on: date


class ResultInput(Result):
    run_id: str


class PaymentInput(Payment):
    run_id: str
