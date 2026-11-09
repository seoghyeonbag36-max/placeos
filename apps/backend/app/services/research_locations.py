"""광주·전주 조사 위치 — `GET /commercial-districts/research-locations`.

**정식 상권도 서빙 거점도 아니다.** 일반음식점 인허가 주소에서 찾은 700m 조사 원(서로 겹친다)의 관측값만 싣는다:
700m 점포 수·건물 수 · 점포가 확인된 지번의 대장(상업층 · 상업용 전유 호수) · 업종 상위 5.
공실률·순위·임대료는 없다 — 받은 대장에 빈 건물이 없어 분모가 없다. 거점이 되려면 hub-chain 을 탄다.

원천: data/gold/platform_research_locations.json (data/pipelines/build_research_locations.py)
결정: docs/decision-research-locations-layer-2026-11-09.md
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
_SRC = ROOT / "data" / "gold" / "platform_research_locations.json"
GROUPS = ("gwangju", "jeonju")


@lru_cache(maxsize=2)
def _read(mtime: float) -> dict | None:
    try:
        doc = json.loads(_SRC.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    # 이 레이어는 서빙 거점과 섞이지 않는다 — 원천이 다른 말을 하면 내보내지 않는다.
    if doc.get("serving_eligible") is not False or doc.get("seed") is not False:
        return None
    return doc


def research_locations(group: str | None = None) -> dict | None:
    """{note, source, built_at, counts, locations}. 원천이 없으면 None(라우터가 404)."""
    try:
        doc = _read(_SRC.stat().st_mtime)
    except OSError:
        return None
    if doc is None:
        return None
    locs = doc.get("locations") or []
    if group:
        locs = [loc for loc in locs if loc.get("group") == group]
    return {
        "note": doc.get("note"), "source": doc.get("source"), "built_at": doc.get("built_at"),
        "counts": doc.get("counts") or {}, "locations": locs,
    }
