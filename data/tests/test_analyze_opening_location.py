import importlib.util
import sys
from pathlib import Path

import pytest


def _load():
    pytest.importorskip("shapely")  # 프로브 전용 의존성 — CI data 잡은 선택 의존성을 설치하지 않는다
    pytest.importorskip("pyproj")
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("analyze_opening_location_t", scripts / "analyze_opening_location.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PRE, MID, POST = ("2016~2018 (쿠팡이츠 전)", "2019~2020", "2021~2026")


def _hub(pre, n_pre, post, n_post):
    def s(p, n):
        return {"n": n, "대로변": p, "중로": 0.0, "그외": round(1 - p, 3)} if n else {"n": 0, "대로변": None, "중로": None, "그외": None}
    return {"by_period": {PRE: s(pre, n_pre), MID: s(0.2, 50), POST: s(post, n_post)}}


def test_heterogeneity_separates_increase_decrease_none_and_drops_small_hubs():
    m = _load()
    res = {"up": _hub(0.10, 200, 0.40, 200), "down": _hub(0.40, 200, 0.10, 200), "same": _hub(0.30, 200, 0.30, 200),
           "tiny": _hub(0.10, 10, 0.50, 200), "_pooled": {"by_period": {}}}
    h = m.heterogeneity(res)
    assert h["hubs"] == 3  # tiny(전 구간 n<30)와 `_` 키는 뺀다
    assert (h["increase"], h["decrease"], h["no_difference"]) == (1, 1, 1)
    assert [r["slug"] for r in h["rows"]] == ["down", "same", "up"]  # 변화량 오름차순
    assert h["rows"][-1]["delta"] == 0.3
    assert h["expected_by_chance_each_direction"] == 0.1  # 0.025 × 3


def test_heterogeneity_with_no_hubs_does_not_crash():
    m = _load()
    h = m.heterogeneity({"_pooled": {}})
    assert h["hubs"] == 0 and h["median_delta"] is None and h["rows"] == []


def test_one_failing_hub_does_not_kill_the_rest(monkeypatch):
    m = _load()
    row = {"svc": "일반음식점", "APVPERMYMD": "2017-05-01"}

    def fake_assign(slug):
        if slug == "bad":
            raise KeyError("stores_raw 없음")
        return {"building_pnus": ["p1", "p2"]}, [{"row": row, "pnu": "p1"}, {"row": row, "pnu": None}]

    monkeypatch.setattr(m, "assign_rows", fake_assign)
    parcels = {"p1": {"v": {"y": [[2020, "광대로한면", 1]]}}, "p2": {"v": {"y": [[2020, "소로한면", 1]]}}}
    out = m.analyze(["good", "bad"], parcels)
    assert out["_errors"] == {"bad": "KeyError"}
    assert out["good"]["food_openings_in_buildings"] == 1  # pnu 없는 행은 세지 않는다
    assert out["good"]["by_period"][PRE]["대로변"] == 1.0
    assert out["good"]["baseline_share"]["대로변"] == 0.5  # 기준선 = 건물 필지 2개 중 1개
    assert out["_pooled"]["hubs"] == 1
