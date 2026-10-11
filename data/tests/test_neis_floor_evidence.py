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
from data.pipelines.build_building_attrs import (
    _name_key,
    _same_business,
    _store_roads_and_blanks,
    aca_floor_nos,
    academy_floors,
    road_key,
)
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
        {"lnoCd": PNU_A, "rdnmAdr": "서울특별시 강남구 도산대로 1", "flrNo": "", "bizesNm": "가나다수학학원",
         "indsLclsNm": "교육"},
        {"lnoCd": PNU_A, "rdnmAdr": "서울특별시 강남구 도산대로 1", "flrNo": "1", "bizesNm": "편의점",
         "indsLclsNm": "소매"},
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


def test_resolution_pool_is_education_only() -> None:
    """층 미상 점포 해소는 교육·독서실 업종만 — 'YBM어학원' 이 'YBM점'(소매)을 해소하면 안 된다."""
    stores = [
        {"lnoCd": PNU_A, "rdnmAdr": "서울특별시 종로구 종로 1", "flrNo": "", "bizesNm": "씨제이올리브영종로YBM점",
         "indsLclsNm": "소매"},
        {"lnoCd": PNU_A, "rdnmAdr": "서울특별시 종로구 종로 1", "flrNo": "", "bizesNm": "열공독서실",
         "indsLclsNm": "예술·스포츠", "indsSclsNm": "독서실/스터디 카페"},
    ]
    roads, blanks = _store_roads_and_blanks(stores)
    assert blanks == {PNU_A: ["열공독서실"]}
    out, _ = academy_floors([_aca("YBM어학원", "서울특별시 종로구 종로 1", ", 5층")], roads, blanks)
    assert out[PNU_A]["resolved"] == 0


def test_academy_floor_parse_cases() -> None:
    """NEIS 상세주소 층 해석 — 지하 약어·지하에서 시작하는 범위·괄호 안 건물명."""
    cases = {
        ", 3층 301호 (개포동, 삼성빌딩)": [3],
        ", 지1층 B125호(도곡동)": [],            # 지하 약어
        ", B1층 12호": [],
        ", 2~4층": [2, 3, 4],                   # 범위는 사이 층까지
        ", 1.2층": [1, 2],
        ", (3층)": [3],                         # 괄호 안에 층 표기만
        ", 301호 (대치동, 3층빌딩)": [],         # 참고항목의 건물명은 층이 아니다
        "외1필지 2층": [2],                      # '필지' 의 '지' 는 지하 약어가 아니다
        ", 지하1층~4층": [1, 2, 3, 4],           # 지하에서 시작하는 범위 → 지상 1층부터
        ", B1~3층": [1, 2, 3],
        ", 301호": [],
    }
    assert {k: sorted(aca_floor_nos(k)) for k in cases} == cases


def test_same_business_rules() -> None:
    """같은 업소 판정 — 포함·일치·오타·상호, 그리고 숫자로 갈리는 관(館)은 다른 업소다."""
    same = [("깨움학원", "깨움"),                              # 일치(2자)
            ("퀀텀과학학원", "퀸텀과학"),                       # 오타 한 글자
            ("압구정파인만중2관학원", "압구정파인만교육"),       # 상호: 브랜드 ↔ 법인명
            ("메이플베어어학학원", "메이플베어주"),
            ("가나다수학학원", "가나다 수학학원")]               # 포함
    other = [("잇올스파르타목동1독학재수학원", "잇올스파르타목동3독학재수"),   # 관 번호만 다르다
             ("팬더중국어교습소", "팬더공부방"),                               # 앞 2자만 같다
             ("뮤스토리미술학원", "심포니발레스튜디오")]
    assert all(_same_business(_name_key(a), _name_key(b)) for a, b in same)
    assert not any(_same_business(_name_key(a), _name_key(b)) for a, b in other)
