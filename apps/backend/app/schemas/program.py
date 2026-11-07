"""Program 리뉴얼(2026-11-07) 응답 — 지원 프로그램 · 네트워킹 · 오프라인 마케팅 실행 카드.

원천 상태(SourceStatus.status): ok(불렀다 · 0건 가능) | no_key(키 미설정) | error(실패 — 지난 목록을 보이지 않는다).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SourceStatus(BaseModel):
    id: str
    name: str
    status: Literal["ok", "no_key", "error"]
    count: int = 0
    fetched_at: str | None = None
    note: str | None = None


class ProgramRegion(BaseModel):
    sido: str
    local: str | None = None
    label: str


class SupportItem(BaseModel):
    source: Literal["kstartup", "gov24", "bizinfo"]
    source_label: str
    id: str
    title: str
    org: str | None = None
    region: str | None = None
    category: str | None = None
    target: str | None = None
    start: str | None = None
    end: str | None = None
    # 정부24 처럼 신청기한이 자유 문구인 원천 — 날짜로 읽지 않고 원문 그대로 보인다
    deadline_text: str | None = None
    url: str | None = None
    apply_url: str | None = None
    summary: str | None = None
    matched: list[str] = Field(default_factory=list)


class SupportPrograms(BaseModel):
    """GET /program/support — 조건이 맞을 수 있는 지원 공고(자격 판정이 아니다)."""
    district_id: str
    region: ProgramRegion
    stage: Literal["pre_founder", "founder"] | None = None
    industry: str | None = None
    items: list[SupportItem]
    total: int
    sources: list[SourceStatus]
    note: str


class NetworkEvent(BaseModel):
    source: Literal["kstartup", "bizinfo_event"]
    source_label: str
    id: str
    title: str
    kind: str | None = None
    org: str | None = None
    area: str | None = None
    start: str | None = None
    end: str | None = None
    period_text: str | None = None
    apply_period: str | None = None
    url: str | None = None
    summary: str | None = None
    matched: list[str] = Field(default_factory=list)


class Complement(BaseModel):
    key: str | None = None
    label: str | None = None
    lift: float | None = None
    n_both: int | None = None


class DirectoryEntry(BaseModel):
    name: str
    url: str
    role: str


class ProgramNetwork(BaseModel):
    """GET /program/network — 공식 행사·지원기관 + 방문형 이웃 가게. 개인 연락처 칸이 없다(설계)."""
    district_id: str
    region: ProgramRegion
    industry: str | None = None
    events: list[NetworkEvent]
    total_events: int
    sources: list[SourceStatus]
    complements: list[Complement]
    complements_note: str | None = None
    questions: list[str]
    directory: list[DirectoryEntry]
    note: str


class CardBasis(BaseModel):
    label: str
    value: str


class ExecutionCard(BaseModel):
    kind: Literal["event", "time", "neighbor", "own"]
    title: str
    when: str
    where: str
    who: str
    what: str
    measure: str
    basis: list[CardBasis]
    caveat: str | None = None
    link: str | None = None


class ExecutionPlan(BaseModel):
    """GET /program/plan — 근거가 있는 실행 카드만. 예산·예상 성과는 싣지 않는다."""
    district_id: str
    mode: Literal["popup", "soft_open", "mvp", "actual_open"]
    cards: list[ExecutionCard]
    events_source: str
    notes: list[str]
    note: str
