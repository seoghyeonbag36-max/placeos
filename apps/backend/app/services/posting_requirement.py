"""Posting 요구치 — 「이 층 조건이면 하루 몇 개를 팔아야 하나」 (2026-11-19 · 결정 P2).

예측(「N개월이면 본전」)을 **요구치**로 뒤집는다. 월세와 비용률이 정해지면 본전에 필요한 월매출은 산수다:

    필요 월매출 = 월세 ÷ (1 − 임차 외 비용률)        # 임차 외 비용률 = 매출 대비 원가·인건비·기타
    하루 판매량 = 필요 월매출 ÷ (객단가 × 영업일)

예측 모델을 새로 만들지 않는다. 비교 기준(같은 상권·같은 업종 점포당 추정매출)은 공식 통계라 「실력」을 주장할 일이 없고,
그 기준이 없으면 `benchmark` 는 null 이다 — 지어내지 않는다.

## 근거 층위 (`evidence`)
숫자마다 어디서 왔는지를 단다: 사용자 입력 · 통계 · 추정 · 계산. 월세는 사용자가 들은 금액이 R-ONE 추정을 늘 이긴다(P3).

## 한계 (낮추어 말해야 하는 것)
- 임차 외 비용률은 KOSIS 서울 업종군 평균이다. 사용자가 원가율을 넣으면 `원가율 + KOSIS 인건비율`로 바꾸는데,
  기타경비(관리비·감가상각 등)는 빠지므로 **필요 매출의 하한**이다(`nonrent_floor: true`).
- 점포당 추정매출은 상권 평균이라 면적·층·가맹여부를 구분하지 않는다(`platform_posting_revenue.json` caveat).
"""
from __future__ import annotations

from app.services import districts as svc
from app.services import posting_revenue as pr

TIERS = pr.TIERS
DEFAULT_OPEN_DAYS = 26


def _benchmark(district_id: str | None, tier: str, required_mn: float) -> dict | None:
    doc = pr._read(pr._REV)
    row = ((doc.get("districts") or {}).get(district_id or "") or {}).get(tier)
    scope = "district"
    if not row or not row.get("median"):
        row, scope = (doc.get("seoul") or {}).get(tier), "seoul"
    if not row or not row.get("median"):
        return None
    med = float(row["median"])
    p25, p75 = row.get("p25"), row.get("p75")
    band = None
    if p25 is not None and p75 is not None:
        band = ("하위 25% 미만" if required_mn < p25 else "25~50%" if required_mn < med
                else "50~75%" if required_mn <= p75 else "상위 25% 초과")
    return {"per_store_sales_mn": round(med, 1), "p25_mn": p25, "p75_mn": p75, "scope": scope,
            "share_pct": round(required_mn / med * 100, 1), "band": band,
            "n_obs": row.get("n_obs"), "quarter": doc.get("quarter"),
            "source": "서울시 상권분석서비스 추정매출"}


def compute(district_id: str, tier: str, price_won: int, *, rent_mn: float | None = None,
            unit_id: str | None = None, cost_rate: float | None = None,
            open_days: int = DEFAULT_OPEN_DAYS) -> dict:
    """요구치를 계산한다. 계산할 수 없으면 `available: false` 와 사유 — 숫자를 지어내지 않는다."""
    if tier not in TIERS:
        raise ValueError(f"unknown tier: {tier}")
    evidence: dict[str, str] = {}

    rent_basis = None
    if rent_mn is not None:
        rent_basis, evidence["rent_mn"] = "user", "사용자 입력"
    elif unit_id:
        unit = next((u for u in svc.resolved_units(district_id) if u.get("id") == unit_id), None)
        if unit and unit.get("rent"):
            rent_mn, rent_basis, evidence["rent_mn"] = float(unit["rent"]), "rone_estimate", "추정"
    if rent_mn is None:
        return {"available": False, "reason": "월세를 모른다 — 들은 금액을 넣거나 자리를 고른다.", "evidence": {}}

    rates = (pr._rates().get(tier) or {})
    base = rates.get("opex_rate_ex_rent")
    labor = rates.get("labor_rate")
    floor = False
    if cost_rate is not None:
        if labor is None:
            return {"available": False, "reason": "인건비율 통계가 없어 원가율만으로 계산하지 않는다.", "evidence": evidence}
        nonrent, floor = cost_rate + labor, True
        evidence["cost_rate"] = "사용자 입력"
        evidence["labor_rate"] = "통계"
    elif base is not None:
        nonrent = float(base)
        evidence["nonrent_rate"] = "통계"
    else:
        return {"available": False, "reason": "임차 외 비용률 통계가 없다.", "evidence": evidence}
    if nonrent >= 1:
        return {"available": False, "reason": f"임차 외 비용률 {nonrent:.0%} 이 매출을 넘어 월세를 감당할 매출이 없다.",
                "evidence": evidence}

    required = rent_mn / (1 - nonrent)
    daily = required * 10000 / (price_won * open_days)
    evidence.update({"price_won": "사용자 입력", "open_days": "사용자 입력" if open_days != DEFAULT_OPEN_DAYS else "추정",
                     "monthly_sales_mn": "계산", "daily_units": "계산"})
    bm = _benchmark(district_id, tier, required)
    if bm:
        evidence["benchmark"] = "통계"
    return {"available": True, "tier": tier, "rent_mn": round(rent_mn, 1), "rent_basis": rent_basis,
            "price_won": price_won, "nonrent_rate": round(nonrent, 4), "nonrent_floor": floor,
            "open_days": open_days, "monthly_sales_mn": round(required, 1), "daily_units": round(daily, 1),
            "benchmark": bm, "evidence": evidence}
