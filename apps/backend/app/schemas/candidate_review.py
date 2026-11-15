"""계약 전 후보 확인 자료 — 사용자 확인 기록과 분리되는 외부 조회 계약."""
from pydantic import BaseModel, Field

from app.schemas.use_check import UseCheck, UseCheckStatus


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
    # 2026-11-15 — 업종(industry)을 받으면 입점 점검(services/use_check)의 다섯 갈래. 업종이 없거나 층·대장을 이 후보에
    # 확실히 잇지 못하면 missing_inputs 로 남는다(지어내지 않는다). 허가 판정이 아니다 — permission 은 늘 None.
    regulation_status: UseCheckStatus = "missing_inputs"
    regulation_note: str
    industry: str | None = None
    use_check: UseCheck | None = None
    sources: list[ReviewSource]
    permission: None = None
