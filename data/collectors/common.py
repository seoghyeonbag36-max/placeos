"""수집기 공용 유틸 — Bronze/Silver/Gold 저장 규칙(data/README.md)을 한곳에서 강제.

Bronze 경로 규칙: data/bronze/{상권}/{YYYY-MM-DD}/{파일}.json — 원본 무가공 저장.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any

# Windows cp949 콘솔에서 한글·특수문자 print 크래시 방지 (UnicodeEncodeError)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

DATA_ROOT = Path(__file__).resolve().parents[1]  # data/
# worktree 처럼 bronze·silver 가 없는 체크아웃에서 빌드할 때 원천 루트만 돌린다(출력 GOLD 는 그대로).
BRONZE = Path(os.environ.get("PLACEOS_BRONZE_ROOT") or DATA_ROOT / "bronze")
SILVER = Path(os.environ.get("PLACEOS_SILVER_ROOT") or DATA_ROOT / "silver")
GOLD = DATA_ROOT / "gold"


def load_env() -> None:
    """data/.env 로드 — run_collection 의 인코딩 관대 로더를 재사용."""
    from data.run_collection import _load_env

    _load_env()


def today() -> str:
    return datetime.date.today().isoformat()


def bronze_dir(district: str, date: str | None = None) -> Path:
    d = BRONZE / district / (date or today())
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_json(obj: Any, district: str, name: str, date: str | None = None) -> Path:
    """Bronze 에 JSON 저장. obj 가 list 면 행 수를 로그로 남긴다."""
    path = bronze_dir(district, date) / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    n = f" ({len(obj)}행)" if isinstance(obj, list) else ""
    # 원천 루트를 다른 트리로 돌리면(`PLACEOS_BRONZE_ROOT` — worktree) path 가 DATA_ROOT 밖이다. 저장은 이미 끝났으니
    # 로그 한 줄 때문에 수집이 exit 1 로 끝나지 않게 한다(2026-11-23: 고양·파주 12거점 「점포」 단계가 전부 이 줄에서 실패로 읽혔다).
    try:
        shown: Path = path.relative_to(DATA_ROOT)
    except ValueError:
        shown = path
    print(f"[bronze] {shown}{n}")
    return path


def latest_bronze(district: str, name: str) -> Path | None:
    """가장 최근 수집일 폴더에서 name 파일을 찾는다 (없으면 None)."""
    root = BRONZE / district
    if not root.exists():
        return None
    for day in sorted((p for p in root.iterdir() if p.is_dir()), reverse=True):
        f = day / name
        if f.exists():
            return f
    return None


def load_latest(district: str, name: str) -> Any | None:
    f = latest_bronze(district, name)
    if f is None:
        return None
    return json.loads(f.read_text(encoding="utf-8"))
