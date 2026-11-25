"""직거래 관리자 창구 — 소유자 확인 · 신고 처리 · 퍼널 (2026-11-18).

관리자는 매물 **내용을 고치지 않는다**(L2) — 확인(verified)·반려(rejected)·숨김·복구만 한다. 소유자명·등기 고유번호는
이 창구에서만 원문으로 보인다(L5). 퍼널은 계측기다 — n 이 작으면 비율을 말하지 않는다(KPI 규칙 ②).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.direct import (
    BriefDisclosure, DirectBrief, DirectInquiry, DirectListing, DirectOffer, ListingReport, ListingVerification,
    PurchaseIntent,
)
from app.services.direct_listings import DirectError, aware, is_public, title
from app.services.direct_pricing import floor_band


def verifications(db: Session, status: str = "pending") -> list[dict[str, Any]]:
    rows = db.execute(select(ListingVerification).where(ListingVerification.status == status)
                      .order_by(ListingVerification.created_at.asc())).scalars().all()
    out = []
    for v in rows:
        listing = db.get(DirectListing, v.listing_id)
        out.append({"id": v.id, "listing_id": v.listing_id, "listing_title": title(listing) if listing else "",
                    "address": listing.address if listing else "", "relation": v.relation,
                    "registry_number": v.registry_number, "owner_name": v.owner_name,
                    "delegation_note": v.delegation_note, "status": v.status,
                    "created_at": aware(v.created_at).isoformat()})
    return out


def decide(db: Session, verification_id: str, decision: str, note: str = "") -> dict[str, Any]:
    v = db.get(ListingVerification, verification_id)
    if v is None:
        raise DirectError(404, "확인 요청을 찾지 못했어요")
    if v.status != "pending":
        raise DirectError(409, "이미 결정한 요청이에요")
    listing = db.get(DirectListing, v.listing_id)
    if listing is None:
        raise DirectError(404, "매물을 찾지 못했어요")
    now = datetime.now(timezone.utc)
    if decision == "verified":
        v.status = "verified"
        listing.status = "published"
        listing.published_at = listing.published_at or now
    elif decision == "rejected":
        v.status = "rejected"
        listing.status = "rejected"
    else:
        raise DirectError(422, "verified 또는 rejected 로 정해 주세요")
    v.reviewer_note = (note or "")[:500]
    v.decided_at = now
    listing.updated_at = now
    db.commit()
    return {"id": v.id, "status": v.status, "listing_id": listing.id, "listing_status": listing.status}


def reports(db: Session, status: str = "open") -> list[dict[str, Any]]:
    rows = db.execute(select(ListingReport).where(ListingReport.status == status)
                      .order_by(ListingReport.created_at.asc())).scalars().all()
    out = []
    for r in rows:
        listing = db.get(DirectListing, r.listing_id)
        out.append({"id": r.id, "listing_id": r.listing_id, "listing_title": title(listing) if listing else "",
                    "listing_status": listing.status if listing else None, "reason": r.reason, "detail": r.detail,
                    "status": r.status, "created_at": aware(r.created_at).isoformat()})
    return out


def act_on_report(db: Session, report_id: str, action: str) -> dict[str, Any]:
    r = db.get(ListingReport, report_id)
    if r is None:
        raise DirectError(404, "신고를 찾지 못했어요")
    listing = db.get(DirectListing, r.listing_id)
    now = datetime.now(timezone.utc)
    if action == "resolve":
        r.status = "resolved"
    elif action == "hide_listing":
        r.status = "resolved"
        if listing is not None:
            listing.status = "hidden"
            listing.updated_at = now
    elif action == "restore_listing":
        # 신고를 모두 닫고 매물을 되살린다 — 소유자 확인이 살아 있을 때만 게시로
        for other in db.execute(select(ListingReport).where(ListingReport.listing_id == r.listing_id,
                                                            ListingReport.status == "open")).scalars():
            other.status = "resolved"
        r.status = "resolved"
        if listing is not None and listing.status == "hidden":
            listing.status = "published"
            db.flush()
            if not is_public(db, listing):
                listing.status = "pending"
            listing.updated_at = now
    else:
        raise DirectError(422, "resolve · hide_listing · restore_listing 중에서 골라 주세요")
    db.commit()
    return {"id": r.id, "status": r.status, "listing_status": listing.status if listing else None}


def funnel(db: Session) -> dict[str, Any]:
    by_status = dict(db.execute(select(DirectListing.status, func.count()).group_by(DirectListing.status)).all())
    public_rows = [listing for listing in db.execute(select(DirectListing).where(DirectListing.status == "published"))
                   .scalars() if is_public(db, listing)]
    public_n = len(public_rows)
    # 2026-11-21 사용자 확인 — 좋은 1층은 이미 중개사에게 가 있다고 보고, 직거래는 1층 밖(상층·지하)이 몰린다고 미리 안다.
    # 그 쏠림을 세는 칸이다(판정이 아니라 분포).
    bands = {"first": 0, "upper": 0, "basement": 0}
    for listing in public_rows:
        bands[floor_band(listing.floor)] += 1
    by_kind = dict(db.execute(select(DirectInquiry.kind, func.count()).group_by(DirectInquiry.kind)).all())
    scheduled = db.execute(select(func.count()).select_from(DirectInquiry)
                           .where(DirectInquiry.confirmed_slot.is_not(None))).scalar_one()
    outcomes = dict(db.execute(select(DirectInquiry.outcome, func.count()).group_by(DirectInquiry.outcome)).all())
    purchases = [{"product": p, "status": s, "n": n} for p, s, n in db.execute(
        select(PurchaseIntent.product, PurchaseIntent.status, func.count())
        .group_by(PurchaseIntent.product, PurchaseIntent.status)).all()]
    total_inq = sum(by_kind.values())
    by_initiator = dict(db.execute(select(DirectInquiry.initiated_by, func.count())
                                   .group_by(DirectInquiry.initiated_by)).all())
    now = datetime.now(timezone.utc)
    briefs = db.execute(select(DirectBrief)).scalars().all()
    brief_status: dict[str, int] = {}
    for b in briefs:
        brief_status[b.status] = brief_status.get(b.status, 0) + 1
    live = [b for b in briefs if b.status == "active" and aware(b.expires_at) is not None and aware(b.expires_at) > now]
    brief_bands = {"first": 0, "upper": 0, "basement": 0}
    for b in live:
        for band in b.floor_bands or []:
            if band in brief_bands:
                brief_bands[band] += 1
    offers = [{"kind": k, "status": s, "n": n} for k, s, n in db.execute(
        select(DirectOffer.kind, DirectOffer.status, func.count())
        .group_by(DirectOffer.kind, DirectOffer.status)).all()]
    contract_paths = dict(db.execute(select(DirectInquiry.contract_path, func.count())
                                     .group_by(DirectInquiry.contract_path)).all())
    return {
        "listings_by_status": by_status,
        "public_listings": public_n,
        "public_listings_by_floor_band": bands,
        "inquiries_total": total_inq,
        "inquiries_by_kind": by_kind,
        "inquiries_by_initiator": by_initiator,
        "briefs": {
            "by_status": brief_status,
            "live": len(live),
            "live_by_floor_band": brief_bands,
            "live_popup_first": sum(1 for b in live if b.popup_first),
            "disclosures": db.execute(select(func.count()).select_from(BriefDisclosure)).scalar_one(),
        },
        "offers": offers,
        "contract_paths": {"direct": contract_paths.get("direct", 0), "broker": contract_paths.get("broker", 0),
                           "undecided": contract_paths.get("", 0)},
        "visits_scheduled": scheduled,
        "outcomes": {"contracted": outcomes.get("contracted", 0), "not_contracted": outcomes.get("not_contracted", 0),
                     "unreported": outcomes.get("", 0)},
        "purchases": purchases,
        "note": "계측기다 — n 이 작으면 비율을 말하지 않는다. 계약 여부는 당사자 자기보고라 과소·과대가 섞인다.",
    }
