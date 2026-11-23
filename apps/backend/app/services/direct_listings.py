"""직거래 매물 — 건물주 직접 등록 · 필수 정보 · 소유자 확인 · 공개 조건 · 신고 (2026-11-18).

docs/decision-owner-direct-matching-2026-11-18.md 의 법적 불변식(L1~L10)을 여기서 지킨다.

- 매물은 **건물주 본인**이 쓴다. PlaceOS(관리자 포함)는 내용을 대신 쓰거나 고치지 않는다 — 공인중개사법 제18조의2 ③
  (비개업자가 중개업을 하려고 표시·광고) · L2. 관리자는 확인·반려·숨김만 한다(services/direct_admin).
- 공개 = `published` 이고 최신 소유자 확인이 `verified` 인 것(L3). 2027-06-17 시행 「플랫폼의 게시자 신원·소유자 관계 확인
  의무」(부동산거래신고법 개정)를 미리 따른다.
- 필수 정보(소재지·면적·가격·종류·거래 형태·층)가 없으면 제출할 수 없다(L4).
- 등기 고유번호는 끝 4자리만, 소유자명은 관리자에게만 보인다(L5).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models.direct import (
    DirectInquiry, DirectListing, DirectMessage, DirectOffer, ListingReport, ListingVerification,
)

# 화면·응답에 그대로 싣는 고지문(L8). 「받지 않습니다」 부정문 말고는 과금 표현을 쓰지 않는다(L1).
DIRECT_NOTICE = ("PlaceOS는 부동산 중개를 하지 않으며 중개보수·성사 수수료를 받지 않습니다. "
                 "임대 조건은 건물주와 직접 정하고, 계약서 검토가 필요하면 변호사·법무사 등 전문가와 상의하세요.")

# 「장기 공실」 표시 규칙 — 건물주가 적은 공실 시작일 기준. 판정이 아니라 목록을 거르는 표시다.
LONG_VACANCY_MONTHS = 6
# 서로 다른 신고자가 이만큼 open 신고를 남기면 관리자 확인 전까지 숨긴다(국토부 직거래 플랫폼 운영 가이드 — 자율 시정).
AUTO_HIDE_REPORTERS = 3

USE_TYPES = ("제1종 근린생활시설", "제2종 근린생활시설", "판매시설", "업무시설", "교육연구시설", "의료시설", "기타")
DEAL_TYPES = ("lease", "lease_popup", "popup")
DEAL_LABELS = {"lease": "임대", "lease_popup": "임대 · 팝업(단기) 가능", "popup": "팝업(단기) 사용만"}
RELATIONS = ("owner", "agent", "manager")
RELATION_LABELS = {"owner": "소유자 본인", "agent": "소유자의 위임을 받은 대리인", "manager": "관리단·관리회사(위임)"}
REPORT_REASONS = ("fake", "not_owner", "broker", "wrong_info", "other")
STATUS_LABELS = {
    "draft": "작성 중", "pending": "소유자 확인 대기", "published": "게시 중", "paused": "일시중지",
    "rejected": "확인 반려", "hidden": "숨김(신고 확인 중)", "closed": "종료",
}
REQUIRED_LABELS = {
    "address": "소재지(주소)", "area_m2": "면적(㎡)", "price": "가격(보증금·월세)", "popup_price": "팝업 일 단가",
    "use_type": "건물 용도(종류)", "deal_type": "거래 형태", "floor": "층",
}

# 게시 중에 바뀌면 소유자 확인을 다시 받는 칸 — 「어느 자리인가」가 바뀌는 칸이다. 가격·설명은 게시 중 수정 가능.
CORE_FIELDS = ("address", "floor", "area_m2", "use_type", "district_id", "building_id", "unit_label")
EDITABLE_FIELDS = (
    "district_id", "building_id", "address", "lat", "lng", "floor", "unit_label", "area_m2", "use_type", "ledger_use",
    "deal_type", "deposit_manwon", "monthly_rent_manwon", "maintenance_manwon", "rent_free_months", "min_term_months",
    "available_from", "vacant_since", "popup_min_days", "popup_max_days", "popup_daily_manwon",
    "preferred_industries", "excluded_industries", "description",
    # 설비(2026-11-21) — 입점 희망서의 「필요 설비」와 맞춰 본다. None 은 「모름」이다
    "exhaust_ok", "power_kw", "water_ok",
)

_REGISTRY_RE = re.compile(r"^[0-9-]{14,24}$")


class DirectError(Exception):
    """서비스 오류 — 라우터가 HTTP 상태로 옮긴다. `missing` 은 필수 정보 누락 목록(L4)."""

    def __init__(self, status: int, message: str, missing: list[str] | None = None):
        super().__init__(message)
        self.status = status
        self.missing = missing or []


def _now() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite 는 timezone 을 버리고 돌려준다 — 비교 전에 UTC 로 맞춘다(Postgres 는 그대로)."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def schema_ready(db: Session) -> bool:
    """배포(자동)와 마이그레이션(수동) 사이에도 앱이 서도록 — 표가 없으면 직거래 기능만 「준비 중」으로 물러난다.

    2026-11-21: 모델이 b8c9d0e1f2a3(희망서·조건 제안 · 문의 칼럼 추가)까지 읽으므로 그 표까지 있어야 「준비됨」이다 —
    a7b8c9d0e1f2 만 올린 DB 에서 문의를 읽으면 없는 칼럼(initiated_by)을 SELECT 해 500 이 난다.
    """
    ins = inspect(db.connection())
    return ins.has_table(DirectListing.__tablename__) and ins.has_table(DirectOffer.__tablename__)


# ── 조회 ───────────────────────────────────────────────────────────────────

def get_listing(db: Session, listing_id: str) -> DirectListing | None:
    return db.get(DirectListing, listing_id)


def get_owned(db: Session, user_id: str, listing_id: str) -> DirectListing:
    listing = db.get(DirectListing, listing_id)
    if listing is None or listing.owner_user_id != user_id:
        raise DirectError(404, "매물을 찾지 못했어요")
    return listing


def latest_verification(db: Session, listing_id: str) -> ListingVerification | None:
    return db.execute(select(ListingVerification).where(ListingVerification.listing_id == listing_id)
                      .order_by(ListingVerification.created_at.desc())).scalars().first()


def is_public(db: Session, listing: DirectListing) -> bool:
    """L3 — 게시 중이고 최신 소유자 확인이 verified 인 매물만 공개한다."""
    if listing.status != "published":
        return False
    v = latest_verification(db, listing.id)
    return v is not None and v.status == "verified"


def missing_required(listing: DirectListing) -> list[str]:
    """제출 전 필수 정보(L4). 빈 칸의 키를 돌려준다 — 화면은 REQUIRED_LABELS 로 보인다."""
    miss: list[str] = []
    if not (listing.address or "").strip():
        miss.append("address")
    if not listing.area_m2 or listing.area_m2 <= 0:
        miss.append("area_m2")
    if listing.use_type not in USE_TYPES:
        miss.append("use_type")
    if listing.deal_type not in DEAL_TYPES:
        miss.append("deal_type")
    if not listing.floor:
        miss.append("floor")
    if listing.deal_type in ("lease", "lease_popup") and not (listing.monthly_rent_manwon or 0) > 0:
        miss.append("price")
    if listing.deal_type in ("lease_popup", "popup") and not (listing.popup_daily_manwon or 0) > 0:
        miss.append("popup_price")
    return miss


# ── 표시 ───────────────────────────────────────────────────────────────────

def mask_registry(number: str | None) -> str:
    digits = re.sub(r"[^0-9]", "", number or "")
    return f"****-****-{digits[-4:]}" if len(digits) >= 4 else ""


def is_ad(listing: DirectListing, now: datetime | None = None) -> bool:
    """L6 — 상단 노출(정액 광고) 중인가. 응답의 is_ad 와 화면의 「광고」 배지가 이 값을 따른다."""
    until = aware(listing.promoted_until)
    return until is not None and until > (now or _now())


def vacant_months(listing: DirectListing, today: date | None = None) -> int | None:
    if listing.vacant_since is None:
        return None
    today = today or _now().date()
    months = (today.year - listing.vacant_since.year) * 12 + (today.month - listing.vacant_since.month)
    if today.day < listing.vacant_since.day:
        months -= 1
    return max(0, months)


def flags(listing: DirectListing, today: date | None = None) -> dict[str, Any]:
    """먼저 가져갈 자리(장기 공실·상층·팝업)의 표시. 판정이 아니다."""
    months = vacant_months(listing, today)
    return {
        "upper_floor": listing.floor >= 2,
        "basement": listing.floor < 0,
        "long_vacancy": months is not None and months >= LONG_VACANCY_MONTHS,
        "vacant_months": months,
        "popup_ok": listing.deal_type in ("lease_popup", "popup"),
    }


def floor_text(floor: int) -> str:
    return f"지하 {abs(floor)}층" if floor < 0 else f"{floor}층"


def title(listing: DirectListing) -> str:
    unit = f" {listing.unit_label}" if listing.unit_label else ""
    return f"{listing.address} {floor_text(listing.floor)}{unit}".strip()


def card(listing: DirectListing, now: datetime | None = None) -> dict[str, Any]:
    """공개 목록·상세에 싣는 값. 소유자 정보(이름·등기 번호)는 싣지 않는다(L5)."""
    now = now or _now()
    return {
        "id": listing.id,
        "title": title(listing),
        "district_id": listing.district_id,
        "building_id": listing.building_id,
        "address": listing.address,
        "lat": listing.lat,
        "lng": listing.lng,
        "floor": listing.floor,
        "unit_label": listing.unit_label,
        "area_m2": listing.area_m2,
        "use_type": listing.use_type,
        "ledger_use": listing.ledger_use,
        "deal_type": listing.deal_type,
        "deal_label": DEAL_LABELS.get(listing.deal_type, listing.deal_type),
        "deposit_manwon": listing.deposit_manwon,
        "monthly_rent_manwon": listing.monthly_rent_manwon,
        "maintenance_manwon": listing.maintenance_manwon,
        "rent_free_months": listing.rent_free_months,
        "min_term_months": listing.min_term_months,
        "available_from": listing.available_from.isoformat() if listing.available_from else None,
        "vacant_since": listing.vacant_since.isoformat() if listing.vacant_since else None,
        "popup_min_days": listing.popup_min_days,
        "popup_max_days": listing.popup_max_days,
        "popup_daily_manwon": listing.popup_daily_manwon,
        "preferred_industries": list(listing.preferred_industries or []),
        "excluded_industries": list(listing.excluded_industries or []),
        "description": listing.description,
        # 설비 — None 은 건물주가 적지 않은 것(모름). 화면은 「없음」과 「모름」을 가른다
        "facilities": {"exhaust_ok": listing.exhaust_ok, "power_kw": listing.power_kw, "water_ok": listing.water_ok},
        "poster_relation": listing.poster_relation,
        "poster_label": RELATION_LABELS.get(listing.poster_relation, ""),
        "verified": True,
        "is_ad": is_ad(listing, now),
        "flags": flags(listing),
        "published_at": aware(listing.published_at).isoformat() if listing.published_at else None,
    }


def owner_view(db: Session, listing: DirectListing) -> dict[str, Any]:
    """소유자 본인 화면용 — 상태와 확인 진행(등기 번호는 끝 4자리)을 더한다."""
    out = card(listing)
    v = latest_verification(db, listing.id)
    out.update({
        "verified": v is not None and v.status == "verified",
        "status": listing.status,
        "status_label": STATUS_LABELS.get(listing.status, listing.status),
        "missing": missing_required(listing),
        "promoted_until": aware(listing.promoted_until).isoformat() if listing.promoted_until else None,
        "verification": None if v is None else {
            "status": v.status, "relation": v.relation, "registry_masked": mask_registry(v.registry_number),
            "reviewer_note": v.reviewer_note if v.status == "rejected" else "",
            "created_at": aware(v.created_at).isoformat(),
        },
    })
    return out


# ── 쓰기(건물주 본인) ──────────────────────────────────────────────────────

def _apply(listing: DirectListing, data: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for key, value in data.items():
        if key not in EDITABLE_FIELDS:
            continue
        if key in ("preferred_industries", "excluded_industries"):
            value = list(dict.fromkeys(value or []))[:20]
        if getattr(listing, key) != value:
            setattr(listing, key, value)
            changed.append(key)
    return changed


def create_draft(db: Session, user_id: str, data: dict[str, Any]) -> DirectListing:
    listing = DirectListing(owner_user_id=user_id, status="draft", preferred_industries=[], excluded_industries=[])
    _apply(listing, data)
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def update(db: Session, user_id: str, listing_id: str, data: dict[str, Any]) -> DirectListing:
    listing = get_owned(db, user_id, listing_id)
    if listing.status in ("hidden", "closed"):
        raise DirectError(409, "숨김·종료된 매물은 고칠 수 없어요")
    changed = _apply(listing, data)
    if not changed:
        return listing
    listing.updated_at = _now()
    # 「어느 자리인가」가 바뀌었다 — 게시 중이면 확인 대기로 돌리고 같은 확인 정보로 다시 확인을 받는다.
    if listing.status in ("published", "paused") and any(k in CORE_FIELDS for k in changed):
        prev = latest_verification(db, listing.id)
        if prev is not None:
            db.add(ListingVerification(listing_id=listing.id, submitted_by=user_id, relation=prev.relation,
                                       registry_number=prev.registry_number, owner_name=prev.owner_name,
                                       delegation_note=prev.delegation_note, status="pending"))
        listing.status = "pending"
    db.commit()
    db.refresh(listing)
    return listing


def submit(db: Session, user_id: str, listing_id: str, ver: dict[str, Any]) -> DirectListing:
    """소유자 확인 요청과 함께 제출한다 — 필수 정보(L4)와 게시자 신원·관계(L5)를 함께 본다."""
    listing = get_owned(db, user_id, listing_id)
    if listing.status not in ("draft", "rejected"):
        raise DirectError(409, f"지금 상태({STATUS_LABELS.get(listing.status, listing.status)})에서는 제출할 수 없어요")
    miss = missing_required(listing)
    if miss:
        raise DirectError(422, "필수 정보가 비어 있어요: " + " · ".join(REQUIRED_LABELS[m] for m in miss), missing=miss)
    relation = ver.get("relation") or ""
    registry = (ver.get("registry_number") or "").strip()
    owner_name = (ver.get("owner_name") or "").strip()
    note = (ver.get("delegation_note") or "").strip()
    if relation not in RELATIONS:
        raise DirectError(422, "게시자와 소유자의 관계를 골라 주세요", missing=["relation"])
    if not _REGISTRY_RE.match(registry):
        raise DirectError(422, "등기부등본의 고유번호(숫자·하이픈 14~24자)를 적어 주세요", missing=["registry_number"])
    if not 1 <= len(owner_name) <= 50:
        raise DirectError(422, "등기부등본의 소유자 이름을 적어 주세요", missing=["owner_name"])
    if relation != "owner" and not note:
        raise DirectError(422, "대리인·관리인은 위임 관계를 적어 주세요", missing=["delegation_note"])
    db.add(ListingVerification(listing_id=listing.id, submitted_by=user_id, relation=relation,
                               registry_number=registry, owner_name=owner_name, delegation_note=note[:500],
                               status="pending"))
    listing.poster_relation = relation
    listing.status = "pending"
    listing.updated_at = _now()
    db.commit()
    db.refresh(listing)
    return listing


def set_status(db: Session, user_id: str, listing_id: str, action: str) -> DirectListing:
    listing = get_owned(db, user_id, listing_id)
    if action == "pause":
        if listing.status != "published":
            raise DirectError(409, "게시 중인 매물만 일시중지할 수 있어요")
        listing.status = "paused"
    elif action == "resume":
        v = latest_verification(db, listing.id)
        if listing.status != "paused" or v is None or v.status != "verified":
            raise DirectError(409, "소유자 확인이 끝난 일시중지 매물만 다시 게시할 수 있어요")
        listing.status = "published"
    elif action == "close":
        if listing.status == "hidden":
            raise DirectError(409, "신고 확인 중인 매물은 관리자 확인 뒤에 종료할 수 있어요")
        listing.status = "closed"
    else:
        raise DirectError(422, "알 수 없는 동작이에요")
    listing.updated_at = _now()
    db.commit()
    db.refresh(listing)
    return listing


def remove_listing_rows(db: Session, listing_ids: list[str]) -> None:
    """매물과 그에 딸린 확인·문의·메시지·신고를 자식 → 부모 순서로 지운다(Postgres 외래키 순서 · 탈퇴에서도 쓴다)."""
    if not listing_ids:
        return
    inquiry_ids = list(db.execute(select(DirectInquiry.id).where(DirectInquiry.listing_id.in_(listing_ids))).scalars())
    pairs = {(f, o) for f, o in db.execute(select(DirectInquiry.founder_user_id, DirectInquiry.owner_user_id)
                                           .where(DirectInquiry.listing_id.in_(listing_ids))).all()}
    if inquiry_ids:
        # 조건 제안서 표(b8c9d0e1f2a3)가 아직 없는 DB 에서도 탈퇴가 깨지지 않게 표 존재를 본다
        if inspect(db.connection()).has_table(DirectOffer.__tablename__):
            db.execute(sa_delete(DirectOffer).where(DirectOffer.inquiry_id.in_(inquiry_ids)))
        db.execute(sa_delete(DirectMessage).where(DirectMessage.inquiry_id.in_(inquiry_ids)))
        db.execute(sa_delete(DirectInquiry).where(DirectInquiry.id.in_(inquiry_ids)))
    # 배치도 사진 표(c9d0e1f2a3b4)가 아직 없는 DB 에서도 탈퇴가 깨지지 않게 표 존재를 본다
    from app.services.direct_floor_plans import remove_for_listings

    remove_for_listings(db, listing_ids)
    db.execute(sa_delete(ListingReport).where(ListingReport.listing_id.in_(listing_ids)))
    db.execute(sa_delete(ListingVerification).where(ListingVerification.listing_id.in_(listing_ids)))
    db.execute(sa_delete(DirectListing).where(DirectListing.id.in_(listing_ids)))
    # 대화가 사라진 (창업자, 건물주) 짝의 희망서 ② 공개 동의를 닫는다 — 남겨 두면 그 건물주가 같은 상권에 매물을
    # 다시 올렸을 때 ② 가 대화 없이 다시 보인다(2026-11-21 리뷰 반영). 순환 임포트를 피해 함수 안에서 부른다
    from app.services.direct_briefs import prune_disclosures

    prune_disclosures(db, pairs)


def delete(db: Session, user_id: str, listing_id: str) -> None:
    listing = get_owned(db, user_id, listing_id)
    remove_listing_rows(db, [listing.id])
    db.commit()


def mine(db: Session, user_id: str) -> list[dict[str, Any]]:
    rows = db.execute(select(DirectListing).where(DirectListing.owner_user_id == user_id)
                      .order_by(DirectListing.created_at.desc())).scalars().all()
    return [owner_view(db, r) for r in rows]


# ── 공개 검색 ──────────────────────────────────────────────────────────────

def public_listings(db: Session, district_id: str | None = None, building_id: str | None = None) -> list[DirectListing]:
    q = select(DirectListing).where(DirectListing.status == "published")
    if district_id:
        q = q.where(DirectListing.district_id == district_id)
    if building_id:
        q = q.where(DirectListing.building_id == building_id)
    rows = db.execute(q.order_by(DirectListing.published_at.desc())).scalars().all()
    return [r for r in rows if is_public(db, r)]


def search(db: Session, *, district_id: str | None = None, building_id: str | None = None,
           floor_band: str | None = None, popup: bool | None = None, long_vacancy: bool | None = None,
           max_rent: int | None = None) -> list[DirectListing]:
    rows = public_listings(db, district_id, building_id)
    out: list[DirectListing] = []
    for r in rows:
        f = flags(r)
        if floor_band == "first" and r.floor != 1:
            continue
        if floor_band == "upper" and not f["upper_floor"]:
            continue
        if floor_band == "basement" and not f["basement"]:
            continue
        if popup and not f["popup_ok"]:
            continue
        if long_vacancy and not f["long_vacancy"]:
            continue
        if max_rent is not None and r.deal_type != "popup" and r.monthly_rent_manwon > max_rent:
            continue
        out.append(r)
    return out


# ── 신고(L9) ───────────────────────────────────────────────────────────────

def report(db: Session, user_id: str, listing_id: str, reason: str, detail: str) -> dict[str, Any]:
    listing = db.get(DirectListing, listing_id)
    if listing is None or listing.status in ("draft",):
        raise DirectError(404, "매물을 찾지 못했어요")
    if listing.owner_user_id == user_id:
        raise DirectError(400, "내 매물은 신고할 수 없어요")
    if reason not in REPORT_REASONS:
        raise DirectError(422, "신고 사유를 골라 주세요")
    dup = db.execute(select(ListingReport).where(ListingReport.listing_id == listing_id,
                                                 ListingReport.reporter_user_id == user_id,
                                                 ListingReport.status == "open")).scalars().first()
    if dup is not None:
        raise DirectError(409, "이미 신고한 매물이에요 — 확인 중이에요")
    db.add(ListingReport(listing_id=listing_id, reporter_user_id=user_id, reason=reason, detail=(detail or "")[:500]))
    db.flush()
    reporters = {r for r in db.execute(select(ListingReport.reporter_user_id)
                                        .where(ListingReport.listing_id == listing_id,
                                               ListingReport.status == "open")).scalars() if r}
    hidden = False
    if len(reporters) >= AUTO_HIDE_REPORTERS and listing.status in ("published", "paused"):
        listing.status = "hidden"           # 관리자 확인 전까지 숨긴다 — 건물주가 스스로 다시 게시할 수 없게
        listing.updated_at = _now()
        hidden = True
    db.commit()
    return {"ok": True, "auto_hidden": hidden}
