"""세부 업종·경쟁점·사용자 입력 손익 계약. 임의 운영 가정은 채우지 않는다."""
from __future__ import annotations

import importlib.util
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.industry_benchmarks import benchmark

ROOT = Path(__file__).resolve().parents[4]
COMPETITION = ROOT / "data/gold/industry_detail/competition.json"


@lru_cache(maxsize=1)
def catalog() -> list[dict]:
    spec = importlib.util.spec_from_file_location("placeos_industry_details", ROOT / "data/config/industry_details.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("세부 업종 계약을 찾을 수 없습니다")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DETAILS


def get(key: str) -> dict | None:
    return next((i for i in catalog() if i["key"] == key), None)


def fields(family: str) -> list[dict]:
    """입력 단위·범위를 API/UI가 공유한다. 숫자 기본값은 없다."""
    spec = {
        "seats": [("capacity", "좌석 수", "석", 1, 100000), ("cycles", "하루 좌석 회전 수", "회/일", 0, 100),
                  ("utilization", "좌석 이용률", "비율(0~1)", 0, 1), ("days", "월 영업일", "일", 1, 31), ("price", "고객 1인당 객단가", "만원", 0, 100000)],
        "appointments": [("capacity", "동시 서비스 가능 수(인력 포함)", "자리", 1, 100000), ("cycles", "자리당 하루 예약 시간대 수", "회/일", 0, 100),
                         ("utilization", "예약·이용률", "비율(0~1)", 0, 1), ("days", "월 영업일", "일", 1, 31), ("price", "시간대·시술 1회 가격", "만원", 0, 100000)],
        "retail": [("transactions", "하루 구매 건수", "건/일", 0, 1000000), ("days", "월 영업일", "일", 1, 31),
                   ("price", "할인 반영 구매 객단가", "만원", 0, 100000), ("return_rate", "반품·환불 금액 비율", "비율(0~1)", 0, 1)],
        "tuition": [("capacity", "시간표·강사 기준 월 수강 가능 인원", "명", 1, 100000), ("utilization", "충원율", "비율(0~1)", 0, 1),
                    ("price", "환불 차감 후 1인당 월 귀속 수강료", "만원/월", 0, 100000)],
        "membership": [("capacity", "월 유효 회원·입주 가능 수", "명/실", 1, 100000), ("utilization", "가입·입주율", "비율(0~1)", 0, 1),
                       ("price", "환불 차감 후 1인·실당 월 귀속 이용료", "만원/월", 0, 100000)],
        "rooms": [("capacity", "판매 가능 객실·숙박 단위 수", "실", 1, 100000), ("utilization", "객실 점유율", "비율(0~1)", 0, 1),
                  ("days", "월 판매 가능일", "일", 1, 31), ("price", "객실 1박 판매단가", "만원", 0, 100000)],
        "tickets": [("capacity", "회차당 판매 가능 좌석", "석", 1, 100000), ("cycles", "월 공연 회차", "회/월", 0, 10000),
                   ("utilization", "유료 객석 점유율", "비율(0~1)", 0, 1), ("price", "할인·환불 반영 티켓 단가", "만원", 0, 100000)],
        "rental": [("days", "월 대관 가능일", "일", 1, 31), ("utilization", "대관 가동률", "비율(0~1)", 0, 1),
                   ("price", "하루 대관료", "만원", 0, 100000)],
        "commission": [("sales", "월 작품 거래액", "만원", 0, 1000000000), ("commission_rate", "갤러리 판매 수수료율", "비율(0~1)", 0, 1)],
    }[family]
    common = [("variable_cost_rate", "매출 대비 변동비(원가·결제/예약 수수료 포함)", "비율(0~1)", 0, 1),
              ("rent", "월 임대료·관리비", "만원/월", 0, 1000000000),
              ("fixed_cost", "월 기타 고정비(대표자 인건비 포함·임대료 제외)", "만원/월", 0, 1000000000),
              ("investment", "초기 투자비(권리금 포함·회수 가능한 보증금 제외)", "만원", 0, 1000000000)]
    return [dict(key=k, label=l, unit=u, min=lo, max=hi) for k, l, u, lo, hi in spec + common]


def options() -> list[dict]:
    return [{**{k: i[k] for k in ("key", "parent", "label", "family", "evidence_needed")},
             "fields": fields(i["family"]),
             "benchmark": benchmark(i["key"], fields(i["family"])),
             "recommendation_available": False,
             "recommendation_reason": "세부 업종 추천 모델은 검증·공개 전입니다"} for i in catalog()]


@lru_cache(maxsize=1)
def _competition() -> dict:
    if not COMPETITION.exists():
        return {}
    return json.loads(COMPETITION.read_text(encoding="utf-8"))


def competition(district_id: str, detail_key: str) -> dict:
    item = get(detail_key)
    if item is None:
        raise ValueError("알 수 없는 세부 업종")
    doc = _competition()
    row = doc.get("districts", {}).get(district_id)
    reason = ("이 상권의 경쟁점 집계가 없습니다" if not row else
              "이 업종을 식별할 원천 점포 자료가 없습니다" if not item["source_names"] else
              "유효한 점포 집계가 없습니다" if row.get("counts", {}).get(detail_key) is None else None)
    return {"district_id": district_id, "detail_key": detail_key,
            "count": row.get("counts", {}).get(detail_key) if row and not reason else None,
            "unavailable_reason": reason, "coverage": {k: v for k, v in row.items() if k != "counts"} if row else None,
            "note": doc.get("note"), "source_url": doc.get("source_url"),
            "recommendation_available": False, "fit": None, "fit_rank": None}


def calculate(detail_key: str, inputs: dict[str, Any]) -> dict:
    item = get(detail_key)
    if item is None:
        raise ValueError("알 수 없는 세부 업종")
    spec = fields(item["family"])
    required = {f["key"] for f in spec}
    if set(inputs) - required:
        raise ValueError("이 업종에서 사용하지 않는 입력: " + ", ".join(sorted(set(inputs) - required)))
    values: dict[str, float] = {}
    for f in spec:
        value = inputs.get(f["key"])
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not f["min"] <= value <= f["max"]:
            raise ValueError(f"{f['label']}: {f['min']}~{f['max']} 범위의 유한한 숫자가 필요합니다")
        if f["key"] in ("capacity", "days") and value != int(value):
            raise ValueError(f"{f['label']}: 정수가 필요합니다")
        values[f["key"]] = float(value)
    missing = [f for f in spec if f["key"] not in values]
    out = {"detail_key": detail_key, "label": item["label"], "status": "needs_inputs" if missing else "calculated",
           "required_inputs": missing, "input_fields": spec, "assumptions": values,
           "provenance": {k: "user_input" for k in values},
           "source": "user_input_scenario", "monthly_revenue": None, "monthly_cost": None,
           "monthly_surplus": None, "break_even_revenue": None, "payback_months": None,
           "note": "사용자 입력에 따른 월 운영 시나리오입니다. 예측·실측 매출이 아니며 세금·금융비용·감가상각을 제외합니다. 선납금은 해당 월 귀속분만 입력하세요."}
    if missing:
        return out
    v, family = values, item["family"]
    if family in ("seats", "appointments"):
        revenue = v["capacity"] * v["cycles"] * v["utilization"] * v["days"] * v["price"]
        formula = "수용량 × 하루 회전/예약 수 × 이용률 × 영업일 × 단가"
    elif family == "retail":
        revenue = v["transactions"] * v["days"] * v["price"] * (1 - v["return_rate"])
        formula = "하루 구매 건수 × 영업일 × 객단가 × (1 − 반품률)"
    elif family in ("tuition", "membership"):
        revenue = v["capacity"] * v["utilization"] * v["price"]
        formula = "월 수용 인원/실 × 충원율 × 월 귀속 이용료"
    elif family == "rooms":
        revenue = v["capacity"] * v["utilization"] * v["days"] * v["price"]
        formula = "객실 수 × 점유율 × 판매 가능일 × 1박 단가"
    elif family == "tickets":
        revenue = v["capacity"] * v["cycles"] * v["utilization"] * v["price"]
        formula = "좌석 수 × 월 회차 × 유료 점유율 × 티켓 단가"
    elif family == "rental":
        revenue = v["days"] * v["utilization"] * v["price"]
        formula = "대관 가능일 × 가동률 × 하루 대관료"
    else:
        revenue = v["sales"] * v["commission_rate"]
        formula = "작품 거래액 × 판매 수수료율"
    fixed = v["rent"] + v["fixed_cost"]
    cost = fixed + revenue * v["variable_cost_rate"]
    surplus = revenue - cost
    out.update(monthly_revenue=round(revenue, 2), monthly_cost=round(cost, 2),
               monthly_surplus=round(surplus, 2), formula=formula,
               break_even_revenue=round(fixed / (1 - v["variable_cost_rate"]), 2) if v["variable_cost_rate"] < 1 else None,
               payback_months=round(v["investment"] / surplus, 1) if surplus > 0 else None,
               payback_unavailable_reason=None if surplus > 0 else "월 운영 잉여가 0 이하라 단순 회수기간을 계산할 수 없습니다")
    return out
