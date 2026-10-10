"""체크리스트 수집분 → 표준 bronze 변환기의 판정 규칙 (네트워크·실데이터 없음).

합성 페이지만 쓴다 — 실측값이 아니다. 지키는 것:
  · 거점 수집 상태는 recovery 가 최초 실패를 덮는다(2026-10-09 suyu)
  · 행 수가 totalCount 와 다르거나 점포 ID 가 겹치면 변환하지 않는다
  · 업종은 모든 페이지 행 합이 list_total_count 와 같을 때만 '완주'다(첫 페이지 프로브 거르기)
"""
from __future__ import annotations

import json
from pathlib import Path

from data.collectors import import_acquisition as ia


def _write(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _store_page(items: list[dict], total: int) -> dict:
    return {"header": {"stdrYm": "202606"}, "body": {"items": items, "totalCount": total}}


def test_store_status_recovery_overrides_first_failure(tmp_path: Path) -> None:
    _write(tmp_path / "manifest.json", {"entries": [
        {"source": "stores/a", "status": "complete"},
        {"source": "stores/b", "status": "failed_or_partial"},
        {"source": "seoul/X/all", "status": "complete"},
    ]})
    _write(tmp_path / "recovery_manifest.json", [{"source": "stores/b", "status": "complete"}])
    assert ia._store_status(tmp_path) == {"a": "complete", "b": "recovered"}


def test_read_stores_requires_total_and_unique_ids(tmp_path: Path) -> None:
    rows = [{"bizesId": "1"}, {"bizesId": "2"}]
    _write(tmp_path / "stores/a/001.json", _store_page(rows, 2))
    got, info = ia._read_stores(tmp_path, "a", "complete")
    assert got == rows and info["complete"] and info["stdrYm"] == "202606"

    # 페이지가 모자라면(2/3) 쓰지 않는다
    _write(tmp_path / "stores/b/001.json", _store_page(rows, 3))
    got, info = ia._read_stores(tmp_path, "b", "complete")
    assert got == [] and not info["complete"]

    # recovered 는 recovery/stores 쪽을 읽는다 · ID 중복이면 거른다
    _write(tmp_path / "recovery/stores/c/001.json", _store_page([{"bizesId": "1"}, {"bizesId": "1"}], 2))
    got, info = ia._read_stores(tmp_path, "c", "recovered")
    assert got == [] and info["unique_ids"] == 1


def test_service_complete_only_when_all_rows_received(tmp_path: Path) -> None:
    sid = "LOCALDATA_000001"
    blk = {sid: {"list_total_count": 3, "row": [{"MGTNO": "1"}, {"MGTNO": "2"}]}}
    _write(tmp_path / f"seoul/{sid}/all/001.json", blk)
    _pages, ok, info = ia._service_pages(tmp_path, sid)
    assert not ok and info["rows"] == 2 and info["total"] == 3     # 첫 페이지만 받은 프로브

    _write(tmp_path / f"seoul/{sid}/all/002.json", {sid: {"list_total_count": 3, "row": [{"MGTNO": "3"}]}})
    _pages, ok, info = ia._service_pages(tmp_path, sid)
    assert ok and info["pages"] == 2


def test_canon_ignores_row_order() -> None:
    a = [{"bizesId": "1", "flrNo": "2"}, {"bizesId": "2", "flrNo": ""}]
    assert ia._canon(a) == ia._canon(list(reversed(a)))
    assert ia._canon(a) != ia._canon([{"bizesId": "1", "flrNo": "3"}, a[1]])
