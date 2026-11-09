"""광주·전주 조사 위치 레이어 — 서빙 거점과 섞이지 않고, 공실·순위·임대료를 말하지 않는가.

결정: docs/decision-research-locations-layer-2026-11-09.md
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services import districts as svc

client = TestClient(app)
API = "/api/v1/commercial-districts/research-locations"
GOLD = Path(__file__).resolve().parents[3] / "data" / "gold" / "platform_research_locations.json"
# 광주·전주 시 경계를 넉넉히 감싼 상자 — [lat, lng] 순서와 지역 뒤섞임을 잡는다.
BOX = {"gwangju": (34.9, 35.35, 126.6, 127.1), "jeonju": (35.7, 35.95, 126.95, 127.25)}
FORBIDDEN = ("vacancy", "rank", "rent", "score", "anchor")


def _doc() -> dict:
    return json.loads(GOLD.read_text(encoding="utf-8"))


def test_gold_is_observation_only_and_traceable():
    doc = _doc()
    assert doc["serving_eligible"] is False and doc["seed"] is False
    assert "정식 상권" in doc["note"] and "공실률" in doc["note"]
    locs = doc["locations"]
    assert locs and {loc["group"] for loc in locs} <= {"gwangju", "jeonju"}
    assert doc["counts"] == {g: sum(loc["group"] == g for loc in locs) for g in doc["counts"]}
    assert len({loc["id"] for loc in locs}) == len(locs)
    assert len({(loc["group"], loc["name"]) for loc in locs}) == len(locs), "지도 칩 이름이 겹친다"
    for loc in locs:
        assert len(loc["evidence"]["sha256"]) == 64 and loc["evidence"]["path"].endswith("ledger_evidence.json.gz")
        led = loc["ledger"]
        assert 0 <= led["pnus_with_commercial_floor"] <= led["pnus"]
        assert 0 <= led["pnus_without_ledger"] <= led["pnus"]
        assert not any(word in key for key in loc for word in FORBIDDEN), loc["id"]


def test_route_is_not_swallowed_and_matches_gold():
    r = client.get(API)
    assert r.status_code == 200
    body = r.json()
    assert len(body["locations"]) == len(_doc()["locations"])
    assert "정식 상권" in body["note"]
    for loc in body["locations"]:
        south, north, west, east = BOX[loc["group"]]
        assert south < loc["lat"] < north and west < loc["lng"] < east, loc["id"]


def test_group_filter_and_validation():
    gj = client.get(API, params={"group": "gwangju"}).json()["locations"]
    jj = client.get(API, params={"group": "jeonju"}).json()["locations"]
    assert gj and jj and {x["group"] for x in gj} == {"gwangju"} and {x["group"] for x in jj} == {"jeonju"}
    assert len(gj) + len(jj) == len(client.get(API).json()["locations"])
    assert client.get(API, params={"group": "seoul"}).status_code == 422


def test_never_overlaps_served_hubs():
    """조사 위치는 서빙 목록에 들어가지 않는다 — 거점 승격은 hub-chain 이 따로 한다."""
    served = {p["id"] for p in svc.PAGES}
    ids = {loc["id"] for loc in client.get(API).json()["locations"]}
    assert not ids & served
    assert all(i.startswith("research-") for i in ids)
