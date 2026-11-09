"""리뉴얼 Gold(점포 요약·체인 추정·동시 입지·전 층·외곽선·R-ONE 시계열·유형)의 존재·스키마·정합."""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import pytest

from data.config.hub_types import HUB_TYPE_FROM_DATA, HUB_TYPES, TYPE_NAMES, type_of
from data.config.page_hubs import ACTIVE_HUBS
from data.pipelines.build_building_floors import (
    FLOOR_FIELDS,
    floor_of_row,
    fold_floors,
    parse_floor,
    pnu_of_building_id,
)
from data.pipelines.build_hub_outlines import _heatmap_service, outline
from data.pipelines.build_rone_history import series_by_hub
from data.pipelines.build_stores_lite import (
    LITE_FIELDS,
    LITE_FIELDS_V1,
    BrandMatcher,
    industry_of,
    lite_doc,
    name_key,
    store_floor,
    store_ho,
)

GOLD = Path(__file__).resolve().parents[1] / "gold"
MB = 1_000_000
HUBS = list(ACTIVE_HUBS)
# R-ONE 소규모 임대 표본이 없는 상권과 그 앵커를 공유하는 거점. 값은 null로 남긴다.
# 2026-11-03 공개 36곳 중 5곳도 같은 원천 결측이다(중대형 공실 앵커는 있다).
NO_RENT_HUBS = {"ajou", "yeongtong", "dandae", "gj-eoryong", "gj-usan", "gj-ilgok", "jj-newtown",
                "pyeongtaekcity", "gwangnam", "yatap", "jeongja", "maetan"}


def _json(name: str) -> dict:
    return json.loads((GOLD / name).read_text(encoding="utf-8"))


def _gz(slug: str, name: str) -> dict:
    with gzip.open(GOLD / slug / name, "rt", encoding="utf-8") as fh:
        return json.load(fh)


# ── 층 표기 ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,want", [
    ("지1층", ("B", 1)), ("지2", ("B", 2)), ("B1", ("B", 1)), ("B2층", ("B", 2)), ("지하1층", ("B", 1)),
    ("지-1층", ("B", 1)), ("지하층", ("B", None)), ("지층", ("B", None)), ("지하", ("B", None)),
    ("옥탑", ("R", None)), ("옥탑층", ("R", None)), ("옥탑1층", ("R", 1)), ("옥탑 2층", ("R", 2)), ("옥1", ("R", 1)),
    ("옥상", ("R", None)),
    ("1층", ("G", 1)), ("3", ("G", 3)), ("지상5층", ("G", 5)), ("지상2", ("G", 2)), ("10 층", ("G", 10)),
    ("일층", ("G", 1)), ("삼층", ("G", 3)), ("2층(증축)", ("G", 2)), ("(기존)4층", ("G", 4)), ("(지상2층)", ("G", 2)),
    ("A동3층", ("G", 3)), ("2동 5층", ("G", 5)), ("3층이상", ("G", 3)), ("2층101호", ("G", 2)),
    ("101호", ("?", None)), ("1-2호", ("?", None)), ("각층", ("?", None)), ("", ("?", None)), (None, ("?", None)),
    ("301", ("?", None)), ("1,2층", ("?", None)),
])
def test_parse_floor(raw, want):
    assert parse_floor(raw) == want


def test_floor_of_row_prefers_structured_values():
    assert floor_of_row({"flrGbCdNm": "지하", "flrNo": 2, "flrNoNm": "지2층"}) == ("B", 2)
    assert floor_of_row({"flrGbCdNm": "옥탑", "flrNo": 1, "flrNoNm": "옥탑"}) == ("R", 1)
    assert floor_of_row({"flrGbCdNm": "지하", "flrNo": 0, "flrNoNm": "지층"}) == ("B", None)
    assert floor_of_row({"flrGbCdNm": "지상", "flrNo": 0, "flrNoNm": "A"}) == ("G", None)


def test_fold_floors_keeps_dongs_apart_and_sums_within_floor():
    rows = [
        {"dongNm": "A동", "flrGbCdNm": "지상", "flrNo": 1, "flrNoNm": "1층", "area": 10, "mainPurpsCdNm": "소매점"},
        {"dongNm": "A동", "flrGbCdNm": "지상", "flrNo": 1, "flrNoNm": "1층", "area": 30, "mainPurpsCdNm": "음식점"},
        {"dongNm": "B동", "flrGbCdNm": "지상", "flrNo": 1, "flrNoNm": "1층", "area": 5, "mainPurpsCdNm": "사무소"},
        {"dongNm": "A동", "flrGbCdNm": "지하", "flrNo": 1, "flrNoNm": "지1층", "area": 7, "mainPurpsCdNm": "주차장"},
        {"dongNm": "A동", "flrGbCdNm": "지상", "flrNo": 2, "flrNoNm": "2층", "area": 8, "mainPurpsCdNm": "사무소"},
    ]
    i = {name: FLOOR_FIELDS.index(name) for name in FLOOR_FIELDS}
    got = fold_floors(rows)
    assert [(r[i["dong"]], r[i["kind"]], r[i["no"]]) for r in got] == [
        ("A동", "G", 2), ("A동", "G", 1), ("A동", "B", 1), ("B동", "G", 1)]
    assert got[1][i["area_m2"]] == 40
    assert got[1][i["purps"]] == "음식점"


def test_building_id_join_rule():
    pnu = "1168010700105160014"
    assert pnu_of_building_id(f"{pnu}-1") == pnu
    assert pnu_of_building_id(f"vu-{pnu}-3") == pnu
    assert pnu_of_building_id(f"vfu-{pnu}-2") == pnu


# ── 전 층 Gold ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("slug", HUBS)
def test_building_floors_hub(slug):
    doc = _gz(slug, "building_floors.json.gz")
    assert doc["slug"] == slug and doc["lots"] and doc["n_lots"] == len(doc["lots"])
    kind = FLOOR_FIELDS.index("kind")
    for pnu, lot in doc["lots"].items():
        assert re.fullmatch(r"\d{19}", pnu)
        assert all(len(f) == len(FLOOR_FIELDS) and f[kind] in "GBR?" for f in lot["floors"])


def test_building_floors_keeps_basements_and_joins_master():
    doc = _gz("garosugil", "building_floors.json.gz")
    kind = FLOOR_FIELDS.index("kind")
    assert sum(f[kind] == "B" for lot in doc["lots"].values() for f in lot["floors"]) > 100
    fc = json.loads((GOLD / "garosugil" / "page_building_master.geojson").read_text(encoding="utf-8"))
    ids = {pnu_of_building_id(f["properties"]["id"]) for f in fc["features"]}
    assert set(doc["lots"]) <= ids
    assert len(set(doc["lots"]) & ids) / len(ids) > 0.5


def test_building_floors_has_units_only_where_silver_had_them():
    with_units = sum(any("units" in lot for lot in _gz(s, "building_floors.json.gz")["lots"].values()) for s in HUBS)
    assert 40 <= with_units < len(HUBS)
    doc = _gz("garosugil", "building_floors.json.gz")
    unit = next(lot["units"][0] for lot in doc["lots"].values() if lot.get("units"))
    # 2026-11-08 pub_m2(공용면적) 열이 붙었다 — 재빌드 전 6열 · 후 7열. 행 길이는 그 파일의 unit_fields 와 같아야 한다.
    assert len(unit) == len(doc["unit_fields"]) in (6, 7) and unit[1] in "GBR?"


def test_building_floors_size_budget():
    total = sum((GOLD / s / "building_floors.json.gz").stat().st_size for s in HUBS)
    assert total <= 25 * MB


# ── 점포 요약 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("slug", HUBS)
def test_stores_lite_hub(slug):
    doc = _gz(slug, "stores_lite.json.gz")
    # 호수를 싣기 전 판(8칸)도 받는다 — 재빌드는 bronze 가 있는 수집 PC 몫이라 거점마다 시차가 난다(2026-11-09)
    assert doc["slug"] == slug and doc["fields"] in (LITE_FIELDS, LITE_FIELDS_V1) and doc["n"] == len(doc["rows"]) > 0
    head = doc["rows"][0]
    assert len(head) == len(doc["fields"])
    lat, lng = head[LITE_FIELDS.index("lat")], head[LITE_FIELDS.index("lng")]
    assert round(lat, 5) == lat and 33 < lat < 39 and 124 < lng < 132


def test_stores_lite_size_budget_and_no_private_fields():
    assert sum((GOLD / s / "stores_lite.json.gz").stat().st_size for s in HUBS) <= 15 * MB
    # 전화는 싣지 않는다. 호수(ho)는 2026-11-09 사용자 요청으로 싣는다 — 점포 위치(공공데이터)이지 개인 정보가 아니다.
    assert not {"hoNo", "tel", "phone", "telNo"} & set(LITE_FIELDS)
    assert LITE_FIELDS[: len(LITE_FIELDS_V1)] == LITE_FIELDS_V1   # 앞 칸 자리를 바꾸지 않는다(위치로 읽는 소비자)


@pytest.mark.parametrize("raw,want", [("101호", "101호"), (" B 01 ", "B01"), ("", None), (None, None), ("１０１", "101")])
def test_store_ho(raw, want):
    assert store_ho(raw) == want


def test_lite_doc_keeps_ho_and_counts_it():
    rows = [
        {"bizesId": "a", "bizesNm": "카페A", "lat": 37.5, "lon": 127.0, "flrNo": "2", "hoNo": "201호", "lnoCd": "1"},
        {"bizesId": "b", "bizesNm": "학원B", "lat": 37.5, "lon": 127.0, "flrNo": "", "hoNo": "", "lnoCd": "1"},
    ]
    doc = lite_doc("t", rows, None, BrandMatcher({}))
    ho = LITE_FIELDS.index("ho")
    assert doc["fields"] == LITE_FIELDS and doc["n_with_ho"] == 1
    assert {r[0]: r[ho] for r in doc["rows"]} == {"카페A": "201호", "학원B": None}


@pytest.mark.parametrize("raw,want", [("1", 1), ("B1", -1), ("지", -99), ("", None), (None, None), ("401", None)])
def test_store_floor(raw, want):
    assert store_floor(raw) == want


def test_name_key_strips_branch_and_corp():
    assert name_key("스타벅스 신사역점") == "스타벅스"
    assert name_key("스타벅스 신사역점", "신사역점") == "스타벅스"
    assert name_key("(주)이디야 강남") == "이디야강남"
    assert name_key("한국맥도날드 청담점") == "맥도날드"


def test_manual_ascii_prefix_stops_at_word_boundary():
    m = BrandMatcher({})
    assert m._manual("cu압구정", "소매") == "CU"
    assert m._manual("cu", "소매") == "CU"
    assert m._manual("cube", "소매") is None
    assert m._manual("씨유서초", "소매") == "CU"
    assert m._manual("씨유서초", "교육") is None


def test_industry_of_codes():
    assert industry_of("I21201") == "cafe"
    assert industry_of("I20701") is None
    assert industry_of("L10201") is None


# ── 체인 추정 ────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def brands() -> dict:
    return _json("platform_store_brands.json")


@pytest.mark.parametrize("name", ["스타벅스", "이디야커피", "메가MGC커피", "CU", "GS25", "파리바게뜨", "올리브영", "다이소",
                                  "컴포즈커피", "세븐일레븐", "BBQ", "맘스터치"])
def test_representative_brands_caught(brands, name):
    assert name in brands["brands"]


@pytest.mark.parametrize("name", ["김밥", "미용실", "분식", "카페", "커피", "치킨", "호프", "부동산", "약국", "슈퍼", "곱창",
                                  "휴식", "전자담배", "복권", "더카페", "명동칼국수", "업소명없음"])
def test_generic_names_not_caught(brands, name):
    assert name not in brands["brands"]


def test_brand_table_schema(brands):
    assert brands["label"] == "체인 추정" and brands["criteria"]
    assert set(v["basis"] for v in brands["brands"].values()) == {"ftc", "repeat", "manual"}
    assert (GOLD / "platform_store_brands.json").stat().st_size <= 3 * MB
    row = brands["brands"]["스타벅스"]
    assert row["n"] > 100 and row["n_sigungu"] > 10


# ── 동시 입지 ────────────────────────────────────────────────────────────
def test_colocation_doc():
    doc = _json("platform_industry_colocation.json")
    assert (GOLD / "platform_industry_colocation.json").stat().st_size <= 3 * MB
    assert doc["label"] == "함께 모이는 업종(관측)"
    assert {"seoul", "gwangju"} <= set(doc["scopes"])
    seoul = doc["scopes"]["seoul"]
    assert "cafe" in seoul["industries"] and seoul["details"]
    for val in seoul["industries"].values():
        assert len(val["top"]) <= 5
        for row in val["top"]:
            assert row["lift"] >= row["lift_lo"] > 1 and row["n_both"] >= doc["min_sample"]["cells_both"]


# ── 외곽선 ───────────────────────────────────────────────────────────────
def _cells(*ij):
    """서버(`gold_vacancy.build_cells`) 규약 — `i` = 위도(남→북) 칸 · `j` = 경도(서→동) 칸.

    2026-11-08 까지 이 픽스처가 거꾸로(`i` = 경도) 만들어, 같은 착오를 한 `outline` 과 맞물려 통과했다.
    """
    d = 0.001
    return [{"i": i, "j": j, "lat": 37 + i * d, "lng": 127 + j * d, "dlat": d, "dlng": d} for i, j in ij]


def _in_ring(lat: float, lng: float, ring: list[list[float]]) -> bool:
    """짝홀 규칙 점-다각형 판정. 링은 `[lat, lng]` 순."""
    inside = False
    for (y1, x1), (y2, x2) in zip(ring, ring[1:] + ring[:1]):
        if (x1 > lng) != (x2 > lng) and lat < (y2 - y1) * (lng - x1) / (x2 - x1) + y1:
            inside = not inside
    return inside


def _covers(pieces: list[dict], lat: float, lng: float) -> bool:
    return any(_in_ring(lat, lng, p["outer"]) and not any(_in_ring(lat, lng, h) for h in p["holes"])
               for p in pieces)


def test_outline_reads_latlng_not_index_axes():
    """비대칭 L자(동쪽 3칸 + 서쪽 끝 위 1칸) — 외곽선이 셀 자리에 서고, i·j 를 뒤바꿔 넣어도 같다.

    정사각형은 뒤집혀도 같은 모양이라 축 착오를 못 잡는다(2026-11-08 · 실셀과 같은 거점 0/158).
    """
    cells = _cells((0, 0), (0, 1), (0, 2), (1, 0))
    doc = outline(cells)
    outer = doc["pieces"][0]["outer"]
    lats, lngs = [p[0] for p in outer], [p[1] for p in outer]
    assert (min(lats), max(lats), min(lngs), max(lngs)) == (37.0, 37.002, 127.0, 127.003)
    assert [37.001, 127.001] in outer                       # L자의 오목한 꼭짓점
    assert not _covers(doc["pieces"], 37.0015, 127.0025)    # 빠진 북동쪽 칸은 밖
    assert outline([{**c, "i": c["j"], "j": c["i"]} for c in cells]) == doc


def test_outline_merges_square_and_drops_collinear():
    doc = outline(_cells((0, 0), (1, 0), (0, 1), (1, 1)))
    assert doc["components"] == 1 and doc["cells"] == 4
    assert len(doc["pieces"][0]["outer"]) == 4 and doc["pieces"][0]["holes"] == []
    assert [37.0, 127.0] in doc["pieces"][0]["outer"] and [37.002, 127.002] in doc["pieces"][0]["outer"]


def test_outline_keeps_separate_pieces_and_holes():
    ring = [(i, j) for i in range(3) for j in range(3) if (i, j) != (1, 1)]
    doc = outline(_cells(*ring, (9, 9)))
    assert doc["components"] == 2 and len(doc["pieces"]) == 2
    assert doc["pieces"][0]["cells"] == 8 and len(doc["pieces"][0]["holes"]) == 1
    assert doc["largest_share"] == pytest.approx(88.9)


def test_outline_empty():
    assert outline([]) is None


def test_outlines_gold():
    doc = _json("platform_hub_outlines.json")
    assert (GOLD / "platform_hub_outlines.json").stat().st_size <= 3 * MB
    assert "공식 상권 경계가 아니" in doc["note"]
    assert set(doc["hubs"]) == set(HUBS)
    for hub in doc["hubs"].values():
        assert hub["pieces"] and all(len(p["outer"]) >= 4 for p in hub["pieces"])
        lat, lng = hub["pieces"][0]["outer"][0]
        assert round(lat, 5) == lat and 33 < lat < 39 and 124 < lng < 132


def test_outlines_gold_cover_exactly_the_measured_cells():
    """저장된 외곽선이 **실제 셀 자리**를 덮는가 — 셀 중심은 전부 안, 셀이 아닌 격자 칸 중심은 전부 밖.

    합성 셀 테스트만으로는 축 착오를 못 잡았다. 2026-11-08 에 실셀과 대조하자 정확히 같은 거점이
    0/158 이었고, 왕십리는 Page 공실 점 242개 중 4개만 Platform 범위 안이었다. 점-다각형 판정은
    `outline` 알고리즘과 무관하게 저장본만 읽는다 — 셀 Gold 를 새로 빌드하고 외곽선을 안 다시 만들어도 여기서 걸린다.
    """
    svc = _heatmap_service()
    bad: list[str] = []
    for slug, hub in _json("platform_hub_outlines.json")["hubs"].items():
        cells = svc.get_vacancy_heatmap(slug)["cells"]
        dlat, dlng = cells[0]["dlat"], cells[0]["dlng"]
        lat0, lng0 = min(c["lat"] for c in cells), min(c["lng"] for c in cells)
        filled = {(round((c["lng"] - lng0) / dlng), round((c["lat"] - lat0) / dlat)) for c in cells}
        xs, ys = [x for x, _ in filled], [y for _, y in filled]
        wrong = [(x, y) for x in range(min(xs) - 1, max(xs) + 2) for y in range(min(ys) - 1, max(ys) + 2)
                 if _covers(hub["pieces"], lat0 + (y + .5) * dlat, lng0 + (x + .5) * dlng) != ((x, y) in filled)]
        pts = [p for piece in hub["pieces"] for p in piece["outer"]]
        bbox = (min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts))
        want = (lat0, lat0 + (max(ys) + 1) * dlat, lng0, lng0 + (max(xs) + 1) * dlng)
        if wrong or any(abs(a - b) > 1e-5 for a, b in zip(bbox, want)):
            bad.append(f"{slug}(어긋난 칸 {len(wrong)})")
    assert not bad, f"외곽선이 실측 셀과 다르다 {len(bad)}곳: {bad[:8]} — python -m data.pipelines.build_hub_outlines"


# ── R-ONE 시계열 ─────────────────────────────────────────────────────────
def test_series_prefers_newest_table_and_skips_null():
    rows = [
        {"district_id": "a", "quarter": "20243", "value": 1.0, "statbl_id": "A_2024_00275"},
        {"district_id": "a", "quarter": "20243", "value": 2.0, "statbl_id": "T248"},
        {"district_id": "a", "quarter": "20244", "value": None, "statbl_id": "T248"},
    ]
    assert series_by_hub(rows) == {"a": {"20243": 2.0}}


def test_rone_history_gold():
    doc = _json("platform_rone_history.json")
    posting = _json("platform_posting_inputs.json")
    assert (GOLD / "platform_rone_history.json").stat().st_size <= 3 * MB
    assert doc["quarters"][-1] == posting["quarter"]
    assert len(doc["quarters"]) == 22 and doc["quarters"][0] == "20211"
    assert set(doc["hubs"]) == set(HUBS)
    assert doc["floor_factor"] == posting["floor_factor"]
    no_rent = {s for s, h in doc["hubs"].items() if not h["rent_per_m2"]}
    assert no_rent == NO_RENT_HUBS
    for slug, h in doc["hubs"].items():
        for key in ("rent_per_m2", "vacancy_mid_pct", "vacancy_small_pct"):
            assert h[key] is None or len(h[key]) == len(doc["quarters"])
        if h["source"] == "rone-shared":
            assert h["shared_from"] == h["rone_cls"]


def test_rone_history_matches_posting_inputs_without_fallback():
    doc = _json("platform_rone_history.json")
    posting = _json("platform_posting_inputs.json")["districts"]
    compared = 0
    for slug, h in doc["hubs"].items():
        if h["rent_per_m2"] is None:
            assert posting.get(slug, {}).get("rent_per_m2_krw_thousand") is None
            continue
        latest = next(v for v in reversed(h["rent_per_m2"]) if v is not None)
        assert latest == pytest.approx(posting[slug]["rent_per_m2_krw_thousand"], abs=0.011), slug
        compared += 1
    assert compared == len(HUBS) - len(NO_RENT_HUBS)


# ── 유형 라벨 ────────────────────────────────────────────────────────────
def test_hub_types_cover_exactly_seoul():
    seoul = {s for s, h in ACTIVE_HUBS.items() if h.city == "seoul"}
    assert set(HUB_TYPES) == seoul and len(seoul) == 81
    assert set(HUB_TYPES.values()) <= set(TYPE_NAMES) and len(TYPE_NAMES) == 10
    assert HUB_TYPE_FROM_DATA < set(HUB_TYPES)
    assert type_of("garosugil") is not None and type_of("myeongdong") == ("T1", "도심 관광·쇼핑")
    assert type_of("unjeong") is None
