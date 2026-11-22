"""양쪽이 함께 보는 임대 조건 계산 — Posting 의 직거래 쪽 단일 출처 (2026-11-18).

창업자의 매물 상세와 건물주의 공실 진단이 **같은 함수**를 부른다 — 한쪽만 고치면 두 사람이 다른 숫자를 보고
협상하게 된다. 여기서는 순수 산술만 한다: 기준선 없는 임계값이나 「적정 임대료」 판정을 만들지 않는다(KPI 규칙 ①).
"""
from __future__ import annotations

import statistics
from typing import Any

from sqlalchemy.orm import Session

from app.models.direct import DirectListing
from app.services import posting_inputs

DEFAULT_TERM_MONTHS = 24          # 기간을 안 적은 매물의 계산 기간 — 응답에 term_assumed 로 밝힌다
PYEONG_M2 = 3.3058
PEER_MIN_N = 3                    # 같은 상권·같은 층 띠의 확인 매물이 이보다 적으면 중앙값을 말하지 않는다


def floor_band(floor: int) -> str:
    if floor < 0:
        return "basement"
    return "first" if floor == 1 else "upper"


def rent_per_m2_thousand(listing: DirectListing) -> float | None:
    """㎡당 월세(천원) — R-ONE 단위와 같다. 만원 → 천원은 ×10."""
    if not listing.area_m2 or listing.area_m2 <= 0 or not listing.monthly_rent_manwon:
        return None
    return round(listing.monthly_rent_manwon * 10 / listing.area_m2, 2)


def _rone(listing: DirectListing, per_m2: float | None) -> dict[str, Any]:
    inputs = posting_inputs.for_district(listing.district_id) if listing.district_id else None
    rate = (inputs or {}).get("rent_per_m2_krw_thousand")
    base: dict[str, Any] = {"rent_per_m2_thousand": rate, "quarter": posting_inputs.quarter(), "ratio": None}
    if not rate:
        base["note"] = "이 상권은 R-ONE 임대 표본이 없어 견주지 않아요."
    elif floor_band(listing.floor) != "first":
        base["note"] = "R-ONE 소규모상가 임대료는 1층 기준이라 상층·지하와 바로 견주지 않아요."
    elif per_m2 is None:
        base["note"] = "월세가 없어 견주지 않아요."
    else:
        base["ratio"] = round(per_m2 / rate, 2)
        base["note"] = "R-ONE 소규모상가 1층 평균 대비예요(같은 상권 · 분기 통계). 개별 자리의 시세가 아니에요."
    return base


def _peers(db: Session, listing: DirectListing) -> dict[str, Any]:
    from app.services import direct_listings     # 순환 임포트를 피한다

    band = floor_band(listing.floor)
    values = [v for r in direct_listings.public_listings(db, listing.district_id) if r.id != listing.id
              and floor_band(r.floor) == band and r.deal_type != "popup"
              and (v := rent_per_m2_thousand(r)) is not None] if listing.district_id else []
    if len(values) < PEER_MIN_N:
        return {"n": len(values), "median_rent_per_m2_thousand": None, "band": band,
                "note": f"같은 상권·같은 층 띠의 건물주 확인 매물이 {PEER_MIN_N}곳 미만이라 비교값을 내지 않아요."}
    return {"n": len(values), "median_rent_per_m2_thousand": round(statistics.median(values), 2), "band": band,
            "note": "같은 상권·같은 층 띠의 건물주 확인 매물 ㎡당 월세 중앙값이에요(호가)."}


def terms(db: Session, listing: DirectListing, term_months: int | None = None) -> dict[str, Any]:
    """임대 조건 계산 — 창업자·건물주가 같은 값을 본다."""
    term = term_months or listing.min_term_months or DEFAULT_TERM_MONTHS
    term = max(1, min(int(term), 120))
    rent = listing.monthly_rent_manwon or 0
    free = max(0, min(listing.rent_free_months or 0, term))
    effective = round(rent * (term - free) / term, 1)
    maint = listing.maintenance_manwon or 0
    per_m2 = rent_per_m2_thousand(listing)
    out: dict[str, Any] = {
        "listing_id": listing.id,
        "deposit_manwon": listing.deposit_manwon,
        "monthly_rent_manwon": rent,
        "maintenance_manwon": maint,
        "rent_free_months": free,
        "term_months": term,
        "term_assumed": not (term_months or listing.min_term_months),
        "effective_monthly_rent_manwon": effective,
        "monthly_occupancy_manwon": round(effective + maint, 1),
        "first_year_cash_manwon": listing.deposit_manwon + rent * max(0, 12 - free) + maint * 12,
        "rent_per_m2_thousand": per_m2,
        "rent_per_pyeong_manwon": round(rent / (listing.area_m2 / PYEONG_M2), 1) if listing.area_m2 and rent else None,
        "rone": _rone(listing, per_m2),
        "peers": _peers(db, listing),
        "popup": None,
        "notes": [
            "실질 월세 = 월세 × (계약 기간 − 렌트프리) ÷ 계약 기간. 렌트프리는 명목 월세를 그대로 두고 첫 달들을 비우는 방식이에요.",
            "첫해 현금 = 보증금 + 월세 × (12 − 렌트프리) + 관리비 × 12. 권리금·인테리어·세금은 넣지 않았어요.",
        ],
    }
    if listing.deal_type in ("lease_popup", "popup") and listing.popup_daily_manwon:
        out["popup"] = {
            "daily_manwon": listing.popup_daily_manwon,
            "min_days": listing.popup_min_days,
            "max_days": listing.popup_max_days,
            "min_total_manwon": listing.popup_daily_manwon * listing.popup_min_days if listing.popup_min_days else None,
        }
    if out["term_assumed"]:
        out["notes"].append(f"건물주가 계약 기간을 적지 않아 {DEFAULT_TERM_MONTHS}개월로 계산했어요.")
    return out


def vacancy_tradeoff(monthly_rent_manwon: int, cut_pct: float, vacancy_months: float,
                     fixed_monthly_manwon: float = 0) -> dict[str, Any]:
    """건물주용 「월세 인하 vs 공실」 손익 — 12개월 인하로 줄어드는 임대 수입 vs 비어 있는 동안 잃는 수입."""
    cut_pct = max(0.0, min(float(cut_pct), 90.0))
    vacancy_months = max(0.0, min(float(vacancy_months), 36.0))
    loss_cut = round(monthly_rent_manwon * cut_pct / 100 * 12, 1)
    loss_vacant = round((monthly_rent_manwon + fixed_monthly_manwon) * vacancy_months, 1)
    cheaper = "same" if loss_cut == loss_vacant else ("cut" if loss_cut < loss_vacant else "vacant")
    return {
        "monthly_rent_manwon": monthly_rent_manwon, "cut_pct": cut_pct, "vacancy_months": vacancy_months,
        "loss_if_cut_12m_manwon": loss_cut, "loss_if_vacant_manwon": loss_vacant, "cheaper": cheaper,
        "note": "임대 수입만 비교했어요. 세금·대출·건물 가치 영향과 새 임차인을 구하는 비용은 넣지 않았어요.",
    }
