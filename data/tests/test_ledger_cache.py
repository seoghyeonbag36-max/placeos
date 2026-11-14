"""대장 응답 캐시(data/collectors/ledger_cache.py) — 같은 요청의 검증된 조사 원본만 돌려주는가.

캐시가 틀린 응답을 주면 Bronze 대장이 조용히 다른 지번의 것이 된다. 그래서 ① 파라미터 역산이 `_jibun` 의 정확한 역이고
② 표식·해시가 어긋나면 실호출로 넘기며 ③ 꺼져 있을 때는 수집기 동작이 그대로인지를 잰다.
"""
from __future__ import annotations

import gzip
import hashlib
import json

import pytest

from data.collectors import building_vacancy as bv
from data.collectors import ledger_cache as lc

EXPOS = f"{bv.BASE_BLD}/getBrExposPubuseAreaInfo"
FLOORS = f"{bv.BASE_BLD}/getBrFlrOulnInfo"
TITLE = f"{bv.BASE_BLD}/getBrTitleInfo"


@pytest.mark.parametrize("pnu", ["1221010100100040002", "4511310800213670001", "1168010100200450012"])
def test_pnu_of_inverts_jibun(pnu):
    assert lc.pnu_of(bv._jibun(pnu)) == pnu


def test_pnu_of_rejects_malformed():
    assert lc.pnu_of({"sigunguCd": "12210"}) is None
    assert lc.pnu_of({**bv._jibun("1221010100100040002"), "platGbCd": "7"}) is None


@pytest.fixture()
def cache(tmp_path, monkeypatch):
    """임시 조사 원장 — 지번 하나, 전유부 2쪽."""
    pnu = "1221010100100040002"
    root = tmp_path
    markers = root / "data/bronze/regional_research_ledgers/2026-11-03"
    pages = []
    for n, rows in ((1, [{"a": 1}]), (2, [{"a": 2}])):
        payload = {"response": {"header": {"resultCode": "00"},
                                "body": {"totalCount": 2, "items": {"item": rows}}}}
        rel = f"data/bronze/regional_research_ledgers/2026-11-07/expos/{pnu}/page_{n:05d}.json.gz"
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = gzip.compress(json.dumps(payload).encode("utf-8"), mtime=0)
        path.write_bytes(raw)
        pages.append({"path": rel, "sha256": hashlib.sha256(raw).hexdigest()})
    marker = markers / "expos" / pnu / "complete.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"pnu": pnu, "endpoint": "expos", "complete": True, "total": 2,
                                  "received": 2, "pages": pages}), encoding="utf-8")
    monkeypatch.setattr(lc, "ROOT", root)
    monkeypatch.setattr(lc, "MARKERS", markers)
    monkeypatch.setattr(lc, "_markers", {})
    monkeypatch.setattr(lc, "STATS", lc.Counter())
    monkeypatch.setenv("PLACEOS_LEDGER_CACHE", "1")
    return pnu, root, pages


def _params(pnu, page=1, **over):
    return {"serviceKey": "never-sent", "_type": "json", "numOfRows": 100, "pageNo": page, **bv._jibun(pnu), **over}


def test_hit_returns_the_exact_page(cache):
    pnu, _, _ = cache
    assert bv._items(lc.lookup(EXPOS, _params(pnu, 1))) == [{"a": 1}]
    assert bv._items(lc.lookup(EXPOS, _params(pnu, 2))) == [{"a": 2}]
    assert lc.STATS["hit_expos"] == 2


def test_misses_fall_through_to_the_api(cache):
    pnu, root, pages = cache
    assert lc.lookup(TITLE, _params(pnu)) is None                       # 표제부는 늘 실호출
    assert lc.lookup(FLOORS, _params(pnu)) is None                      # 표식 없는 엔드포인트
    assert lc.lookup(EXPOS, _params(pnu, 3)) is None                    # 없는 쪽
    assert lc.lookup(EXPOS, _params(pnu, numOfRows=10)) is None         # 다른 요청이면 다른 응답이다
    assert lc.lookup(EXPOS, _params("1221010100100040003")) is None     # 다른 지번
    (root / pages[0]["path"]).write_bytes(b"tampered")                  # 해시가 어긋나면 쓰지 않는다
    assert lc.lookup(EXPOS, _params(pnu, 1)) is None
    assert lc.STATS["hash_mismatch_expos"] == 1


def test_on_by_default_and_opt_out(cache, monkeypatch):
    """기본은 켬 — 예약 작업이 되살린 배치에는 환경변수가 없다. `=0` 이면 수집기 동작은 종전 그대로다."""
    pnu, _, _ = cache
    monkeypatch.delenv("PLACEOS_LEDGER_CACHE")
    assert lc.lookup(EXPOS, _params(pnu)) is not None
    monkeypatch.setenv("PLACEOS_LEDGER_CACHE", "0")
    assert lc.lookup(EXPOS, _params(pnu)) is None


def test_collector_uses_cache_before_network(cache, monkeypatch):
    """`_get_json` 은 캐시 적중이면 네트워크를 타지 않는다 — 쿼터를 포기한 엔드포인트여도 그렇다."""
    pnu, _, _ = cache

    def boom(*a, **k):
        raise AssertionError("network called")

    monkeypatch.setattr(bv, "requests", type("R", (), {"get": staticmethod(boom)}))
    monkeypatch.setattr(bv, "_DEAD", {"getBrExposPubuseAreaInfo"})
    data = bv._get_json(EXPOS, _params(pnu, 1))
    assert bv._items(data) == [{"a": 1}] and bv._LAST_RETRYABLE[0] is False
