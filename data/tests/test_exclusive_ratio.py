"""상업층 전용률(일반건축물 전용면적 추정 근거) — build_exclusive_ratio (2026-11-08).

순수 함수 시험 + 실린 Gold 의 계약. 비율을 지어내지 않는지(표본 없으면 None), 지번 한 표인지, 거르기 범위를 본다.
"""
import json
from pathlib import Path

from data.pipelines.build_exclusive_ratio import OUT, floor_ratios, summarise

FF = ["dong", "kind", "no", "raw", "area_m2", "purps", "etc", "strct", "atch"]
UF = ["flr", "kind", "no", "ho", "area_m2", "purps"]


def _doc(lots):
    return {"floor_fields": FF, "unit_fields": UF, "lots": lots}


def test_floor_ratio_is_exclusive_over_floor_plate():
    doc = _doc({"p1": {"floors": [["", "G", 1, "1층", 100.0, "소매점", None, None, 0]],
                       "units": [["1층", "G", 1, "101", 40.0, "소매점"], ["1층", "G", 1, "102", 40.0, "소매점"]]}})
    assert floor_ratios(doc) == {"p1": [0.8]}


def test_multi_dong_lots_and_lots_without_floor_rows_are_skipped():
    doc = _doc({
        "two_dong": {"floors": [["A", "G", 1, "1층", 100.0, "", None, None, 0], ["B", "G", 1, "1층", 100.0, "", None, None, 0]],
                     "units": [["1층", "G", 1, "101", 50.0, "소매점"]]},
        "no_floors": {"floors": [], "units": [["1층", "G", 1, "101", 50.0, "소매점"]]},
    })
    assert floor_ratios(doc) == {}


def test_one_vote_per_lot_and_out_of_range_dropped():
    s = summarise({("h", "a"): [0.8, 0.8, 0.8, 0.8, 0.8], ("h", "b"): [0.6], ("h", "c"): [0.2, 1.4]})
    assert s["n_lots"] == 2 and s["n_floors"] == 6      # c 는 거르기로 빠진다
    assert s["median"] == 0.7                             # 층 수가 아니라 지번 한 표: median(0.8, 0.6)


def test_no_sample_means_no_ratio():
    assert summarise({})["median"] is None


def test_shipped_gold_is_sane():
    doc = json.loads(Path(OUT).read_text(encoding="utf-8"))
    assert doc["n_lots"] >= 20
    assert 0.5 <= doc["p25"] <= doc["median"] <= doc["p75"] <= 1.0
    lo, hi = doc["median_ci95"]
    assert lo <= doc["median"] <= hi
    assert "추정" in doc["caveat"] or "빌려" in doc["caveat"]
