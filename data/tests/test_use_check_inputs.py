"""입점 점검 재료 빌더 — 토지이음 cp949 응답 · 별표1 면적 기준 · 「접함」 제외 · 코드 묶음 한도."""
from __future__ import annotations

import json

from data.collectors import eum_landuse
from data.pipelines import build_use_check_inputs as b

# 2026-11-15 실측 응답과 같은 모양(제1종전용주거 × 휴게음식점 — 가능(조건)·금지 두 행 + QnodeCond)
XML = ("<response><header><resultCode>0</resultCode><resultMsg>OK</resultMsg></header><body><items><item>"
       "<UNAME>제1종전용주거지역</UNAME><UCODE>UQA111</UCODE>"
       "<actRegList><ACT_NM>건축</ACT_NM><REG_NM>가능</REG_NM><QNODE_CONDS><RNUM>R16</RNUM></QNODE_CONDS>"
       "<luInfoList><NODE_DESC>휴게음식점</NODE_DESC><LU_REF_LAW_NM1>건축법 시행령 별표 1  제3호나목</LU_REF_LAW_NM1>"
       "<DEF_REF>같은 건축물에 해당 용도로 쓰는 바닥면적의 합계가 300제곱미터 미만인 것</DEF_REF></luInfoList></actRegList>"
       "<actRegList><ACT_NM>건축</ACT_NM><REG_NM>금지</REG_NM>"
       "<luInfoList><NODE_DESC>휴게음식점</NODE_DESC><LU_REF_LAW_NM1>건축법 시행령 별표 1  제4호아목</LU_REF_LAW_NM1>"
       "<DEF_REF>같은 건축물에 해당 용도로 쓰는 바닥면적의 합계가 300제곱미터 이상인 것</DEF_REF></luInfoList></actRegList>"
       "</item><item><UNAME>대공방어협조구역</UNAME><UCODE>UNE200</UCODE><actRegList><luInfoList>"
       "<NODE_DESC>검색결과 없음</NODE_DESC></luInfoList></actRegList></item>"
       "<QnodeCond><QNODE_DESC>해당 용도에 쓰이는 바닥면적의 합계가 1천제곱미터 미만인 것</QNODE_DESC><RNUM>R16</RNUM></QnodeCond>"
       "</items><totalCount>2</totalCount></body></response>")


def test_parse_eum_handles_cp949_without_and_with_declaration():
    assert eum_landuse.parse_eum(XML.encode("cp949")).findtext(".//UNAME") == "제1종전용주거지역"
    declared = ('<?xml version="1.0" encoding="EUC-KR" standalone="yes"?>'
                "<response><ERROR_CODE>10</ERROR_CODE></response>").encode("cp949")
    assert eum_landuse.parse_eum(declared).findtext(".//ERROR_CODE") == "10"


def test_area_bounds_read_from_definition_text():
    assert b.area_bounds("같은 건축물에 해당 용도로 쓰는 바닥면적의 합계가 300제곱미터 미만인 것") == (None, 300.0)
    assert b.area_bounds("바닥면적의 합계가 300제곱미터 이상인 것") == (300.0, None)
    assert b.area_bounds("바닥면적의 합계가 1천제곱미터 미만인 것") == (None, 1000.0)
    assert b.area_bounds("제2종 근린생활시설에 해당하지 아니하는 것") == (None, None)


def test_progress_lock_is_reentrant():
    """진행 flush 가 잠금 안에서 다시 잠금을 잡는다 — Lock 이면 500건째에 교착(11-15 실측)."""
    with eum_landuse._lock:
        with eum_landuse._lock:
            pass


def test_chunk_limit_and_skip_prefix():
    """11-15 실측 — 코드 11개부터 오류 10 · 도시지역(UQA01X)은 오류 98."""
    assert eum_landuse.UCODE_CHUNK <= 10
    assert "UQA01X".startswith(eum_landuse.SKIP_PREFIX)


def test_act_rules_and_parcel_zones(tmp_path):
    (tmp_path / "eum" / "11680").mkdir(parents=True)
    (tmp_path / "eum" / "11680" / "휴게음식점__abcd1234.xml").write_bytes(XML.encode("cp949"))
    conds, defs = b.Interner(), b.Interner()
    acts = b.act_rules(tmp_path, conds, defs)
    rows = acts["11680"]["휴게음식점"]["UQA111"]
    assert [r["reg"] for r in rows] == ["가능", "금지"]
    assert conds.items[rows[0]["c"][0]].startswith("해당 용도에 쓰이는 바닥면적")
    assert rows[0]["laws"][0] | {} == {**rows[0]["laws"][0], "ho": 3, "mok": "나", "max": 300.0, "min": None}
    assert rows[1]["laws"][0]["ho"] == 4 and rows[1]["laws"][0]["min"] == 300.0
    assert acts["11680"]["휴게음식점"]["UNE200"] == []  # 「검색결과 없음」 = 그 지역지구에 규정 없음

    (tmp_path / "vworld" / "11680").mkdir(parents=True)
    page = {"field": [
        {"prposAreaDstrcCode": "UQA220", "prposAreaDstrcCodeNm": "일반상업지역", "cnflcAtNm": "저촉", "lastUpdtDt": "2026-11-06"},
        {"prposAreaDstrcCode": "UQA122", "prposAreaDstrcCodeNm": "제2종일반주거지역", "cnflcAtNm": "접함", "lastUpdtDt": "2026-11-06"},
        {"prposAreaDstrcCode": "UQQ600", "prposAreaDstrcCodeNm": "토지거래계약에관한허가구역", "cnflcAtNm": "포함", "lastUpdtDt": "2026-11-01"},
        {"prposAreaDstrcCode": "UQQ600", "prposAreaDstrcCodeNm": "토지거래계약에관한허가구역", "cnflcAtNm": "저촉", "lastUpdtDt": "2026-11-01"},
    ]}
    (tmp_path / "vworld" / "11680" / "1168010800100060013.json").write_text(
        json.dumps({"pnu": "1168010800100060013", "pages": [page]}, ensure_ascii=False), encoding="utf-8")
    parcels, names, dates = b.parcel_zones(tmp_path)
    assert parcels["1168010800100060013"] == [["UQA220", "저촉"], ["UQQ600", "포함"]]  # 접함 제외 · 중복은 포함 우선
    assert names["UQA122"] == "제2종일반주거지역" and max(dates) == "2026-11-06"
