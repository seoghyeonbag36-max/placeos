"""Proposal 「메뉴 설정」 업종 기준값(2026-11-26 사용자 요청) — 공식 통계에서 **확인한 값만** 싣는다.

사용자 요청: 선택한 업종에 맞는 메뉴 · 판매가 · 원가 · 비중 평균값(개인사업 · 가맹점), 재료값 · 장비값 설정란,
월 영업일 · 영업 시간 · 고정비 예시. 이 모듈은 그중 **출처가 있는 업종 평균**을 업종(세부 업종 키)마다 돌려준다.
화면(`components/MenuPlanner`)은 이 값을 참고로 보이고, 창업자가 누를 때만 빈칸에 넣는다(값을 지어 넣지 않는다).

지금 연결한 원천 둘 — 저장소에 이미 있는 것만 쓴다(새 수치를 손으로 적지 않는다):
  · KOSIS 통계청 서비스업조사 시도/산업별 총괄(DT_3KB9001 · 서울 2024) — `data/gold/platform_posting_cost_rates.json`
    점포당 월매출 · 월 인건비 · 월 임차료와 매출 대비 비율. 개인사업 · 가맹점을 합친 **사업체 전체** 평균이다.
  · 농식품부 「2025 외식업체 경영실태 조사 통계보고서」 — `services/industry_benchmarks.ROWS`(표 25 · 29 · 67)
    월 영업일 · 객단가. 전국 · **운영형태 전체** 평균이다.

⚠ 개인사업 · 가맹점을 나눈 평균은 아직 없다 — 둘을 같은 값으로 보이면 구분이 있는 것처럼 읽힌다. 그래서
`ownership_split.available = False` 와 이유를 싣고, 화면은 「전체 평균」이라고 적는다.
TODO(실제 연동 지점 · 사용자 결정 대기 2026-11-26 — 원문 내려받기가 자동 권한 검사에서 막혔다):
  · 개인사업/가맹점 구분 — 통계청 「프랜차이즈(가맹점) 조사」(가맹점 쪽) − 서비스업조사(전체) 또는
    농식품부 경영실태 조사의 운영형태(가맹 · 비가맹)별 표
  · 하루 영업 시간 · 식재료비 비중(원가율) — 농식품부 경영실태 조사의 해당 표
  · 메뉴별 평균 판매가 — 한국소비자원 참가격 외식비(서울 8개 품목)
  · 장비값 · 인테리어 — 공정위 가맹사업 정보공개서 창업비용(가맹점 쪽)
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services import industry_benchmarks

ROOT = Path(__file__).resolve().parents[4]
KOSIS_GOLD = ROOT / "data" / "gold" / "platform_posting_cost_rates.json"

KOSIS_ID = "kosis_service_2024_seoul"
MAFRA_ID = "mafra_dining_2025"

# 세부 업종 키(data/config/industry_details.py) → 원천의 업종. 원천에 그 업종 행이 없으면 None — 비슷한 업종으로 채우지 않는다
# (요리 주점만 원천 모듈이 「기타 주점업 참고값」이라고 밝혀 둔 대로 따른다).
CATEGORIES: dict[str, dict[str, str | None]] = {
    "restaurant_korean": {"label": "한식", "kosis": "56111", "mafra": "restaurant_korean"},
    "restaurant_chinese": {"label": "중식", "kosis": "56121", "mafra": None},
    "restaurant_japanese": {"label": "일식", "kosis": "56122", "mafra": None},
    "restaurant_western": {"label": "양식", "kosis": "56123", "mafra": None},
    "restaurant_snack": {"label": "분식", "kosis": None, "mafra": None},
    "restaurant_chicken": {"label": "치킨", "kosis": "56162", "mafra": None},
    "restaurant_fastfood": {"label": "피자·패스트푸드", "kosis": "56161", "mafra": None},
    "restaurant_other": {"label": "기타 음식점", "kosis": None, "mafra": None},
    "cafe_coffee": {"label": "커피·음료", "kosis": "56221", "mafra": None},
    "cafe_bakery": {"label": "제과·베이커리", "kosis": "56150", "mafra": None},
    "bar_beer": {"label": "생맥주 전문점", "kosis": "56213", "mafra": "bar_beer"},
    "bar_cooking": {"label": "요리 주점", "kosis": None, "mafra": "bar_cooking"},
}

OWNERSHIP_NOTE = ("개인사업 · 가맹점을 나눈 공식 평균은 아직 연결하지 않았어요. 아래 값은 둘을 합친 전체 평균이라 "
                  "어느 쪽을 골라도 같아요 — 가맹점이라면 가맹본부 정보공개서의 값(판매가 · 공급가 · 로열티)을 넣어 보세요.")
MISSING = {
    "menus": ("메뉴별 판매가 · 원가 · 판매 비중", "메뉴별 평균을 확인한 공식 자료를 아직 연결하지 않았어요. 내 메뉴로 직접 넣어 주세요."),
    "food_cost_rate": ("재료비 비율(원가율)", "KOSIS 서비스업조사는 음식점업의 매출원가(재료비)를 따로 공표하지 않아요 — 기타경비에 섞여 있어 원가율로 쓸 수 없어요."),
    "open_hours": ("하루 영업 시간", "영업 시간 평균을 확인한 공식 자료를 아직 연결하지 않았어요."),
    "equipment": ("장비값", "장비 · 설비 비용 평균을 확인한 공식 자료를 아직 연결하지 않았어요."),
}
NOTE = ("업종 평균은 그 업종 사업체 전체의 평균이라 내 가게의 값이 아니에요. 참고로만 보고, 넣을 때는 내 조건으로 고치세요. "
        "「평균으로 빈칸 채우기」는 비어 있는 칸만 채워요.")


@lru_cache(maxsize=1)
def _kosis() -> dict[str, Any]:
    try:
        return json.loads(KOSIS_GOLD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _per_store_month(total_mn: float | None, estab: float | None) -> float | None:
    """KOSIS 연간 합계(백만원) → 점포당 월평균(만원). 백만원 × 100 = 만원."""
    if total_mn is None or not estab:
        return None
    return total_mn * 100 / estab / 12


def _kosis_values(code: str) -> list[dict[str, Any]]:
    row = (_kosis().get("industries") or {}).get(code)
    if not row or not row.get("estab") or not row.get("sales_mn"):
        return []
    estab, sales = row["estab"], row["sales_mn"]
    where = f"{row.get('name', code)}(KSIC {code}) · 서울 · {row.get('period', '')} · 사업체 {int(estab):,}곳"
    out: list[dict[str, Any]] = []
    for key, label, total in (("sales", "점포당 월매출", sales), ("labor", "점포당 월 인건비", row.get("labor_mn")),
                              ("rent", "점포당 월 임차료", row.get("rent_mn"))):
        raw = _per_store_month(total, estab)
        if raw is not None:
            out.append(dict(key=key, label=label, value=round(raw), raw=round(raw, 1), unit="만원", source=KOSIS_ID,
                            detail=where + (" · 급여를 받는 종사자 몫 — 대표자 본인 몫은 들어 있지 않아요" if key == "labor" else ""),
                            conversion="연간 합계(백만원) ÷ 사업체 수 ÷ 12개월"))
    for key, label, total in (("labor_rate", "매출 대비 인건비", row.get("labor_mn")),
                              ("rent_rate", "매출 대비 임차료", row.get("rent_mn"))):
        if total is not None:
            out.append(dict(key=key, label=label, value=round(total / sales * 100, 1), raw=None, unit="%", source=KOSIS_ID,
                            detail=where, conversion="연간 합계 ÷ 연간 매출액"))
    if row.get("opex_rate") is not None:
        out.append(dict(key="profit_rate", label="영업이익률", value=round((1 - row["opex_rate"]) * 100, 1), raw=None, unit="%",
                        source=KOSIS_ID, detail=where, conversion="1 − 영업비용 ÷ 매출액"))
    return out


def _mafra_values(key: str) -> tuple[list[dict[str, Any]], str | None]:
    row = industry_benchmarks.ROWS.get(key)
    if not row:
        return [], None
    category, sample_n, _seats, days, price_won, match = row
    where = f"{category} · 전국 · 운영형태 전체 · 사례 {sample_n:,}곳"
    values = [
        dict(key="open_days", label="월 영업일", value=round(days), raw=days, unit="일", source=MAFRA_ID,
             detail=f"표 25 · 49쪽 · {where}", conversion="30일 기준 월 영업일 평균을 정수로 반올림"),
        dict(key="avg_ticket", label="객단가(고객 1인)", value=round(price_won), raw=price_won, unit="원", source=MAFRA_ID,
             detail=f"표 67 · 133쪽 · {where}", conversion="원 단위 반올림"),
    ]
    note = ("요리 주점 단독 평균은 없어 기타 주점업의 참고 평균이에요." if match == "broader_category" else None)
    return values, note


def categories() -> list[dict[str, Any]]:
    out = []
    for key, spec in CATEGORIES.items():
        values: list[dict[str, Any]] = []
        notes: list[str] = []
        if spec["mafra"]:
            mafra, note = _mafra_values(spec["mafra"])
            values += mafra
            if note:
                notes.append(note)
        if spec["kosis"]:
            values += _kosis_values(spec["kosis"])
        have = {v["key"] for v in values}
        missing = [dict(key=k, label=label, reason=reason) for k, (label, reason) in MISSING.items()]
        if "open_days" not in have:
            missing.append(dict(key="open_days", label="월 영업일", reason="이 업종의 월 영업일 평균을 확인한 공식 자료를 아직 연결하지 않았어요."))
        if not values:
            missing.append(dict(key="all", label="업종 평균", reason="이 업종에 대응하는 공식 통계 행이 없어 평균을 보일 수 없어요. 직접 넣어 주세요."))
        out.append(dict(key=key, label=spec["label"], values=values, missing=missing, notes=notes))
    return out


def sources() -> dict[str, dict[str, Any]]:
    k = _kosis().get("source") or {}
    return {
        KOSIS_ID: dict(title=k.get("name", "통계청 서비스업조사 시도/산업별 총괄"), org="통계청(KOSIS)",
                       url=f"https://kosis.kr/statHtml/statHtml.do?orgId={k.get('org_id', '101')}&tblId={k.get('tbl_id', 'DT_3KB9001')}",
                       geography="서울", period=str(k.get("period", "2024")), population="사업체 전체(개인 · 가맹 합계)"),
        MAFRA_ID: dict(title=industry_benchmarks.SOURCE_TITLE, org="농림축산식품부", url=industry_benchmarks.SOURCE_URL,
                       geography="전국", period="2025", population="운영형태 전체(가맹 · 비가맹 합계)"),
    }


def payload() -> dict[str, Any]:
    return dict(categories=categories(), sources=sources(),
                ownership_split=dict(available=False, reason=OWNERSHIP_NOTE), note=NOTE)
