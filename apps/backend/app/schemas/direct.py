"""직거래 연결 층 요청 스키마 (2026-11-18). 응답은 서비스가 만든 dict 를 그대로 싣는다(campaigns 와 같은 관례)."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ListingIn(BaseModel):
    """건물주 본인이 적는 매물 칸. 초안은 빈 칸을 허용하고, 필수 여부는 제출 때 본다(L4)."""

    model_config = ConfigDict(extra="forbid")

    district_id: str | None = Field(default=None, max_length=64)
    building_id: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=300)
    lat: float | None = Field(default=None, ge=33.0, le=39.0)
    lng: float | None = Field(default=None, ge=124.0, le=132.0)
    floor: int | None = Field(default=None, ge=-10, le=120)
    unit_label: str | None = Field(default=None, max_length=50)
    area_m2: float | None = Field(default=None, ge=0, le=100_000)
    use_type: str | None = Field(default=None, max_length=40)
    ledger_use: str | None = Field(default=None, max_length=60)
    deal_type: Literal["lease", "lease_popup", "popup"] | None = None
    deposit_manwon: int | None = Field(default=None, ge=0, le=10_000_000)
    monthly_rent_manwon: int | None = Field(default=None, ge=0, le=1_000_000)
    maintenance_manwon: int | None = Field(default=None, ge=0, le=100_000)
    rent_free_months: int | None = Field(default=None, ge=0, le=24)
    min_term_months: int | None = Field(default=None, ge=1, le=120)
    available_from: date | None = None
    vacant_since: date | None = None
    popup_min_days: int | None = Field(default=None, ge=1, le=365)
    popup_max_days: int | None = Field(default=None, ge=1, le=365)
    popup_daily_manwon: int | None = Field(default=None, ge=0, le=100_000)
    preferred_industries: list[str] | None = Field(default=None, max_length=20)
    excluded_industries: list[str] | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=1000)
    # 설비(2026-11-21) — None 은 「모름」
    exhaust_ok: bool | None = None
    power_kw: int | None = Field(default=None, ge=0, le=10_000)
    water_ok: bool | None = None


class VerificationIn(BaseModel):
    """게시자 신원·소유자 관계(L5). 등기 고유번호·소유자명은 관리자만 본다."""

    model_config = ConfigDict(extra="forbid")

    relation: Literal["owner", "agent", "manager"]
    registry_number: str = Field(max_length=32)
    owner_name: str = Field(max_length=50)
    delegation_note: str = Field(default="", max_length=500)


class StatusIn(BaseModel):
    action: Literal["pause", "resume", "close"]


class OfferIn(BaseModel):
    """창업자가 적는 조건 제안서(임대) · 팝업·단기 사용 신청(2026-11-21). PlaceOS 는 값을 채우거나 권하지 않는다.

    ⛔ 수수료·보수 칸이 없다(L1) — extra="forbid" 라 그런 칸을 보내면 422 다.
    """

    model_config = ConfigDict(extra="forbid")

    rent_manwon: int | None = Field(default=None, ge=0, le=1_000_000)
    deposit_manwon: int | None = Field(default=None, ge=0, le=10_000_000)
    rent_free_months: int | None = Field(default=None, ge=0, le=24)
    term_months: int | None = Field(default=None, ge=1, le=120)
    start_date: date | None = None
    popup_days: int | None = Field(default=None, ge=1, le=365)
    popup_daily_manwon: int | None = Field(default=None, ge=0, le=100_000)


class InquiryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["question", "visit", "offer", "popup"] = "question"
    body: str = Field(max_length=1000)
    visit_slots: list[str] = Field(default_factory=list, max_length=3)
    industry_key: str = Field(default="", max_length=32)
    # kind 가 offer(조건 제안) · popup(팝업·단기 신청)일 때 그 값
    offer: OfferIn | None = None


class OfferProposeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["lease", "popup"]
    offer: OfferIn


class OfferDecisionIn(BaseModel):
    action: Literal["accept", "decline", "withdraw"]


class ContractPathIn(BaseModel):
    path: Literal["direct", "broker"]


class BriefIn(BaseModel):
    """입점 희망서(2026-11-21) — 초안은 빈 칸을 허용하고, 필수 여부는 「건물주에게 보이기」 때 본다.

    ① 공개 · ② 동의 공개 · ③ 비공개 칸이 한 요청에 함께 오지만, 누가 무엇을 보는지는 서버(services/direct_briefs)가 가른다.
    ⛔ 신용 점수·등급 칸은 받지 않는다(extra="forbid").
    """

    model_config = ConfigDict(extra="forbid")

    # ① 공개
    industry_key: str | None = Field(default=None, max_length=32)
    area_min_m2: float | None = Field(default=None, ge=1, le=100_000)
    area_max_m2: float | None = Field(default=None, ge=1, le=100_000)
    floor_bands: list[Literal["first", "upper", "basement"]] | None = Field(default=None, max_length=3)
    needs_exhaust: bool | None = None
    needs_water: bool | None = None
    power_kw_min: int | None = Field(default=None, ge=1, le=10_000)
    rent_cap_manwon: int | None = Field(default=None, ge=1, le=1_000_000)
    deposit_cap_manwon: int | None = Field(default=None, ge=0, le=10_000_000)
    desired_start: date | None = None
    district_ids: list[str] | None = Field(default=None, max_length=3)
    popup_first: bool | None = None
    accept_invites: bool | None = None
    # ② 동의 공개
    summary: str | None = Field(default=None, max_length=500)
    business_stage: Literal["pre", "registered", "operating", ""] | None = None
    funding_total_manwon: int | None = Field(default=None, ge=0, le=10_000_000)
    funding_own_manwon: int | None = Field(default=None, ge=0, le=10_000_000)
    # ③ 비공개(본인 계산)
    unit_price_won: int | None = Field(default=None, ge=1, le=100_000_000)
    variable_cost_pct: float | None = Field(default=None, ge=0, le=95)
    other_fixed_manwon: int | None = Field(default=None, ge=0, le=1_000_000)
    open_days: int | None = Field(default=None, ge=1, le=31)
    target_daily_units: int | None = Field(default=None, ge=0, le=1_000_000)


class BriefStatusIn(BaseModel):
    action: Literal["activate", "pause", "close"]


class InviteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: str = Field(max_length=64)
    body: str = Field(max_length=1000)


class MessageIn(BaseModel):
    body: str = Field(max_length=1000)


class VisitIn(BaseModel):
    action: Literal["propose", "confirm", "cancel"]
    slots: list[str] = Field(default_factory=list, max_length=3)
    slot: str | None = Field(default=None, max_length=40)


class OutcomeIn(BaseModel):
    outcome: Literal["contracted", "not_contracted"]


class ReportIn(BaseModel):
    reason: Literal["fake", "not_owner", "broker", "wrong_info", "other"]
    detail: str = Field(default="", max_length=500)


class PurchaseIn(BaseModel):
    product: str = Field(max_length=40)
    target_id: str = Field(max_length=64)
    depositor_name: str = Field(max_length=50)


class AdminDecisionIn(BaseModel):
    decision: Literal["verified", "rejected"]
    note: str = Field(default="", max_length=500)


class AdminReportActionIn(BaseModel):
    action: Literal["resolve", "hide_listing", "restore_listing"]


class AdminPurchaseActionIn(BaseModel):
    action: Literal["confirm_paid", "fulfill", "cancel"]


class FloorPlanIn(BaseModel):
    """층 배치도 사진 — base64(JPEG/PNG). 클라이언트가 먼저 줄여 보내지만 서버가 형식·크기를 다시 본다(services/direct_floor_plans)."""

    model_config = ConfigDict(extra="forbid")

    mime: Literal["image/jpeg", "image/png"]
    data: str = Field(min_length=100, max_length=4_200_000)
