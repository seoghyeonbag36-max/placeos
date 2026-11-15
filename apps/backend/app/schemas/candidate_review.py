"""계약 전 후보 확인 자료 — 사용자 확인 기록과 분리되는 외부 조회 계약."""
from typing import Literal

from pydantic import BaseModel, Field


class ReviewFact(BaseModel):
    label: str
    value: str
    scope: str


class ReviewSource(BaseModel):
    name: str
    url: str


class CandidateReview(BaseModel):
    building_id: str
    unit_id: str | None = None
    pnu: str
    queried_at: str
    source_date: str | None = None
    ledger_status: str
    ledger_note: str
    facts: list[ReviewFact] = Field(default_factory=list)
    regulation_status: Literal["missing_inputs"] = "missing_inputs"
    regulation_note: str
    sources: list[ReviewSource]
    permission: None = None
