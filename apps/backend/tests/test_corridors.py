"""상권 흐름(파주-고양-서울) API 계약 — 2026-10-26.

지키는 것:
  · 구간 순서는 파주 → 고양 → 서울(화면이 위에서 아래로 그리는 순서)
  · 경기 마디는 시군구, 서울 마디는 거점 — 경기 거점은 시군구 마디에 소속되고 그 사실이 응답에 있다
  · 짝(시너지 후보)은 있는 마디만 가리키고, 값은 측정값(하루 이동)이다
  · 출처·한계가 응답에 실린다 — 「동선이 아니다」가 빠지면 집계가 궤적처럼 읽힌다
  · 서빙 목록 밖 거점(추후 확장 과제)은 마디에 나오지 않는다
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import corridor as corridor_svc
from app.services import districts as districts_svc

client = TestClient(app)
V1 = "/api/v1"

pytestmark = pytest.mark.skipif(not corridor_svc.is_available(),
                                reason="gold/platform_corridor.json 미적재 — build_corridor 실행 필요")


def _get(**params):
    r = client.get(f"{V1}/corridors/paju-goyang-seoul", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_list_names_the_corridor():
    r = client.get(f"{V1}/corridors")
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert "paju-goyang-seoul" in ids


def test_segments_run_north_to_south():
    doc = _get()
    assert [s["key"] for s in doc["segments"]] == ["paju", "goyang", "seoul"]


def test_cross_segment_links_are_measured_both_ways():
    doc = _get()
    links = {(lk["from"], lk["to"]): lk for lk in doc["links"]}
    for a, b in [("paju", "goyang"), ("goyang", "seoul"), ("paju", "seoul")]:
        assert links[(a, b)]["per_day"] > 0 and links[(b, a)]["per_day"] > 0, (a, b)
        assert len(links[(a, b)]["arr_hour_share"]) == 24
        assert all(0 <= h <= 23 for h in links[(a, b)]["peak_hours"]), "시각 코드가 0~23 으로 접히지 않았다"


def test_gyeonggi_hubs_sit_on_sgg_nodes_and_seoul_hubs_on_their_own():
    doc = _get()
    nodes = {n["id"]: n for n in doc["nodes"]}
    for slug, nid in doc["hub_nodes"].items():
        node = nodes[nid]
        assert slug in {h["id"] for h in node["hubs"]}, (slug, nid)
        page = districts_svc.PAGES_BY_ID[slug]
        if page.get("city", "seoul") == "seoul":
            assert node["kind"] == "hub" and nid == slug
        else:
            assert node["kind"] == "sgg" and nid.startswith("sgg:")


def test_deferred_hubs_are_not_on_any_node():
    doc = _get()
    on_nodes = {h["id"] for n in doc["nodes"] for h in n["hubs"]}
    served = set(districts_svc.PAGES_BY_ID)
    assert on_nodes <= served
    for slug in ("ilsan", "westerndom", "hwajeong", "tanhyeon", "kintex", "starfield"):
        assert slug not in on_nodes, f"{slug}: 추후 확장 과제 거점이 흐름에 나왔다"


def test_synergies_point_at_existing_nodes_with_measured_values():
    doc = _get()
    ids = {n["id"] for n in doc["nodes"]}
    kinds = {s["kind"] for s in doc["synergies"]}
    assert {"visit_link", "local_belt"} <= kinds
    for s in doc["synergies"]:
        assert s["node"] in ids and s["from"] in ids and s["to"] in ids, s
        assert s["value"] >= doc["params"]["pair_min_per_day"] or s["kind"] == "local_belt", s
        assert s["node"].startswith("sgg:"), "시너지 후보는 경기 마디마다 고른다"


def test_caveats_say_it_is_not_a_trajectory():
    doc = _get()
    assert any("동선이 아니다" in c for c in doc["caveats"])
    assert "공공누리 1유형" in doc["source"]
    assert doc["resolution"] == {"seoul": "adong", "gyeonggi": "sgg"}


def test_industry_adds_fit_rank_from_the_same_ranking_as_business_fit():
    from app.services import business_fit

    doc = _get(industry="cafe")
    fit = {r["district_id"]: r for r in business_fit.fit_by_district("cafe")["districts"]}
    seen = 0
    for n in doc["nodes"]:
        for h in n["hubs"]:
            assert h["fit_rank"] == fit[h["id"]]["fit_rank"], h["id"]
            assert h["rank_group_name"] == fit[h["id"]]["rank_group_name"], h["id"]
            seen += 1
    assert seen
    assert doc["rank_groups"] == business_fit.fit_by_district("cafe")["rank_groups"]
    # 서울 거점은 서울 묶음으로만 줄 선다 — 경기 점수와 한 줄에 섞이지 않는다(2026-10-27)
    assert {h["rank_group_name"] for n in doc["nodes"] if n["segment"] == "seoul" for h in n["hubs"]} == {"서울"}


def test_unknown_corridor_and_industry_are_refused():
    assert client.get(f"{V1}/corridors/nowhere").status_code == 404
    assert client.get(f"{V1}/corridors/paju-goyang-seoul", params={"industry": "zzz"}).status_code == 400
