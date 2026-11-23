"""입점 희망서 — 창업자가 「이 업종으로 이런 자리를 찾는다」를 올린다 (2026-11-21 · docs/decision-founder-brief-2026-11-21.md).

누가 무엇을 보나(단계별 공개):
① 공개 — 희망 상권에 **소유자 확인을 거친 게시 매물**이 있는 건물주만(`owner_district_ids`). 구조화된 칸만 싣는다
   (업종 · 필요 면적 · 희망 층 · 필요 설비 · 월세·보증금 상한 · 희망 시기 · 희망 상권 · 팝업 먼저). 누구인지(이메일·이름)는
   싣지 않고, 연락은 건물주가 **내 매물로 보내는 제안**(문의함 대화)으로만 시작한다.
② 동의 공개 — 창업자가 대화 중인 건물주 한 명에게 직접 열어 줄 때만(사업 개요 · 단계 · 자금 계획 — 본인 기재).
③ 비공개 — 본인에게만. 객단가·변동비율·기타 고정비·영업일·목표 판매량은 요구 판매량 계산(services/direct_fit)에만 쓴다.

⛔ 신용 점수·등급·순위를 만들지 않는다 — 개인의 신용(임대료를 낼 수 있나)을 평가해 남에게 주면 개인신용평가업
   (신용정보법 · 금융위원회 허가)에 걸릴 수 있고, 검증하지 않은 점수는 KPI 규칙 ①②를 어긴다. 대신 「PlaceOS 가 확인한 것」과
   「창업자가 적은 것」을 나눠 보인다(`trust_facts`). 건물주가 보는 목록도 점수순이 아니라 최근에 올린 순이다.
⛔ 묶음 수요(공개 · `demand`)는 n≥3 일 때만 숫자를 보이고, 3명 미만인 업종은 **이름도 싣지 않는다** — 차감으로 개인이 드러나지 않게.
"""
from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.direct import BriefDisclosure, DirectBrief, DirectInquiry, DirectListing
from app.services import business_fit
from app.services import districts as districts_svc
from app.services.direct_listings import DIRECT_NOTICE, DirectError, aware, floor_text, is_public, title

# 게시 기간 — 지나면 건물주에게 보이지 않는다(낡은 희망서가 남지 않게 · 다시 올리면 이 기간이 새로 시작한다)
BRIEF_TTL_DAYS = 90
MAX_DISTRICTS = 3
# 묶음 수요를 숫자로 보이는 최소 인원 — direct_matching.DEMAND_MIN_N 과 같은 값(테스트가 둘이 같은지 잠근다)
DEMAND_MIN_N = 3

FLOOR_BANDS = ("first", "upper", "basement")
FLOOR_BAND_LABELS = {"first": "1층", "upper": "2층 이상", "basement": "지하"}
BUSINESS_STAGES = {
    "pre": "예비 창업(사업자등록 전)",
    "registered": "사업자등록 함(개업 전)",
    "operating": "지금 영업 중(옮기기·바꾸기)",
}
STATUS_LABELS = {"draft": "작성 중", "active": "건물주에게 보이는 중", "paused": "잠시 숨김", "closed": "끝냄"}
REQUIRED_LABELS = {
    "industry_key": "업종", "area": "필요 면적 범위(㎡)", "floor_bands": "희망 층", "rent_cap": "월세 상한",
    "deposit_cap": "보증금 상한", "desired_start": "희망 시기", "district_ids": "희망 상권(1~3곳)",
}
PRIVATE_LABELS = {
    "unit_price_won": "객단가(원)", "variable_cost_pct": "변동비율(재료·수수료 · %)",
    "other_fixed_manwon": "기타 월 고정비(인건비 등 · 만원)", "open_days": "월 영업일",
}

# 단계별 칸 — 응답을 만들 때 이 묶음으로만 꺼낸다(칸을 더하면 어느 단계인지 여기서 정한다)
PUBLIC_FIELDS = (
    "industry_key", "area_min_m2", "area_max_m2", "floor_bands", "needs_exhaust", "needs_water", "power_kw_min",
    "rent_cap_manwon", "deposit_cap_manwon", "desired_start", "district_ids", "popup_first",
)
CONSENT_FIELDS = ("summary", "business_stage", "funding_total_manwon", "funding_own_manwon")
PRIVATE_FIELDS = ("unit_price_won", "variable_cost_pct", "other_fixed_manwon", "open_days", "target_daily_units")
SETTING_FIELDS = ("accept_invites",)
EDITABLE_FIELDS = PUBLIC_FIELDS + CONSENT_FIELDS + PRIVATE_FIELDS + SETTING_FIELDS
_BOOL_FIELDS = ("needs_exhaust", "needs_water", "popup_first", "accept_invites")

TRUST_NOTE = ("PlaceOS 는 창업자의 신용을 평가하거나 점수·등급을 매기지 않아요. 희망서의 값은 창업자가 적은 것이고, "
              "임대차 계약 전에 필요한 확인은 당사자가 직접 해요.")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def industry_label(key: str) -> str:
    item = business_fit.get(key) if key else None
    return str(item.get("label")) if item else key


def district_name(district_id: str) -> str:
    page = districts_svc.PAGES_BY_ID.get(district_id)
    return str(page.get("name") or district_id) if page else district_id


# ── 쓰기(창업자 본인) ──────────────────────────────────────────────────────

def get_mine(db: Session, user_id: str) -> DirectBrief | None:
    return db.execute(select(DirectBrief).where(DirectBrief.user_id == user_id)).scalars().first()


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key not in EDITABLE_FIELDS:
            continue
        if key in _BOOL_FIELDS:
            value = bool(value)
        elif key == "industry_key":
            value = (value or "").strip()
            if value and business_fit.get(value) is None:
                raise DirectError(422, "업종은 목록(12종)에서 골라 주세요", missing=["industry_key"])
        elif key == "floor_bands":
            value = [b for b in dict.fromkeys(value or []) if b in FLOOR_BANDS]
        elif key == "district_ids":
            value = list(dict.fromkeys(d.strip() for d in (value or []) if d and d.strip()))
            if len(value) > MAX_DISTRICTS:
                raise DirectError(422, f"희망 상권은 {MAX_DISTRICTS}곳까지 골라요", missing=["district_ids"])
            if any(d not in districts_svc.PAGES_BY_ID for d in value):
                raise DirectError(422, "희망 상권은 목록에서 골라 주세요", missing=["district_ids"])
        elif key == "business_stage":
            value = value or ""
            if value and value not in BUSINESS_STAGES:
                raise DirectError(422, "사업 단계를 골라 주세요")
        elif key == "summary":
            value = (value or "").strip()[:500]
        out[key] = value
    return out


def _check_pairs(values: dict[str, Any]) -> None:
    lo, hi = values.get("area_min_m2"), values.get("area_max_m2")
    if lo is not None and hi is not None and lo > hi:
        raise DirectError(422, "필요 면적은 작은 값부터 적어 주세요(최소 ≤ 최대)", missing=["area"])
    total, own = values.get("funding_total_manwon"), values.get("funding_own_manwon")
    if total is not None and own is not None and own > total:
        raise DirectError(422, "자기 자금이 총 창업 자금보다 클 수 없어요")


def missing_required(brief: DirectBrief) -> list[str]:
    """건물주에게 보이기(activate) 전 필수 칸. 빈 칸의 키를 돌려준다 — 화면은 REQUIRED_LABELS 로 보인다."""
    miss: list[str] = []
    if not brief.industry_key:
        miss.append("industry_key")
    if not (brief.area_min_m2 and brief.area_max_m2):
        miss.append("area")
    if not brief.floor_bands:
        miss.append("floor_bands")
    if not brief.rent_cap_manwon:
        miss.append("rent_cap")
    if brief.deposit_cap_manwon is None:
        miss.append("deposit_cap")
    if brief.desired_start is None:
        miss.append("desired_start")
    if not brief.district_ids:
        miss.append("district_ids")
    return miss


def save(db: Session, user_id: str, data: dict[str, Any]) -> DirectBrief:
    """희망서를 만들거나 고친다(한 사람에 하나). 보이는 중인데 필수 칸이 비면 「작성 중」으로 내린다."""
    brief = get_mine(db, user_id)
    clean = _clean(data)
    merged = {f: clean.get(f, getattr(brief, f) if brief is not None else None) for f in EDITABLE_FIELDS}
    _check_pairs(merged)
    if brief is None:
        brief = DirectBrief(user_id=user_id, status="draft", floor_bands=[], district_ids=[],
                            needs_exhaust=False, needs_water=False, popup_first=False, accept_invites=True)
        db.add(brief)
    for key, value in clean.items():
        setattr(brief, key, value)
    brief.updated_at = _now()
    if brief.status == "active" and missing_required(brief):
        brief.status = "draft"
    db.commit()
    db.refresh(brief)
    return brief


def set_status(db: Session, user_id: str, action: str) -> DirectBrief:
    brief = get_mine(db, user_id)
    if brief is None:
        raise DirectError(404, "희망서를 먼저 써 주세요")
    now = _now()
    if action == "activate":
        miss = missing_required(brief)
        if miss:
            raise DirectError(422, "필수 칸이 비어 있어요: " + " · ".join(REQUIRED_LABELS[m] for m in miss), missing=miss)
        brief.status = "active"
        brief.activated_at = now                                  # 건물주 목록은 「최근에 올리거나 다시 올린 순」이다
        brief.expires_at = now + timedelta(days=BRIEF_TTL_DAYS)   # 다시 올리면 기간이 새로 시작한다
    elif action == "pause":
        if brief.status != "active":
            raise DirectError(409, "건물주에게 보이는 중인 희망서만 숨길 수 있어요")
        brief.status = "paused"
    elif action == "close":
        brief.status = "closed"
    else:
        raise DirectError(422, "알 수 없는 동작이에요")
    brief.updated_at = now
    db.commit()
    db.refresh(brief)
    return brief


def remove_brief_rows(db: Session, brief_ids: list[str]) -> None:
    """희망서와 그 공개 동의를 자식 → 부모 순서로 지운다(탈퇴에서도 쓴다)."""
    if not brief_ids:
        return
    db.execute(sa_delete(BriefDisclosure).where(BriefDisclosure.brief_id.in_(brief_ids)))
    db.execute(sa_delete(DirectBrief).where(DirectBrief.id.in_(brief_ids)))


def delete(db: Session, user_id: str) -> None:
    brief = get_mine(db, user_id)
    if brief is None:
        raise DirectError(404, "희망서가 없어요")
    remove_brief_rows(db, [brief.id])
    db.commit()


# ── 보이는가 ───────────────────────────────────────────────────────────────

def is_visible(brief: DirectBrief, now: datetime | None = None) -> bool:
    """건물주에게 보이는 조건 — 보이는 중(active)이고 게시 기간 안."""
    expires = aware(brief.expires_at)
    return brief.status == "active" and expires is not None and expires > (now or _now())


def owner_public_listings(db: Session, owner_id: str) -> list[DirectListing]:
    rows = db.execute(select(DirectListing).where(DirectListing.owner_user_id == owner_id,
                                                  DirectListing.status == "published")).scalars().all()
    return [r for r in rows if is_public(db, r)]


def owner_district_ids(db: Session, owner_id: str) -> set[str]:
    """이 건물주가 희망서를 볼 수 있는 상권 — 소유자 확인을 거친 게시 매물이 있는 상권만."""
    return {r.district_id for r in owner_public_listings(db, owner_id) if r.district_id}


def visible_to_owner(db: Session, brief: DirectBrief, owner_id: str, allowed: set[str] | None = None) -> bool:
    if brief.user_id == owner_id or not is_visible(brief):
        return False
    allowed = owner_district_ids(db, owner_id) if allowed is None else allowed
    return any(d in allowed for d in (brief.district_ids or []))


def is_disclosed(db: Session, brief_id: str, owner_id: str) -> bool:
    """공개 동의 행이 있나(창업자 본인 화면용 — 「거두기」를 보일지). 건물주에게 ②를 보일지는 `consent_live` 가 정한다."""
    return db.execute(select(BriefDisclosure.id).where(BriefDisclosure.brief_id == brief_id,
                                                       BriefDisclosure.owner_user_id == owner_id)).first() is not None


def open_thread_between(db: Session, founder_id: str, owner_id: str) -> bool:
    """두 사람 사이에 끝나지 않은 대화가 하나라도 있나."""
    return db.execute(select(DirectInquiry.id).where(DirectInquiry.founder_user_id == founder_id,
                                                     DirectInquiry.owner_user_id == owner_id,
                                                     DirectInquiry.status != "closed")).first() is not None


def consent_live(db: Session, brief: DirectBrief, owner_id: str) -> bool:
    """② 를 이 건물주에게 보이나 — 창업자가 열었고 **두 사람의 대화가 아직 이어지는 동안만**(2026-11-21 리뷰 반영).

    대화가 다 끝나거나(결과 자기보고) 매물이 지워져 대화가 사라지면 ② 는 더 보이지 않는다(`prune_disclosures` 가 행도 지운다).
    """
    return is_disclosed(db, brief.id, owner_id) and open_thread_between(db, brief.user_id, owner_id)


def disclose(db: Session, founder_id: str, owner_id: str) -> None:
    """창업자가 대화 상대(건물주) 한 명에게 ② 단계를 연다. 호출부(direct_connect)가 둘이 대화 중인지 먼저 본다."""
    brief = get_mine(db, founder_id)
    if brief is None:
        raise DirectError(409, "열어 줄 희망서가 없어요 — 희망서를 먼저 써 주세요")
    if not is_disclosed(db, brief.id, owner_id):
        db.add(BriefDisclosure(brief_id=brief.id, owner_user_id=owner_id))
        db.commit()


def revoke(db: Session, founder_id: str, owner_id: str) -> None:
    brief = get_mine(db, founder_id)
    if brief is None:
        return
    db.execute(sa_delete(BriefDisclosure).where(BriefDisclosure.brief_id == brief.id,
                                                BriefDisclosure.owner_user_id == owner_id))
    db.commit()


def revoke_by_id(db: Session, founder_id: str, disclosure_id: str) -> None:
    """대화가 없어도 거둔다 — 희망서 화면의 「열어 준 건물주」 목록에서(2026-11-21 리뷰 반영)."""
    brief = get_mine(db, founder_id)
    row = db.get(BriefDisclosure, disclosure_id)
    if brief is None or row is None or row.brief_id != brief.id:
        raise DirectError(404, "열어 준 기록을 찾지 못했어요")
    db.delete(row)
    db.commit()


def prune_disclosures(db: Session, pairs: set[tuple[str, str]]) -> None:
    """(창업자, 건물주) 짝 사이에 끝나지 않은 대화가 더 없으면 ② 공개 동의를 지운다. 커밋은 호출부가 한다.

    대화가 끝난 뒤(결과 자기보고) · 매물이 지워져 대화가 사라진 뒤 동의가 남아 있다가, 나중에 그 건물주가 같은 상권에
    매물을 다시 올리면 ② 가 다시 보이는 일을 막는다. 표가 없는 DB(마이그레이션 전)에서는 아무것도 하지 않는다.
    """
    from sqlalchemy import inspect

    if not pairs or not inspect(db.connection()).has_table(BriefDisclosure.__tablename__):
        return
    for founder_id, owner_id in pairs:
        if open_thread_between(db, founder_id, owner_id):
            continue
        brief_ids = list(db.execute(select(DirectBrief.id).where(DirectBrief.user_id == founder_id)).scalars())
        if brief_ids:
            db.execute(sa_delete(BriefDisclosure).where(BriefDisclosure.brief_id.in_(brief_ids),
                                                        BriefDisclosure.owner_user_id == owner_id))


def list_disclosures(db: Session, brief: DirectBrief) -> list[dict[str, Any]]:
    """창업자 본인에게 — 누구에게 ② 를 열었나. 건물주 신원 대신 두 사람이 이야기한 매물 이름으로 보인다."""
    rows = db.execute(select(BriefDisclosure).where(BriefDisclosure.brief_id == brief.id)
                      .order_by(BriefDisclosure.created_at.desc())).scalars().all()
    out = []
    for d in rows:
        threads = db.execute(select(DirectInquiry).where(DirectInquiry.founder_user_id == brief.user_id,
                                                         DirectInquiry.owner_user_id == d.owner_user_id)).scalars().all()
        titles = []
        for t in threads:
            listing = db.get(DirectListing, t.listing_id)
            if listing is not None:
                titles.append(title(listing))
        out.append({"id": d.id, "created_at": aware(d.created_at).isoformat(),
                    "listings": list(dict.fromkeys(titles)),
                    "open_threads": sum(1 for t in threads if t.status != "closed")})
    return out


# ── 보이는 값 ──────────────────────────────────────────────────────────────

def public_view(brief: DirectBrief) -> dict[str, Any]:
    """① 공개 칸만. 누구인지(user_id·이메일·이름)는 싣지 않는다."""
    bands = [b for b in brief.floor_bands or [] if b in FLOOR_BANDS]
    return {
        "id": brief.id,
        "code": brief.id[:6].upper(),
        "industry_key": brief.industry_key,
        "industry_label": industry_label(brief.industry_key),
        "area_min_m2": brief.area_min_m2,
        "area_max_m2": brief.area_max_m2,
        "floor_bands": bands,
        "floor_labels": [FLOOR_BAND_LABELS[b] for b in bands],
        "needs_exhaust": bool(brief.needs_exhaust),
        "needs_water": bool(brief.needs_water),
        "power_kw_min": brief.power_kw_min,
        "rent_cap_manwon": brief.rent_cap_manwon,
        "deposit_cap_manwon": brief.deposit_cap_manwon,
        "desired_start": brief.desired_start.strftime("%Y-%m") if brief.desired_start else None,
        "districts": [{"id": d, "name": district_name(d)} for d in brief.district_ids or []],
        "popup_first": bool(brief.popup_first),
        "accept_invites": bool(brief.accept_invites),
        "updated_at": aware(brief.updated_at).date().isoformat() if brief.updated_at else None,
    }


def consent_view(brief: DirectBrief) -> dict[str, Any]:
    """② 동의 공개 칸 — 창업자가 연 건물주에게만."""
    return {
        "summary": brief.summary,
        "business_stage": brief.business_stage,
        "business_stage_label": BUSINESS_STAGES.get(brief.business_stage, ""),
        "funding_total_manwon": brief.funding_total_manwon,
        "funding_own_manwon": brief.funding_own_manwon,
    }


def private_view(brief: DirectBrief) -> dict[str, Any]:
    """③ 비공개 칸 — 본인에게만."""
    return {f: getattr(brief, f) for f in PRIVATE_FIELDS}


def trust_facts(brief: DirectBrief, *, disclosed: bool) -> dict[str, Any]:
    """신용 점수 대신 — 확인한 사실과 창업자가 적은 값을 나눠 보인다. 숫자로 합치지 않는다."""
    checked = ["PlaceOS 계정으로 로그인해 쓴 희망서예요(이메일·이름은 보이지 않아요)."]
    if not missing_required(brief):
        checked.append("필수 칸(업종·면적·층·예산·시기·상권)을 모두 채웠어요.")
    if brief.updated_at:
        checked.append(f"최근 고친 날: {aware(brief.updated_at).date().isoformat()}")
    self_declared = ["업종·면적·층·설비·예산 상한·시기·상권은 창업자가 적은 값이에요."]
    if disclosed:
        self_declared.append("사업 개요·단계·자금 계획도 창업자가 적은 값이에요 — PlaceOS 가 확인하지 않았어요.")
    return {"checked": checked, "self_declared": self_declared, "note": TRUST_NOTE}


def self_view(db: Session, brief: DirectBrief) -> dict[str, Any]:
    now = _now()
    expires = aware(brief.expires_at)
    disclosures = list_disclosures(db, brief)
    disclosed_n = len(disclosures)
    return {
        "disclosures": disclosures,
        **public_view(brief),
        "desired_start_date": brief.desired_start.isoformat() if brief.desired_start else None,
        **consent_view(brief),
        "private": private_view(brief),
        "status": brief.status,
        "status_label": STATUS_LABELS.get(brief.status, brief.status),
        "missing": missing_required(brief),
        "visible": is_visible(brief, now),
        "expired": brief.status == "active" and expires is not None and expires <= now,
        "expires_at": expires.isoformat() if expires else None,
        "disclosed_n": disclosed_n,
        "trust": trust_facts(brief, disclosed=True),
        "notice": DIRECT_NOTICE,
    }


# ── 건물주가 보는 희망서 ────────────────────────────────────────────────────

NO_ACCESS = ("희망서는 희망 상권에 소유자 확인을 마친 게시 매물이 있는 건물주만 볼 수 있어요. "
             "빈 자리를 올리고 확인을 받으면 그 상권의 희망서가 보여요.")


def _my_listing_rows(db: Session, brief: DirectBrief, mine: list[DirectListing],
                     terms_by_id: dict[str, dict], owner_id: str) -> list[dict[str, Any]]:
    from app.services import direct_fit   # direct_fit → direct_pricing → direct_listings 순환을 피한다

    rows = []
    for listing in mine:
        if listing.district_id not in (brief.district_ids or []):
            continue
        fit = direct_fit.pair(listing, brief, terms_by_id[listing.id], include_private=False)
        thread = db.execute(select(DirectInquiry.id).where(
            DirectInquiry.listing_id == listing.id, DirectInquiry.founder_user_id == brief.user_id,
            DirectInquiry.owner_user_id == owner_id, DirectInquiry.status != "closed")).scalars().first()
        rows.append({"listing_id": listing.id, "title": title(listing), "floor_text": floor_text(listing.floor),
                     "fit": fit, "open_thread_id": thread})
    return rows


def list_for_owner(db: Session, owner_id: str, *, district_id: str | None = None, industry: str | None = None,
                   popup_first: bool | None = None) -> dict[str, Any]:
    """건물주에게 보이는 희망서 — 내 확인 매물이 있는 상권만, **최근에 올린 순**(점수순 아님)."""
    from app.services import direct_pricing

    mine = owner_public_listings(db, owner_id)
    allowed = {r.district_id for r in mine if r.district_id}
    if not allowed:
        raise DirectError(403, NO_ACCESS)
    if district_id and district_id not in allowed:
        raise DirectError(403, "내 확인 매물이 있는 상권의 희망서만 볼 수 있어요")
    targets = {district_id} if district_id else allowed
    terms_by_id = {r.id: direct_pricing.terms(db, r) for r in mine}
    now = _now()
    rows = db.execute(select(DirectBrief).where(DirectBrief.status == "active", DirectBrief.user_id != owner_id)
                      .order_by(DirectBrief.activated_at.desc())).scalars().all()
    items = []
    for brief in rows:
        if not is_visible(brief, now) or not any(d in targets for d in brief.district_ids or []):
            continue
        if industry and brief.industry_key != industry:
            continue
        if popup_first is not None and bool(brief.popup_first) != popup_first:
            continue
        items.append({**public_view(brief), "trust": trust_facts(brief, disclosed=False),
                      "my_listings": _my_listing_rows(db, brief, mine, terms_by_id, owner_id)})
    return {
        "items": items, "n": len(items),
        "districts": [{"id": d, "name": district_name(d)} for d in sorted(allowed)],
        "order_note": "최근에 올리거나 다시 올린 순이에요 — 점수·순위가 아니에요.",
        "trust_note": TRUST_NOTE,
        "notice": DIRECT_NOTICE,
    }


def get_for_owner(db: Session, owner_id: str, brief_id: str) -> dict[str, Any]:
    """희망서 한 장(건물주) — 보일 조건이 아니면 있는지도 드러내지 않는다(404)."""
    from app.services import direct_pricing

    brief = db.get(DirectBrief, brief_id)
    mine = owner_public_listings(db, owner_id)
    allowed = {r.district_id for r in mine if r.district_id}
    if brief is None or not visible_to_owner(db, brief, owner_id, allowed):
        raise DirectError(404, "희망서를 찾지 못했어요")
    disclosed = consent_live(db, brief, owner_id)
    terms_by_id = {r.id: direct_pricing.terms(db, r) for r in mine}
    out = {**public_view(brief), "trust": trust_facts(brief, disclosed=disclosed), "disclosed": disclosed,
           "consent": consent_view(brief) if disclosed else None,
           "my_listings": _my_listing_rows(db, brief, mine, terms_by_id, owner_id),
           "can_invite": bool(brief.accept_invites), "notice": DIRECT_NOTICE}
    return out


def thread_view_for_owner(db: Session, inquiry: DirectInquiry, owner_id: str) -> dict[str, Any] | None:
    """대화 중인 건물주에게 그 창업자의 희망서 — **붙는 경우는 둘뿐이다**(2026-11-21 리뷰 반영).

    (가) 건물주가 그 희망서를 보고 먼저 제안한 대화(`initiated_by == "owner"`)이고 지금도 희망서 게이트(L12)를 지나는 경우 → ①만.
    (나) 창업자가 이 건물주에게 희망서를 직접 열었고 대화가 이어지는 중인 경우 → ① + ②.
    창업자가 먼저 문의한 대화에 희망서를 말없이 붙이지 않는다 — 협상 상대에게 예산 상한을 동의 없이 넘기게 된다.
    """
    brief = get_mine(db, inquiry.founder_user_id)
    if brief is None or not is_visible(brief):
        return None
    live = inquiry.status != "closed" and is_disclosed(db, brief.id, owner_id)
    from_brief = inquiry.initiated_by == "owner" and visible_to_owner(db, brief, owner_id)
    if not (live or from_brief):
        return None
    return {**public_view(brief), "trust": trust_facts(brief, disclosed=live), "disclosed": live,
            "consent": consent_view(brief) if live else None}


# ── 묶음 수요(공개) ─────────────────────────────────────────────────────────

def _cell(n: int) -> int | None:
    return n if n >= DEMAND_MIN_N else None


def demand(db: Session, district_id: str, now: datetime | None = None, *, include_caps: bool = False) -> dict[str, Any]:
    """이 상권을 희망한 게시 중 희망서의 묶음 — 건물주의 「다음 공실」 대비 수요 신호.

    n<3 이면 숫자를 감추고, 3명 미만 업종은 이름도 싣지 않는다(차감으로 한 사람이 드러나지 않게).
    ⛔ 월세·보증금 상한 중앙값은 `include_caps=True` 일 때만 싣는다 — **그 상권에 소유자 확인 매물이 있는 건물주 경로**
       (공실 진단)만 켠다. 공개 경로(GET /direct/demand · 공개 /listings/{id}/fit)에서는 끈다: n=3 이면 중앙값이 한 사람의
       상한 그대로이고, 계정 하나로 자기 희망서를 넣었다 빼며 남의 상한을 캐낼 수 있다(2026-11-21 리뷰 반영). 그 건물주는
       어차피 희망서 ① 을 한 장씩 볼 수 있어 중앙값이 새로 드러내는 것이 없다.
    """
    now = now or _now()
    rows = [b for b in db.execute(select(DirectBrief).where(DirectBrief.status == "active")).scalars().all()
            if is_visible(b, now) and district_id in (b.district_ids or [])]
    n = len(rows)
    industries = Counter(b.industry_key for b in rows if b.industry_key)
    bands = Counter(band for b in rows for band in (b.floor_bands or []) if band in FLOOR_BANDS)
    rents = [b.rent_cap_manwon for b in rows if b.rent_cap_manwon]
    deposits = [b.deposit_cap_manwon for b in rows if b.deposit_cap_manwon is not None]
    return {
        "district_id": district_id,
        "district_name": district_name(district_id),
        "min_n": DEMAND_MIN_N,
        "total": _cell(n),
        "suppressed": n < DEMAND_MIN_N,
        "by_industry": [{"industry_key": k, "label": industry_label(k), "founders": c}
                        for k, c in industries.most_common() if c >= DEMAND_MIN_N],
        "by_floor_band": [{"band": b, "label": FLOOR_BAND_LABELS[b], "founders": c}
                          for b, c in sorted(bands.items(), key=lambda kv: FLOOR_BANDS.index(kv[0]))
                          if c >= DEMAND_MIN_N],
        "popup_first": _cell(sum(1 for b in rows if b.popup_first)),
        "rent_cap_median_manwon": statistics.median(rents) if include_caps and len(rents) >= DEMAND_MIN_N else None,
        "deposit_cap_median_manwon": (statistics.median(deposits)
                                      if include_caps and len(deposits) >= DEMAND_MIN_N else None),
        "caps_shown": include_caps,
        "note": (f"이 상권을 희망 상권으로 고른, 게시 중인 입점 희망서(올리거나 다시 올린 지 {BRIEF_TTL_DAYS}일 안)를 묶은 값이에요. "
                 f"{DEMAND_MIN_N}명 미만이면 숫자를 보이지 않아요. 창업자가 적은 희망 조건이지 계약 수요가 아니에요."
                 + ("" if include_caps else " 예산 상한 중앙값은 이 상권에 소유자 확인 매물이 있는 건물주 화면에만 보여요.")),
        "notice": DIRECT_NOTICE,
    }


def meta() -> dict[str, Any]:
    """희망서 작성 화면의 선택지."""
    return {
        "floor_bands": [{"key": k, "label": v} for k, v in FLOOR_BAND_LABELS.items()],
        "business_stages": [{"key": k, "label": v} for k, v in BUSINESS_STAGES.items()],
        "required": REQUIRED_LABELS,
        "private_labels": PRIVATE_LABELS,
        "ttl_days": BRIEF_TTL_DAYS,
        "max_districts": MAX_DISTRICTS,
        "trust_note": TRUST_NOTE,
    }
