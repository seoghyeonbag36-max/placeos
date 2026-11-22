"""입점 희망서 × 건물주 확인 매물 맞춰 보기 — Posting 의 직거래 쪽 (2026-11-21 · docs/decision-founder-brief-2026-11-21.md).

창업자(내 희망서로 매물 보기)와 건물주(내 매물로 희망서 보기)가 **같은 함수**로 같은 조건표를 본다 — direct_pricing 과
같은 이유다(한쪽만 고치면 두 사람이 다른 표로 협상한다). 조건마다 「맞아요(ok) / 차이 있어요(gap) / 모름(unknown) /
참고(info)」만 적고 **점수·순위를 내지 않는다.** 칸 수를 세어 보이지만(counts) 정렬하지 않는다.

요구 판매량(`required_sales`)은 ③ 비공개 입력(객단가·변동비율·기타 고정비·영업일)으로만 계산하고 **창업자 본인에게만** 준다
(`include_private=True` 는 본인 경로에서만). 식은 Posting 세부 업종 계산과 같은 `industry_detail.break_even_revenue` 다.
예측이 아니라 산수다 — 같은 상권·업종 점포 매출과 견주는 것(2026-11-15 결정 P2)은 이 계산에 없다.
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from app.models.direct import DirectBrief, DirectListing
from app.services import industry_detail
from app.services.direct_briefs import FLOOR_BAND_LABELS, PRIVATE_LABELS, industry_label
from app.services.direct_listings import floor_text
from app.services.direct_pricing import floor_band

OK, GAP, UNKNOWN, INFO = "ok", "gap", "unknown", "info"
# 희망 시기와 입주 가능일의 여유 — 희망한 달 안이면 맞는다고 본다(표시 규칙이지 판정이 아니다)
START_SLACK_DAYS = 31
FIT_NOTE = "점수가 아니라 조건마다 견준 표예요. 「모름」은 건물주나 창업자가 적지 않은 칸이에요."


def _num(v: float | int | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"


def _tri(rows: list[dict], key: str, label: str, value: bool | None) -> None:
    if value is True:
        rows.append({"key": key, "label": label, "status": OK, "text": f"{label} — 건물주가 된다고 적었어요."})
    elif value is False:
        rows.append({"key": key, "label": label, "status": GAP, "text": f"{label} — 건물주가 안 된다고 적었어요."})
    else:
        rows.append({"key": key, "label": label, "status": UNKNOWN,
                     "text": f"{label} — 건물주가 적지 않았어요. 방문해서 확인해요."})


def pair(listing: DirectListing, brief: DirectBrief, terms: dict[str, Any], *, include_private: bool) -> dict[str, Any]:
    """조건표 한 장. `terms` 는 direct_pricing.terms(listing) — 양쪽이 같은 실질 월세를 쓴다."""
    rows: list[dict[str, Any]] = []

    def add(key: str, label: str, status: str, text: str) -> None:
        rows.append({"key": key, "label": label, "status": status, "text": text})

    # 업종 — 건물주가 적은 선호·제외. 들어갈 수 있는지(법)는 입점 점검(UseCheckCard)이 따로 본다
    ind = brief.industry_key
    name = industry_label(ind)
    if ind and ind in (listing.excluded_industries or []):
        add("industry", "업종", GAP, f"건물주가 {name} 업종은 받지 않는다고 적었어요.")
    elif ind and ind in (listing.preferred_industries or []):
        add("industry", "업종", OK, f"건물주가 {name} 업종을 반긴다고 적었어요.")
    else:
        add("industry", "업종", INFO, "건물주가 이 업종을 따로 적지 않았어요 — 들어갈 수 있는지는 입점 점검(대장·토지이음)으로 봐요.")

    # 상권
    if listing.district_id and listing.district_id in (brief.district_ids or []):
        add("district", "상권", OK, "희망 상권 안이에요.")
    else:
        add("district", "상권", GAP, "희망 상권 밖이에요.")

    # 층 — 1층 밖(상층·지하) 매물이 많다(2026-11-21 사용자 확인: 좋은 1층은 이미 중개사에게 가 있다고 본다)
    band = floor_band(listing.floor)
    wanted = [FLOOR_BAND_LABELS[b] for b in brief.floor_bands or [] if b in FLOOR_BAND_LABELS]
    if band in (brief.floor_bands or []):
        add("floor", "층", OK, f"{floor_text(listing.floor)} — 희망 층({' · '.join(wanted)})에 들어요.")
    else:
        add("floor", "층", GAP, f"{floor_text(listing.floor)} — 희망 층({' · '.join(wanted) or '없음'})이 아니에요.")

    # 면적
    lo, hi, area = brief.area_min_m2, brief.area_max_m2, listing.area_m2
    if lo is None or hi is None or not area:
        add("area", "면적", UNKNOWN, "면적을 견줄 값이 없어요.")
    elif lo <= area <= hi:
        add("area", "면적", OK, f"{_num(area)}㎡ — 희망 {_num(lo)}~{_num(hi)}㎡ 안이에요.")
    else:
        add("area", "면적", GAP, f"{_num(area)}㎡ — 희망 {_num(lo)}~{_num(hi)}㎡ 밖이에요.")

    # 월세 — 명목이 상한을 넘어도 렌트프리를 반영한 실질 월세가 상한 안이면 그렇게 적는다(같은 계산 · direct_pricing)
    cap = brief.rent_cap_manwon
    if listing.deal_type == "popup":
        add("rent", "월세", INFO, f"팝업·단기 전용이라 월세가 없어요 — 하루 {_num(listing.popup_daily_manwon)}만원.")
    elif not cap:
        add("rent", "월세", UNKNOWN, "월세 상한이 없어요.")
    else:
        nominal = listing.monthly_rent_manwon or 0
        effective = terms.get("effective_monthly_rent_manwon")
        if nominal <= cap:
            add("rent", "월세", OK, f"월세 {_num(nominal)}만원 — 상한 {_num(cap)}만원 안이에요.")
        elif effective is not None and effective <= cap:
            add("rent", "월세", OK, f"명목 월세 {_num(nominal)}만원은 상한 {_num(cap)}만원을 넘지만, "
                                    f"렌트프리를 반영한 실질 월세 {_num(effective)}만원은 상한 안이에요.")
        else:
            add("rent", "월세", GAP, f"월세 {_num(nominal)}만원 — 상한 {_num(cap)}만원보다 {_num(nominal - cap)}만원 많아요.")

    # 보증금
    dcap = brief.deposit_cap_manwon
    if listing.deal_type == "popup":
        pass
    elif dcap is None:
        add("deposit", "보증금", UNKNOWN, "보증금 상한이 없어요.")
    elif (listing.deposit_manwon or 0) <= dcap:
        add("deposit", "보증금", OK, f"보증금 {_num(listing.deposit_manwon)}만원 — 상한 {_num(dcap)}만원 안이에요.")
    else:
        add("deposit", "보증금", GAP, f"보증금 {_num(listing.deposit_manwon)}만원 — 상한 {_num(dcap)}만원보다 "
                                     f"{_num(listing.deposit_manwon - dcap)}만원 많아요.")

    # 시기
    start = brief.desired_start
    if start is None:
        add("timing", "시기", UNKNOWN, "희망 시기가 없어요.")
    elif listing.available_from is None:
        add("timing", "시기", UNKNOWN, "입주 가능일을 건물주가 적지 않았어요 — 문의해서 확인해요.")
    elif listing.available_from <= start + timedelta(days=START_SLACK_DAYS):
        add("timing", "시기", OK, f"{listing.available_from.isoformat()}부터 입주 가능 — 희망 {start:%Y-%m}에 맞아요.")
    else:
        add("timing", "시기", GAP, f"{listing.available_from.isoformat()}부터 입주 가능 — 희망 {start:%Y-%m}보다 늦어요.")

    # 설비 — 창업자가 필요하다고 고른 것만 본다
    if brief.needs_exhaust:
        _tri(rows, "exhaust", "배기(덕트)", listing.exhaust_ok)
    if brief.needs_water:
        _tri(rows, "water", "급수·배수", listing.water_ok)
    if brief.power_kw_min:
        if listing.power_kw is None:
            add("power", "전력", UNKNOWN, f"필요 {brief.power_kw_min}kW — 건물주가 계약 전력을 적지 않았어요.")
        elif listing.power_kw >= brief.power_kw_min:
            add("power", "전력", OK, f"계약 전력 {listing.power_kw}kW — 필요 {brief.power_kw_min}kW 이상이에요.")
        else:
            add("power", "전력", GAP, f"계약 전력 {listing.power_kw}kW — 필요 {brief.power_kw_min}kW보다 적어요(증설은 건물주와 상의).")

    # 팝업 먼저
    if brief.popup_first:
        if listing.deal_type in ("lease_popup", "popup"):
            add("popup", "팝업 먼저", OK, "팝업·단기로 먼저 써 볼 수 있어요 — 계약 전에 작게 확인해요.")
        else:
            add("popup", "팝업 먼저", GAP, "이 매물은 팝업·단기 사용을 받지 않아요.")

    counts = {s: sum(1 for r in rows if r["status"] == s) for s in (OK, GAP, UNKNOWN)}
    out: dict[str, Any] = {"listing_id": listing.id, "brief_id": brief.id, "rows": rows, "counts": counts,
                           "note": FIT_NOTE}
    if include_private:
        out["required_sales"] = required_sales(listing, brief, terms)
    return out


def required_sales(listing: DirectListing, brief: DirectBrief, terms: dict[str, Any]) -> dict[str, Any]:
    """이 조건이면 하루 몇 개를 팔아야 본전인가 — 창업자 본인 입력만 쓰는 산수(예측 아님). 본인에게만 보인다."""
    missing = [k for k in ("unit_price_won", "variable_cost_pct", "open_days") if not getattr(brief, k)]
    if brief.variable_cost_pct == 0 and "variable_cost_pct" in missing:
        missing.remove("variable_cost_pct")          # 0% 도 값이다
    if brief.other_fixed_manwon is None:
        missing.append("other_fixed_manwon")
    if listing.deal_type == "popup" and "open_days" in missing:
        missing.remove("open_days")                  # 팝업은 하루 단위로 센다
    if listing.deal_type == "popup" and "other_fixed_manwon" in missing:
        missing.remove("other_fixed_manwon")
    if missing:
        return {"status": "needs_inputs", "missing": missing,
                "labels": [PRIVATE_LABELS[m] for m in missing if m in PRIVATE_LABELS],
                "note": "희망서의 「나만 보는 계산 칸」(객단가·변동비율·기타 고정비·영업일)을 적으면 계산해요. 건물주에게는 보이지 않아요."}
    vc = float(brief.variable_cost_pct or 0) / 100
    price = int(brief.unit_price_won or 0)
    target = brief.target_daily_units
    if listing.deal_type == "popup":
        daily_cost = float(listing.popup_daily_manwon or 0)
        bev = industry_detail.break_even_revenue(daily_cost, vc)
        if bev is None or price <= 0:
            return {"status": "not_calculable", "note": "변동비율이 100% 이상이면 계산할 수 없어요."}
        units = math.ceil(bev * 10000 / price)
        formula = (f"하루 팝업 금액 {_num(daily_cost)}만원 ÷ (1 − 변동비율 {_num(brief.variable_cost_pct)}%) "
                   f"= 하루 {_num(bev)}만원 · ÷ 객단가 {price:,}원")
        out = {"status": "calculated", "basis": "popup", "daily_units": units, "monthly_revenue_manwon": None,
               "daily_revenue_manwon": bev, "formula": formula,
               "note": "팝업 하루 금액만 넣었어요(인건비·재료 준비비·이동비는 빠졌어요)."}
    else:
        occupancy = float(terms.get("monthly_occupancy_manwon") or 0)
        other = float(brief.other_fixed_manwon or 0)
        bev = industry_detail.break_even_revenue(occupancy + other, vc)
        days = int(brief.open_days or 0)
        if bev is None or price <= 0 or days <= 0:
            return {"status": "not_calculable", "note": "변동비율이 100% 이상이면 계산할 수 없어요."}
        units = math.ceil(bev * 10000 / (price * days))
        formula = (f"(실질 월세+관리비 {_num(occupancy)}만원 + 기타 고정비 {_num(other)}만원) ÷ (1 − 변동비율 "
                   f"{_num(brief.variable_cost_pct)}%) = 월 {_num(bev)}만원 · ÷ (객단가 {price:,}원 × 영업일 {days}일)")
        out = {"status": "calculated", "basis": "lease", "daily_units": units, "monthly_revenue_manwon": bev,
               "daily_revenue_manwon": round(bev / days, 2), "formula": formula,
               "note": "내가 적은 값만 쓴 산수예요(예측 아님). 세금·대출 이자·감가상각·권리금은 빠졌어요."}
    if target:
        diff = target - units
        out["target_daily_units"] = target
        out["target_text"] = (f"내 목표 하루 {target:,}개는 필요한 {units:,}개보다 {abs(diff):,}개 "
                              f"{'많아요' if diff > 0 else '적어요'}." if diff else f"내 목표 하루 {target:,}개가 필요한 수와 같아요.")
    return out
