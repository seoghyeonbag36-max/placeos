"""입점 점검 — 「이 빈 층에 내 업종이 들어갈 수 있나」(대장·토지이음 기준 · 허가 판정 아님).

인계 문서(2026-11-15) 인터페이스 ② 의 안을 따른다. 안과 다른 점은 하나 —
`regulation_status` 에 `zoning_prohibited`(토지이음 행위제한상 그 용도지역에서 금지)를 더했다.
「대장상 용도 변경 필요」와 달리 대장을 고쳐도 풀리지 않는 경우라 따로 둔다.
"""
from typing import Literal

from pydantic import BaseModel, Field

UseCheckStatus = Literal["ledger_ok", "needs_check", "use_change_needed", "zoning_prohibited", "missing_inputs"]
CheckItemStatus = Literal["ok", "check", "blocked", "missing"]


class UseCheckItem(BaseModel):
    item: str
    status: CheckItemStatus
    reason: str
    source: str
    source_date: str | None = None
    estimated: bool = False


class UseCheckSource(BaseModel):
    name: str
    url: str


class UseCheck(BaseModel):
    pnu: str
    industry: str
    industry_label: str
    act: str = Field(description="토지이음 행위명 — 이 업종을 어떤 행위로 조회했나")
    regulation_status: UseCheckStatus
    headline: str
    checks: list[UseCheckItem]
    note: str
    sources: list[UseCheckSource]
    permission: None = None  # 허가 여부는 만들지 않는다
