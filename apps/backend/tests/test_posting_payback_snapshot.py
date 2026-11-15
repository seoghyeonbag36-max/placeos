"""Posting 변경 전·후 스냅샷의 집계 규칙 잠금 (2026-11-15) — scripts/posting_payback_snapshot.py.

서빙 계산을 실호출하는 부분은 데이터에 기대므로 여기서 세지 않는다(스크립트를 돌려 보고서로 본다).
여기서는 **세는 규칙**만 잠근다: 투자비를 실측으로 바꾼 뒤 「줄었다」는 말이 이 규칙 위에서 나오기 때문이다.
"""
import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "posting_payback_snapshot.py"
_spec = importlib.util.spec_from_file_location("posting_payback_snapshot", _SCRIPT)
snap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(snap)


def _tier(roi, *, available=True, viable=True, recommended=False):
    return {"available": available, "viable": viable, "roi_months": roi, "recommended": recommended}


def test_roi_bin_edges_are_half_open():
    assert snap.roi_bin(0.9) == "<1"
    assert snap.roi_bin(1.0) == "1-3"       # 1개월 「미만」이 아니다 — 경계는 위 구간으로
    assert snap.roi_bin(11.9) == "6-12"
    assert snap.roi_bin(24) == ">=24"


def test_headline_kind_mirrors_months_function():
    # flow/format.ts months(): < 1 → 「한 달 안에」 · 반올림 개월 < 12 → 「약 n개월」 · 그 위 → 「약 n년…」
    assert snap.headline_kind(0.8) == "한 달 안에"
    assert snap.headline_kind(1.0) == "약 n개월"
    assert snap.headline_kind(11.4) == "약 n개월"
    assert snap.headline_kind(11.6) == "약 n년 이상"      # 반올림하면 12 — 화면도 「약 1년」이라 말한다


def test_unavailable_and_unviable_tiers_are_not_candidates():
    sc = {
        "premium": _tier(None, available=False, viable=False),
        "value": _tier(99.0, viable=False),                 # 회수 불가 — 자료는 있다
        "factory": _tier(0.8, recommended=True),
    }
    row = snap.summarize_unit(sc)
    assert row["available"] == ["factory", "value"]
    assert row["viable"] == ["factory"]
    assert row["rec"] == "factory" and row["rec_roi"] == 0.8
    assert row["viable_roi"] == {"factory": 0.8}


def test_unit_without_recommendation_has_no_roi():
    row = snap.summarize_unit({"premium": _tier(None, available=False, viable=False)})
    assert row["rec"] is None and row["rec_roi"] is None and row["available"] == []


def _row(city, sc):
    return {"city": city, "hub": "h", **snap.summarize_unit(sc)}


def test_aggregate_counts_with_both_denominators():
    rows = [
        _row("서울", {"value": _tier(0.5, recommended=True), "factory": _tier(2.0)}),   # 추천 · 1개월 미만
        _row("서울", {"value": _tier(5.0, recommended=True)}),                           # 추천 · 5개월
        _row("서울", {"value": _tier(99.0, viable=False)}),                              # 자료는 있으나 추천 없음
        _row("광주", {"value": _tier(None, available=False, viable=False)}),             # 자료 부족 — 분모에서 빠진다
    ]
    s = snap.aggregate(rows)
    assert s["units"] == 4 and s["units_with_any_tier"] == 3
    assert s["units_with_recommendation"] == 2 and s["units_without_recommendation"] == 2
    lt1 = s["recommended_lt1_month"]
    assert lt1["count"] == 1
    assert lt1["of_units_with_any_tier"] == 3 and lt1["pct_of_units_with_any_tier"] == 33.3
    assert lt1["of_recommended"] == 2 and lt1["pct_of_recommended"] == 50.0
    assert s["roi_bins"]["<1"] == 1 and s["roi_bins"]["3-6"] == 1
    assert s["headline_kinds"] == {"한 달 안에": 1, "약 n개월": 1, "약 n년 이상": 0}
    # 회수되는 tier × 유닛 쌍: 0.5 · 2.0 · 5.0 (99.0 은 회수 불가라 빠진다)
    assert s["viable_pairs"]["count"] == 3 and s["viable_pairs"]["lt1"] == 1
    assert s["viable_pairs"]["roi_median"] == 2.0
    assert s["by_city"]["서울"] == {"units": 3, "rec_units": 2, "rec_lt1": 1, "no_tier_units": 1}
    assert s["by_city"]["광주"]["no_tier_units"] == 1


def test_empty_input_does_not_divide_by_zero():
    s = snap.aggregate([])
    assert s["units"] == 0
    assert s["recommended_lt1_month"]["pct_of_recommended"] is None
    assert s["recommended_roi_median"] is None
