"""거점 실측 범위 외곽선 + 사람이 붙인 상권 유형 — `GET /commercial-districts/outlines`.

외곽선은 100m 격자 실측 셀의 합집합이다. **공식 상권 경계가 아니다.** 유형(T1~T10)은 서울 81곳에 사람이 붙인
라벨이고 일부는 원본에서도 데이터 분류다(`type_is_manual=False`). 서울 밖은 유형이 없다.
"""
from __future__ import annotations

import importlib.util
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
_SRC = ROOT / "data" / "gold" / "platform_hub_outlines.json"


@lru_cache(maxsize=1)
def _types():
    spec = importlib.util.spec_from_file_location("placeos_hub_types", ROOT / "data/config/hub_types.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("상권 유형 표를 찾을 수 없습니다")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def type_of(slug: str) -> dict:
    """{type_code, type_name, type_is_manual}. 유형이 없으면 셋 다 비어 있다."""
    mod = _types()
    found = mod.type_of(slug)
    if not found:
        return {"type_code": None, "type_name": None, "type_is_manual": False}
    return {"type_code": found[0], "type_name": found[1], "type_is_manual": slug not in mod.HUB_TYPE_FROM_DATA}


@lru_cache(maxsize=1)
def _read(mtime: float) -> dict | None:
    try:
        doc = json.loads(_SRC.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    hubs = []
    for slug, h in sorted((doc.get("hubs") or {}).items()):
        pieces = h.get("pieces") or []
        hubs.append({
            "id": slug,
            # 조각마다 바깥 고리 하나. 구멍은 재지 않은 곳이라 따로 싣는다(지도에서 뚫을지는 화면 몫).
            "rings": [p["outer"] for p in pieces if p.get("outer")],
            "holes": [hole for p in pieces for hole in (p.get("holes") or [])],
            **type_of(slug),
        })
    return {"note": doc.get("note"), "hubs": hubs}


def outlines() -> dict | None:
    try:
        return _read(_SRC.stat().st_mtime)
    except OSError:
        return None
