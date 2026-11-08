"""전유부 유닛에 그 호의 공용면적(pub_m2)을 붙이는 규칙 — build_expos_units.attach_pub (2026-11-08).

bronze 없이 도는 순수 함수 시험이다. 계약면적(전용 + 공용)·전용률을 실측으로 보이기 위한 재료라,
짝이 없으면 0 으로 채우지 않고(지어내지 않는다) 한 호의 공용을 두 번 세지 않는지를 본다.
"""
from data.pipelines.build_expos_units import attach_pub


def test_pub_attached_by_dong_and_ho():
    units = [{"dong": "", "ho": "101호", "area_m2": 50.0}, {"dong": "", "ho": "102호", "area_m2": 30.0}]
    n = attach_pub(units, {("", "101호"): 12.345, ("", "102호"): 7.0})
    assert n == 2 and units[0]["pub_m2"] == 12.35 and units[1]["pub_m2"] == 7.0


def test_no_match_means_no_value_not_zero():
    units = [{"dong": "A동", "ho": "101호", "area_m2": 50.0}, {"dong": "", "ho": "", "area_m2": 9.0}]
    assert attach_pub(units, {("B동", "101호"): 10.0, ("", ""): 3.0}) == 0
    assert all("pub_m2" not in u for u in units)


def test_common_area_counted_once_per_ho():
    units = [{"dong": "", "ho": "201호", "area_m2": 20.0}, {"dong": "", "ho": "201호", "area_m2": 15.0}]
    assert attach_pub(units, {("", "201호"): 8.0}) == 1
    assert units[0]["pub_m2"] == 8.0 and "pub_m2" not in units[1]
