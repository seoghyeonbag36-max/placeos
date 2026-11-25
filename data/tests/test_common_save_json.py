"""`common.save_json` — 원천 루트(PLACEOS_BRONZE_ROOT)가 DATA_ROOT 밖이어도 저장·로그가 예외 없이 끝난다."""
from __future__ import annotations

import json

from data.collectors import common


def test_save_json_survives_bronze_root_outside_data_root(tmp_path, monkeypatch, capsys):
    # worktree 에서 메인 트리의 bronze 를 쓰면 저장 경로가 DATA_ROOT 하위가 아니다 — 2026-11-23 고양·파주 12거점 「점포」가 이 줄에서 exit 1.
    monkeypatch.setattr(common, "BRONZE", tmp_path / "bronze")
    path = common.save_json([{"a": 1}], "hub-x", "stores_raw.json", date="2026-11-23")
    assert path.exists() and json.loads(path.read_text(encoding="utf-8")) == [{"a": 1}]
    assert "[bronze]" in capsys.readouterr().out
