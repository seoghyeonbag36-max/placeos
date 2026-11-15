"""입점 점검(services/use_check) — 재료 없으면 자료 부족 · 금지·용도변경·확인 필요·대장상 가능 네 갈래 · 단정 금지."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services import business_fit, use_check

ROOT = Path(__file__).resolve().parents[3]

LAW = {
    "3나": {"ho": 3, "mok": "나", "ref": "건축법 시행령 별표 1 제3호나목", "d": 0, "min": None, "max": 300.0},
    "4아": {"ho": 4, "mok": "아", "ref": "건축법 시행령 별표 1 제4호아목", "d": 1, "min": 300.0, "max": None},
    "4자": {"ho": 4, "mok": "자", "ref": "건축법 시행령 별표 1 제4호자목", "d": 2, "min": None, "max": None},
    "15가": {"ho": 15, "mok": "가", "ref": "건축법 시행령 별표 1 제15호가목", "d": 3, "min": None, "max": None},
}

INPUTS = {
    "basis": {"vworld_updated_max": "2026-11-06", "eum_fetched": "2026-11-15"},
    "zone_names": {"UQA111": "제1종전용주거지역", "UQA220": "일반상업지역", "UQA122": "제2종일반주거지역", "UQA123": "제3종일반주거지역",
                   "UQQ300": "지구단위계획구역", "UOA120": "상대보호구역", "UQA01X": "도시지역"},
    "parcels": {
        "1100000000000000001": [["UQA01X", "포함"], ["UQA220", "포함"]],
        "1100000000000000002": [["UQA122", "포함"]],
        "1100000000000000003": [["UQA220", "저촉"], ["UQA123", "저촉"]],
        "1100000000000000004": [["UQA220", "포함"], ["UQQ300", "포함"]],
        "1100000000000000005": [["UQA220", "포함"], ["UOA120", "포함"]],
        "1100000000000000006": [["UQA111", "포함"]],
    },
    "acts": {"11000": {
        "휴게음식점": {
            "UQA220": [{"reg": "가능", "c": [], "laws": [LAW["4아"], LAW["3나"]]}],
            "UQA122": [{"reg": "가능", "c": [0], "laws": [LAW["3나"]]}, {"reg": "가능", "c": [], "laws": [LAW["4아"]]}],
        },
        "일반음식점": {
            "UQA220": [{"reg": "가능", "c": [], "laws": [LAW["4자"]]}],
            "UQA123": [{"reg": "가능", "c": [], "laws": [LAW["4자"]]}],
            "UQQ300": [],
            "UOA120": [{"reg": "금지", "c": [], "laws": [LAW["4자"]]}],
            "UQA111": [{"reg": "금지", "c": [], "laws": [LAW["4자"]]}],
        },
        "일반숙박시설": {"UQA122": [{"reg": "금지", "c": [], "laws": [LAW["15가"]]}]},
    }},
    "conds": ["경관관리 등을 위하여 도시·군계획조례로 건축물의 층수를 제한하는 경우에는 그 층수 이하의 건축물로 한정한다"],
    "defs": [],
}


@pytest.fixture(autouse=True)
def _inputs(monkeypatch):
    monkeypatch.setattr(use_check, "_load", lambda: INPUTS)


def part(purps: str, code: str, area: float = 80.0) -> dict:
    return {"purps": purps, "code": code, "area_m2": area, "etc": None}


def by_item(r: dict) -> dict:
    return {c["item"]: c for c in r["checks"]}


def test_industries_match_business_fit_and_collector():
    """업종 key 는 business_fit 이 단일 출처 · 행위명은 수집기가 실제로 받은 것만."""
    assert set(use_check.INDUSTRY_ACTS) == {i["key"] for i in business_fit.INDUSTRIES}
    src = (ROOT / "data" / "collectors" / "eum_landuse.py").read_text(encoding="utf-8")
    node = next(n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", "") == "ACT_NAMES")
    collected = set(ast.literal_eval(node.value))
    assert {s["act"] for s in use_check.INDUSTRY_ACTS.values()} <= collected


def test_ledger_ok_needs_same_use_single_zone_unconditional():
    r = use_check.check("1100000000000000001", "restaurant", parts=[part("일반음식점", "04001")], area_m2=80)
    assert r["regulation_status"] == "ledger_ok"
    assert "허가 판정 아님" in r["headline"] and r["permission"] is None
    assert by_item(r)["필지 용도지역"]["reason"].startswith("일반상업지역")  # 도시지역(UQA0*)은 용도지역으로 세지 않는다


def test_use_change_needed_when_ledger_ho_differs():
    """1종 근생 소매점 층에 일반음식점(2종 근생 · 별표1 제4호자목)."""
    r = use_check.check("1100000000000000001", "restaurant", parts=[part("소매점", "03001")], area_m2=80)
    assert r["regulation_status"] == "use_change_needed"
    item = by_item(r)["대장 층 용도"]
    assert item["status"] == "blocked" and "제2종 근린생활시설" in item["reason"] and "정화조" in item["reason"]


def test_same_ho_other_detail_use_is_check_not_ok():
    r = use_check.check("1100000000000000001", "restaurant", parts=[part("학원", "04010")], area_m2=80)
    assert r["regulation_status"] == "needs_check"
    assert by_item(r)["대장 층 용도"]["status"] == "check"


def test_zoning_prohibited_when_every_use_zone_forbids():
    """1종전용주거 × 일반음식점 금지 — 대장을 고쳐도 풀리지 않는 경우."""
    r = use_check.check("1100000000000000006", "restaurant", parts=[part("일반음식점", "04001")], area_m2=80)
    assert r["regulation_status"] == "zoning_prohibited"
    assert "금지" in r["headline"] and "토지이음" in r["headline"]


def test_lodging_prohibition_is_not_asserted():
    """숙박은 일반숙박시설 하나로만 조회했다 — 호텔·도시민박은 분류가 달라 금지를 단정하지 않는다."""
    r = use_check.check("1100000000000000002", "lodging", parts=[part("일반숙박시설", "15001")], area_m2=80)
    assert r["regulation_status"] == "needs_check"
    assert by_item(r)["용도지역 행위제한"]["status"] == "check" and "관광숙박시설" in r["note"]


def test_conditional_zone_and_area_split_are_checks():
    """2종일반주거 × 휴게음식점 1종(300㎡ 미만)은 조건부 · 합계 면적에 따라 1종/2종이 갈린다."""
    r = use_check.check("1100000000000000002", "cafe", parts=[part("휴게음식점", "03002")], area_m2=120)
    assert r["regulation_status"] == "needs_check"
    items = by_item(r)
    assert items["용도지역 행위제한"]["status"] == "check" and "조건" in items["용도지역 행위제한"]["reason"]
    assert items["면적 기준"]["status"] == "check" and "300㎡" in items["면적 기준"]["reason"]


def test_unit_area_over_threshold_drops_lower_class():
    """한 층만으로 300㎡ 이상이면 1종(3호나목)은 될 수 없다 — 분류가 갈리지 않는다."""
    r = use_check.check("1100000000000000001", "cafe", parts=[part("휴게음식점", "04002", 400)], area_m2=400)
    assert r["regulation_status"] == "ledger_ok"
    assert "면적 기준" not in by_item(r)


def test_two_use_zones_is_check():
    r = use_check.check("1100000000000000003", "restaurant", parts=[part("일반음식점", "04001")], area_m2=80)
    assert r["regulation_status"] == "needs_check"
    assert by_item(r)["필지 용도지역"]["status"] == "check" and "제84조" in by_item(r)["필지 용도지역"]["reason"]


def test_district_unit_plan_is_always_check():
    r = use_check.check("1100000000000000004", "restaurant", parts=[part("일반음식점", "04001")], area_m2=80)
    assert r["regulation_status"] == "needs_check"
    assert "결정도서" in by_item(r)["다른 지역지구"]["reason"]


def test_other_district_prohibition_is_check_not_prohibited():
    """상대보호구역 금지는 심의로 풀릴 수 있어 단정하지 않는다."""
    r = use_check.check("1100000000000000005", "restaurant", parts=[part("일반음식점", "04001")], area_m2=80)
    assert r["regulation_status"] == "needs_check"
    assert "상대보호구역" in by_item(r)["다른 지역지구"]["reason"]


def test_missing_inputs_never_invents():
    r = use_check.check("1199999999999999999", "restaurant", parts=[part("일반음식점", "04001")])
    assert r["regulation_status"] == "missing_inputs" and "자료 부족" in r["headline"]
    r = use_check.check("1100000000000000001", "restaurant", parts=None)
    assert r["regulation_status"] == "missing_inputs"
    r = use_check.check("1100000000000000001", "beauty", parts=[part("미용원", "03027")])  # 행위 미조회
    assert r["regulation_status"] == "missing_inputs"


def test_unknown_industry_is_none():
    assert use_check.check("1100000000000000001", "spaceship", parts=[part("일반음식점", "04001")]) is None


@pytest.mark.parametrize("industry", sorted(use_check.INDUSTRY_ACTS))
def test_never_asserts_permission(industry):
    r = use_check.check("1100000000000000001", industry, parts=[part("일반음식점", "04001")], area_m2=80)
    text = r["headline"] + " ".join(c["reason"] for c in r["checks"])
    assert "허가됨" not in text and "입점 가능" not in text
    assert r["permission"] is None and "허가 판정이 아닙니다" in r["note"]


def test_ledger_code_survives_summarise_and_twin_schema():
    """대장 용도코드가 실시간 요약 → /twin 응답 모델까지 살아남는다(response_model 이 모르는 키는 조용히 버린다)."""
    from app.schemas.renewal import TwinLedgerFloor
    from app.services import building_ledger_live as bll

    rows = [{"flrGbCdNm": "지상", "flrNo": 1, "mainPurpsCdNm": "소매점", "mainPurpsCd": "03001", "area": 282.0}]
    s = bll.summarise([], rows)
    assert s["floors"]["1"]["parts"][0]["code"] == "03001"
    assert TwinLedgerFloor(**s["floors"]["1"]).model_dump()["parts"][0]["code"] == "03001"


def test_ho_of():
    assert use_check.ho_of("03002") == 3 and use_check.ho_of("14299") == 14
    assert use_check.ho_of(None) is None and use_check.ho_of("x1") is None
