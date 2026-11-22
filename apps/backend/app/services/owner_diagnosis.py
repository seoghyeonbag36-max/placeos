"""건물주 공실 진단 — 정보 판매(건물주) (2026-11-18).

미리보기는 누구나(소유자 본인) 보고, 상세는 「공실 진단 상세 리포트」 정액 상품의 입금 확인 뒤에 열린다
(services/direct_purchases). 숫자를 지어내지 않는다 — Page(층 이력·주변 추정 공실) · Platform(업종 신호 · 공실 예측 참고) ·
Posting(같은 임대 조건 계산 · 인하 vs 공실)의 산출물을 그대로 모으고, 제안은 규칙 문장으로만 한다.
"""
from __future__ import annotations

import collections
import math
from typing import Any

from sqlalchemy.orm import Session

from app.models.direct import DirectListing
from app.services import building_history, vacancy_forecast, vacant_inventory
from app.services.direct_listings import flags
from app.services.direct_matching import industry_label, observed, signals_for_listing
from app.services.direct_pricing import terms, vacancy_tradeoff

NEARBY_M = 150
LOCKED_NOTE = "상세 리포트는 「공실 진단 상세 리포트」를 신청하고 입금이 확인되면 열려요."
FORECAST_CAVEAT = ("LSTM 공실 예측은 사전등록 규칙에 따라 다음 분기 자료가 나오기 전까지 참고로만 보여요 "
                   "(scripts/kpi_baseline.py · 확정 대기).")


def _forecast(listing: DirectListing) -> dict[str, Any] | None:
    if not listing.district_id:
        return None
    fc = vacancy_forecast.get_forecast(listing.district_id)
    if not fc:
        return None
    keep = {k: fc.get(k) for k in ("forecast_quarter", "direction", "delta", "forecast_vac_proxy") if k in fc}
    return {**keep, "caveat": FORECAST_CAVEAT}


def _nearby_vacant(listing: DirectListing) -> dict[str, Any] | None:
    """주변(150m) 추정 공실 유닛 수와 그 직전 업종 — 대장·인허가로 추정한 빈 자리다(매물이 아니다)."""
    if listing.lat is None or listing.lng is None or not listing.district_id:
        return None
    lat0, lng0 = listing.lat, listing.lng
    k_lat = 111_000.0
    k_lng = 111_000.0 * math.cos(math.radians(lat0))
    near = [u for u in vacant_inventory.units(listing.district_id)
            if u.get("lat") is not None and u.get("lng") is not None
            and math.hypot((u["lat"] - lat0) * k_lat, (u["lng"] - lng0) * k_lng) <= NEARBY_M]
    was = collections.Counter((u.get("was") or "미상").strip() for u in near)
    return {"radius_m": NEARBY_M, "n": len(near), "previous_uses": [{"label": k, "n": v} for k, v in was.most_common(5)],
            "note": "건축물대장·인허가로 추정한 빈 자리예요. 건물주 확인 매물이 아니에요."}


def _history(listing: DirectListing) -> dict[str, Any] | None:
    if not listing.building_id:
        return None
    try:
        events, source, year = building_history.get_history(listing.building_id)
    except Exception:            # 이력 산출물이 없는 건물 — 없는 것을 지어내지 않는다
        return None
    return {"events": list(events)[:12], "source": source, "since_year": year}


def _suggestions(listing: DirectListing, f: dict[str, Any], obs: dict | None) -> list[str]:
    out: list[str] = []
    if f["long_vacancy"]:
        out.append(f"{f['vacant_months']}개월째 비어 있어요 — 아래 「인하 vs 공실」 계산으로 조건을 다시 보세요.")
        if not listing.rent_free_months:
            out.append("렌트프리를 주면 명목 월세는 그대로 두고 실질 월세를 낮출 수 있어요(실질 월세는 위 계산에 나와요).")
    if f["upper_floor"] and obs and obs.get("top"):
        out.append("상층이에요 — 같은 용도·층에서 실제 영업 중인 업종(관측): "
                   + " · ".join(t["industry"] for t in obs["top"][:3]) + ".")
    if not f["popup_ok"]:
        out.append("팝업·단기 사용을 열어 두면 빈 기간에도 수입이 생길 수 있어요(거래 형태를 「임대 · 팝업 가능」으로).")
    excluded = set(listing.excluded_industries or [])
    if excluded:
        out.append("받지 않는 업종: " + " · ".join(industry_label(k) for k in excluded)
                   + " — 문의가 적다면 이 조건부터 다시 보세요.")
    return out


def _verified(db: Session, listing: DirectListing) -> bool:
    """예산 상한 중앙값을 보일 수 있는 건물주인가 — 이 매물이 소유자 확인을 마치고 게시 중일 때만(희망서 게이트 L12 와 같은 문턱).
    작성 중·확인 대기 매물로 아무 상권이나 적어 남의 상한을 캐내지 못하게 한다."""
    from app.services.direct_listings import is_public

    return is_public(db, listing)


def _brief_demand(db: Session, listing: DirectListing) -> dict[str, Any] | None:
    from app.services import direct_briefs   # direct_briefs → direct_listings 순환을 피한다

    if not listing.district_id:
        return None
    return direct_briefs.demand(db, listing.district_id, include_caps=_verified(db, listing))


def diagnose(db: Session, listing: DirectListing, *, cut_pct: float = 10, vacancy_months: float = 3,
             full: bool = False) -> dict[str, Any]:
    f = flags(listing)
    obs = observed(listing)
    preview = {
        "flags": f,
        "terms": terms(db, listing),
        "tradeoff": vacancy_tradeoff(listing.monthly_rent_manwon or 0, cut_pct, vacancy_months),
        "observed_top": (obs or {}).get("top", [])[:3],
        "observed_note": (obs or {}).get("note"),
        "forecast": _forecast(listing),
        "suggestions": _suggestions(listing, f, obs),
        # 2026-11-21 — 이 상권을 희망한 입점 희망서 묶음(n≥3 만 숫자 · 다음 공실 대비 수요 신호). 무료 미리보기에 싣는다 —
        # 같은 값이 공개 GET /direct/demand 에도 있지만, 건물주 화면은 이 계정 경로(계측 없음)로 받아 KPI③ 에 섞이지 않게 한다
        "brief_demand": _brief_demand(db, listing),
    }
    detail = None
    if full:
        detail = {
            "signals": signals_for_listing(db, listing, include_caps=_verified(db, listing)),
            "nearby_vacant": _nearby_vacant(listing),
            "history": _history(listing),
        }
    return {"listing_id": listing.id, "full": full, "preview": preview, "detail": detail,
            "locked_note": None if full else LOCKED_NOTE}
