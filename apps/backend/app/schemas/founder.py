"""창업 후보 비용 계약. 미입력은 0원이 아닌 미확인이다."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Money = Annotated[int, Field(ge=0, le=1_000_000_000_000, strict=True)]


class CandidateCosts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deposit: Money | None = None
    premium: Money | None = None
    fitout: Money | None = None
    equipment: Money | None = None
    rent: Money | None = None
    maintenance: Money | None = None
    other_monthly: Money | None = None
    reserve_months: Annotated[int, Field(ge=0, le=36, strict=True)] = 3
    budget: Money | None = None


class CostAssessment(BaseModel):
    source: Literal["user_input"] = "user_input"
    currency: Literal["KRW"] = "KRW"
    known_initial: int
    known_monthly: int
    required_cash: int | None
    budget_remaining: int | None
    missing_fields: list[str]
    status: Literal["incomplete", "within_budget", "over_budget", "budget_unknown"]
    note: str
