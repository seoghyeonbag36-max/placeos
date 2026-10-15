"""대표 구 코드가 다른 구의 이력에 섞이는 회귀를 막는다."""
import json
from pathlib import Path

from data.pipelines import build_building_history as H


def test_address_uses_gu_and_dong_together():
    stores = [
        {"lnoAdr": "서울특별시 강남구 신사동 10", "lnoCd": "1168010700100100000"},
        {"lnoAdr": "서울특별시 은평구 신사동 10", "lnoCd": "1138010900100100000"},
        {"lnoAdr": "서울특별시 서초구 잠원동 9-4", "lnoCd": "1165010600100090004"},
    ]
    codes = H.address_codes(stores)
    assert H.address_pnu("서울특별시 강남구 신사동 10", codes) == "1168010700100100000"
    assert H.address_pnu("서울특별시 은평구 신사동 10", codes) == "1138010900100100000"
    assert H.address_pnu("서울 서초구 잠원동 9-4 지상1층", codes) == "1165010600100090004"


def test_unresolved_or_ambiguous_address_is_not_guessed():
    codes = {("강남구", "신사동"): {"1168010700", "1138010900"}}
    assert H.address_pnu("서울 강남구 신사동 10", codes) is None
    assert H.address_pnu("서울 서초구 잠원동 10", codes) is None
    assert H.address_pnu("신사동 10", codes) is None
    assert H.address_pnu("서울 강남구 도산대로 10", codes) is None
    unique = {("강남구", "신사동"): {"1168010700"}}
    assert H.address_pnu("서울 강남구 신사동 10-12345", unique) is None
    assert H.address_pnu("서울 강남구 신사동 10 - 미상", unique) is None


def test_mountain_and_numeric_dong_are_preserved():
    codes = {("중구", "을지로3가"): {"1114015500"}}
    assert H.address_pnu("서울 중구 을지로3가 산 10-2", codes) == "1114015500200100002"
    assert H.address_pnu("서울 중구 을지로3가 10-0", codes) == "1114015500100100000"


def test_complete_lot_survives_empty_detail_address_markers():
    codes = {("강남구", "신사동"): {"1168010700"}, ("강북구", "수유동"): {"1130510300"}}
    assert H.address_pnu("서울특별시 강남구 신사동 510-11 ---------", codes) == "1168010700105100011"
    assert H.address_pnu("서울특별시 강북구 수유동 191-30 ----호", codes) == "1130510300101910030"
    assert H.address_pnu("서울특별시 강남구 신사동 510-11 ----동 ----호", codes) == "1168010700105100011"


def test_parenthetical_lot_requires_same_dong_and_unique_parcel():
    codes = {("강북구", "미아동"): {"1130510100"}}
    assert H.address_pnu("서울 강북구 미아동 호 대지길 39(미아동 44-15)", codes) == "1130510100100440015"
    assert H.address_pnu("서울 강북구 미아동 호 송천길 38(미아동 450-64)", codes) == "1130510100104500064"
    assert H.address_pnu("서울 강북구 미아동 호 대지길 39(수유동 44-15)", codes) is None
    assert H.address_pnu("서울 강북구 미아동 (미아동 44-15)(미아동 45-1)", codes) is None


def test_broken_subnumber_and_multiple_lots_stay_unresolved():
    codes = {("서초구", "잠원동"): {"1165010600"}, ("영등포구", "여의도동"): {"1156011000"}}
    assert H.address_pnu("서울 서초구 잠원동 69-5 -10 쇼핑5동 지하", codes) is None
    assert H.address_pnu("서울 영등포구 여의도동 36-", codes) is None
    assert H.address_pnu("서울 영등포구 여의도동 37-", codes) is None
    assert H.address_pnu("서울 영등포구 여의도동 36--", codes) is None


def test_staged_build_reads_silver_and_preserves_gold(tmp_path, monkeypatch):
    bronze, gold = tmp_path / "bronze", tmp_path / "gold"
    raw = bronze / "test" / "2026-10-15"
    raw.mkdir(parents=True)
    target = gold / "test"
    target.mkdir(parents=True)
    pnu = "1165010600100090004"
    (target / "page_building_master.geojson").write_text(json.dumps({"features": [
        {"properties": {"id": "a", "pnu": pnu}},
        {"properties": {"id": "b", "pnu": pnu}},
    ]}), encoding="utf-8")
    original = target / "building_history.json"
    original.write_text('{"preserve":true}', encoding="utf-8")
    (raw / "stores_raw.json").write_text(json.dumps([
        {"lnoAdr": "서울 서초구 잠원동 9-4", "lnoCd": pnu}
    ]), encoding="utf-8")
    (raw / "licensing_biz.json").write_text(json.dumps([
        {"SITEWHLADDR": "서울 서초구 잠원동 9-4", "APVPERMYMD": "2001-01-01",
         "TRDSTATEGBN": "01", "BPLCNM": "원본 업소"},
        {"SITEWHLADDR": "서울 강남구 미상동 1", "APVPERMYMD": "2001-01-01"},
    ]), encoding="utf-8")
    monkeypatch.setattr(H, "BRONZE", bronze)
    monkeypatch.setattr(H, "GOLD", gold)
    staged = tmp_path / "staged"
    assert H.build("test", "2026-10-15", output_root=staged, silver_root=tmp_path / "silver")
    out = json.loads((staged / "test" / "building_history.json").read_text(encoding="utf-8"))
    assert out["buildings"] == {"a": pnu, "b": pnu}
    assert len(out["lots"][pnu]) == 1
    assert out["lots"][pnu][0]["source"] == "localdata"
    assert out["lots"][pnu][0]["end_date"] is None
    assert out["lots"][pnu][0]["closure_reason_summary"] is None
    assert original.read_text(encoding="utf-8") == '{"preserve":true}'
    silver = json.loads((tmp_path / "silver" / "test" / "licensing_lots.json").read_text(encoding="utf-8"))
    assert silver["rejected"] == {"unresolved_address": 1}


def test_missing_stores_fails_without_writing_history(tmp_path, monkeypatch):
    monkeypatch.setattr(H, "GOLD", tmp_path)
    licensing = tmp_path / "licensing.json"
    licensing.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(H, "latest_bronze", lambda slug, name: licensing if name == "licensing_biz.json" else None)
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "page_building_master.geojson").write_text('{"features":[]}', encoding="utf-8")
    assert not H.build("test", output_root=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_approved_26_records_are_present_in_shipped_gold():
    """Bronze가 없는 CI에서도 승인된 26건의 실제 Gold 보존을 검증한다."""
    root = Path(__file__).resolve().parents[2]
    silver = json.loads((root / "data/silver/history_recovery_26_2026-10-15.json").read_text(encoding="utf-8"))
    assert silver["source"] == "localdata"
    assert len(silver["rows"]) == 26
    for row in silver["rows"]:
        gold = json.loads((root / "data/gold" / row["hub"] / "building_history.json").read_text(encoding="utf-8"))
        assert row["record"] in gold["lots"].get(row["pnu"], []), row["mgtno"]
        assert row["pnu"] in gold["buildings"].values()
        assert row["record"]["source"] == "localdata"
        assert row["record"]["closure_reason_summary"] is None
