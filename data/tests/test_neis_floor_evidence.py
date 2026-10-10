"""학원(NEIS) 층 근거 — 매칭·층 해석·분모 불변 규칙 (합성 입력, 네트워크·실데이터 없음).

입력은 전부 테스트용 합성값이다. 지키는 것:
  · 도로명주소가 지번 하나에만 걸릴 때만 붙인다(다지번은 버린다)
  · 층은 인허가와 같은 규칙으로 읽는다 — 지하·층 미표기는 근거가 아니다
  · 층 미상 상가정보 점포와 이름이 맞으면 한 번만 '해소'로 센다(이중 계상 방지)
  · 학원 층은 분모(com_floors)를 넓히지 않는다 — 분모 안 층의 점유만 확인한다
"""
from __future__ import annotations

import json
from pathlib import Path

from data.collectors import neis_academies
from data.pipelines.build_building_attrs import _store_roads_and_blanks, academy_floors, road_key
from data.pipelines.build_page_master import _aggregate

PNU_A = "1168010700105110001"
PNU_B = "1168010700105610000"
PNU_C = "1168010800100060021"


def _aca(name: str, road: str, detail: str, status: str = "개원") -> dict:
    return {"ACA_NM": name, "FA_RDNMA": road, "FA_RDNDA": detail, "REG_STTUS_NM": status}


def test_road_key_drops_reference_and_spaces() -> None:
    assert road_key("서울특별시 강남구 강남대로156길 12 (신사동)") == road_key("서울특별시 강남구  강남대로156길 12")
    assert road_key(None) == ""


def test_unique_parcel_floor_and_ambiguity() -> None:
    road2pnu = {road_key("서울특별시 강남구 도산대로 1"): {PNU_A},
                road_key("서울특별시 강남구 도산대로 2"): {PNU_B, PNU_C}}
    acas = [
        _aca("가나다수학학원", "서울특별시 강남구 도산대로 1", ", 3층 301호 (신사동, 테스트빌딩)"),
        _aca("라마바영어학원", "서울특별시 강남구 도산대로 2", ", 4층"),          # 다지번 → 버린다
        _aca("사아자교습소", "서울특별시 강남구 도산대로 1", ", 301호"),          # 층 미표기
        _aca("차카타학원", "서울특별시 강남구 도산대로 1", ", 지하1층"),          # 지하
        _aca("파하학원", "서울특별시 강남구 도산대로 1", ", 5층", status="폐원"),  # 영업 아님
        _aca("밖학원", "서울특별시 종로구 종로 1", ", 2층"),                      # 거점 밖
    ]
    out, stats = academy_floors(acas, road2pnu, {})
    assert out == {PNU_A: {"floors": [3], "n": 1, "resolved": 0}}
    assert stats == {"rows": 6, "matched": 3, "ambiguous": 1, "with_floor": 1}


def test_blank_floor_store_resolved_once() -> None:
    stores = [
        {"lnoCd": PNU_A, "rdnmAdr": "서울특별시 강남구 도산대로 1", "flrNo": "", "bizesNm": "가나다수학학원"},
        {"lnoCd": PNU_A, "rdnmAdr": "서울특별시 강남구 도산대로 1", "flrNo": "1", "bizesNm": "편의점"},
    ]
    roads, blanks = _store_roads_and_blanks(stores)
    assert roads == {road_key("서울특별시 강남구 도산대로 1"): {PNU_A}}
    acas = [_aca("가나다수학학원", "서울특별시 강남구 도산대로 1", ", 3층"),
            _aca("가나다 수학학원", "서울특별시 강남구 도산대로 1", ", 4층")]   # 같은 이름 둘째 — 이미 소진
    out, _ = academy_floors(acas, roads, blanks)
    assert out[PNU_A] == {"floors": [3, 4], "n": 2, "resolved": 1}


def test_academy_floor_confirms_only_inside_denominator() -> None:
    rows = [{"name": "", "active": 2, "industry": "", "capacity": 3, "capacity_method": "floor_ouln",
             "capacity_floors": [1, 2, 3]}]
    at = {"store_flr_nos": [1], "aca_flr_nos": [2, 7], "store_flr_unknown": 0}
    agg = _aggregate(rows, at=at, lic={})
    assert agg["com_floors"] == [1, 2, 3]          # 7층은 분모 밖 — 넓히지 않는다
    assert agg["occ_floors"] == [1, 2]
    base = _aggregate(rows, at={"store_flr_nos": [1], "store_flr_unknown": 0}, lic={})
    assert base["occ_floors"] == [1]               # 학원 근거가 없으면 종전과 같다


def _neis_page(rows: list[dict], total: int) -> dict:
    return {"acaInsTiInfo": [{"head": [{"list_total_count": total}, {"RESULT": {"CODE": "INFO-000"}}]},
                             {"row": rows}]}


def test_read_run_validates_total_ids_and_office(tmp_path: Path) -> None:
    ok = [{"ACA_ASNUM": "1", "ATPT_OFCDC_SC_CODE": "B10"}, {"ACA_ASNUM": "2", "ATPT_OFCDC_SC_CODE": "B10"}]
    (tmp_path / "neis_001.json").write_text(json.dumps(_neis_page(ok, 2)), encoding="utf-8")
    rows, info = neis_academies.read_run(tmp_path)
    assert rows == ok and info["complete"]

    (tmp_path / "neis_001.json").write_text(json.dumps(_neis_page(ok, 3)), encoding="utf-8")   # 부분 수집
    rows, info = neis_academies.read_run(tmp_path)
    assert rows == [] and not info["complete"]

    other = [{"ACA_ASNUM": "1", "ATPT_OFCDC_SC_CODE": "J10"}]                                   # 서울 밖
    (tmp_path / "neis_001.json").write_text(json.dumps(_neis_page(other, 1)), encoding="utf-8")
    rows, info = neis_academies.read_run(tmp_path)
    assert rows == [] and info["non_b10"] == 1
