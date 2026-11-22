"""Platform 인스타그램 Gold 로더 (data/gold/platform_instagram.json · 2026-11-22).

공식 Instagram Graph API 해시태그 검색의 **집계**만 싣는다(계정·본문·링크 없음 — data/collectors/instagram_hashtags.py).
파일이 없으면 None — 「인스타 칸이 없다」와 「연결 전(pending)」을 구분한다. 수집 전에도 파일은 거점별 대표 해시태그를 싣는다.
⛔ 이 값은 무료 Platform 화면에만 쓴다 — 유료 상품(공실 진단 상세 리포트·광고)에 싣지 않는다(Meta 플랫폼 약관: 플랫폼 데이터 판매 금지 ·
   tests/test_instagram_context.py 가 유료 경로가 이 모듈을 읽지 않음을 잠근다).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PATH = Path(__file__).resolve().parents[4] / "data/gold/platform_instagram.json"
_cache: dict[str, Any] = {}
_GLOBAL = ("connected", "source", "built_at", "window", "stale_after_days", "api_version")


def _load() -> dict | None:
    if not _PATH.exists():
        return None
    stamp = _PATH.stat().st_mtime_ns
    if _cache.get("stamp") != stamp:
        _cache.update(stamp=stamp, data=json.loads(_PATH.read_text(encoding="utf-8")))
    return _cache["data"]


def for_district(slug: str) -> dict | None:
    """그 거점의 인스타 칸 — 거점 값 + 전체 메타(연결 여부·출처·기준 창). 파일·거점이 없으면 None."""
    data = _load()
    if not data:
        return None
    hub = (data.get("hubs") or {}).get(slug)
    if hub is None:
        return None
    return {**hub, **{k: data.get(k) for k in _GLOBAL}}
