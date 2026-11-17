import importlib.util
import sys
from pathlib import Path

import pytest

from data.collectors.vworld_landchar import compact, road_group


def test_road_group_keeps_the_main_road_class_and_ignores_corner_or_side_suffix():
    assert [road_group(n) for n in ("광대로한면", "광대소각", "광대세각")] == ["대로변"] * 3
    assert [road_group(n) for n in ("중로한면", "중로각지")] == ["중로"] * 2
    assert [road_group(n) for n in ("소로한면", "세로각지(가)", "세로한면(불)", "지정되지않음", None, "")] == ["그외"] * 6


def test_compact_one_row_per_year_later_month_wins_and_price_is_int():
    rows = [
        {"stdrYear": "2020", "stdrMt": "01", "roadSideCodeNm": "소로한면", "pblntfPclnd": "1000000", "lndpclAr": "50.5", "prposArea1Nm": "일반상업지역"},
        {"stdrYear": "2020", "stdrMt": "07", "roadSideCodeNm": "중로한면", "pblntfPclnd": "1100000", "lndpclAr": "50.5", "prposArea1Nm": "일반상업지역"},
        {"stdrYear": "2019", "stdrMt": "01", "roadSideCodeNm": "소로한면", "pblntfPclnd": "", "lndpclAr": "50.5"},
    ]
    c = compact(rows)
    assert c["y"] == [[2019, "소로한면", None], [2020, "중로한면", 1100000]]
    assert c["z"] == "일반상업지역" and c["a"] == 50.5


def test_compact_empty_rows_gives_empty_series():
    assert compact([]) == {"y": [], "z": None, "a": None}


def _load_analysis():
    pytest.importorskip("shapely")  # 프로브 전용 의존성 — CI data 잡은 설치하지 않는다
    pytest.importorskip("pyproj")
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("analyze_opening_location", scripts / "analyze_opening_location.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_opening_location_helpers():
    m = _load_analysis()
    assert m.opening_year({"APVPERMYMD": "2019-05-14              "}) == 2019
    assert m.opening_year({"APVPERMYMD": "1901-01-01"}) is None  # 인허가 자료의 오기 연도
    assert m.opening_year({"APVPERMYMD": ""}) is None
    parcels = {"p1": {"v": {"y": [[2013, "소로한면", 1], [2020, "광대로한면", 2]]}}, "p2": {"empty": True}}
    assert m.latest_group(parcels, "p1") == "대로변"  # 최신 연도 값
    assert m.latest_group(parcels, "p2") == "미상" and m.latest_group(parcels, "nope") == "미상"
    import collections
    s = m.shares(collections.Counter({"대로변": 1, "중로": 1, "그외": 2, "미상": 6}))
    assert s == {"n": 4, "대로변": 0.25, "중로": 0.25, "그외": 0.5}  # 미상은 분모에서 뺀다
