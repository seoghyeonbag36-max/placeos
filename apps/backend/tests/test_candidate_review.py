"""외부 자료의 범위·결측을 보존하는 후보 확인 계약. 네트워크는 별도 실호출로 확인한다."""
from fastapi.testclient import TestClient

from app.main import app
from app.services import candidate_review as service


def test_missing_building_does_not_call_external(monkeypatch):
    monkeypatch.setattr(service.building_twin, "twin", lambda *_: None)
    monkeypatch.setattr(service.building_ledger_live, "ledger", lambda *_: (_ for _ in ()).throw(AssertionError()))
    assert service.review("a", "b") is None


def test_wrong_floor_does_not_attach_other_candidate_evidence(monkeypatch):
    monkeypatch.setattr(service.building_twin, "twin", lambda *_: {"floors": [{"unit_id": "floor-a", "lv": 1}]})
    assert service.review("a", "b", "floor-b") is None


def test_failed_external_keeps_unknown_and_official_links(monkeypatch):
    monkeypatch.setattr(service.building_twin, "twin", lambda *_: {"floors": []})
    monkeypatch.setattr(service.building_ledger_live, "ledger", lambda *_: {"status": "no_key"})
    result = TestClient(app).get("/api/v1/buildings/1168010800100060013-1/candidate-review?district=garosugil")
    assert result.status_code == 200
    doc = result.json()
    assert doc["permission"] is None and doc["source_date"] is None
    assert doc["facts"] == [] and doc["ledger_status"] == "no_key"
    assert doc["regulation_status"] == "missing_inputs"
    assert any("eum.go.kr" in s["url"] for s in doc["sources"])


def test_multiple_buildings_do_not_inherit_main_building_facts(monkeypatch):
    monkeypatch.setattr(service.building_twin, "twin", lambda *_: {"floors": []})
    monkeypatch.setattr(service.building_ledger_live, "ledger", lambda *_: {"status": "ok", "title": {"n_titles": 2, "grnd": 9}})
    result = service.review("a", "1168010800100060013-1")
    assert result.facts == []
    assert "대표 동" in result.ledger_note


def test_selected_floor_only_and_zero_is_not_missing(monkeypatch):
    monkeypatch.setattr(service.building_twin, "twin", lambda *_: {"floors": [{"unit_id": "f2", "lv": 2}]})
    monkeypatch.setattr(service.building_ledger_live, "ledger", lambda *_: {
        "status": "ok", "title": {"n_titles": 1, "ugrnd": 0},
        "floors": {"1": {"parts": [{"purps": "다른 층"}]}, "2": {"parts": [{"purps": "근린생활시설"}]}},
    })
    result = service.review("a", "1168010800100060013-1", "f2")
    assert [f.value for f in result.facts] == ["0", "근린생활시설"]
    assert result.permission is None


# ── 입점 점검 연결(2026-11-15 · 인계 문서 2-B) ───────────────────────────────

PNU = "1168010800100060013"
LAW_4JA = {"ho": 4, "mok": "자", "ref": "건축법 시행령 별표 1 제4호자목", "d": 0, "min": None, "max": None}
INPUTS = {
    "basis": {"vworld_updated_max": "2026-11-06", "eum_fetched": "2026-11-15"},
    "zone_names": {"UQA220": "일반상업지역"},
    "parcels": {PNU: [["UQA220", "포함"]]},
    "acts": {"11680": {"일반음식점": {"UQA220": [{"reg": "가능", "c": [], "laws": [LAW_4JA]}]}}},
    "conds": [], "defs": [],
}


def _floor_candidate(monkeypatch, parts, n_titles=1):
    from app.services import use_check

    monkeypatch.setattr(use_check, "_load", lambda: INPUTS)
    monkeypatch.setattr(service.building_twin, "twin", lambda *_: {"floors": [
        {"unit_id": "f2", "lv": 2, "area_m2": 120.0, "purps": "소매점"}]})
    monkeypatch.setattr(service.building_ledger_live, "ledger", lambda *_: {
        "status": "ok", "title": {"n_titles": n_titles}, "floors": {"2": {"parts": parts}}})


def test_industry_fills_regulation_from_use_check(monkeypatch):
    """1종 근생 소매점 층에 음식점 → 대장상 용도 변경 필요. 허가는 여전히 만들지 않는다."""
    _floor_candidate(monkeypatch, [
        {"purps": "사무소", "code": "14204", "area_m2": 300.0},     # 더 넓은 다른 행 — 자리의 용도로 좁혀 무시된다
        {"purps": "소매점", "code": "03001", "area_m2": 120.0},
    ])
    r = service.review("garosugil", f"{PNU}-1", "f2", "restaurant")
    assert r.regulation_status == "use_change_needed" and r.industry == "restaurant"
    assert r.use_check is not None and "용도 변경" in r.regulation_note
    ledger_item = next(c for c in r.use_check.checks if c.item == "대장 층 용도")
    assert "소매점" in ledger_item.reason and "사무소" not in ledger_item.reason.split("(같은 층")[0]
    assert "허가 판정이 아닙니다" in r.regulation_note and r.permission is None
    assert any("law.go.kr" in s.url for s in r.sources)


def test_no_industry_keeps_missing_inputs(monkeypatch):
    _floor_candidate(monkeypatch, [{"purps": "소매점", "code": "03001", "area_m2": 120.0}])
    r = service.review("garosugil", f"{PNU}-1", "f2")
    assert r.regulation_status == "missing_inputs" and r.use_check is None


def test_building_candidate_and_multi_dong_are_not_judged(monkeypatch):
    _floor_candidate(monkeypatch, [{"purps": "소매점", "code": "03001", "area_m2": 120.0}])
    r = service.review("garosugil", f"{PNU}-1", None, "restaurant")
    assert r.regulation_status == "missing_inputs" and "층을 골라" in r.regulation_note
    _floor_candidate(monkeypatch, [{"purps": "소매점", "code": "03001", "area_m2": 120.0}], n_titles=2)
    r = service.review("garosugil", f"{PNU}-1", "f2", "restaurant")
    assert r.regulation_status == "missing_inputs" and r.use_check is None and "건물이 여럿" in r.regulation_note


def test_api_industry_round_trip_and_unknown_industry(monkeypatch):
    _floor_candidate(monkeypatch, [{"purps": "소매점", "code": "03001", "area_m2": 120.0}])
    c = TestClient(app)
    base = f"/api/v1/buildings/{PNU}-1/candidate-review"
    j = c.get(base, params={"district": "garosugil", "unit_id": "f2", "industry": "restaurant"}).json()
    assert j["regulation_status"] == "use_change_needed" and j["use_check"]["industry"] == "restaurant"
    assert c.get(base, params={"district": "garosugil", "unit_id": "f2", "industry": "spaceship"}).status_code == 400
