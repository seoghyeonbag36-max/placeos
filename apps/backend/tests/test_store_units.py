"""트윈 호실 ↔ 상가정보 점포 대조(services/store_units) — 2026-11-09.

네트워크 없이: 호 정규화 · 층 · 호 대조 규칙 · 「기록 없음」을 공실로 단정하지 않는지 · Gold 대안 · 트윈 응답에 실리는지.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services import store_units as S

client = TestClient(app)


def _floors():
    return [
        {"lv": 2, "units": [{"ho": "201호", "area_m2": 40}, {"ho": "202호", "area_m2": 30}]},
        {"lv": 1, "units": [{"ho": "101", "area_m2": 50}]},
        {"lv": 3, "units": None},
    ]


def test_ho_key_normalisation():
    assert S.ho_key("201호") == S.ho_key(" 201 ") == S.ho_key("2층201호") == S.ho_key("0201") == "201"
    assert S.ho_key("A호") == "a" and S.ho_key("") is None and S.ho_key(None) is None


def test_matches_same_floor_and_ho_only_and_lists_floor_stores():
    floors = _floors()
    found = {"status": "ok", "source": "x", "has_ho": True, "stores": [
        {"name": "카페A", "ind": "카페", "floor": 2, "ho": "201"},       # 2층 201호와 맞는다
        {"name": "학원B", "ind": "학원", "floor": 1, "ho": "202"},       # 층이 달라 202호와 맞추지 않는다
        {"name": "식당C", "ind": "한식", "floor": None, "ho": "101"},    # 층 미상 — 101 이 건물에 하나뿐이라 맞춘다
        {"name": "사무D", "ind": None, "floor": 3, "ho": None},           # 호실 없는 층 — 층 목록에만
    ]}
    out = S.annotate(floors, found)
    f2, f1, f3 = floors
    assert f2["units"][0]["store"]["name"] == "카페A" and f2["units"][1]["store"] is None
    assert f1["units"][0]["store"]["name"] == "식당C"
    assert [s["name"] for s in f3["stores"]] == ["사무D"]
    assert out["units_total"] == 3 and out["units_matched"] == 2 and out["has_ho"] is True and out["n_with_ho"] == 3
    # 3층의 사무D 는 호가 없지만 3층엔 호실이 없다 — 2층 202호의 「기록 없음」은 뜻이 있다
    assert f2["units"][1]["store_checked"] is True and out["units_unchecked"] == 0


def test_store_without_ho_on_the_floor_makes_absence_unknown():
    floors = _floors()
    out = S.annotate(floors, {"status": "ok", "source": "x", "has_ho": True, "stores": [
        {"name": "카페A", "ind": "카페", "floor": 2, "ho": "201"},
        {"name": "호없음", "ind": "학원", "floor": 2, "ho": ""},          # 2층 어느 호실인지 모른다
    ]})
    f2, f1, _ = floors
    assert f2["units"][0]["store"]["name"] == "카페A" and f2["units"][0]["store_checked"] is True
    assert f2["units"][1]["store"] is None and f2["units"][1]["store_checked"] is False   # 202호 — 대조 불가
    assert f1["units"][0]["store_checked"] is True                                       # 1층 — 대조됨 · 기록 없음
    assert out["units_unchecked"] == 1


def test_floor_unknown_store_without_ho_blinds_every_floor():
    floors = _floors()
    out = S.annotate(floors, {"status": "ok", "source": "x", "has_ho": True,
                              "stores": [{"name": "층모름", "ind": None, "floor": None, "ho": None}]})
    assert all(u["store_checked"] is False for f in floors for u in (f["units"] or []))
    assert out["units_unchecked"] == 3 and out["n_with_ho"] == 0


def test_without_ho_no_unit_matching_but_floor_lists():
    floors = _floors()
    out = S.annotate(floors, {"status": "gold", "source": "g", "has_ho": False,
                              "stores": [{"name": "카페A", "ind": "카페", "floor": 2, "ho": None}]})
    assert all(u["store"] is None and u["store_checked"] is False for f in floors for u in (f["units"] or []))
    assert floors[0]["stores"][0]["name"] == "카페A" and out["units_matched"] == 0


def test_live_filters_to_the_lot_and_is_soft_on_failure(monkeypatch):
    monkeypatch.setattr(S.settings, "data_go_kr_service_key", "dummy", raising=False)
    monkeypatch.setattr(S, "_fetch_live", lambda lat, lng, key, radius=60: [
        {"bizesNm": "카페A", "indsSclsNm": "카페", "lnoCd": "1123010800100160081", "flrNo": "4", "hoNo": "401"},
        {"bizesNm": "옆건물", "indsSclsNm": "한식", "lnoCd": "1123010800100160082", "flrNo": "1", "hoNo": ""},
    ])
    got = S.stores_for("kyunghee", "1123010800100160081", 37.59, 127.05)
    assert got["status"] == "ok" and [s["name"] for s in got["stores"]] == ["카페A"] and got["stores"][0]["floor"] == 4


def test_radius_covers_the_outline():
    lat, lng = 37.5, 127.0
    assert S.radius_for(lat, lng, None) == S.RADIUS_M                                 # 외곽선이 없으면 기본
    assert S.radius_for(lat, lng, [[lat + 0.0009, lng]]) == 130                       # 약 100m 끝 + 30m
    assert S.radius_for(lat, lng, [[lat + 0.01, lng]]) == S.RADIUS_MAX_M              # 상한


def test_falls_back_to_gold_when_live_is_down(monkeypatch):
    monkeypatch.setattr(S.settings, "data_go_kr_service_key", "", raising=False)
    got = S.stores_for("kyunghee", "1123010800100160081", 37.59, 127.05)
    assert got["status"] == "gold" and got["live_status"] == "no_key" and got["source"] == S.SOURCE_GOLD


def test_twin_carries_stores_live():
    body = client.get("/api/v1/buildings/1123010800100160081-1/twin", params={"district": "kyunghee"}).json()
    sl = body["stores_live"]
    assert sl["status"] in ("gold", "ok") and "units_matched" in sl
    assert all("stores" in f for f in body["floors"])
