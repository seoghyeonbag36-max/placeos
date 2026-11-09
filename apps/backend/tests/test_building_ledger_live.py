"""트윈 건축물대장 실시간 조회(services/building_ledger_live) — 승강기 수 · 층별개요 용도별 행 (2026-11-09).

네트워크 없이: 행 요약(summarise) · 지번 파라미터 · 실패 사유 · 트윈 응답에 실리는지.
행 모양은 수집기가 bronze 에 남기는 건축HUB 응답 필드(mainAtchGbCdNm · totArea · flrGbCdNm · flrNo · mainPurpsCdNm · etcPurps · area)다.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services import building_ledger_live as L

client = TestClient(app)

TITLES = [
    {"dongNm": "", "mainAtchGbCdNm": "주건축물", "totArea": "580.5", "rideUseElvtCnt": "1", "emgenUseElvtCnt": "0",
     "grndFlrCnt": "5", "ugrndFlrCnt": "1", "heit": "17.43", "strctCdNm": "철근콘크리트구조"},
    {"dongNm": "", "mainAtchGbCdNm": "부속건축물", "totArea": "900", "rideUseElvtCnt": "3", "emgenUseElvtCnt": "1"},
]
FLOORS = [
    {"dongNm": "", "flrGbCdNm": "지상", "flrNo": "4", "mainPurpsCdNm": "제2종근린생활시설", "etcPurps": "학원", "area": "100.2"},
    {"dongNm": "", "flrGbCdNm": "지상", "flrNo": "4", "mainPurpsCdNm": "제2종근린생활시설", "etcPurps": "계단실", "area": "14.3"},
    {"dongNm": "", "flrGbCdNm": "지하", "flrNo": "1", "mainPurpsCdNm": "주차장", "etcPurps": "", "area": "124.8"},
    {"dongNm": "", "flrGbCdNm": "옥탑", "flrNo": "1", "mainPurpsCdNm": "계단실", "etcPurps": "", "area": "12"},
]


def test_jibun_from_pnu():
    assert L.jibun_of("1123010800100160081") == {"sigunguCd": "11230", "bjdongCd": "10800", "platGbCd": "0", "bun": "0016", "ji": "0081"}
    assert L.jibun_of("1123010800200160081")["platGbCd"] == "1"     # 산
    assert L.jibun_of("vu-123") is None


def test_summary_counts_elevators_from_main_building_and_floor_parts():
    s = L.summarise(TITLES, FLOORS)
    assert s["elevators"] == {"passenger": 1, "emergency": 0}       # 부속건축물이 더 커도 주건축물
    assert s["title"]["height_m"] == 17.43 and s["title"]["n_titles"] == 2
    f4 = s["floors"]["4"]
    assert [p["etc"] for p in f4["parts"]] == ["학원", "계단실"] and f4["stair_m2"] == 14.3 and f4["ev_m2"] is None
    assert s["floors"]["-1"]["parts"][0]["purps"] == "주차장"
    assert "1" not in s["floors"] or s["floors"]["1"]["parts"]            # 옥탑 행은 층 번호로 쓰지 않는다


def test_missing_elevator_fields_are_reported_not_zeroed():
    s = L.summarise([{"mainAtchGbCdNm": "주건축물", "totArea": "100"}], [])
    assert s["elevators"] is None and s["fields_missing"] is True


def test_no_key_and_offline_are_soft(monkeypatch):
    monkeypatch.setattr(L.settings, "data_go_kr_service_key", "", raising=False)
    assert L.ledger("1123010800100160081")["status"] == "no_key"
    monkeypatch.setattr(L.settings, "data_go_kr_service_key", "dummy", raising=False)
    first = L.ledger("1123010800100160081")
    assert first["status"] == "error" and first["elevators"] is None
    assert L.ledger("1123010800100160081")["status"] == "backoff"


def test_refused_key_message_is_kept(monkeypatch):
    monkeypatch.setattr(L.settings, "data_go_kr_service_key", "dummy", raising=False)
    monkeypatch.setattr(L, "_fetch", lambda op, j, k: (_ for _ in ()).throw(L.LedgerError("SERVICE_KEY_IS_NOT_REGISTERED_ERROR")))
    out = L.ledger("1123010800100160081")
    assert out["status"] == "refused" and "NOT_REGISTERED" in out["error"]


def test_twin_carries_ledger_live(monkeypatch):
    monkeypatch.setattr(L.settings, "data_go_kr_service_key", "dummy", raising=False)
    monkeypatch.setattr(L, "_fetch", lambda op, j, k: TITLES if op == "getBrTitleInfo" else FLOORS)
    body = client.get("/api/v1/buildings/1123010800100160081-1/twin", params={"district": "kyunghee"}).json()
    lv = body["ledger_live"]
    assert lv["status"] == "ok" and lv["elevators"] == {"passenger": 1, "emergency": 0}
    assert lv["floors"]["4"]["stair_m2"] == 14.3
    assert body["floors"]                                             # 트윈 본체는 그대로
