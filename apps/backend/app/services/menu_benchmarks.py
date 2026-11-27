"""Proposal 「메뉴 설정」 업종 기준값(2026-11-26 사용자 요청) — 공식 통계에서 **확인한 값만** 싣는다.

사용자 요청: 선택한 업종을 (개인사업, 가맹점)에 맞는 메뉴 · 판매가 · 원가 · 비중 평균값, 재료값 · 장비값 설정란,
월 영업일 · 영업 시간 · 고정비 예시. 화면(`components/MenuPlanner`)은 이 값을 출처와 함께 보이고,
창업자가 누를 때만 빈칸에 넣는다(값을 지어 넣지 않는다).

원천 둘(둘 다 저장소 Gold 를 그대로 환산한다 — 새 수치를 손으로 적지 않는다):
  · 농식품부 「2025 외식업체 경영실태 조사 통계보고서」 — `data/gold/mafra_dining_2025.json`
    (`data/pipelines/build_mafra_dining_2025.py` 가 사용자 제공 PDF 에서 뽑았다 · 회계 항등식 검산 통과)
    업종별: 대표메뉴 평균 가격 · 객단가 · 월 영업일 · 하루 영업 시간 · 식재료비 비율 · 월 매출 · 월 인건비 · 월 임차료 · 개업 투자비(주방 · 홀)
    운영형태별(외식업 전체): 개인사업(비프랜차이즈 = 독립운영) · 가맹점(프랜차이즈 = 가맹점 + 본사직영)
  · KOSIS 서비스업조사 시도/산업별 총괄(DT_3KB9001 · 서울 2024) — `data/gold/platform_posting_cost_rates.json` · 서울 참고값

⚠ 보고서의 표는 한 축씩만 나눈다 — **업종 × 운영형태 교차가 없다.** 그래서 개인사업/가맹점 차이는 외식업 전체 값으로만 보이고,
업종 안에서 나눈 값을 만들지 않는다(두 평균을 곱하거나 비율로 보정하지 않는다).
⚠ 대표메뉴의 「응답 수」는 그 메뉴를 대표메뉴로 꼽은 업체 수다 — 판매 비중이 아니다. 메뉴 원가는 판매가 × 그 업종 식재료비 비율로 본 추정이다.
"""
from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
KOSIS_GOLD = ROOT / "data" / "gold" / "platform_posting_cost_rates.json"
MAFRA_GOLD = ROOT / "data" / "gold" / "mafra_dining_2025.json"

KOSIS_ID = "kosis_service_2024_seoul"
MAFRA_ID = "mafra_dining_2025"
MENU_TOP = 6

# 세부 업종 키(data/config/industry_details.py) → 원천의 업종 행. 원천에 그 업종이 없으면 None — 비슷한 업종으로 채우지 않는다.
# 분식은 보고서의 「김밥 및 기타 간이음식점업」(KSIC 56194 — 분식이 여기에 든다), 요리 주점은 「기타 주점업」(더 넓은 업종)이다.
CATEGORIES: dict[str, dict[str, str | None]] = {
    "restaurant_korean": {"label": "한식", "kosis": "56111", "mafra": "한식"},
    "restaurant_chinese": {"label": "중식", "kosis": "56121", "mafra": "중식 음식점업"},
    "restaurant_japanese": {"label": "일식", "kosis": "56122", "mafra": "일식 음식점업"},
    "restaurant_western": {"label": "양식", "kosis": "56123", "mafra": "서양식 음식점업"},
    "restaurant_snack": {"label": "분식", "kosis": None, "mafra": "김밥 및 기타 간이음식점업"},
    "restaurant_chicken": {"label": "치킨", "kosis": "56162", "mafra": "치킨 전문점"},
    "restaurant_fastfood": {"label": "피자·패스트푸드", "kosis": "56161", "mafra": "피자·햄버거·샌드위치"},
    "restaurant_other": {"label": "기타 음식점", "kosis": None, "mafra": None},
    "cafe_coffee": {"label": "커피·음료", "kosis": "56221", "mafra": "커피 전문점"},
    "cafe_bakery": {"label": "제과·베이커리", "kosis": "56150", "mafra": "제과"},
    "bar_beer": {"label": "생맥주 전문점", "kosis": "56213", "mafra": "생맥주 전문점"},
    "bar_cooking": {"label": "요리 주점", "kosis": None, "mafra": "기타 주점업"},
}
MAFRA_NOTES = {
    "김밥 및 기타 간이음식점업": "분식은 보고서의 「김밥 및 기타 간이음식점업」 값이에요.",
    "기타 주점업": "요리 주점 단독 평균은 없어 「기타 주점업」의 참고 평균이에요.",
}
OWNERSHIP_ROWS = {"independent": ("개인사업", "비프랜차이즈", "독립운영(개인경영권)"),
                  "franchise": ("가맹점", "프랜차이즈", "프랜차이즈 가맹점 + 본사직영")}
OWNERSHIP_NOTE = ("보고서는 업종과 운영형태를 따로 나눠 공표해요 — 업종 안에서 개인사업 · 가맹점을 나눈 평균은 없어서, "
                  "아래 비교는 외식업 전체 값이에요. 가맹점이라면 가맹본부 정보공개서 · 가맹계약서의 판매가 · 공급가 · 로열티를 넣어 보세요.")
NOTE = ("업종 평균은 그 업종 사업체의 평균이라 내 가게의 값이 아니에요. 참고로만 보고, 넣을 때는 내 조건으로 고치세요. "
        "「채우기」 버튼은 비어 있는 칸만 채워요.")


def _r(x: float, nd: int = 0) -> float:
    """사사오입(28.5 → 29). 파이썬 round 는 짝수 쪽으로 붙어(28.5 → 28) 원문 평균과 화면 값이 어긋난다."""
    v = Decimal(str(x)).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
    return int(v) if nd == 0 else float(v)


@lru_cache(maxsize=1)
def _kosis() -> dict[str, Any]:
    try:
        return json.loads(KOSIS_GOLD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _mafra() -> dict[str, Any]:
    try:
        return json.loads(MAFRA_GOLD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _value(key: str, label: str, value: float, unit: str, source: str, detail: str, conversion: str = "",
           raw: float | None = None) -> dict[str, Any]:
    return dict(key=key, label=label, value=value, raw=raw, unit=unit, source=source, detail=detail, conversion=conversion)


def _mafra_values(row: str) -> list[dict[str, Any]]:
    """보고서 한 행(업종 · 운영형태 · 전체)의 평균들. 매출 · 비용은 연간 금액이라 ÷12 로 월을 낸다."""
    t = _mafra().get("tables") or {}
    if not t or row not in (t.get("open_days", {}).get("rows") or {}):
        return []

    def mean(k: str) -> float:
        return float(t[k]["rows"][row]["mean"])

    def ref(*keys: str) -> str:
        n = int(t[keys[0]]["rows"][row]["n"])
        return " · ".join(f"표 {t[k]['table']} {t[k]['page']}쪽" for k in keys) + f" · {row} · 전국 · 사례 {n:,}곳"

    days, hours, ticket = mean("open_days"), mean("open_hours"), mean("avg_ticket")
    sales, food, labor, rent, owner = mean("sales"), mean("food_cost"), mean("labor"), mean("rent"), mean("owner_pay")
    return [
        _value("open_days", "월 영업일", _r(days), "일", MAFRA_ID, ref("open_days"), "30일 기준 평균을 정수로 반올림", days),
        _value("open_hours", "하루 영업 시간", _r(hours, 1), "시간", MAFRA_ID, ref("open_hours")),
        _value("avg_ticket", "객단가(고객 1인)", _r(ticket), "원", MAFRA_ID, ref("avg_ticket"), "원 단위 반올림", ticket),
        _value("food_cost_rate", "식재료비 비율(원가율)", _r(food / sales * 100, 1), "%", MAFRA_ID, ref("food_cost", "sales"),
               "연 식재료비 ÷ 연 매출액"),
        _value("sales_month", "월 매출", _r(sales / 12), "만원", MAFRA_ID, ref("sales"), "연 매출 ÷ 12", _r(sales / 12, 1)),
        _value("labor_month", "월 인건비(고용인)", _r(labor / 12), "만원", MAFRA_ID,
               ref("labor") + " · 대표자 · 가족 몫 제외", "연 고용인 인건비 ÷ 12", _r(labor / 12, 1)),
        _value("rent_month", "월 임차료", _r(rent / 12), "만원", MAFRA_ID, ref("rent"), "연 임차료 ÷ 12", _r(rent / 12, 1)),
        _value("owner_pay_month", "월 대표자 인건비", _r(owner / 12), "만원", MAFRA_ID, ref("owner_pay") + " · 고정비 칸에는 넣지 않아요",
               "연 대표자 인건비 ÷ 12", _r(owner / 12, 1)),
        _value("invest_total", "개업 투자비", _r(mean("invest_total")), "만원", MAFRA_ID, ref("invest_total") + " · 「모름」 응답 제외"),
        _value("invest_kitchen", "개업 투자비 중 주방 관련", _r(mean("invest_kitchen")), "만원", MAFRA_ID,
               ref("invest_kitchen") + " · 「모름」 응답 제외"),
        _value("invest_hall", "개업 투자비 중 홀 관련", _r(mean("invest_hall")), "만원", MAFRA_ID,
               ref("invest_hall") + " · 「모름」 응답 제외"),
        _value("invest_interior", "개업 투자비 중 인테리어", _r(mean("invest_interior")), "만원", MAFRA_ID,
               ref("invest_interior") + " · 「모름」 응답 제외"),
    ]


def _menus(row: str) -> dict[str, Any] | None:
    m = (_mafra().get("menus") or {}).get(row)
    t = _mafra().get("tables") or {}
    if not m or not t:
        return None
    sales, food = float(t["sales"]["rows"][row]["mean"]), float(t["food_cost"]["rows"][row]["mean"])
    items = [dict(name=i["name"], n=int(i["n"]), price=int(i["price"])) for i in m["items"] if int(i["n"]) >= 2][:MENU_TOP]
    return dict(table=m["table"], page=m["page"], title=m["title"], total=m["total"], items=items,
                cost_rate=dict(value=_r(food / sales * 100, 1),
                               detail=f"표 {t['food_cost']['table']} 식재료비 ÷ 표 {t['sales']['table']} 매출액 · {row}"),
                note=("판매가는 대표메뉴 평균 가격(전국)이에요. 원가는 판매가 × 이 업종 식재료비 비율로 본 추정이고, "
                      "비중은 그 메뉴를 대표메뉴로 꼽은 응답 수의 비중이라 판매 비중이 아니에요 — 내 가게 값으로 고치세요."))


def _food_mix(row: str) -> dict[str, Any] | None:
    """표 105 품목별 식재료비 비중(%) — 큰 순. 그 업종 업체들이 식재료비를 어디에 쓰는지 보는 참고값이다(2026-11-27 「식재료비」 칸)."""
    fm = _mafra().get("food_mix") or {}
    r = (fm.get("rows") or {}).get(row)
    if not r:
        return None
    items = sorted(({"label": c, "value": float(v)} for c, v in zip(fm["columns"], r["values"])), key=lambda it: -it["value"])
    return dict(table=fm["table"], page=fm["page"], title=fm["title"], n=int(r["n"]), items=items,
                note="응답 업체가 적은 품목별 식재료비 비중의 평균이에요 — 내 메뉴의 재료 구성과 견줘 보는 참고값이에요.")


def _per_store_month(total_mn: float | None, estab: float | None) -> float | None:
    """KOSIS 연간 합계(백만원) → 점포당 월평균(만원). 백만원 × 100 = 만원."""
    if total_mn is None or not estab:
        return None
    return total_mn * 100 / estab / 12


def _kosis_values(code: str) -> list[dict[str, Any]]:
    """서울 참고값 — 키에 seoul_ 을 붙여 보고서 값(전국)과 섞지 않는다."""
    row = (_kosis().get("industries") or {}).get(code)
    if not row or not row.get("estab") or not row.get("sales_mn"):
        return []
    estab, sales = row["estab"], row["sales_mn"]
    where = f"{row.get('name', code)}(KSIC {code}) · 서울 · {row.get('period', '')} · 사업체 {int(estab):,}곳"
    out: list[dict[str, Any]] = []
    for key, label, total in (("seoul_sales_month", "서울 점포당 월매출", sales),
                              ("seoul_labor_month", "서울 점포당 월 인건비", row.get("labor_mn")),
                              ("seoul_rent_month", "서울 점포당 월 임차료", row.get("rent_mn"))):
        raw = _per_store_month(total, estab)
        if raw is not None:
            out.append(_value(key, label, _r(raw), "만원", KOSIS_ID,
                              where + (" · 급여를 받는 종사자 몫 — 대표자 본인 몫 없음" if key == "seoul_labor_month" else ""),
                              "연간 합계(백만원) ÷ 사업체 수 ÷ 12개월", _r(raw, 1)))
    if row.get("opex_rate") is not None:
        out.append(_value("seoul_profit_rate", "서울 영업이익률", _r((1 - row["opex_rate"]) * 100, 1), "%", KOSIS_ID, where,
                          "1 − 영업비용 ÷ 매출액"))
    return out


def categories() -> list[dict[str, Any]]:
    out = []
    for key, spec in CATEGORIES.items():
        row = spec["mafra"]
        values = (_mafra_values(row) if row else []) + (_kosis_values(spec["kosis"]) if spec["kosis"] else [])
        notes = [MAFRA_NOTES[row]] if row in MAFRA_NOTES else []
        missing = []
        if not values:
            missing.append(dict(key="all", label="업종 평균",
                                reason="이 업종에 대응하는 공식 통계 행이 없어 평균을 보일 수 없어요. 직접 넣어 주세요."))
        out.append(dict(key=key, label=spec["label"], values=values, menus=_menus(row) if row else None,
                        food_mix=_food_mix(row) if row else None, notes=notes, missing=missing))
    return out


def ownership() -> dict[str, Any]:
    groups = []
    for key, (label, row, detail) in OWNERSHIP_ROWS.items():
        values = _mafra_values(row)
        if values:
            n = int(_mafra()["tables"]["open_days"]["rows"][row]["n"])
            groups.append(dict(key=key, label=label, detail=f"{detail} · 보고서 「{row}」 행 · 사례 {n:,}곳", n=n, values=values,
                               food_mix=_food_mix(row)))
    return dict(available=len(groups) == 2, scope="외식업 전체(전국)", note=OWNERSHIP_NOTE, groups=groups)


def sources() -> dict[str, dict[str, Any]]:
    k = _kosis().get("source") or {}
    m = _mafra().get("source") or {}
    return {
        MAFRA_ID: dict(title=m.get("title", "2025 외식업체 경영실태 조사 통계보고서"), org=m.get("org", "농림축산식품부"),
                       url=m.get("url", ""), geography="전국", period="2025",
                       population=f"외식업체 {int(m.get('sample_n', 0)):,}곳 표본 · 업종 · 운영형태를 따로 나눈 표"),
        KOSIS_ID: dict(title=k.get("name", "통계청 서비스업조사 시도/산업별 총괄"), org="통계청(KOSIS)",
                       url=f"https://kosis.kr/statHtml/statHtml.do?orgId={k.get('org_id', '101')}&tblId={k.get('tbl_id', 'DT_3KB9001')}",
                       geography="서울", period=str(k.get("period", "2024")), population="사업체 전체(개인 · 가맹 합계)"),
    }


def payload() -> dict[str, Any]:
    return dict(categories=categories(), ownership=ownership(), sources=sources(), note=NOTE)
