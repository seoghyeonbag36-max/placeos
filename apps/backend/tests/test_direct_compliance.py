"""직거래 법적 불변식 잠금 — 성사 수수료 없음(L1) · 알선하지 않음(L2) · 고지문(L8) · 계측 분리(KPI③) (2026-11-18).

근거: 공인중개사법 제2조(중개·중개업 정의) · 제48조(무등록 중개 3년/3천만원) · 시행규칙 제20조(상가 보수 상한 0.9%)
→ docs/decision-owner-direct-matching-2026-11-18.md. 이 파일이 빨개지면 「돈 받는 방식」이 법 밖으로 나간 것이다.
"""
from __future__ import annotations

import json

from fastapi.routing import APIRoute

from app.api.deps import track_access
from app.main import app
from app.models.direct import BriefDisclosure, DirectBrief, DirectInquiry, DirectListing, DirectOffer, PurchaseIntent
from app.services import direct_listings, direct_purchases

# 과금 표현(L1). 고지문의 「받지 않습니다」 부정문은 따로 본다.
BANNED = ("성사 수수료", "성사수수료", "중개수수료", "중개 수수료", "성공보수", "성공 보수", "commission", "success fee",
          "success_fee", "fee_rate")


def _without_notice(text: str) -> str:
    return text.replace(direct_listings.DIRECT_NOTICE, "")


def test_products_are_flat_priced_only():
    kinds = {p["kind"] for p in direct_purchases.PRODUCTS.values()}
    assert kinds <= direct_purchases.KINDS == {"free", "ad", "report", "subscription"}
    text = _without_notice(json.dumps(direct_purchases.catalog(), ensure_ascii=False)).lower()
    assert not [w for w in BANNED if w.lower() in text]


def test_no_fee_or_premium_columns_exist():
    # 2026-11-21 — 입점 희망서·공개 동의·조건 제안서·문의 표도 같이 본다(제안·수락에 돈이 붙는 칸이 없어야 한다)
    cols: set[str] = set()
    for model in (DirectListing, PurchaseIntent, DirectInquiry, DirectBrief, BriefDisclosure, DirectOffer):
        cols |= set(model.__table__.columns.keys())
    assert not [c for c in cols if any(w in c for w in ("fee", "commission", "premium", "kwonri"))], cols


def test_notice_says_no_brokerage_and_no_fee():
    assert "중개를 하지 않으며" in direct_listings.DIRECT_NOTICE
    assert "받지 않습니다" in direct_listings.DIRECT_NOTICE


def test_public_responses_carry_the_notice_and_no_fee_words(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    for path in ("/products", "/meta", "/listings?district_id=garosugil", f"/listings/{lid}",
                 "/demand?district_id=garosugil"):
        body = env.client.get(env.base + path).json()
        assert body["notice"] == direct_listings.DIRECT_NOTICE, path
        text = _without_notice(json.dumps(body, ensure_ascii=False)).lower()
        assert not [w for w in BANNED if w.lower() in text], path


def _routes(prefix: str) -> list[APIRoute]:
    return [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith(prefix)]


def test_reads_are_metered_but_owner_and_connect_writes_are_not():
    """KPI③(창업자 파일럿 W4)에 건물주 활동이 섞이지 않게 — 쓰기 라우터에는 track_access 가 없다."""
    def tracked(r: APIRoute) -> bool:
        return track_access in {d.call for d in r.dependant.dependencies}

    direct = _routes("/api/v1/direct")
    assert direct, "직거래 라우트가 등록돼야 한다"
    public_reads = [r for r in direct if r.methods == {"GET"} and not r.path.startswith("/api/v1/direct/me")
                    and r.path not in ("/api/v1/direct/inbox", "/api/v1/direct/inquiries/{inquiry_id}",
                                       "/api/v1/direct/listings/{listing_id}/diagnosis")]
    writes = [r for r in direct if r.methods & {"POST", "PATCH", "DELETE"}]
    assert public_reads and all(tracked(r) for r in public_reads)
    assert writes and not any(tracked(r) for r in writes)


def test_admin_cannot_rewrite_listing_content():
    """L2 — 관리자 창구는 확인·신고·입금 처리만 한다. 매물 내용을 바꾸는 PATCH/PUT 은 없다."""
    admin_direct = _routes("/api/v1/admin/direct")
    assert admin_direct
    assert not [r.path for r in admin_direct if r.methods & {"PATCH", "PUT"}]
