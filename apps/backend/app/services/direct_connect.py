"""직거래 연결 — 창업자 ↔ 건물주 문의 · 방문 예약 · 조건 제안서 · 팝업 신청 · 결과 자기보고 (2026-11-18 · 11-21).

⛔ PlaceOS 는 조건을 조율하지 않는다(L2). 메시지는 당사자끼리 주고받고, 방문은 창업자가 시각을 제안하면 건물주가 고른다.
   조건 제안서(임대 조건)·팝업 신청은 **창업자가 적고 건물주가 받거나 거절한다** — PlaceOS 는 값을 권하지 않는다.
   「받음」은 그 조건으로 계약 이야기를 이어 간다는 뜻이지 계약이 아니다. 계약은 당사자 직접 또는 제휴 공인중개사(정액 제휴만)가 한다.
결과 자기보고(계약함/안 함)는 「연결이 계약으로 이어졌나」를 재는 계측기다 — 과금과 무관하다(성사 수수료 없음 · L1).
   제안·수락·계약 진행 방법 어느 것에도 돈이 붙지 않는다(상품 목록 · tests/test_direct_compliance.py).
참여자(그 문의의 창업자·건물주) 밖에서는 스레드가 없는 것처럼 404 를 돌려준다(L10).

2026-11-21: 건물주가 입점 희망서를 보고 **내 매물로 제안**(invite)을 보낼 수 있다 — 대화를 연 쪽(`initiated_by`)을 남겨
창업자 하루 문의 상한과 「문의 수요」 신호가 건물주가 연 대화를 세지 않게 한다.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import User
from app.models.direct import DirectBrief, DirectInquiry, DirectListing, DirectMessage, DirectOffer
from app.services import direct_briefs
from app.services.direct_listings import DIRECT_NOTICE, DirectError, aware, is_public, title

logger = logging.getLogger(__name__)

MAX_NEW_PER_DAY = 5           # 창업자 한 명이 하루에 여는 문의 상한 — 건물주 스팸 방지
MAX_INVITES_PER_DAY = 10      # 건물주 한 명이 하루에 보내는 제안 상한 — 창업자 스팸 방지
MAX_SLOTS = 3
KINDS = ("question", "visit", "offer", "popup", "invite")
FOUNDER_KINDS = ("question", "visit", "offer", "popup")
KIND_LABELS = {"question": "문의", "visit": "방문 예약", "offer": "조건 제안", "popup": "팝업·단기 신청",
               "invite": "건물주 제안"}
OUTCOMES = ("contracted", "not_contracted")
OFFER_KINDS = ("lease", "popup")
OFFER_STATUS_LABELS = {"proposed": "답을 기다려요", "accepted": "건물주가 받았어요(계약 아님)", "declined": "건물주가 거절했어요",
                       "withdrawn": "창업자가 거뒀어요", "superseded": "새 제안으로 바뀌었어요"}
CONTRACT_PATHS = ("direct", "broker")
CONTRACT_PATH_LABELS = {"direct": "당사자끼리 직접 계약", "broker": "제휴 공인중개사에게 맡기기"}

# 계약 전에 확인할 것 — 일반 안내다(법률 자문 아님). 화면은 그대로 보인다.
CONTRACT_GUIDE = (
    "등기부등본(건물)을 직접 떼어 소유자 이름·근저당을 확인해요.",
    "건축물대장에서 그 층·호의 용도가 내 업종과 맞는지 다시 봐요(PlaceOS 입점 점검은 허가 판정이 아니에요).",
    "건물을 넘겨받고 사업자등록을 신청하면 대항력이, 세무서에서 확정일자까지 받으면 우선변제권이 생길 수 있어요"
    "(상가건물 임대차보호법 · 보증금 규모에 따라 적용이 달라요).",
    "원상복구 범위·렌트프리·관리비에 들어가는 항목은 계약서 특약으로 적어요.",
    "계약서 검토는 변호사·법무사에게, 중개를 맡기려면 개업공인중개사에게 의뢰해요.",
)

# TODO(사용자 결정): 제휴 공인중개사 — 제휴가 생기면 여기에 넣는다. ⛔ 정액 제휴만(`deal_model == "flat_partnership"`).
#   건별 보수를 나누거나 성사에 연동해 받으면 무등록 중개(공인중개사법 제2조·제48조)이고, 중개사도 무등록자를 통해
#   의뢰받는 금지행위(제33조)에 걸린다. 각 항목: name · office · registration_no · district_ids · contact_url · deal_model.
PARTNER_BROKERS: list[dict[str, Any]] = []
BROKERS_NOTE = ("제휴 공인중개사는 아직 없어요. 당사자끼리 직접 계약하거나, 가까운 개업공인중개사에게 따로 의뢰하세요. "
                "PlaceOS 는 제휴 중개사와도 정액 제휴만 하고 건별 보수를 나누지 않아요.")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# 「오늘」은 한국 날짜다 — 서비스가 국내 전용이고, UTC 날짜로 재면 00~09시(KST)에 「어제」를 오늘로 받는다.
# 한국은 서머타임이 없어 고정 +9 로 충분하다(Windows 파이썬에 tzdata 가 없어도 돈다).
KST = timezone(timedelta(hours=9))


def _today_kst() -> date:
    return datetime.now(KST).date()


def brokers_for(district_id: str | None) -> list[dict[str, Any]]:
    if not district_id:
        return []
    return [{k: b[k] for k in ("name", "office", "registration_no", "contact_url") if k in b}
            for b in PARTNER_BROKERS if district_id in (b.get("district_ids") or [])]


def _parse_slots(raw: list[str] | None) -> list[str]:
    slots: list[str] = []
    for s in raw or []:
        try:
            dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        except ValueError as exc:
            raise DirectError(422, "방문 희망 시각 형식이 맞지 않아요") from exc
        dt = aware(dt)
        if dt <= _now():
            raise DirectError(422, "방문 희망 시각은 지금 이후여야 해요")
        slots.append(dt.isoformat())
    if not 1 <= len(slots) <= MAX_SLOTS:
        raise DirectError(422, f"방문 희망 시각을 1~{MAX_SLOTS}개 골라 주세요")
    return list(dict.fromkeys(slots))


def _body(text: str | None) -> str:
    body = (text or "").strip()
    if not 1 <= len(body) <= 1000:
        raise DirectError(422, "메시지는 1~1,000자로 적어 주세요")
    return body


# ── 조건 제안서 · 팝업 신청 ─────────────────────────────────────────────────

def _new_offer(listing: DirectListing, proposer_id: str, kind: str, data: dict[str, Any] | None) -> DirectOffer:
    """창업자가 적은 제안을 검사해 만든다(저장은 호출부). PlaceOS 는 값을 채우거나 권하지 않는다."""
    data = data or {}
    today = _today_kst()
    start: date | None = data.get("start_date")
    if start is not None and start < today:
        raise DirectError(422, "시작일은 오늘 이후로 적어 주세요")
    if kind == "lease":
        if listing.deal_type not in ("lease", "lease_popup"):
            raise DirectError(409, "이 매물은 팝업·단기 사용만 받아요 — 팝업·단기 신청으로 보내 주세요")
        if data.get("rent_manwon") is None:
            raise DirectError(422, "제안할 월세를 적어 주세요", missing=["rent_manwon"])
        return DirectOffer(proposer_user_id=proposer_id, kind="lease", status="proposed",
                           rent_manwon=data.get("rent_manwon"), deposit_manwon=data.get("deposit_manwon"),
                           rent_free_months=data.get("rent_free_months"), term_months=data.get("term_months"),
                           start_date=start)
    if kind == "popup":
        if listing.deal_type not in ("lease_popup", "popup"):
            raise DirectError(409, "이 매물은 팝업·단기 사용을 받지 않아요")
        days = data.get("popup_days")
        if not days:
            raise DirectError(422, "팝업 일수를 적어 주세요", missing=["popup_days"])
        if start is None:
            raise DirectError(422, "팝업 시작일을 적어 주세요", missing=["start_date"])
        lo, hi = listing.popup_min_days, listing.popup_max_days
        if (lo and days < lo) or (hi and days > hi):
            span = " · ".join(x for x in (f"최소 {lo}일" if lo else "", f"최대 {hi}일" if hi else "") if x)
            raise DirectError(422, f"건물주가 적은 팝업 기간({span}) 밖이에요")
        daily = data.get("popup_daily_manwon")
        return DirectOffer(proposer_user_id=proposer_id, kind="popup", status="proposed", start_date=start,
                           popup_days=days, popup_daily_manwon=daily if daily is not None else listing.popup_daily_manwon)
    raise DirectError(422, "제안 종류를 골라 주세요")


def _offer_out(o: DirectOffer) -> dict[str, Any]:
    return {
        "id": o.id, "kind": o.kind, "status": o.status, "status_label": OFFER_STATUS_LABELS.get(o.status, o.status),
        "rent_manwon": o.rent_manwon, "deposit_manwon": o.deposit_manwon, "rent_free_months": o.rent_free_months,
        "term_months": o.term_months, "start_date": o.start_date.isoformat() if o.start_date else None,
        "popup_days": o.popup_days, "popup_daily_manwon": o.popup_daily_manwon,
        "popup_total_manwon": (o.popup_days * o.popup_daily_manwon) if o.popup_days and o.popup_daily_manwon else None,
        "created_at": aware(o.created_at).isoformat(),
        "decided_at": aware(o.decided_at).isoformat() if o.decided_at else None,
    }


def _offers(db: Session, inquiry_id: str) -> list[DirectOffer]:
    return list(db.execute(select(DirectOffer).where(DirectOffer.inquiry_id == inquiry_id)
                           .order_by(DirectOffer.created_at.asc())).scalars().all())


# ── 문의 열기 ──────────────────────────────────────────────────────────────

def create_inquiry(db: Session, founder_id: str, listing_id: str, *, kind: str, body: str,
                   visit_slots: list[str] | None = None, industry_key: str = "",
                   offer: dict[str, Any] | None = None) -> DirectInquiry:
    listing = db.get(DirectListing, listing_id)
    if listing is None or not is_public(db, listing):
        raise DirectError(404, "매물을 찾지 못했어요")
    if listing.owner_user_id == founder_id:
        raise DirectError(400, "내 매물에는 문의할 수 없어요")
    if kind not in FOUNDER_KINDS:
        raise DirectError(422, "문의 종류를 골라 주세요")
    text = _body(body)
    since = _now() - timedelta(days=1)
    recent = db.execute(select(func.count()).select_from(DirectInquiry)
                        .where(DirectInquiry.founder_user_id == founder_id, DirectInquiry.initiated_by == "founder",
                               DirectInquiry.created_at >= since)).scalar_one()
    if recent >= MAX_NEW_PER_DAY:
        raise DirectError(429, f"문의는 하루 {MAX_NEW_PER_DAY}건까지 보낼 수 있어요")
    slots = _parse_slots(visit_slots) if kind == "visit" else []
    offer_row = _new_offer(listing, founder_id, "popup" if kind == "popup" else "lease", offer) \
        if kind in ("offer", "popup") else None
    inquiry = DirectInquiry(listing_id=listing.id, founder_user_id=founder_id, owner_user_id=listing.owner_user_id,
                            kind=kind, status="open", industry_key=(industry_key or "")[:32], visit_slots=slots,
                            initiated_by="founder")
    db.add(inquiry)
    db.flush()
    db.add(DirectMessage(inquiry_id=inquiry.id, sender_user_id=founder_id, body=text))
    if offer_row is not None:
        offer_row.inquiry_id = inquiry.id
        db.add(offer_row)
    db.commit()
    db.refresh(inquiry)
    return inquiry


def invite(db: Session, owner_id: str, brief_id: str, listing_id: str, body: str) -> DirectInquiry:
    """건물주 → 창업자 제안 — 희망서를 보고 **내 확인 매물**로 대화를 연다. 창업자가 제안을 받지 않으면 막는다."""
    listing = db.get(DirectListing, listing_id)
    if listing is None or listing.owner_user_id != owner_id or not is_public(db, listing):
        raise DirectError(404, "매물을 찾지 못했어요")
    brief = db.get(DirectBrief, brief_id)
    if brief is None or not direct_briefs.visible_to_owner(db, brief, owner_id):
        raise DirectError(404, "희망서를 찾지 못했어요")
    if listing.district_id not in (brief.district_ids or []):
        raise DirectError(409, "이 매물은 창업자의 희망 상권 밖이에요 — 희망 상권 안의 매물로 제안해요")
    if not brief.accept_invites:
        raise DirectError(409, "이 창업자는 지금 건물주 제안을 받지 않아요")
    dup = db.execute(select(DirectInquiry.id).where(
        DirectInquiry.listing_id == listing.id, DirectInquiry.founder_user_id == brief.user_id,
        DirectInquiry.status != "closed")).first()
    if dup is not None:
        raise DirectError(409, "이미 이 매물로 이 창업자와 이야기하고 있어요 — 문의함에서 이어 가요")
    text = _body(body)
    since = _now() - timedelta(days=1)
    recent = db.execute(select(func.count()).select_from(DirectInquiry)
                        .where(DirectInquiry.owner_user_id == owner_id, DirectInquiry.initiated_by == "owner",
                               DirectInquiry.created_at >= since)).scalar_one()
    if recent >= MAX_INVITES_PER_DAY:
        raise DirectError(429, f"제안은 하루 {MAX_INVITES_PER_DAY}건까지 보낼 수 있어요")
    inquiry = DirectInquiry(listing_id=listing.id, founder_user_id=brief.user_id, owner_user_id=owner_id, kind="invite",
                            status="open", industry_key=brief.industry_key or "", visit_slots=[], initiated_by="owner")
    db.add(inquiry)
    db.flush()
    db.add(DirectMessage(inquiry_id=inquiry.id, sender_user_id=owner_id, body=text))
    db.commit()
    db.refresh(inquiry)
    return inquiry


# ── 스레드 ─────────────────────────────────────────────────────────────────

def _participant(db: Session, user_id: str, inquiry_id: str) -> tuple[DirectInquiry, str]:
    inquiry = db.get(DirectInquiry, inquiry_id)
    if inquiry is None:
        raise DirectError(404, "문의를 찾지 못했어요")
    if user_id == inquiry.owner_user_id:
        return inquiry, "owner"
    if user_id == inquiry.founder_user_id:
        return inquiry, "founder"
    raise DirectError(404, "문의를 찾지 못했어요")


def _summary(db: Session, inquiry: DirectInquiry, role: str) -> dict[str, Any]:
    listing = db.get(DirectListing, inquiry.listing_id)
    last = db.execute(select(DirectMessage).where(DirectMessage.inquiry_id == inquiry.id)
                      .order_by(DirectMessage.created_at.desc())).scalars().first()
    latest = db.execute(select(DirectOffer).where(DirectOffer.inquiry_id == inquiry.id)
                        .order_by(DirectOffer.created_at.desc())).scalars().first()
    return {
        "id": inquiry.id, "role": role, "kind": inquiry.kind, "kind_label": KIND_LABELS.get(inquiry.kind, inquiry.kind),
        "status": inquiry.status, "initiated_by": inquiry.initiated_by,
        "listing_id": inquiry.listing_id, "listing_title": title(listing) if listing else "",
        "confirmed_slot": aware(inquiry.confirmed_slot).isoformat() if inquiry.confirmed_slot else None,
        "outcome": inquiry.outcome,
        "latest_offer_status": latest.status if latest else None,
        "last_message": (last.body[:80] if last else ""),
        "updated_at": aware(inquiry.updated_at).isoformat(),
    }


def inbox(db: Session, user_id: str) -> dict[str, Any]:
    owned = db.execute(select(DirectInquiry).where(DirectInquiry.owner_user_id == user_id)
                       .order_by(DirectInquiry.updated_at.desc())).scalars().all()
    sent = db.execute(select(DirectInquiry).where(DirectInquiry.founder_user_id == user_id)
                      .order_by(DirectInquiry.updated_at.desc())).scalars().all()
    return {"as_owner": [_summary(db, i, "owner") for i in owned],
            "as_founder": [_summary(db, i, "founder") for i in sent], "notice": DIRECT_NOTICE}


def thread(db: Session, user_id: str, inquiry_id: str) -> dict[str, Any]:
    inquiry, role = _participant(db, user_id, inquiry_id)
    msgs = db.execute(select(DirectMessage).where(DirectMessage.inquiry_id == inquiry.id)
                      .order_by(DirectMessage.created_at.asc())).scalars().all()
    listing = db.get(DirectListing, inquiry.listing_id)
    out: dict[str, Any] = {
        **_summary(db, inquiry, role),
        "visit_slots": list(inquiry.visit_slots or []),
        "industry_key": inquiry.industry_key,
        "messages": [{"id": m.id, "mine": m.sender_user_id == user_id,
                      "from": "owner" if m.sender_user_id == inquiry.owner_user_id else "founder",
                      "body": m.body, "created_at": aware(m.created_at).isoformat()} for m in msgs],
        "offers": [_offer_out(o) for o in _offers(db, inquiry.id)],
        "listing_deal_type": listing.deal_type if listing else None,
        "contract_path": inquiry.contract_path,
        "contract_path_label": CONTRACT_PATH_LABELS.get(inquiry.contract_path, ""),
        "contract_guide": list(CONTRACT_GUIDE),
        "brokers": brokers_for(listing.district_id if listing else None),
        "brokers_note": BROKERS_NOTE,
        "notice": DIRECT_NOTICE,
    }
    if role == "owner":
        # 건물주에게 — 그 희망서를 보고 먼저 제안한 대화(①)이거나 창업자가 직접 연 대화(① + ②)일 때만. ③은 절대 싣지 않는다
        out["brief"] = direct_briefs.thread_view_for_owner(db, inquiry, user_id)
    else:
        mine = direct_briefs.get_mine(db, user_id)
        out["has_brief"] = mine is not None
        out["brief_disclosed"] = mine is not None and direct_briefs.is_disclosed(db, mine.id, inquiry.owner_user_id)
    return out


def add_message(db: Session, user_id: str, inquiry_id: str, body: str) -> dict[str, Any]:
    inquiry, _role = _participant(db, user_id, inquiry_id)
    if inquiry.status == "closed":
        raise DirectError(409, "끝난 문의에는 메시지를 보낼 수 없어요")
    db.add(DirectMessage(inquiry_id=inquiry.id, sender_user_id=user_id, body=_body(body)))
    inquiry.updated_at = _now()
    db.commit()
    return thread(db, user_id, inquiry_id)


def visit(db: Session, user_id: str, inquiry_id: str, action: str, *, slots: list[str] | None = None,
          slot: str | None = None) -> dict[str, Any]:
    inquiry, role = _participant(db, user_id, inquiry_id)
    if inquiry.status == "closed":
        raise DirectError(409, "끝난 문의예요")
    if action == "propose":
        if role != "founder":
            raise DirectError(403, "방문 시각은 창업자가 제안해요")
        inquiry.visit_slots = _parse_slots(slots)
        if inquiry.kind == "question":      # 질문이 방문 요청이 된다(11-18 동작) — 제안·팝업·건물주 제안의 종류는 지키고
            inquiry.kind = "visit"
        inquiry.confirmed_slot = None
        inquiry.status = "open"
    elif action == "confirm":
        if role != "owner":
            raise DirectError(403, "방문 시각은 건물주가 확정해요")
        if not slot or slot not in (inquiry.visit_slots or []):
            raise DirectError(422, "창업자가 제안한 시각 중에서 골라 주세요")
        inquiry.confirmed_slot = datetime.fromisoformat(slot)
        inquiry.status = "scheduled"
    elif action == "cancel":
        inquiry.confirmed_slot = None
        inquiry.status = "open"
    else:
        raise DirectError(422, "알 수 없는 동작이에요")
    inquiry.updated_at = _now()
    db.commit()
    return thread(db, user_id, inquiry_id)


def propose_offer(db: Session, user_id: str, inquiry_id: str, kind: str, data: dict[str, Any]) -> dict[str, Any]:
    """대화 중에 새 조건 제안서·팝업 신청 — 창업자만. 답을 기다리던 앞 제안은 「새 제안으로 바뀜」이 된다."""
    inquiry, role = _participant(db, user_id, inquiry_id)
    if role != "founder":
        raise DirectError(403, "조건 제안서는 창업자가 적어요")
    if inquiry.status == "closed":
        raise DirectError(409, "끝난 문의예요")
    listing = db.get(DirectListing, inquiry.listing_id)
    if listing is None:
        raise DirectError(404, "매물을 찾지 못했어요")
    row = _new_offer(listing, user_id, kind, data)
    now = _now()
    for prev in _offers(db, inquiry.id):
        if prev.status == "proposed":
            prev.status = "superseded"
            prev.decided_at = now
    row.inquiry_id = inquiry.id
    db.add(row)
    inquiry.updated_at = now
    db.commit()
    return thread(db, user_id, inquiry_id)


def decide_offer(db: Session, user_id: str, inquiry_id: str, offer_id: str, action: str) -> dict[str, Any]:
    """건물주가 받거나(accept) 거절(decline) · 창업자가 거둔다(withdraw). 받아도 계약이 아니다 — 돈도 붙지 않는다."""
    inquiry, role = _participant(db, user_id, inquiry_id)
    if inquiry.status == "closed":
        raise DirectError(409, "끝난 문의예요")
    offer = db.get(DirectOffer, offer_id)
    if offer is None or offer.inquiry_id != inquiry.id:
        raise DirectError(404, "제안을 찾지 못했어요")
    if offer.status != "proposed":
        raise DirectError(409, "이미 답한 제안이에요")
    if action in ("accept", "decline"):
        if role != "owner":
            raise DirectError(403, "제안은 건물주가 받거나 거절해요")
        offer.status = "accepted" if action == "accept" else "declined"
    elif action == "withdraw":
        if role != "founder":
            raise DirectError(403, "제안은 적은 창업자가 거둬요")
        offer.status = "withdrawn"
    else:
        raise DirectError(422, "알 수 없는 동작이에요")
    now = _now()
    offer.decided_at = now
    inquiry.updated_at = now
    db.commit()
    return thread(db, user_id, inquiry_id)


def set_contract_path(db: Session, user_id: str, inquiry_id: str, path: str) -> dict[str, Any]:
    """계약 진행 방법 기록 — 당사자 직접 / 제휴 공인중개사. 기록일 뿐 PlaceOS 가 계약을 대신하지 않는다."""
    inquiry, _role = _participant(db, user_id, inquiry_id)
    if path not in CONTRACT_PATHS:
        raise DirectError(422, "계약 진행 방법을 골라 주세요")
    inquiry.contract_path = path
    inquiry.updated_at = _now()
    db.commit()
    return thread(db, user_id, inquiry_id)


def set_disclosure(db: Session, user_id: str, inquiry_id: str, open_: bool) -> dict[str, Any]:
    """창업자가 이 대화의 건물주에게 희망서 ②(사업 개요·단계·자금 계획)를 열거나 거둔다."""
    inquiry, role = _participant(db, user_id, inquiry_id)
    if role != "founder":
        raise DirectError(403, "희망서 상세는 창업자가 열어요")
    if open_:
        if inquiry.status == "closed":
            raise DirectError(409, "끝난 대화에서는 희망서를 열 수 없어요 — 거두기는 언제든 할 수 있어요")
        direct_briefs.disclose(db, user_id, inquiry.owner_user_id)
    else:
        direct_briefs.revoke(db, user_id, inquiry.owner_user_id)
    return thread(db, user_id, inquiry_id)


def set_outcome(db: Session, user_id: str, inquiry_id: str, outcome: str) -> dict[str, Any]:
    """결과 자기보고 — 연결이 계약으로 이어졌나(KPI 계측). 과금과 무관하다."""
    inquiry, role = _participant(db, user_id, inquiry_id)
    if outcome not in OUTCOMES:
        raise DirectError(422, "결과를 골라 주세요")
    inquiry.outcome = outcome
    inquiry.outcome_by = role
    inquiry.status = "closed"
    inquiry.updated_at = _now()
    db.flush()
    # 두 사람 사이에 이어지는 대화가 더 없으면 희망서 ② 공개 동의도 닫는다(2026-11-21 리뷰 반영)
    direct_briefs.prune_disclosures(db, {(inquiry.founder_user_id, inquiry.owner_user_id)})
    db.commit()
    return thread(db, user_id, inquiry_id)


# ── 알림(이메일 먼저 · decision-lightweight-first) ──────────────────────────

def owner_email(db: Session, inquiry: DirectInquiry) -> str | None:
    user = db.get(User, inquiry.owner_user_id)
    return user.email if user else None


def founder_email(db: Session, inquiry: DirectInquiry) -> str | None:
    user = db.get(User, inquiry.founder_user_id)
    return user.email if user else None


def _send(email: str | None, subject: str, text: str) -> str:
    """본문에 문의 내용·연락처를 싣지 않는다. SMTP 는 방문자 의견 알림과 같은 설정을 쓴다.

    미설정이면 disabled, 실패하면 failed — 실패해도 문의는 이미 저장돼 있다.
    """
    if not email or not (settings.feedback_smtp_host and settings.feedback_mail_from):
        return "disabled"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.feedback_mail_from
    msg["To"] = email
    msg.set_content(text + "\n이 메일에는 문의 내용과 연락처를 싣지 않습니다.\n\n" + DIRECT_NOTICE)
    try:
        with smtplib.SMTP(settings.feedback_smtp_host, settings.feedback_smtp_port, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if settings.feedback_smtp_user:
                smtp.login(settings.feedback_smtp_user, settings.feedback_smtp_password)
            smtp.send_message(msg)
        return "sent"
    except (OSError, smtplib.SMTPException):
        logger.warning("직거래 알림 메일 발송 실패")
        return "failed"


def notify_owner(email: str | None) -> str:
    """새 문의 알림(건물주)."""
    return _send(email, "[PlaceOS] 내 매물에 새 문의가 왔어요",
                 "내 매물에 새 문의가 왔어요. PlaceOS 문의함(placeos.co.kr/#/inbox)에서 확인하세요.")


def notify_founder(email: str | None) -> str:
    """새 제안 알림(창업자) — 건물주가 내 입점 희망서를 보고 자리를 제안했다."""
    return _send(email, "[PlaceOS] 건물주가 내 입점 희망서를 보고 자리를 제안했어요",
                 "건물주가 내 입점 희망서를 보고 자리를 제안했어요. PlaceOS 문의함(placeos.co.kr/#/inbox)에서 확인하세요.")
