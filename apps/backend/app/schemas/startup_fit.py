"""Page 빈 층의 창업 가능 등급 · 건물주 등록 스키마(2026-11-25) — `services/startup_fit` 의 응답 모양.

등급은 허가 판정이 아니고(대장 · 토지이음 기재 + Posting 3-Tier 1층 기준 추정), 건물주 등록은 게시 중 · 소유자 확인 매물(L3)만
센다. `owner_status` 가 ready 가 아니면 `owner` 가 비어 있어도 「등록 없음」이 아니다 — 화면은 `owner_note` 를 그대로 적는다.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class StartupReason(BaseModel):
    code: str
    # hard = 어려움으로 보낸 사유 · soft = 조건부로 보낸 사유 · ok = 열림 · info = 참고(등급 불변)
    tone: Literal["hard", "soft", "ok", "info"]
    text: str


class OpenIndustry(BaseModel):
    key: str
    label: str


class OwnerListingBrief(BaseModel):
    """같은 건물 · 층에 건물주가 직접 올린 매물(공개 카드에서 고른 칸만 · 소유자 정보 없음)."""
    id: str
    title: str = ""
    unit_label: str = ""
    area_m2: float | None = None
    deal_type: str | None = None
    deposit_manwon: int | None = None
    monthly_rent_manwon: int | None = None


class StartupFitUnit(BaseModel):
    id: str
    building_id: str | None = None
    pnu: str | None = None
    n: str = ""
    floor: int
    floor_label: str
    certainty: Literal["confirmed", "probable"]
    area_m2: float | None = None
    purps: str = ""
    grade: Literal["A1", "A2", "B", "C"]
    grade_label: str = ""
    reasons: list[StartupReason] = []
    open_industries: list[OpenIndustry] = []
    best_tier: str | None = None
    best_margin_1f: float | None = None     # 1층 기준 최고 순익률(월 순익 ÷ 매출)
    seoul_avg: float | None = None          # 그 가격대 서울 평균 영업이익률(KOSIS 2024)
    owner: list[OwnerListingBrief] = []


class StartupFitList(BaseModel):
    district_id: str
    computed_at: str
    owner_status: Literal["ready", "not_ready", "unavailable"]
    owner_note: str
    counts: dict[str, int]
    owner_floors: int
    note: str
    units: list[StartupFitUnit]
