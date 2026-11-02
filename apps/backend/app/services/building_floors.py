"""건물 층·호실 Gold(`{거점}/building_floors.json.gz`) 로더 — 지번(PNU) 단위 대장 기재값.

키는 지번이다. 건물 id `{pnu}-{n}` 의 n 은 폴리곤 번호이고 대장의 동이 아니라서, 폴리곤 하나가 어느 동인지는
이 파일로 말할 수 없다. 파일이 있어도 지번이 없으면 「자료 없음」이지 0 이 아니다(master 지번 일부만 실린다).
"""
from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

from app.services import vacant_inventory

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"
_LRU = 8    # 거점 하나가 수 MB 라 전 거점을 메모리에 들고 있지 않는다


def pnu_of(building_id: str) -> str:
    """'vu-1168…0014-1' · 'vfu-…-3' · '1168…0014-1' → 지번."""
    return re.sub(r"^vf?u-", "", building_id or "").split("-", 1)[0]


def _path(slug: str) -> Path:
    return _GOLD_DIR / slug / "building_floors.json.gz"


@lru_cache(maxsize=_LRU)
def _read(slug: str, mtime: float) -> dict | None:
    try:
        with gzip.open(_path(slug), "rt", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc.get("lots"), dict) else None


def load(district_id: str | None) -> dict | None:
    """거점의 층·호실 문서. 없으면 None(정상 상태 — 호출부가 자료 없음으로 말한다)."""
    slug = vacant_inventory.slug_of(district_id)
    if slug is None:
        return None
    try:
        stamp = _path(slug).stat().st_mtime
    except OSError:
        return None
    return _read(slug, stamp)


def mtime(district_id: str | None) -> float:
    slug = vacant_inventory.slug_of(district_id)
    try:
        return _path(slug).stat().st_mtime if slug else 0.0
    except OSError:
        return 0.0


def rows_of(doc: dict, lot: dict) -> tuple[list[dict], list[dict]]:
    """지번의 층 행 · 호실 행을 필드 이름이 붙은 dict 로 편다."""
    ff, uf = doc.get("floor_fields") or [], doc.get("unit_fields") or []
    return ([dict(zip(ff, r)) for r in lot.get("floors") or []],
            [dict(zip(uf, r)) for r in lot.get("units") or []])
