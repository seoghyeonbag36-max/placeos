"""상권 흐름(파주-고양-서울) 수집·빌드가 지켜야 할 것 — 합성 입력으로 고정한다(2026-10-26).

  · 이동목적 코드는 안내서 순서다 — 3 은 「귀가」(포털 나열 순서로 붙이면 쇼핑이 된다)
  · 출퇴근대 시각 `HHMM`(0720 …)은 0~23시로 접힌다
  · 서울만 행정동, 경기는 시군구 — 경기 거점의 행정동은 시군구 코드로 접힌다
  · 원본 헤더가 바뀌면 추측하지 않고 멈춘다
  · 시너지 후보는 규칙(경기 마디마다 종류별 최대 1개)대로만 고른다
"""
from __future__ import annotations

import csv
import io
import json
import zipfile

import pytest

from data.collectors import capital_od as C
from data.pipelines import build_corridor as B

HEADER = list(C._HEADER)


def _zip(tmp_path, rows, name="seoul_purpose_admdong3_20260914.zip", header=HEADER):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    p = tmp_path / name
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("seoul_purpose_admdong3_final_20260914.csv", buf.getvalue().encode("cp949"))
    return p


def test_purpose_codes_follow_the_guide_not_the_portal_listing():
    assert C.PURPOSE["3"] == "귀가" and C.PURPOSE["4"] == "쇼핑" and C.PURPOSE["7"] == "기타"


def test_unit_level_is_adong_only_in_seoul():
    assert C.unit_level("11440660") == "adong"
    assert C.unit_level("41480510") == "sgg"
    assert C._sgg_unit("41480510") == "41480000"


def test_gyeonggi_hub_shares_fold_to_sgg(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "DATA_ROOT", tmp_path)
    for slug, cds in {"paju-hub": ["41480510"] * 9 + ["41480520"],
                      "seoul-hub": ["11440660"] * 9 + ["11440710"] * 1}.items():
        d = tmp_path / "bronze" / slug / "2026-10-26"
        d.mkdir(parents=True)
        (d / "stores_raw.json").write_text(json.dumps([{"adongCd": c} for c in cds]), encoding="utf-8")
    out = C.hub_adong_shares(["paju-hub", "seoul-hub"])
    assert out["paju-hub"] == {"41480000": 1.0}, "경기 행정동이 시군구로 안 접혔다"
    assert out["seoul-hub"]["11440660"] == pytest.approx(0.9)
    assert out["seoul-hub"]["11440710"] == pytest.approx(0.1)


def test_collect_folds_hours_maps_purpose_and_skips_masked(tmp_path, monkeypatch):
    rows = [
        # o, d, st, fns, 내외, 국적, 목적, 거리, 시간, cnt, 날짜
        ["41480000", "11440660", "07", "0840", "내국인", "한국", "1", "30000", "80", "10.0", "20260914"],
        ["41480000", "11440660", "17", "1820", "내국인", "한국", "7", "30000", "80", "5.0", "20260914"],
        ["11440660", "41480000", "19", "21", "내국인", "한국", "3", "30000", "85", "7.0", "20260914"],
        ["41480000", "11440660", "07", "08", "내국인", "한국", "1", "30000", "80", "*", "20260914"],
        ["26110510", "26110520", "07", "08", "내국인", "한국", "1", "300", "8", "99.0", "20260914"],  # 흐름 밖
    ]
    z = _zip(tmp_path, rows)
    saved = {}
    monkeypatch.setattr(C, "save_json", lambda doc, *a, **k: saved.setdefault("doc", doc))
    monkeypatch.setattr(C, "hub_adong_shares", lambda slugs: {"x-paju": {"41480000": 1.0},
                                                               "x-seoul": {"11440660": 1.0}})
    doc = C.collect([z])
    assert doc["masked_rows"] == 1
    assert doc["rows_used"] == 3, "흐름 밖(부산↔부산) 행이 섞였다"
    od = doc["city_od"]["paju|seoul"]
    assert od["total"] == pytest.approx(15.0)
    assert set(od["arr_hour"]) == {"08", "18"}, "HHMM 시각이 0~23시로 안 접혔다"
    assert od["purpose"] == {"출근": 10.0, "기타": 5.0}
    assert doc["city_od"]["seoul|paju"]["purpose"] == {"귀가": 7.0}
    assert doc["adong_pair"]["41480000|11440660"]["total"] == pytest.approx(15.0)


def test_changed_header_stops_instead_of_guessing(tmp_path, monkeypatch):
    z = _zip(tmp_path, [], header=HEADER[:-1] + ["etl_date"])
    monkeypatch.setattr(C, "hub_adong_shares", lambda slugs: {})
    with pytest.raises(SystemExit):
        C.collect([z])


def test_hours_fold_and_group_purposes():
    assert B._hours({"07": 1, "0720": 2, "0740": 3, "18": 4, "x": 9, "25": 9}) == {"07": 6, "18": 4}
    assert B._group({"출근": 1, "등교": 1, "귀가": 2, "기타": 3, "쇼핑": 1}) == {"work": 2, "home": 2, "visit": 4}


def test_roles_need_the_margin_over_the_median():
    nodes = [{"purpose_group_share": {"work": 10.0, "home": 40.0, "visit": 50.0}},
             {"purpose_group_share": {"work": 30.0, "home": 20.0, "visit": 50.0}},
             {"purpose_group_share": {"work": 12.0, "home": 38.0, "visit": 50.0}}]
    B._assign_roles(nodes)
    assert nodes[1]["role"]["kind"] == "출근형"         # 30 − 중앙 12 = +18
    assert nodes[2]["role"]["kind"] == "혼합"           # 어느 쪽도 여백(3%p) 안
    assert nodes[0]["role"]["deviation_pp"]["home"] == pytest.approx(2.0)


def test_synergies_pick_one_per_kind_per_gyeonggi_node():
    nodes = {"sgg:41480000": {"segment": "paju"}, "sgg:41287000": {"segment": "goyang"},
             "a": {"segment": "seoul"}, "b": {"segment": "seoul"}}

    def pair(f, t, visit, work):
        return {"from": f, "to": t, "per_day": visit + work, "visit_per_day": visit, "work_per_day": work,
                "home_per_day": 0.0, "purpose_group_share": {}, "peak_hours": [8], "avg_min": 60.0}

    pairs = {("sgg:41480000", "a"): pair("sgg:41480000", "a", 900, 100),
             ("sgg:41480000", "b"): pair("sgg:41480000", "b", 100, 800),
             ("b", "sgg:41480000"): pair("b", "sgg:41480000", 300, 0),
             ("sgg:41480000", "sgg:41287000"): pair("sgg:41480000", "sgg:41287000", 5000, 0),
             ("sgg:41287000", "sgg:41480000"): pair("sgg:41287000", "sgg:41480000", 4000, 0)}
    out = {(s["node"], s["kind"]): s for s in B._synergies(nodes, pairs)}
    assert out[("sgg:41480000", "visit_link")]["to"] == "a"
    assert out[("sgg:41480000", "commute")]["to"] == "b"
    assert out[("sgg:41480000", "inbound")]["from"] == "b"
    assert out[("sgg:41480000", "local_belt")]["value"] == pytest.approx(9000)
    assert all(s["node"].startswith("sgg:") for s in out.values())
