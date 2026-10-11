"""수집 컨텍스트 Gold 로더. 파일이 없으면 None으로 결측을 밝힌다."""
import json
from pathlib import Path

_PATH = Path(__file__).resolve().parents[4] / "data/gold/platform_collected_context.json"
_cache: dict = {}


def for_district(slug: str) -> dict | None:
    if not _PATH.exists():
        return None
    stamp = _PATH.stat().st_mtime_ns
    if _cache.get("stamp") != stamp:
        _cache.update(stamp=stamp, data=json.loads(_PATH.read_text(encoding="utf-8")))
    return _cache["data"].get("districts", {}).get(slug)
