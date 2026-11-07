"""2026-11 리뉴얼 새 경로 — 실제 Gold 로 응답 계약과 「다른 경로와 같은 말을 하는가」를 본다."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import building_twin, districts as svc, floor_vacancy, posting, vacancy_class

client = TestClient(app)
API = "/api/v1"
GOLD = Path(__file__).resolve().parents[3] / "data" / "gold"
HUBS = ("garosugil", "suwonst", "gj-chungjang")
NO_RENT = ("ajou", "yeongtong", "dandae", "gj-eoryong", "gj-usan", "gj-ilgok")
SERVED = [p["id"] for p in svc.PAGES]


def _raw_rone() -> dict:
    return json.loads((GOLD / "platform_rone_history.json").read_text(encoding="utf-8"))


# ── 외곽선 ──────────────────────────────────────────────────────────────
def test_outlines_cover_served_and_route_is_not_swallowed():
    r = client.get(f"{API}/commercial-districts/outlines")
    assert r.status_code == 200
    body = r.json()
    assert "공식 상권 경계가 아니" in body["note"]
    by_id = {h["id"]: h for h in body["hubs"]}
    assert set(SERVED) <= set(by_id)
    assert by_id["garosugil"]["rings"] and len(by_id["garosugil"]["rings"][0][0]) == 2
    lat, lng = by_id["garosugil"]["rings"][0][0]
    assert 33 < lat < 39 and 124 < lng < 132       # [lat, lng] 순서
    assert by_id["garosugil"]["type_code"]
    assert by_id["suwonst"]["type_code"] is None and by_id["suwonst"]["type_is_manual"] is False


# ── 임대 시계열 ─────────────────────────────────────────────────────────
def test_rent_history_converts_units_and_keeps_nulls():
    raw = _raw_rone()
    body = client.get(f"{API}/commercial-districts/garosugil/rent-history").json()
    assert len(body["quarters"]) == 22
    assert body["rent_per_pyeong_manwon"][-1] == round(raw["hubs"]["garosugil"]["rent_per_m2"][-1] * 3.3058 / 10, 1)
    assert body["floor_factor"]["1F"] == 1.0


def test_rent_history_shared_and_missing():
    assert client.get(f"{API}/commercial-districts/wondang/rent-history").json()["source"] == "rone-shared"
    assert client.get(f"{API}/commercial-districts/nope/rent-history").status_code == 404
    assert client.get(f"{API}/commercial-districts/..%2F..%2Fetc/rent-history").status_code == 404


@pytest.mark.parametrize("hub", NO_RENT)
def test_rent_history_without_rent_is_null_not_zero(hub):
    body = client.get(f"{API}/commercial-districts/{hub}/rent-history").json()
    assert body["rent_available"] is False
    assert all(v is None for v in body["rent_per_pyeong_manwon"])


# ── 자리 순위 ───────────────────────────────────────────────────────────
def test_site_ranking_sorted_with_nulls_last():
    body = client.get(f"{API}/commercial-districts/garosugil/site-ranking", params={"industry": "cafe"}).json()
    assert body["model_covered"] is True
    scores = [s["selected"]["score"] for s in body["sites"]]
    known = [v for v in scores if v is not None]
    assert known == sorted(known, reverse=True)
    assert all(v is None for v in scores[len(known):])    # 값 없는 자리는 뒤로
    for s in body["sites"]:
        if s["selected"]["score"] is None:
            assert s["selected"]["rank_note"]
            assert s["selected"]["delta_pp"] is None     # 0 으로 채우지 않는다
    assert any(s["floor_units"] for s in body["sites"])
    for s in body["sites"]:
        for u in s["floor_units"]:
            assert u["id"].startswith("vfu-")


def test_site_ranking_uncovered_and_bad_input():
    body = client.get(f"{API}/commercial-districts/garosugil/site-ranking", params={"industry": "beauty"}).json()
    assert body["model_covered"] is False and body["unavailable_reason"]
    assert all(s["selected"]["score"] is None for s in body["sites"])
    assert client.get(f"{API}/commercial-districts/garosugil/site-ranking",
                      params={"industry": "nope"}).status_code == 422
    assert client.get(f"{API}/commercial-districts/nope/site-ranking").status_code == 404


# ── 시간대 ─────────────────────────────────────────────────────────────
def test_hourly_profile_shape_and_seoul_only():
    body = client.get(f"{API}/heatmap/hourly-profile", params={"district": "garosugil", "daytype": "weekend"}).json()
    assert [h["hour"] for h in body["hours"]] == list(range(24))
    assert abs(sum(h["share"] for h in body["hours"]) - 1.0) < 0.01
    assert body["peak"]["value"] == max(h["value"] for h in body["hours"])
    assert body["sample_days"] == 2 and body["as_of"]
    assert client.get(f"{API}/heatmap/hourly-profile", params={"district": "suwonst"}).status_code == 404
    assert client.get(f"{API}/heatmap/hourly-profile",
                      params={"district": "garosugil", "daytype": "x"}).status_code == 422


# ── 공실 3분류 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("hub", HUBS)
def test_vac_class_matches_floor_listing(hub):
    features = client.get(f"{API}/heatmap/buildings", params={"district": hub}).json()["features"]
    units = client.get(f"{API}/commercial-districts/{hub}/floor-vacancies", params={"limit": 2000}).json()["units"]
    conf = {u["pnu"] for u in units if u["certainty"] == "confirmed"}
    prob = {u["pnu"] for u in units} - conf
    seen = set()
    for f in features:
        p = f["properties"]
        assert p["vac_class"] in ("confirmed", "probable", "full", "unknown")
        if p["source"] == "polygon_only":
            assert p["vac_class"] == "unknown"       # 근거 없는 건물은 절대 공실이 아니다
        elif p["pnu"] in conf:
            assert p["vac_class"] == "confirmed"
        elif p["pnu"] in prob:
            assert p["vac_class"] == "probable"
        elif p["status"] == "full":
            assert p["vac_class"] == "full"
        seen.add(p["vac_class"])
        assert "road_addr" in p
    assert "confirmed" in seen and "unknown" in seen


def test_master_cache_is_not_polluted():
    """`load_master` 를 함께 쓰는 집계가 파생 필드를 보지 않는다."""
    client.get(f"{API}/heatmap/buildings", params={"district": "garosugil"})
    from app.services import building_vacancy
    assert "vac_class" not in building_vacancy.load_master("garosugil")["features"][0]["properties"]


# ── 트윈 ────────────────────────────────────────────────────────────────
def test_place_floors_port_matches_frontend_rule():
    """`buildingFloors.placeFloors` 와 같은 규칙 — 낮은 층부터 층 미상 점포를 앉힌다."""
    assert building_twin.place_floors([1, 2, 3, 4], [2], 1, 5) == {
        1: "uncertain", 2: "occupied", 3: "vacant", 4: "vacant", 5: "noncom"}
    assert building_twin.place_floors([2], [], 0, 2) == {1: "noncom", 2: "vacant"}


@pytest.mark.parametrize("hub", HUBS)
def test_twin_floor_status_matches_floor_vacancies_both_ways(hub):
    """트윈의 vacant_* 층 ⇔ `/floor-vacancies` 의 층·certainty. 표본이 아니라 그 거점 지번 전부."""
    listed = vacancy_class.floors_by_pnu(hub)
    assert listed
    for pnu, by_floor in list(listed.items())[:150]:
        bid = next(iter(by_floor.values()))["building_id"]
        body = building_twin.twin(hub, bid)
        assert body is not None
        vacant = {f["lv"]: f["status"] for f in body["floors"] if f["status"].startswith("vacant_")}
        want = {fl: ("vacant_confirmed" if u["certainty"] == "confirmed" else "vacant_probable")
                for fl, u in by_floor.items()}
        assert vacant == want, (pnu, vacant, want)
        for f in body["floors"]:
            if f["lv"] in by_floor:
                assert f["unit_id"] == by_floor[f["lv"]]["id"]
                assert f["area_m2"] == by_floor[f["lv"]]["area_m2"]


def test_twin_rent_matches_rent_layer():
    rent = client.get(f"{API}/heatmap/rent", params={"district": "garosugil"}).json()
    row = rent["listings"][0]
    body = client.get(f"{API}/buildings/{row['building_id']}/twin", params={"district": "garosugil"}).json()
    floor = next(f for f in body["floors"] if f["unit_id"] == row["id"])
    assert floor["rent_est_manwon"] == row["monthly_rent"]
    assert floor["rent_per_pyeong"] == row["rent_per_pyeong"]


def test_twin_shape_and_neighbors_are_measured():
    fid = floor_vacancy.load("garosugil")["units"][0]["building_id"]
    r = client.get(f"{API}/buildings/{fid}/twin", params={"district": "garosugil"})
    assert r.status_code == 200
    body = r.json()
    assert body["ring"] and body["floors"][0]["lv"] >= body["floors"][-1]["lv"]
    assert len(body["neighbors"]) <= 60
    assert all(n["ring"] for n in body["neighbors"])
    assert {s["basis"] for s in body["vacancy_stats"]} >= {"floors_confirmed", "floors_both"}
    assert body["range"]["min"] <= body["range"]["max"]
    assert body["height_source"] in ("vworld", "estimated")


def test_twin_polygon_only_is_never_vacant():
    master = json.loads((GOLD / "garosugil" / "page_building_master.geojson").read_text(encoding="utf-8"))
    pid = next(f["properties"]["id"] for f in master["features"] if f["properties"]["source"] == "polygon_only")
    body = building_twin.twin("garosugil", pid)
    assert body["vac_class"] == "unknown"
    assert all(f["status"] == "unknown" for f in body["floors"])
    assert body["vacancy_stats"] == []


def test_twin_basement_without_evidence_is_unknown():
    for f in (json.loads((GOLD / "garosugil" / "page_building_master.geojson").read_text(encoding="utf-8")))["features"]:
        body = building_twin.twin("garosugil", f["properties"]["id"])
        if body and body["floors_below"]:
            assert all(x["status"] == "unknown" for x in body["floors"] if x["lv"] < 0)
            return
    pytest.fail("지하층이 있는 건물이 없다")


@pytest.mark.parametrize("bid,district", [("nope", "garosugil"), ("../../etc", "garosugil"), ("1-1", "..%2Fetc")])
def test_twin_bad_ids_are_404(bid, district):
    assert client.get(f"{API}/buildings/{bid}/twin?district={district}").status_code == 404


def test_twin_requires_district():
    assert client.get(f"{API}/buildings/x/twin").status_code == 422


# ── 주변 점포 ──────────────────────────────────────────────────────────
def _at(hub="garosugil"):
    u = floor_vacancy.load(hub)["units"][0]
    return {"lat": u["lat"], "lng": u["lng"], "building_id": u["building_id"]}


def test_nearby_counts_add_up_and_relative_is_percentile():
    body = client.get(f"{API}/commercial-districts/garosugil/nearby-stores",
                      params={**_at(), "radius": 100, "industry": "cafe"}).json()
    c = body["counts"]
    assert c["same"] + c["similar"] + c["colocated"] + c["other"] == c["total"]
    assert c["same_chain"] <= c["same"]
    assert sum(body["floor_split"].values()) == c["total"]
    assert body["basis"] == "직선"
    assert body["by_radius"]["100"] == c
    assert body["by_radius"]["50"]["total"] <= body["by_radius"]["100"]["total"]
    ds = [s["distance_m"] for s in body["stores"]]
    assert ds == sorted(ds) and len(ds) <= 200 and all(d <= 100 for d in ds)
    rel = body["relative"]
    assert 0 <= rel["percentile"] <= 100 and rel["compared_sites"] > 100
    assert rel["band"] in ("여유 쪽", "중간", "붐비는 쪽")
    assert "검증된 값이 아닙니다" in rel["note"]
    assert any(s["same_building"] for s in body["stores"]) or c["total"] == 0


def test_nearby_floor_weighted_never_raises_index():
    params = {**_at(), "radius": 100, "industry": "cafe"}
    plain = client.get(f"{API}/commercial-districts/garosugil/nearby-stores", params=params).json()["relative"]["index"]
    weighted = client.get(f"{API}/commercial-districts/garosugil/nearby-stores",
                          params={**params, "floor": "true"}).json()
    assert weighted["relative"]["index"] <= plain and weighted["floor_weighted"] is True


def test_nearby_works_outside_seoul_and_without_industry():
    body = client.get(f"{API}/commercial-districts/suwonst/nearby-stores",
                      params={**_at("suwonst"), "industry": "restaurant"}).json()
    assert body["counts"]["total"] > 0
    bare = client.get(f"{API}/commercial-districts/suwonst/nearby-stores", params=_at("suwonst")).json()
    assert bare["relative"]["percentile"] is None and bare["counts"]["same"] == 0


def test_nearby_detail_key_narrows_same():
    params = {**_at(), "radius": 100}
    wide = client.get(f"{API}/commercial-districts/garosugil/nearby-stores",
                      params={**params, "industry": "beauty"}).json()["counts"]["same"]
    narrow = client.get(f"{API}/commercial-districts/garosugil/nearby-stores",
                        params={**params, "industry": "beauty", "detail_key": "beauty_nail"}).json()["counts"]["same"]
    assert narrow <= wide


@pytest.mark.parametrize("extra,status", [
    ({"radius": 100000}, 422), ({"radius": 1}, 422), ({"lat": 999}, 422), ({"lat": "nan"}, 422),
    ({"industry": "nope"}, 422), ({"detail_key": "nope"}, 422),
    ({"industry": "cafe", "detail_key": "beauty_nail"}, 422),
])
def test_nearby_rejects_bad_input(extra, status):
    assert client.get(f"{API}/commercial-districts/garosugil/nearby-stores",
                      params={**_at(), **extra}).status_code == status


def test_nearby_unknown_hub_is_404():
    assert client.get(f"{API}/commercial-districts/nope/nearby-stores", params=_at()).status_code == 404


def test_store_response_has_no_private_fields():
    body = client.get(f"{API}/commercial-districts/garosugil/nearby-stores", params=_at()).json()
    assert body["stores"]
    assert not {"ho", "hoNo", "phone", "tel"} & set(body["stores"][0])


# ── simulate 확장 ──────────────────────────────────────────────────────
def test_simulate_vu_response_is_unchanged():
    """`vu-` 응답은 층 매물 확장 전과 같다 — 키 집합과 시나리오 둘 다."""
    unit = svc.resolved_units("garosugil")[0]
    r = client.post(f"{API}/ai/simulate-revenue", json={"district_id": "garosugil", "unit_id": unit["id"]}).json()
    assert set(r) == {"district_id", "unit_id", "industry_type", "scenarios", "source", "source_note", "inputs_source",
                      "inputs_quarter", "unviable_note", "calculation_status", "unavailable_reason", "economics"}
    assert r["inputs_source"] == unit["inputs_source"] and r["inputs_source"]["area"] != "user_input"
    want = svc.tier_scenarios(unit, "garosugil")
    for k, s in r["scenarios"].items():
        assert s["month_rev"] == want[k]["month_rev"] and s["roi_months"] == want[k]["roi_months"]


def test_simulate_floor_unit_uses_that_floor():
    units = floor_vacancy.load("garosugil")["units"]
    second = next(u for u in units if u["floor"] == 2 and 20 <= u["area"] <= 60)
    r = client.post(f"{API}/ai/simulate-revenue", json={"district_id": "garosugil", "unit_id": second["id"]}).json()
    assert r["unit_id"] == second["id"]
    assert r["source"] == "fallback-3tier"
    assert r["inputs_source"]["area"] == "gold-ledger-floor" and r["inputs_source"]["floor"] == "floor_unit"
    per_m2 = client.get(f"{API}/heatmap/rent", params={"district": "garosugil"}).json()["base_rent_per_m2_krw_thousand"]
    # 임대료 = R-ONE × 평→㎡ × 2층 계수 × 그 층 면적 — 건물 혼합 계수가 아니다
    rent = max(1, round(per_m2 * second["area"] * 3.3058 * 0.45 / 10))
    done = next(s for s in r["scenarios"].values() if s["available"])
    from app.services.posting_revenue import opex_rate
    assert abs(done["month_cost"] - (rent + done["month_rev"] * opex_rate(done["tier"]))) <= 1.5


def test_area_override_marks_user_input_and_scales():
    unit = svc.resolved_units("garosugil")[0]
    base = client.post(f"{API}/ai/simulate-revenue", json={"district_id": "garosugil", "unit_id": unit["id"]}).json()
    big = client.post(f"{API}/ai/simulate-revenue",
                      json={"district_id": "garosugil", "unit_id": unit["id"], "area_py_override": unit["area"] * 2}).json()
    assert big["inputs_source"]["area"] == "user_input"
    assert big["resolved_inputs"]["area_py"] == unit["area"] * 2
    assert big["resolved_inputs"]["rent_manwon"] > unit["rent"]
    k = next(k for k, s in base["scenarios"].items() if s["available"])
    assert big["scenarios"][k]["month_rev"] > base["scenarios"][k]["month_rev"]
    assert client.post(f"{API}/ai/simulate-revenue",
                       json={"district_id": "garosugil", "area_py_override": -1}).status_code == 422


def test_floor_units_stay_out_of_postings():
    assert not any(str(p["id"]).startswith("vfu-") for p in svc.get_postings("garosugil"))


def test_simulate_floor_unit_outside_seoul_stays_unavailable():
    fid = floor_vacancy.load("suwonst")["units"][0]["id"]
    r = posting.simulate("suwonst", fid)
    assert r["source"] == "unavailable" and r["scenarios"] == {} and r["unavailable_reason"]


def test_simulate_floor_unit_unknown_is_404():
    assert client.post(f"{API}/ai/simulate-revenue",
                       json={"district_id": "garosugil", "unit_id": "vfu-nope-1"}).status_code == 404


# ── 행사 ────────────────────────────────────────────────────────────────
def test_events_all_served_hubs_answer():
    """시드 문지기가 다시 서면 서빙 거점이 조용히 404 가 된다(63곳 실측 · 2026-11-02).

    2026-11-07 계약 변경 — ① 끝난 행사는 서빙 시점(오늘)에 빠진다(10-11 적재본은 11-07 에 66.5% 가 끝나
    있었다) ② 전국 행사 Gold(문화포털·TourAPI)가 덮는 거점은 서울 밖이어도 행사를 싣고 출처가
    "public-open-data" 다. 그래서 「Gold 건수 그대로」 대신 「끝난 행사 0 · 서울 행사는 Gold 에 있는 것만」을 본다.
    """
    from app.services import events as ev

    seoul_doc = json.loads((GOLD / "platform_events.json").read_text(encoding="utf-8"))["districts"]
    today = ev.today_kst()
    assert len(SERVED) >= 117
    for hub in SERVED:
        r = client.get(f"{API}/marketing/events", params={"district_id": hub})
        assert r.status_code == 200, hub
        body = r.json()
        d = svc.get_district(hub)
        covered = ev.national_covers(hub)
        if svc.page_city(d).has_city_events or covered:
            assert body["events_source"] == ("public-open-data" if covered else "seoul-open-data"), hub
            assert body["events_note"] is None, hub
            assert not any(ev.is_ended(e, today) for e in body["events"]), f"{hub}: 끝난 행사가 서빙됐다"
            seoul_ids = {e["id"] for e in seoul_doc.get(hub, [])}
            assert all(e["id"] in seoul_ids for e in body["events"] if e.get("src") == ev.SRC_SEOUL), hub
        else:
            assert body["events"] == [] and body["events_note"] and body["events_source"] == "none", hub
        assert client.get(f"{API}/marketing/{hub}").status_code == 200, hub


# ── 리포트 ─────────────────────────────────────────────────────────────
_SECTIONS = ("overview", "industry", "population", "sales", "openclose", "vacancy", "rent", "site", "competition",
             "posting", "events")
_INTERNAL = re.compile(r"gold/|bronze|silver/|\.json|\.geojson|\.parquet|[A-Za-z]:\\|data/config|mlruns|industry-gnn")


@pytest.mark.parametrize("hub", HUBS)
def test_report_small_clean_and_every_section_present(hub):
    fid = floor_vacancy.load(hub)["units"][0]["id"]
    r = client.get(f"{API}/commercial-districts/{hub}/report", params={"industry": "cafe", "unit_id": fid})
    assert r.status_code == 200
    assert len(r.content) <= 1_000_000
    assert not _INTERNAL.search(r.text), _INTERNAL.search(r.text).group(0)
    body = r.json()
    for name in _SECTIONS:
        s = body[name]
        assert s["status"] in ("ok", "unavailable"), name
        if s["status"] == "unavailable":
            assert s["note"] and s["data"] is None, name
    assert body["site"]["status"] == "ok" and body["competition"]["status"] == "ok"
    assert body["vacancy"]["status"] == "ok"


def test_report_seoul_only_sections_explain_themselves():
    from app.services import events as ev

    fid = floor_vacancy.load("suwonst")["units"][0]["id"]
    body = client.get(f"{API}/commercial-districts/suwonst/report", params={"unit_id": fid}).json()
    for name in ("population", "sales", "openclose"):
        assert body[name]["status"] == "unavailable" and "서울만" in body[name]["note"], name
    # 행사는 2026-11-07 부터 전국 행사 Gold 가 서울 밖도 덮는다 — 덮으면 싣고, 아니면 종전대로 「서울만」
    if ev.national_covers("suwonst"):
        assert body["events"]["status"] == "ok" and "서울 문화행사" not in (body["events"]["source"] or "")
    else:
        assert body["events"]["status"] == "unavailable" and "서울만" in body["events"]["note"]
    assert body["posting"]["status"] == "unavailable" and body["posting"]["note"]


def test_report_seoul_full_and_vacancy_counts_match_buildings():
    fid = floor_vacancy.load("garosugil")["units"][0]["id"]
    body = client.get(f"{API}/commercial-districts/garosugil/report",
                      params={"industry": "cafe", "unit_id": fid}).json()
    for name in ("population", "sales", "openclose", "posting"):
        assert body[name]["status"] == "ok", name
    features = client.get(f"{API}/heatmap/buildings", params={"district": "garosugil"}).json()["features"]
    assert sum(body["vacancy"]["data"]["building_classes"].values()) == len(features)
    assert body["industry"]["data"]["selected"]["fit_rank"]


def test_report_without_site_does_not_borrow_representative_unit():
    body = client.get(f"{API}/commercial-districts/garosugil/report").json()
    assert body["site"]["status"] == "unavailable"
    assert body["posting"]["status"] == "unavailable"


def test_report_bad_input():
    assert client.get(f"{API}/commercial-districts/nope/report").status_code == 404
    assert client.get(f"{API}/commercial-districts/garosugil/report", params={"industry": "nope"}).status_code == 422


# ── 주소 검색 GET ───────────────────────────────────────────────────────
def test_address_get_validates_and_reports_unconfigured(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "kakao_mobility_api_key", "")
    monkeypatch.setattr(settings, "kakao_rest_api_key", "")
    r = client.get(f"{API}/travel/addresses", params={"q": "서울 세종대로 110"})
    assert r.status_code == 200 and r.json() == {"status": "not_configured", "candidates": []}
    assert client.get(f"{API}/travel/addresses", params={"q": "x"}).status_code == 422
    assert client.get(f"{API}/travel/addresses", params={"q": "x" * 201}).status_code == 422
