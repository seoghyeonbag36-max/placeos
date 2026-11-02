"""R-ONE 분기 시계열 — `GET /commercial-districts/{id}/rent-history`.

임대료는 1층 기준이고 층별 분기 실측은 원천에 없다(층 계수는 실측이 아니라 계수다). 값이 없는 분기는 null 그대로
둔다. 인접 표본을 빌린 거점은 `source="rone-shared"` + `shared_from` 으로 가른다.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.services import vacant_inventory

_SRC = Path(__file__).resolve().parents[4] / "data" / "gold" / "platform_rone_history.json"
_PYEONG_TO_M2 = 3.3058


@lru_cache(maxsize=1)
def _read(mtime: float) -> dict | None:
    try:
        return json.loads(_SRC.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _to_pyeong(v: float | None) -> float | None:
    """천원/㎡·월 → 만원/평·월."""
    return None if v is None else round(v * _PYEONG_TO_M2 / 10, 1)


def history(district_id: str | None) -> dict | None:
    """거점 시계열. 표에 없으면 None(→ 404). 임대료만 없는 6곳은 임대 칸이 전부 null 인 200 이다."""
    slug = vacant_inventory.slug_of(district_id)
    if slug is None:
        return None
    try:
        doc = _read(_SRC.stat().st_mtime)
    except OSError:
        return None
    hub = ((doc or {}).get("hubs") or {}).get(slug)
    if hub is None:
        return None
    rent = [_to_pyeong(v) for v in hub.get("rent_per_m2") or []]
    return {
        "district_id": district_id,
        "quarters": doc.get("quarters") or [],
        "rent_per_pyeong_manwon": rent,
        "rent_available": any(v is not None for v in rent),
        "floor_factor": doc.get("floor_factor") or {},
        "vacancy_mid_pct": hub.get("vacancy_mid_pct") or [],
        "vacancy_small_pct": hub.get("vacancy_small_pct") or [],
        "source": hub.get("source") or "none",
        "source_name": doc.get("source"),
        "shared_from": hub.get("shared_from"),
        "note": doc.get("note"),
    }
