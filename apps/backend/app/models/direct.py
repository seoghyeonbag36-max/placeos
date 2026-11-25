"""직거래 연결 층 ORM — 건물주가 직접 올린 빈 자리 · 소유자 확인 · 문의/방문 · 신고 · 정액 상품 신청 (2026-11-18).

docs/decision-owner-direct-matching-2026-11-18.md. 계정층(models/auth.py)과 같은 관례를 따른다 — id 는 String(32)
uuid hex, 시각은 timezone 있는 DateTime(파이썬 기본값), Postgres 전용 타입은 쓰지 않는다(테스트가 SQLite 다).

⛔ 이 표들에는 「성사·중개 수수료」 칸이 없다. 건물주·창업자를 이어 주고 보수를 받으면 명목과 무관하게 중개업이고
   (공인중개사법 제2조), 등록 없이 하면 제48조 위반이다. 돈은 `purchase_intents` 의 정액 상품으로만 받는다.
⛔ 권리금 칸도 없다 — 권리금 계약서 작성 대행은 행정사법 위반 판례가 있다(2024-04 확정). 빈 자리(공실) 직거래만 다룬다.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DirectListing(Base):
    """건물주가 직접 올린 빈 자리 한 곳(건물·층·호).

    초안(draft)은 빈 칸이 있어도 저장된다 — 필수 정보는 제출(submit) 때 검사한다(services/direct_listings.missing_required).
    공개 조건은 status == published 이고 최신 소유자 확인이 verified 인 것(L3).
    """

    __tablename__ = "direct_listings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    poster_relation: Mapped[str] = mapped_column(String(16), default="owner")
    district_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    building_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str] = mapped_column(String(300), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor: Mapped[int] = mapped_column(Integer, default=0)
    unit_label: Mapped[str] = mapped_column(String(50), default="")
    area_m2: Mapped[float] = mapped_column(Float, default=0.0)
    use_type: Mapped[str] = mapped_column(String(40), default="")
    ledger_use: Mapped[str] = mapped_column(String(60), default="")
    deal_type: Mapped[str] = mapped_column(String(16), default="lease")
    deposit_manwon: Mapped[int] = mapped_column(Integer, default=0)
    monthly_rent_manwon: Mapped[int] = mapped_column(Integer, default=0)
    maintenance_manwon: Mapped[int] = mapped_column(Integer, default=0)
    rent_free_months: Mapped[int] = mapped_column(Integer, default=0)
    min_term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    vacant_since: Mapped[date | None] = mapped_column(Date, nullable=True)
    popup_min_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    popup_max_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    popup_daily_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_industries: Mapped[list] = mapped_column(JSON, default=list)
    excluded_industries: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(String(1000), default="")
    promoted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 설비(2026-11-21 · 입점 희망서의 「필요 설비」와 맞춰 보는 칸). None = 건물주가 적지 않음(모름) — 「없음」과 다르다.
    exhaust_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    power_kw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    water_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class ListingVerification(Base):
    """게시자 신원·소유자 관계 확인 요청(2027-06-17 시행 플랫폼 확인 의무 대비).

    등기 고유번호·소유자명은 관리자만 본다(L5). 관리자가 인터넷등기소에서 대조하고 verified/rejected 를 정한다.
    """

    __tablename__ = "direct_listing_verifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("direct_listings.id", ondelete="CASCADE"), index=True)
    submitted_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    relation: Mapped[str] = mapped_column(String(16), default="owner")
    registry_number: Mapped[str] = mapped_column(String(32), default="")
    owner_name: Mapped[str] = mapped_column(String(100), default="")
    delegation_note: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reviewer_note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DirectInquiry(Base):
    """창업자 → 건물주 문의 한 건(질문 또는 방문 요청). PlaceOS 는 조건을 조율하지 않는다(L2)."""

    __tablename__ = "direct_inquiries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("direct_listings.id", ondelete="CASCADE"), index=True)
    founder_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="question")
    status: Mapped[str] = mapped_column(String(16), default="open")
    industry_key: Mapped[str] = mapped_column(String(32), default="")
    visit_slots: Mapped[list] = mapped_column(JSON, default=list)
    confirmed_slot: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), default="")
    outcome_by: Mapped[str] = mapped_column(String(16), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # 2026-11-21 — 누가 이 대화를 열었나(founder = 창업자 문의 · owner = 건물주가 희망서를 보고 보낸 제안).
    # 창업자 하루 문의 상한과 「문의 수요」 신호는 founder 가 연 것만 센다.
    initiated_by: Mapped[str] = mapped_column(String(16), default="founder", server_default="founder")
    # 계약 진행 방법 — "" 미정 · direct 당사자 직접 · broker 제휴 공인중개사. 기록일 뿐 과금과 무관하다(L1).
    contract_path: Mapped[str] = mapped_column(String(16), default="", server_default="")


class DirectMessage(Base):
    __tablename__ = "direct_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    inquiry_id: Mapped[str] = mapped_column(ForeignKey("direct_inquiries.id", ondelete="CASCADE"), index=True)
    sender_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ListingReport(Base):
    """허위·대리 게시 신고(국토부 직거래 플랫폼 운영 가이드 2025-02 — 신고·자율 시정)."""

    __tablename__ = "direct_listing_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("direct_listings.id", ondelete="CASCADE"), index=True)
    reporter_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"),
                                                          nullable=True)
    reason: Mapped[str] = mapped_column(String(16), default="other")
    detail: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PurchaseIntent(Base):
    """정액 상품 신청 — 결제는 계좌이체, 관리자가 입금을 확인한다(PG 없음 · decision-lightweight-first §3).

    탈퇴해도 지우지 않고 user_id·입금자명을 비워 남긴다 — 입금 확인 기록은 거래 기록이라 바로 지우지 않는다.
    """

    __tablename__ = "purchase_intents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
                                                index=True)
    product: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(20), default="requested")
    amount_krw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depositor_name: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ── 입점 희망서 · 조건 제안서 (2026-11-21 · docs/decision-founder-brief-2026-11-21.md) ──────────────

class DirectBrief(Base):
    """창업자 입점 희망서 — 「이 업종으로 이런 자리를 찾는다」. 한 사람에 하나(user_id 고유).

    칸을 세 단계로 나눠 담는다 — 어느 칸이 누구에게 보이는지는 services/direct_briefs 가 정한다.
    ① 공개: 같은 상권에 소유자 확인 매물이 있는 건물주에게. **구조화된 칸만** 둔다(자유 서술 없음 — 연락처·아이디어가 새지 않게).
    ② 동의 공개: 창업자가 대화 중인 건물주 한 명에게 직접 열어 줄 때만 — 사업 개요 · 단계 · 자금 계획(본인 기재).
    ③ 비공개: 본인 계산에만 — 객단가·변동비율·기타 고정비·영업일·목표 판매량(요구 판매량 계산 · services/direct_fit).

    ⛔ 신용 점수·등급·순위 칸은 없다. 개인의 신용(임대료를 낼 수 있나)을 평가해 남에게 주면 개인신용평가업
       (신용정보법 — 금융위 허가)에 걸릴 수 있고, 검증하지 않은 점수는 KPI 규칙 ①②를 어긴다. 확인한 사실만 보인다.
    """

    __tablename__ = "direct_briefs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    # ① 공개
    industry_key: Mapped[str] = mapped_column(String(32), default="")
    area_min_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_max_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor_bands: Mapped[list] = mapped_column(JSON, default=list)
    needs_exhaust: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_water: Mapped[bool] = mapped_column(Boolean, default=False)
    power_kw_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rent_cap_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit_cap_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    desired_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    district_ids: Mapped[list] = mapped_column(JSON, default=list)
    popup_first: Mapped[bool] = mapped_column(Boolean, default=False)
    accept_invites: Mapped[bool] = mapped_column(Boolean, default=True)
    # ② 동의 공개
    summary: Mapped[str] = mapped_column(String(500), default="")
    business_stage: Mapped[str] = mapped_column(String(16), default="")
    funding_total_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    funding_own_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ③ 비공개
    unit_price_won: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variable_cost_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    other_fixed_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    open_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_daily_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BriefDisclosure(Base):
    """창업자가 희망서 ② 단계를 열어 준 건물주 — 대화(문의) 상대에게만, 창업자가 언제든 거둔다(행을 지운다)."""

    __tablename__ = "direct_brief_disclosures"
    __table_args__ = (UniqueConstraint("brief_id", "owner_user_id", name="uq_direct_brief_disclosure"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    brief_id: Mapped[str] = mapped_column(ForeignKey("direct_briefs.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DirectOffer(Base):
    """창업자가 적는 조건 제안서(임대 조건) 또는 팝업·단기 사용 신청 — 한 문의(대화)에 딸린다.

    PlaceOS 는 값을 제안하거나 조율하지 않는다(L2) — 창업자가 적고 건물주가 받거나(accepted) 거절한다(declined).
    「받음」은 **그 조건으로 계약 이야기를 이어 간다는 뜻이지 계약이 아니다.** 계약은 당사자 직접 또는 제휴 공인중개사가 한다.
    ⛔ 수수료·보수 칸이 없다 — 제안·수락·성사에 연동한 과금은 중개 보수다(공인중개사법 제2조·제48조).
    """

    __tablename__ = "direct_offers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    inquiry_id: Mapped[str] = mapped_column(ForeignKey("direct_inquiries.id", ondelete="CASCADE"), index=True)
    proposer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16), default="lease")
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    rent_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rent_free_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    popup_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    popup_daily_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ── 층 배치도 사진 (2026-11-22 · docs/decision-pppp-owner-founder-2026-11-22.md) ─────────────────────

class DirectFloorPlan(Base):
    """건물주가 올린 이 층(매물)의 **실제 배치도 사진** — 한 매물에 한 장(listing_id 고유).

    Page 의 개략(가상) 배치도 자리에 이 사진이 대신 보인다. 공개 조건은 매물과 같다(게시 중 + 소유자 확인 verified — L3).
    사진은 DB 에 바이트로 둔다(Cloud Run 은 디스크가 없고 버킷을 새로 들이지 않는다 — decision-lightweight-first).
    올릴 때 서버가 EXIF·XMP·주석(촬영 위치·기기 정보)을 떼고, 한 장 1.5MB · 한 사람 30MB 로 막는다.
    ⛔ 사진은 건물주 **본인이** 올린다 — PlaceOS 가 대신 그려 넣거나 고쳐 주지 않는다(L1·공인중개사법 제18조의2 ③과 같은 원칙).
    """

    __tablename__ = "direct_floor_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("direct_listings.id", ondelete="CASCADE"), unique=True, index=True)
    mime: Mapped[str] = mapped_column(String(16), default="image/jpeg")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
