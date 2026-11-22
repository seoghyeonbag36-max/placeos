"""직거래 정액 상품 — 정액 광고 · 구독 · 정보 판매 (2026-11-18).

⛔ 성사·중개 수수료는 없다(L1). 상품은 정액(또는 무료)이고, 성사 여부와 무관하게 정해진 금액이다 — 이어 주고 보수를 받으면
   명목과 무관하게 중개업이라(공인중개사법 제2조·제48조) 성사 연동 과금은 이 저장소에서 금지다.
결제는 PG 없이 「신청 → 계좌이체 → 관리자 입금 확인」이다(docs/decision-lightweight-first-2026-10-05.md §3).
가격(`price_krw`)은 **사용자가 정하기 전까지 None** — 화면은 「가격 확정 전」으로 보이고 신청만 받는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.direct import DirectListing, PurchaseIntent
from app.services.direct_listings import DIRECT_NOTICE, DirectError, aware, is_public

KINDS = frozenset({"free", "ad", "report", "subscription"})
PROMOTE_DAYS = 30

# TODO(사용자 결정): price_krw — 판매 전에 가격을 정한다(E1·E2 가격 실험 → docs/decision-owner-direct-matching-2026-11-18.md §6).
PRODUCTS: dict[str, dict[str, Any]] = {
    "owner_listing": {
        "side": "owner", "kind": "free", "title": "빈 자리 직접 등록·게시", "unit": "매물당", "price_krw": 0,
        "available": True, "desc": "소유자 확인을 거쳐 게시해요. 등록·게시는 무료예요.",
    },
    "owner_promote_30d": {
        "side": "owner", "kind": "ad", "title": "상단 노출 30일", "unit": "30일", "price_krw": None,
        "available": True, "desc": "같은 상권 목록 위쪽에 「광고」 표시와 함께 보여요.",
    },
    "owner_diagnosis_report": {
        "side": "owner", "kind": "report", "title": "공실 진단 상세 리포트", "unit": "매물당", "price_krw": None,
        "available": True, "desc": "층 이력·주변 추정 공실·업종 신호 전체·비교를 열어요.",
    },
    "founder_precheck_report": {
        "side": "founder", "kind": "report", "title": "계약 전 확인 리포트", "unit": "매물당", "price_krw": None,
        "available": True, "desc": "사람이 건축물대장·토지이음 등 공적 자료를 다시 대조해 정리해 드려요(허가 판정은 아니에요).",
    },
    "founder_watch_30d": {
        "side": "founder", "kind": "subscription", "title": "관심 상권 새 매물 알림 30일", "unit": "30일",
        "price_krw": None, "available": False, "desc": "준비 중이에요 — 알림 발송이 생기면 열어요.",
    },
}
PAYMENT_NOTE = "결제는 계좌이체로만 받아요(카드·간편결제 없음). 입금이 확인되면 열려요."


def catalog() -> dict[str, Any]:
    return {"products": [{"key": k, **v} for k, v in PRODUCTS.items()], "payment": PAYMENT_NOTE,
            "notice": DIRECT_NOTICE}


def _out(p: PurchaseIntent) -> dict[str, Any]:
    product = PRODUCTS.get(p.product, {})
    return {"id": p.id, "product": p.product, "title": product.get("title", p.product), "target_id": p.target_id,
            "status": p.status, "amount_krw": p.amount_krw, "created_at": aware(p.created_at).isoformat(),
            "decided_at": aware(p.decided_at).isoformat() if p.decided_at else None}


def instructions() -> dict[str, Any]:
    account = (settings.direct_bank_account or "").strip()
    return {"bank_account": account or None,
            "message": (f"아래 계좌로 입금해 주세요: {account}. 입금자명은 신청할 때 적은 이름으로 해 주세요."
                        if account else "입금 계좌는 담당자가 따로 안내해요."),
            "payment": PAYMENT_NOTE}


def request(db: Session, user_id: str, product: str, target_id: str, depositor_name: str) -> dict[str, Any]:
    spec = PRODUCTS.get(product)
    if spec is None:
        raise DirectError(422, "알 수 없는 상품이에요")
    if not spec["available"]:
        raise DirectError(409, "준비 중인 상품이에요")
    if spec["kind"] == "free":
        raise DirectError(422, "무료 상품은 신청하지 않아도 돼요")
    listing = db.get(DirectListing, target_id) if target_id else None
    if listing is None:
        raise DirectError(404, "매물을 찾지 못했어요")
    if spec["side"] == "owner" and listing.owner_user_id != user_id:
        raise DirectError(404, "매물을 찾지 못했어요")
    if spec["side"] == "founder" and (listing.owner_user_id == user_id or not is_public(db, listing)):
        raise DirectError(404, "매물을 찾지 못했어요")
    name = (depositor_name or "").strip()
    if not 1 <= len(name) <= 50:
        raise DirectError(422, "입금자명을 적어 주세요")
    open_one = db.execute(select(PurchaseIntent).where(
        PurchaseIntent.user_id == user_id, PurchaseIntent.product == product, PurchaseIntent.target_id == target_id,
        PurchaseIntent.status == "requested")).scalars().first()
    if open_one is None:
        open_one = PurchaseIntent(user_id=user_id, product=product, target_id=target_id, status="requested",
                                  amount_krw=spec["price_krw"], depositor_name=name)
        db.add(open_one)
        db.commit()
        db.refresh(open_one)
    return {**_out(open_one), "instructions": instructions()}


def mine(db: Session, user_id: str) -> list[dict[str, Any]]:
    rows = db.execute(select(PurchaseIntent).where(PurchaseIntent.user_id == user_id)
                      .order_by(PurchaseIntent.created_at.desc())).scalars().all()
    return [_out(p) for p in rows]


def has_entitlement(db: Session, user_id: str, product: str, target_id: str) -> bool:
    return db.execute(select(PurchaseIntent.id).where(
        PurchaseIntent.user_id == user_id, PurchaseIntent.product == product, PurchaseIntent.target_id == target_id,
        PurchaseIntent.status.in_(("paid", "fulfilled")))).first() is not None


def _fulfill(db: Session, p: PurchaseIntent) -> None:
    """입금 확인 뒤 이행. 광고는 노출 기간을 늘리고, 진단 리포트는 열리고, 계약 전 확인은 사람이 이행한 뒤 fulfilled 로 바꾼다."""
    now = datetime.now(timezone.utc)
    if p.product == "owner_promote_30d":
        listing = db.get(DirectListing, p.target_id)
        if listing is not None:
            base = max(now, aware(listing.promoted_until) or now)
            listing.promoted_until = base + timedelta(days=PROMOTE_DAYS)
        p.status = "fulfilled"
    elif p.product == "owner_diagnosis_report":
        p.status = "fulfilled"


def admin_list(db: Session, status: str | None = None) -> list[dict[str, Any]]:
    q = select(PurchaseIntent).order_by(PurchaseIntent.created_at.desc())
    if status:
        q = q.where(PurchaseIntent.status == status)
    return [{**_out(p), "user_id": p.user_id, "depositor_name": p.depositor_name}
            for p in db.execute(q).scalars().all()]


def admin_act(db: Session, purchase_id: str, action: str) -> dict[str, Any]:
    p = db.get(PurchaseIntent, purchase_id)
    if p is None:
        raise DirectError(404, "신청을 찾지 못했어요")
    now = datetime.now(timezone.utc)
    if action == "confirm_paid":
        if p.status != "requested":
            raise DirectError(409, "신청 상태에서만 입금을 확인해요")
        p.status = "paid"
        p.decided_at = now
        _fulfill(db, p)
    elif action == "fulfill":
        if p.status != "paid":
            raise DirectError(409, "입금 확인 뒤에만 이행 완료로 바꿔요")
        p.status = "fulfilled"
        p.decided_at = now
    elif action == "cancel":
        if p.status in ("fulfilled",):
            raise DirectError(409, "이행이 끝난 신청은 취소하지 않아요(환불은 따로 처리)")
        p.status = "cancelled"
        p.decided_at = now
    else:
        raise DirectError(422, "알 수 없는 동작이에요")
    db.commit()
    db.refresh(p)
    return _out(p)
