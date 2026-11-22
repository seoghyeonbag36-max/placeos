"""직거래 양쪽 신호 — Platform 의 직거래 쪽 (2026-11-18).

창업자에게는 「이 자리의 이유」를, 건물주에게는 「이 자리에 올 만한 업종 신호」를 준다. **점수를 지어내지 않고 이유를 보인다** —
업종 모델의 실력은 무정보 기준보다 조금 나은 정도라(scripts/kpi_baseline.py) 순위를 단정하면 과대 약속이 된다.

- 관측: 같은 대장 용도·층에서 **실제 영업 중인** 업종 분포(services/industry_fit) — 추천이 아니다.
- 위치 모델: 거점·좌표의 GNN 상위 업종(services/industry_recommend).
- 수요: 최근 90일 이 상권 매물에 문의한 서로 다른 창업자 수(업종별). 3명 미만이면 숫자를 감춘다 — 개인이 드러나지 않게.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.direct import DirectInquiry, DirectListing
from app.services import business_fit, industry_fit, industry_recommend
from app.services.direct_listings import flags

DEMAND_WINDOW_DAYS = 90
DEMAND_MIN_N = 3
MODEL_CAVEAT = ("위치 모델은 거점에서 흔한 업종을 고르는 것보다 조금 나은 정도라 참고로만 보세요 "
                "(검증: scripts/kpi_baseline.py). 그 자리에서 잘 된다는 뜻이 아니에요.")


def _industry(key: str) -> dict | None:
    return next((i for i in business_fit.industries() if i.get("key") == key), None)


def industry_label(key: str) -> str:
    item = _industry(key)
    return str(item.get("label")) if item else key


def observed(listing: DirectListing) -> dict | None:
    """같은 대장 용도·층의 영업 업종 관측. 지하·층 미상은 관측 표가 없어 None."""
    if listing.floor < 1:
        return None
    return industry_fit.fit_for(listing.floor, listing.ledger_use or None)


def model_top(listing: DirectListing, k: int = 3) -> list[dict]:
    if not listing.district_id:
        return []
    rec = industry_recommend.recommend(listing.district_id, listing.lat, listing.lng) or {}
    return list(rec.get("recommendations") or [])[:k]


def demand(db: Session, listing: DirectListing) -> list[dict[str, Any]]:
    """같은 상권 매물에 최근 문의한 창업자 수(업종별). n<3 은 숫자 대신 None."""
    if not listing.district_id:
        return []
    since = datetime.now(timezone.utc) - timedelta(days=DEMAND_WINDOW_DAYS)
    rows = db.execute(
        select(DirectInquiry.industry_key, func.count(func.distinct(DirectInquiry.founder_user_id)))
        .join(DirectListing, DirectListing.id == DirectInquiry.listing_id)
        .where(DirectListing.district_id == listing.district_id, DirectInquiry.created_at >= since,
               DirectInquiry.industry_key != "",
               # 2026-11-21 — 건물주가 희망서를 보고 연 대화(invite)는 창업자 문의 수요가 아니다
               DirectInquiry.initiated_by == "founder")
        .group_by(DirectInquiry.industry_key)).all()
    out = [{"industry_key": key, "label": industry_label(key),
            "founders": n if n >= DEMAND_MIN_N else None, "suppressed": n < DEMAND_MIN_N}
           for key, n in rows]
    return sorted(out, key=lambda d: -(d["founders"] or 0))


def signals_for_listing(db: Session, listing: DirectListing, *, include_caps: bool = False) -> dict[str, Any]:
    """건물주에게 보이는 「업종 신호」.

    `include_caps` — 희망서 묶음에 예산 상한 중앙값을 싣나. 공개 경로(/listings/{id}/fit)는 끈 채 부르고, 소유자 확인을 마친
    건물주의 공실 진단만 켠다(services/direct_briefs.demand 머리말).
    """
    obs = observed(listing)
    return {
        "observed": obs,
        "model": {"top": model_top(listing), "caveat": MODEL_CAVEAT},
        "demand": {"window_days": DEMAND_WINDOW_DAYS, "min_n": DEMAND_MIN_N, "rows": demand(db, listing),
                   "note": f"최근 {DEMAND_WINDOW_DAYS}일 이 상권 매물에 문의한 창업자 수예요. "
                           f"{DEMAND_MIN_N}명 미만은 숫자를 보이지 않아요."},
        "preferences": {
            "preferred": [industry_label(k) for k in listing.preferred_industries or []],
            "excluded": [industry_label(k) for k in listing.excluded_industries or []],
        },
        # 2026-11-21 — 이 상권을 희망한 입점 희망서 묶음(n≥3 만 숫자). 다음 공실 대비 수요 신호다
        "briefs": _brief_demand(db, listing.district_id, include_caps),
    }


def _brief_demand(db: Session, district_id: str | None, include_caps: bool) -> dict[str, Any] | None:
    from app.services import direct_briefs   # direct_briefs → direct_listings 순환을 피한다

    return direct_briefs.demand(db, district_id, include_caps=include_caps) if district_id else None


def reasons_for_founder(listing: DirectListing, industry_key: str | None) -> list[str]:
    """창업자에게 보이는 「이 자리의 이유」 — 문장 목록. 순위·점수가 아니다."""
    reasons: list[str] = []
    f = flags(listing)
    if industry_key:
        label = industry_label(industry_key)
        if industry_key in (listing.excluded_industries or []):
            reasons.append(f"건물주가 {label} 업종은 받지 않는다고 적었어요.")
        elif industry_key in (listing.preferred_industries or []):
            reasons.append(f"건물주가 {label} 업종을 반긴다고 적었어요.")
        item = _industry(industry_key)
        model_label = item.get("model_label") if item else None
        if model_label:
            top = model_top(listing)
            rank = next((i for i, t in enumerate(top) if t.get("industry") == model_label), None)
            reasons.append(f"위치 모델 상위 3에서 {label} {rank + 1}위예요(참고)." if rank is not None
                           else f"위치 모델 상위 3에는 {label}이(가) 없어요(참고).")
    obs = observed(listing)
    if obs and obs.get("top"):
        tops = " · ".join(f"{t['industry']} {round(t['share'] * 100)}%" for t in obs["top"][:3])
        reasons.append(f"같은 용도·층에서 영업 중(관측): {tops} — 표본 {obs.get('n', 0):,}곳")
    if f["long_vacancy"]:
        reasons.append(f"{f['vacant_months']}개월째 비어 있다고 건물주가 적었어요 — 조건을 협의할 여지가 있을 수 있어요.")
    if f["upper_floor"]:
        reasons.append("상층이에요 — 1층보다 임대료 부담이 낮은 편이고, 찾아오는 업종(학원·의원·미용 등)에 맞아요.")
    if f["popup_ok"]:
        reasons.append("팝업·단기 사용이 가능해요 — 계약 전에 작게 먼저 확인할 수 있어요.")
    return reasons


def founder_sort_key(listing: DirectListing, industry_key: str | None, now: datetime | None = None) -> tuple:
    """광고(표시됨) → 건물주 선호 일치 → 제외 아님 → 실질 비용 낮은 순. 이유는 reasons_for_founder 로 보인다."""
    from app.services.direct_listings import is_ad

    preferred = bool(industry_key) and industry_key in (listing.preferred_industries or [])
    excluded = bool(industry_key) and industry_key in (listing.excluded_industries or [])
    return (0 if is_ad(listing, now) else 1, 0 if preferred else 1, 1 if excluded else 0,
            listing.monthly_rent_manwon if listing.deal_type != "popup" else 10**9)
