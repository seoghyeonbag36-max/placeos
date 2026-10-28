"""경기 인허가 수집기 + 좌표계 분기 — 조용히 틀리는 두 자리를 고정한다.

이 두 가지는 **틀려도 예외가 안 나고 산출물이 그럴듯하게 만들어진다**:

1. 주소 파싱 — 고양은 구가 있고(`고양시 덕양구 화정동`) 파주는 없다(`파주시 금촌동`).
   한쪽 형식만 맞추면 다른 도시의 인허가가 통째로 0 건이 된다.
2. 좌표계 — 경기 응답은 이미 WGS84 인데 `_licensed_pip` 은 서울 TM 을 가정해
   `EPSG:2097 → 4326` 변환을 한다. 한 번 더 변환하면 좌표가 엉뚱한 곳으로 가고
   **PIP 가 아무 건물에도 안 걸려 분자 보강이 0 이 된다** — 정상처럼 보인다.

근거: docs/finding-gyeonggi-licensing-source-2026-08-30.md
"""
from data.collectors.gg_licensing import _norm, _place


def test_place_parses_goyang_and_paju_forms():
    """구가 있는 주소와 없는 주소, 읍면(리) 주소를 모두 뽑아야 한다."""
    assert _place("경기도 고양시 덕양구 화정동 946") == ("고양시", "덕양구", "화정동")
    assert _place("경기도 파주시 금촌동 544-6") == ("파주시", "", "금촌동")
    assert _place("경기도 파주시 월롱면 도내리 238-2") == ("파주시", "", "도내리")
    # 층·호가 붙어도 잎은 동이다
    assert _place("경기도 고양시 일산동구 백석동 1278-2 1층 전체") == (
        "고양시", "일산동구", "백석동")
    assert _place("") is None


def test_norm_maps_to_seoul_schema():
    """소비층(build_page_master·build_building_history)이 읽는 키를 전부 채운다."""
    row = _norm({
        "MANAGE_NO": "4128000-101-2026-00001",
        "BIZPLC_NM": "함경면옥 백석점",
        "BIZCOND_DIV_NM_INFO": "한식",
        "BSN_STATE_NM": "영업",
        "CLSBIZ_DE": None,
        "LICENSG_DE": "20260506",
        "REFINE_LOTNO_ADDR": "경기도 고양시 일산동구 백석동 1278-2 1층 전체",
        "REFINE_ROADNM_ADDR": "경기도 고양시 일산동구 중앙로 1275",
        "LOCPLC_AR_INFO": "110.14",
        "REFINE_WGS84_LAT": "37.6463787",
        "REFINE_WGS84_LOGT": "126.7858359",
    })
    for k in ("MGTNO", "BPLCNM", "UPTAENM", "TRDSTATEGBN", "TRDSTATENM",
              "DCBYMD", "APVPERMYMD", "SITEWHLADDR", "RDNWHLADDR",
              "SITEAREA", "X", "Y", "CRS"):
        assert k in row, f"소비층 계약 키 누락: {k}"
    assert row["TRDSTATEGBN"] == "01", "영업은 서울 코드 01 로 옮겨야 한다"
    # X=경도, Y=위도 (always_xy 관례) — 뒤집히면 PIP 가 전부 빗나간다
    assert float(row["X"]) > 126 and float(row["Y"]) > 37
    assert row["CRS"] == "EPSG:4326", "좌표계 표기가 빠지면 소비층이 다시 변환한다"


def test_closed_business_maps_to_non_open():
    row = _norm({"BSN_STATE_NM": "폐업", "CLSBIZ_DE": "20070208"})
    assert row["TRDSTATEGBN"] == "02"
    assert row["DCBYMD"] == "20070208"


def test_licensed_pip_skips_transform_for_wgs84_rows():
    """`CRS: EPSG:4326` 행은 좌표 변환을 타지 않아야 한다.

    변환을 타면 경도 126.78 이 TM 좌표로 해석돼 결과가 지구 반대편으로 간다.
    여기서는 `_lonlat` 이 없는 구현으로 되돌아갔는지를 소스로 확인한다 —
    실제 PIP 는 폴리곤·대장이 있어야 돌아서 단위 테스트로 고정하기 어렵다.
    """
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "pipelines" / "build_page_master.py"
    text = src.read_text(encoding="utf-8")
    assert "_lonlat" in text, "좌표계 분기가 사라졌다 — 경기 인허가가 조용히 0 건이 된다"
    assert 'str(r.get("CRS") or "") == "EPSG:4326"' in text, "CRS 표기를 읽지 않는다"
    # 변환 호출은 `_lonlat` 안의 **한 곳뿐**이어야 한다. 루프에서 직접 부르는 자리가
    # 남아 있으면 그 경로만 WGS84 행을 다시 변환한다.
    assert text.count("tr.transform(x, y)") == 1, "변환을 직접 부르는 자리가 남아 있다"


# ── 일반구 표기 차이(2026-10-28) ──────────────────────────────────────────────────
# 경기 3차 50거점에는 부천(2024 일반구 부활)·화성(2026 일반구) 거점이 있다. 상가정보 주소에는 새 구가
# 붙는데 인허가 정제주소가 옛 표기면 (시군, 구, 동) 이 어긋나 그 거점의 인허가가 **통째로 0 행**이 된다.
# 건물 귀속은 좌표 PIP 가 하므로 거점 버킷은 (시군, 동) 으로 고른다.

def test_bucket_key_ignores_gu():
    from data.collectors.gg_licensing import _key
    new = _place("경기도 화성시 병점구 진안동 856-5")
    old = _place("경기도 화성시 진안동 856-5")
    assert new == ("화성시", "병점구", "진안동") and old == ("화성시", "", "진안동")
    assert _key(new) == _key(old) == ("화성시", "진안동")
    assert _key(_place("경기도 부천시 원미구 심곡동 120")) == _key(_place("경기도 부천시 심곡동 120"))


def test_scan_keeps_rows_whose_gu_differs(monkeypatch):
    """구 표기만 다른 행도 거점 버킷에 담긴다 — 종전 키로는 0 행이었다."""
    import data.collectors.gg_licensing as gg
    rows = [
        {"REFINE_LOTNO_ADDR": "경기도 화성시 진안동 856-5", "BSN_STATE_NM": "영업"},       # 옛 표기(구 없음)
        {"REFINE_LOTNO_ADDR": "경기도 화성시 병점구 진안동 860", "BSN_STATE_NM": "영업"},  # 새 표기
        {"REFINE_LOTNO_ADDR": "경기도 오산시 원동 1", "BSN_STATE_NM": "영업"},           # 다른 시
    ]
    body = {"GENRESTRT": [{"head": [{"list_total_count": len(rows)}]}, {"row": rows}]}
    monkeypatch.setattr(gg, "_fetch", lambda key, page: body)
    monkeypatch.setattr(gg.time, "sleep", lambda s: None)
    hub_places = {("화성시", "병점구", "진안동")}
    idx = {gg._key(p): ["byeongjeom"] for p in hub_places}
    part, done = gg._scan("k", idx, ["byeongjeom"], {"byeongjeom": hub_places})
    assert done
    assert len(part["byeongjeom"]) == 2, "구 표기가 다른 행을 놓쳤다"


def test_hub_without_stores_is_not_saved_as_empty(tmp_path, monkeypatch):
    """대상 동을 못 만든 거점은 빈 licensing_biz.json 으로 굳으면 안 된다.

    종전에는 빈 목록이 저장돼 다음 실행부터 「이미 있음」으로 건너뛰었다 — 인허가 0 행인 채로 굳었다.
    """
    import data.collectors.gg_licensing as gg
    monkeypatch.setattr(gg, "load_env", lambda: None)
    monkeypatch.setenv("GG_OPENAPI_KEY", "test-key")
    monkeypatch.setattr(gg, "latest_bronze", lambda s, name: None)
    monkeypatch.setattr(gg, "_hub_places",
                        lambda s: {("화성시", "병점구", "진안동")} if s == "has-stores" else set())
    seen_targets = []

    def fake_scan(key, idx, targets, exact=None):
        seen_targets.extend(targets)
        return {s: [{"TRDSTATEGBN": "01", "DCBYMD": ""}] for s in targets}, True

    monkeypatch.setattr(gg, "_scan", fake_scan)
    monkeypatch.setattr(gg, "_STAGE", tmp_path / "stage")
    monkeypatch.setattr(gg, "today", lambda: "2026-10-28")
    saved = []
    monkeypatch.setattr(gg, "save_json", lambda rows, s, name: saved.append(s))
    gg.collect(["has-stores", "no-stores"])
    assert seen_targets == ["has-stores"]
    assert saved == ["has-stores"], "점포 없는 거점에 빈 인허가 파일을 썼다"


def test_corrupt_stage_cache_does_not_kill_the_day(tmp_path, monkeypatch):
    """쓰다 죽은 스테이지가 그날의 모든 실행(--force 포함)을 JSONDecodeError 로 죽이면 안 된다(10-28 리뷰)."""
    import json

    import data.collectors.gg_licensing as gg
    monkeypatch.setattr(gg, "load_env", lambda: None)
    monkeypatch.setenv("GG_OPENAPI_KEY", "test-key")
    monkeypatch.setattr(gg, "latest_bronze", lambda s, name: None)
    monkeypatch.setattr(gg, "_hub_places", lambda s: {("수원시", "팔달구", "매산로1가")})
    monkeypatch.setattr(gg, "_STAGE", tmp_path / "stage")
    monkeypatch.setattr(gg, "today", lambda: "2026-10-28")
    (tmp_path / "stage").mkdir()
    (tmp_path / "stage" / "2026-10-28.json").write_text('{"suwonst": [{"MGTNO": ', encoding="utf-8")   # 잘린 파일
    scanned = []
    monkeypatch.setattr(gg, "_scan", lambda key, idx, targets, exact=None: (scanned.extend(targets) or
                                                                         {s: [] for s in targets}, True))
    monkeypatch.setattr(gg, "save_json", lambda rows, s, name: None)
    gg.collect(["suwonst"])
    assert scanned == ["suwonst"], "깨진 스테이지 때문에 스캔하지 못했다"
    assert json.loads((tmp_path / "stage" / "2026-10-28.json").read_text(encoding="utf-8")) == {"suwonst": []}
