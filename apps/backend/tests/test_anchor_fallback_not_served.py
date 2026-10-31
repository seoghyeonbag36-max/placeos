"""폴백 앵커는 R-ONE 이 아니다 — 서빙이 앵커로 내려보내지 않는다 (2026-10-31).

`calibrate_vacancy` 는 R-ONE 값이 없으면 10.0 을 쓰고 `anchor_is_fallback` 을 남긴다. 그 값을 앵커로 내려보내면
격차가 「R-ONE 대조」처럼 화면에 서고, 진행률 게이트도 그 거점을 「앵커 대조 보유」로 센다
(경기 3차 13곳이 그 상태로 공개됐다 → docs/decision-gwangju-serve-2026-10-31.md §2).
"""
from __future__ import annotations

import json

from app.services import gold_vacancy as gv


def _write(tmp_path, slug: str, cal: dict) -> None:
    d = tmp_path / slug
    d.mkdir(parents=True)
    (d / "calibration.json").write_text(json.dumps(cal), encoding="utf-8")


def test_fallback_anchor_is_not_served(tmp_path, monkeypatch):
    monkeypatch.setattr(gv, "_GOLD_DIR", tmp_path)
    monkeypatch.setattr(gv, "_resolve", lambda s: s)
    monkeypatch.setattr(gv, "_anchor_cache", {})
    _write(tmp_path, "fb-hub", {"anchor_pct": 10.0, "anchor_is_fallback": True})
    _write(tmp_path, "real-hub", {"anchor_pct": 13.38, "anchor_is_fallback": False})
    _write(tmp_path, "old-hub", {"anchor_pct": 18.23})      # 플래그 이전 산출물 — 종전대로 읽는다
    assert gv.anchor_of("fb-hub") is None
    assert gv.anchor_of("real-hub") == 13.38
    assert gv.anchor_of("old-hub") == 18.23


def test_no_served_hub_carries_a_fallback_anchor():
    """지금 서빙 산출물에 폴백 앵커가 하나도 없어야 한다 — 있으면 그 거점은 R-ONE 대조 없이 공개된 것이다."""
    flagged = sorted(p.parent.name for p in gv._GOLD_DIR.glob("*/calibration.json")
                     if json.loads(p.read_text(encoding="utf-8")).get("anchor_is_fallback"))
    assert not flagged, f"폴백 앵커 거점: {flagged} — python -m data.collectors.rone_rent 뒤 calibrate_vacancy 를 다시 돌릴 것"
