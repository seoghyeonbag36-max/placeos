"""직거래 연결 API — 건물주 확인 매물 · 입점 희망서 · 문의/방문/조건 제안 · 정액 상품
(2026-11-18 · 11-21 · docs/decision-owner-direct-matching-2026-11-18.md · docs/decision-founder-brief-2026-11-21.md).

라우터를 둘로 나눈다(api/v1/router.py 에서 같은 /direct 아래 등록):
- `public_router` — 목록·상세·조건·신호·상품·묶음 수요. 공개 분석 열람이라 **사용량 계측(_tracked)을 건다**.
- `account_router` — 등록·희망서·문의·방문·제안·신고·신청. 로그인 필수이고 **계측을 걸지 않는다** — 건물주의 등록·문의 활동이
  창업자 파일럿 KPI③ W4 「분석 접근」으로 세지면 판정이 오염된다(피드백 라우터와 같은 이유). 계정 전용 읽기는 `/me/...` 아래 둔다.

표가 아직 없는 DB(배포는 자동, 마이그레이션은 수동)에서는 503 「준비 중」으로 물러난다 — 다른 기능은 그대로 선다.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, Principal, get_current_user, get_optional_principal
from app.schemas.direct import (
    BriefIn, BriefStatusIn, ContractPathIn, FloorPlanIn, InquiryIn, InviteIn, ListingIn, MessageIn, OfferDecisionIn, OfferProposeIn,
    OutcomeIn, PurchaseIn, ReportIn, StatusIn, VerificationIn, VisitIn,
)
from app.services import (
    business_fit, direct_briefs, direct_connect, direct_fit, direct_floor_plans as floor_plans, direct_listings as listings,
    direct_matching, direct_pricing, direct_purchases, industry_fit, owner_diagnosis,
)
from app.services import districts as districts_svc
from app.services.direct_listings import DIRECT_NOTICE, DirectError

public_router = APIRouter()
account_router = APIRouter()

NOT_READY = "직거래 기능을 준비하고 있어요(데이터베이스 표가 아직 없습니다)."


def _ready(db: Session) -> None:
    if not listings.schema_ready(db):
        raise HTTPException(503, NOT_READY)


def _raise(exc: DirectError) -> None:
    detail: Any = {"message": str(exc), "missing": exc.missing} if exc.missing else str(exc)
    raise HTTPException(exc.status, detail) from exc


# ── 공개(계측) ─────────────────────────────────────────────────────────────

@public_router.get("/meta")
def meta() -> dict:
    """등록 화면의 선택지 — 건물 용도(종류) · 대장 세부 용도(업종 관측 표의 키) · 업종 key · 고지문."""
    return {
        "use_types": list(listings.USE_TYPES),
        "deal_types": [{"key": k, "label": v} for k, v in listings.DEAL_LABELS.items()],
        "relations": [{"key": k, "label": v} for k, v in listings.RELATION_LABELS.items()],
        "ledger_uses": industry_fit.ledger_uses(),
        "industries": [{"key": i["key"], "label": i["label"]} for i in business_fit.industries()],
        "report_reasons": list(listings.REPORT_REASONS),
        "long_vacancy_months": listings.LONG_VACANCY_MONTHS,
        "required": listings.REQUIRED_LABELS,
        # 2026-11-21 — 입점 희망서 · 조건 제안서 · 계약 진행 방법
        "brief": direct_briefs.meta(),
        "inquiry_kinds": [{"key": k, "label": v} for k, v in direct_connect.KIND_LABELS.items()],
        "contract_paths": [{"key": k, "label": v} for k, v in direct_connect.CONTRACT_PATH_LABELS.items()],
        "notice": DIRECT_NOTICE,
    }


@public_router.get("/products")
def products() -> dict:
    return direct_purchases.catalog()


@public_router.get("/demand")
def demand(district_id: str = Query(min_length=1, max_length=64), db: Session = Depends(get_db)) -> dict:
    """이 상권을 희망한 입점 희망서 묶음 — n≥3 만 숫자. 누구인지는 싣지 않는다(건물주의 다음 공실 대비 수요 신호)."""
    _ready(db)
    if district_id not in districts_svc.PAGES_BY_ID:
        raise HTTPException(404, "상권을 찾지 못했어요")
    return direct_briefs.demand(db, district_id)


@public_router.get("/listings")
def search(district_id: str | None = None, building_id: str | None = None,
           floor_band: str | None = Query(default=None, pattern="^(first|upper|basement)$"),
           popup: bool | None = None, long_vacancy: bool | None = None, max_rent: int | None = Query(default=None, ge=0),
           industry: str | None = Query(default=None, max_length=32), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    rows = listings.search(db, district_id=district_id, building_id=building_id, floor_band=floor_band, popup=popup,
                           long_vacancy=long_vacancy, max_rent=max_rent)
    rows.sort(key=lambda r: direct_matching.founder_sort_key(r, industry))
    items = []
    for r in rows:
        c = listings.card(r)
        c["effective_monthly_rent_manwon"] = direct_pricing.terms(db, r)["effective_monthly_rent_manwon"]
        if industry:
            c["reasons"] = direct_matching.reasons_for_founder(r, industry)
        items.append(c)
    floor_plans.attach(db, items)
    return {"items": items, "n": len(items), "notice": DIRECT_NOTICE}


@public_router.get("/listings/{listing_id}")
def detail(listing_id: str, industry: str | None = Query(default=None, max_length=32),
           principal: Principal | None = Depends(get_optional_principal), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    row = listings.get_listing(db, listing_id)
    mine = row is not None and principal is not None and principal.user is not None \
        and row.owner_user_id == principal.user.id
    if row is None or not (mine or listings.is_public(db, row)):
        raise HTTPException(404, "매물을 찾지 못했어요")
    out = listings.owner_view(db, row) if mine else listings.card(row)
    out.update({"mine": mine, "notice": DIRECT_NOTICE, "terms": direct_pricing.terms(db, row),
                "reasons": direct_matching.reasons_for_founder(row, industry)})
    floor_plans.attach(db, [out])
    return out


@public_router.get("/listings/{listing_id}/floor-plan")
def floor_plan_image(listing_id: str, principal: Principal | None = Depends(get_optional_principal),
                     db: Session = Depends(get_db)) -> Response:
    """건물주가 올린 이 층의 배치도 사진 — 매물이 공개(게시 중 + 소유자 확인)일 때만 보인다. 본인은 올린 직후에도 본다."""
    _ready(db)
    row = listings.get_listing(db, listing_id)
    mine = (row is not None and principal is not None and principal.user is not None
            and row.owner_user_id == principal.user.id)
    if row is None or not (mine or listings.is_public(db, row)):
        raise HTTPException(404, "매물을 찾지 못했어요")
    plan = floor_plans.get_image(db, listing_id)
    if plan is None:
        raise HTTPException(404, "올린 배치도 사진이 없어요")
    # 사진은 바뀌거나 숨겨질 수 있어 **공유 캐시(CDN · Firebase Hosting)에 두지 않고** 브라우저에만 잠깐 둔다 — 신고로 숨기거나
    # 지운 사진이 캐시에서 계속 나가지 않게(2026-11-22 리뷰 반영). 본인 미리보기는 저장하지 않는다. 주소의 v 가 바뀌면 새로 받는다.
    # 업로드된 바이트가 문서로 실행되지 않게 막는다(nosniff · sandbox).
    return Response(content=plan.data, media_type=plan.mime, headers={
        "Cache-Control": "private, no-store" if mine else "private, max-age=60",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Content-Disposition": "inline",
    })


@public_router.get("/listings/{listing_id}/terms")
def listing_terms(listing_id: str, term_months: int | None = Query(default=None, ge=1, le=120),
                  db: Session = Depends(get_db)) -> dict:
    _ready(db)
    row = listings.get_listing(db, listing_id)
    if row is None or not listings.is_public(db, row):
        raise HTTPException(404, "매물을 찾지 못했어요")
    return direct_pricing.terms(db, row, term_months)


@public_router.get("/listings/{listing_id}/fit")
def listing_fit(listing_id: str, industry: str | None = Query(default=None, max_length=32),
                db: Session = Depends(get_db)) -> dict:
    _ready(db)
    row = listings.get_listing(db, listing_id)
    if row is None or not listings.is_public(db, row):
        raise HTTPException(404, "매물을 찾지 못했어요")
    return {"for_founder": direct_matching.reasons_for_founder(row, industry),
            "for_owner": direct_matching.signals_for_listing(db, row)}


# ── 계정(비계측 · 로그인 필수) ──────────────────────────────────────────────

@account_router.post("/listings", status_code=201)
def create_listing(body: ListingIn, current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    _ready(db)
    row = listings.create_draft(db, current.user.id, body.model_dump(exclude_unset=True))
    return listings.owner_view(db, row)


@account_router.get("/me/listings")
def my_listings(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    return {"items": floor_plans.attach(db, listings.mine(db, current.user.id)), "notice": DIRECT_NOTICE}


@account_router.patch("/listings/{listing_id}")
def update_listing(listing_id: str, body: ListingIn, current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        row = listings.update(db, current.user.id, listing_id, body.model_dump(exclude_unset=True))
    except DirectError as exc:
        _raise(exc)
    return listings.owner_view(db, row)


@account_router.post("/listings/{listing_id}/submit")
def submit_listing(listing_id: str, body: VerificationIn, current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        row = listings.submit(db, current.user.id, listing_id, body.model_dump())
    except DirectError as exc:
        _raise(exc)
    return listings.owner_view(db, row)


@account_router.post("/listings/{listing_id}/status")
def listing_status(listing_id: str, body: StatusIn, current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        row = listings.set_status(db, current.user.id, listing_id, body.action)
    except DirectError as exc:
        _raise(exc)
    return listings.owner_view(db, row)


@account_router.delete("/listings/{listing_id}", status_code=204)
def delete_listing(listing_id: str, current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> Response:
    _ready(db)
    try:
        listings.delete(db, current.user.id, listing_id)
    except DirectError as exc:
        _raise(exc)
    return Response(status_code=204)


@account_router.put("/listings/{listing_id}/floor-plan")
def put_floor_plan(listing_id: str, body: FloorPlanIn, current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    """내 매물(층)의 실제 배치도 사진을 올리거나 바꾼다 — 서버가 촬영 위치·기기 정보를 떼고 저장한다."""
    _ready(db)
    try:
        return floor_plans.save(db, current.user.id, listing_id, body.mime, body.data)
    except DirectError as exc:
        _raise(exc)


@account_router.delete("/listings/{listing_id}/floor-plan", status_code=204)
def delete_floor_plan(listing_id: str, current: CurrentUser = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> Response:
    _ready(db)
    try:
        floor_plans.remove(db, current.user.id, listing_id)
    except DirectError as exc:
        _raise(exc)
    return Response(status_code=204)


@account_router.get("/listings/{listing_id}/diagnosis")
def diagnosis(listing_id: str, cut_pct: float = Query(default=10, ge=0, le=90),
              vacancy_months: float = Query(default=3, ge=0, le=36),
              current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        row = listings.get_owned(db, current.user.id, listing_id)
    except DirectError as exc:
        _raise(exc)
    full = direct_purchases.has_entitlement(db, current.user.id, "owner_diagnosis_report", listing_id)
    return owner_diagnosis.diagnose(db, row, cut_pct=cut_pct, vacancy_months=vacancy_months, full=full)


@account_router.post("/listings/{listing_id}/inquiries", status_code=201)
def create_inquiry(listing_id: str, body: InquiryIn, background: BackgroundTasks,
                   current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        inquiry = direct_connect.create_inquiry(
            db, current.user.id, listing_id, kind=body.kind, body=body.body, visit_slots=body.visit_slots,
            industry_key=body.industry_key, offer=body.offer.model_dump(exclude_none=True) if body.offer else None)
    except DirectError as exc:
        _raise(exc)
    background.add_task(direct_connect.notify_owner, direct_connect.owner_email(db, inquiry))
    return direct_connect.thread(db, current.user.id, inquiry.id)


@account_router.post("/listings/{listing_id}/report", status_code=201)
def report_listing(listing_id: str, body: ReportIn, current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        return listings.report(db, current.user.id, listing_id, body.reason, body.detail)
    except DirectError as exc:
        _raise(exc)


@account_router.get("/inbox")
def inbox(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    return direct_connect.inbox(db, current.user.id)


@account_router.get("/inquiries/{inquiry_id}")
def thread(inquiry_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        return direct_connect.thread(db, current.user.id, inquiry_id)
    except DirectError as exc:
        _raise(exc)


@account_router.post("/inquiries/{inquiry_id}/messages", status_code=201)
def message(inquiry_id: str, body: MessageIn, current: CurrentUser = Depends(get_current_user),
            db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        return direct_connect.add_message(db, current.user.id, inquiry_id, body.body)
    except DirectError as exc:
        _raise(exc)


@account_router.post("/inquiries/{inquiry_id}/visit")
def visit(inquiry_id: str, body: VisitIn, current: CurrentUser = Depends(get_current_user),
          db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        return direct_connect.visit(db, current.user.id, inquiry_id, body.action, slots=body.slots, slot=body.slot)
    except DirectError as exc:
        _raise(exc)


@account_router.post("/inquiries/{inquiry_id}/outcome")
def outcome(inquiry_id: str, body: OutcomeIn, current: CurrentUser = Depends(get_current_user),
            db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        return direct_connect.set_outcome(db, current.user.id, inquiry_id, body.outcome)
    except DirectError as exc:
        _raise(exc)


@account_router.post("/inquiries/{inquiry_id}/offers", status_code=201)
def propose_offer(inquiry_id: str, body: OfferProposeIn, current: CurrentUser = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> dict:
    """대화 중 새 조건 제안서·팝업 신청(창업자). PlaceOS 는 값을 권하지 않는다."""
    _ready(db)
    try:
        return direct_connect.propose_offer(db, current.user.id, inquiry_id, body.kind,
                                            body.offer.model_dump(exclude_none=True))
    except DirectError as exc:
        _raise(exc)


@account_router.post("/inquiries/{inquiry_id}/offers/{offer_id}")
def decide_offer(inquiry_id: str, offer_id: str, body: OfferDecisionIn,
                 current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """건물주가 받거나 거절 · 창업자가 거둔다. 받아도 계약이 아니고 돈도 붙지 않는다."""
    _ready(db)
    try:
        return direct_connect.decide_offer(db, current.user.id, inquiry_id, offer_id, body.action)
    except DirectError as exc:
        _raise(exc)


@account_router.post("/inquiries/{inquiry_id}/contract-path")
def contract_path(inquiry_id: str, body: ContractPathIn, current: CurrentUser = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        return direct_connect.set_contract_path(db, current.user.id, inquiry_id, body.path)
    except DirectError as exc:
        _raise(exc)


@account_router.post("/inquiries/{inquiry_id}/disclose")
def disclose_brief(inquiry_id: str, current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    """창업자가 이 대화의 건물주에게 희망서 ②(사업 개요·단계·자금 계획)를 연다."""
    _ready(db)
    try:
        return direct_connect.set_disclosure(db, current.user.id, inquiry_id, True)
    except DirectError as exc:
        _raise(exc)


@account_router.delete("/inquiries/{inquiry_id}/disclose")
def revoke_brief(inquiry_id: str, current: CurrentUser = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        return direct_connect.set_disclosure(db, current.user.id, inquiry_id, False)
    except DirectError as exc:
        _raise(exc)


# ── 입점 희망서(창업자 본인) ────────────────────────────────────────────────

@account_router.get("/me/brief")
def my_brief(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    brief = direct_briefs.get_mine(db, current.user.id)
    return {"brief": direct_briefs.self_view(db, brief) if brief else None, "meta": direct_briefs.meta(),
            "notice": DIRECT_NOTICE}


@account_router.patch("/me/brief")
def save_brief(body: BriefIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """만들거나 고친다(한 사람에 하나 · 보낸 칸만 바꾼다)."""
    _ready(db)
    try:
        brief = direct_briefs.save(db, current.user.id, body.model_dump(exclude_unset=True))
    except DirectError as exc:
        _raise(exc)
    return {"brief": direct_briefs.self_view(db, brief), "meta": direct_briefs.meta(), "notice": DIRECT_NOTICE}


@account_router.post("/me/brief/status")
def brief_status(body: BriefStatusIn, current: CurrentUser = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        brief = direct_briefs.set_status(db, current.user.id, body.action)
    except DirectError as exc:
        _raise(exc)
    return {"brief": direct_briefs.self_view(db, brief), "meta": direct_briefs.meta(), "notice": DIRECT_NOTICE}


@account_router.delete("/me/brief", status_code=204)
def delete_brief(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    _ready(db)
    try:
        direct_briefs.delete(db, current.user.id)
    except DirectError as exc:
        _raise(exc)
    return Response(status_code=204)


@account_router.delete("/me/brief/disclosures/{disclosure_id}")
def revoke_disclosure(disclosure_id: str, current: CurrentUser = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> dict:
    """희망서 ② 공개 동의를 대화 없이 거둔다(대화가 끝났거나 사라져도 — 「언제든 거둘 수 있어요」)."""
    _ready(db)
    try:
        direct_briefs.revoke_by_id(db, current.user.id, disclosure_id)
    except DirectError as exc:
        _raise(exc)
    brief = direct_briefs.get_mine(db, current.user.id)
    return {"brief": direct_briefs.self_view(db, brief) if brief else None, "meta": direct_briefs.meta(),
            "notice": DIRECT_NOTICE}


@account_router.get("/me/brief/fit/{listing_id}")
def my_brief_fit(listing_id: str, current: CurrentUser = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> dict:
    """내 희망서 × 이 매물 — 조건표 + 요구 판매량(③ 비공개 입력 · 본인에게만)."""
    _ready(db)
    brief = direct_briefs.get_mine(db, current.user.id)
    if brief is None:
        raise HTTPException(404, "희망서를 먼저 써 주세요")
    row = listings.get_listing(db, listing_id)
    if row is None or not listings.is_public(db, row):
        raise HTTPException(404, "매물을 찾지 못했어요")
    return {**direct_fit.pair(row, brief, direct_pricing.terms(db, row), include_private=True), "notice": DIRECT_NOTICE}


# ── 입점 희망서(건물주가 보는 쪽 · 희망 상권에 내 확인 매물이 있어야) ──────────────────

@account_router.get("/me/owner/briefs")
def owner_briefs(district_id: str | None = Query(default=None, max_length=64),
                 industry: str | None = Query(default=None, max_length=32),
                 popup_first: bool | None = None,
                 current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        return direct_briefs.list_for_owner(db, current.user.id, district_id=district_id, industry=industry,
                                            popup_first=popup_first)
    except DirectError as exc:
        _raise(exc)


@account_router.get("/me/owner/briefs/{brief_id}")
def owner_brief(brief_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        return direct_briefs.get_for_owner(db, current.user.id, brief_id)
    except DirectError as exc:
        _raise(exc)


@account_router.post("/me/owner/briefs/{brief_id}/invite", status_code=201)
def invite(brief_id: str, body: InviteIn, background: BackgroundTasks,
           current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """건물주가 희망서를 보고 **내 확인 매물**로 대화를 연다(제안). 창업자에게는 알림 메일(내용 없음)만 간다."""
    _ready(db)
    try:
        inquiry = direct_connect.invite(db, current.user.id, brief_id, body.listing_id, body.body)
    except DirectError as exc:
        _raise(exc)
    background.add_task(direct_connect.notify_founder, direct_connect.founder_email(db, inquiry))
    return direct_connect.thread(db, current.user.id, inquiry.id)


@account_router.post("/purchases", status_code=201)
def purchase(body: PurchaseIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    try:
        return direct_purchases.request(db, current.user.id, body.product, body.target_id, body.depositor_name)
    except DirectError as exc:
        _raise(exc)


@account_router.get("/me/purchases")
def my_purchases(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _ready(db)
    return {"items": direct_purchases.mine(db, current.user.id), "payment": direct_purchases.PAYMENT_NOTE}
