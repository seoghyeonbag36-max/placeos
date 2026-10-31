"""광주 거점별 인허가 어댑터 — 조용히 틀리는 두 자리를 고정한다 (2026-10-31).

1. 좌표계 — 행안부 X/Y 는 서울과 같은 중부원점 TM 이다. `CRS` 를 달면 소비층이 변환을 건너뛰어 PIP 가 0건이 된다.
2. 귀속 — 점포 주소의 (구, 동)이 같은 행만 그 거점에 담는다. 구 이름이 다른 같은 동 이름은 섞이지 않는다.
"""
from data.collectors.gwangju_licensing_hubs import bucket, norm

ROW = {"MNG_NO": "5825000-101-2026-00394", "BPLC_NM": "아지매꽃게장", "BZSTAT_SE_NM": "한식", "SALS_STTS_NM": "영업/정상",
       "DTL_SALS_STTS_NM": "영업", "CLSBIZ_YMD": "", "LCPMT_YMD": "2026-10-26", "LOTNO_ADDR": "전남광주통합특별시 광산구 월곡동 611-18",
       "ROAD_NM_ADDR": "전남광주통합특별시 광산구 월곡중앙로 2", "LCTN_AREA": "16.66", "CRD_INFO_X": "182698.16", "CRD_INFO_Y": "185276.95"}


def test_norm_fills_the_seoul_contract_without_crs():
    r = norm(ROW)
    for k in ("MGTNO", "BPLCNM", "UPTAENM", "TRDSTATEGBN", "TRDSTATENM", "DCBYMD", "APVPERMYMD",
              "SITEWHLADDR", "RDNWHLADDR", "SITEAREA", "X", "Y"):
        assert k in r, k
    assert r["TRDSTATEGBN"] == "01"
    assert "CRS" not in r, "CRS 를 달면 소비층이 TM→WGS84 변환을 건너뛴다 — 광주는 서울과 같은 TM 이다"
    assert float(r["X"]) > 100000 and float(r["Y"]) > 100000


def test_closed_business_is_not_alive():
    r = norm({**ROW, "SALS_STTS_NM": "폐업", "CLSBIZ_YMD": "2026-01-01"})
    assert r["TRDSTATEGBN"] == "02" and r["DCBYMD"] == "2026-01-01"


def test_bucket_keeps_gu_and_dong_together():
    places = {"gj-usan": {("광산구", "월곡동")}, "gj-x": {("서구", "월곡동")}}
    other_gu = {**ROW, "LOTNO_ADDR": "전남광주통합특별시 서구 월곡동 1"}
    out = bucket([ROW, other_gu, {**ROW, "LOTNO_ADDR": ""}], places)
    assert len(out["gj-usan"]) == 1 and out["gj-usan"][0]["SITEWHLADDR"].endswith("광산구 월곡동 611-18")
    assert len(out["gj-x"]) == 1 and "서구" in out["gj-x"][0]["SITEWHLADDR"]
