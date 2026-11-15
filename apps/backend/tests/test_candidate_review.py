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
