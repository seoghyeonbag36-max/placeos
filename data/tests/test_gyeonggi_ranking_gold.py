"""경기 Gold 빌더는 미완료·변조 원본을 승격하지 않는다."""
import json

import pytest

from data.pipelines.build_gyeonggi_ranking_gold import ledger_rows, write_once


def test_gold_write_once_refuses_replacement(tmp_path):
    path = tmp_path / "gold/evidence.json"
    write_once(path, b"original")
    write_once(path, b"original")
    with pytest.raises(ValueError, match="기존 산출물과 다름"):
        write_once(path, b"replacement")
    assert path.read_bytes() == b"original"


def test_ledger_missing_completion_is_not_gold(tmp_path):
    with pytest.raises(ValueError, match="완료 원본 없음"):
        ledger_rows(tmp_path, {}, "123", "floors")


def test_ledger_corrupted_page_is_rejected(tmp_path):
    page = tmp_path / "page.json"
    page.write_text("{}", encoding="utf-8")
    marker = tmp_path / "data/bronze/regional_research_ledgers/2026-11-03/floors/123/complete.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({"complete": True, "pnu": "123", "endpoint": "floors",
        "total": 1, "received": 1, "pages": [{"path": "page.json", "sha256": "wrong"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="원본 해시 불일치"):
        ledger_rows(tmp_path, {}, "123", "floors")
