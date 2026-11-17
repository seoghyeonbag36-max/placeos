"""블로그 노출 패널(CSV) · 빈 주 감지 · 오프사이트 복사.

Bronze 스냅샷(`data/bronze/platform13/<날짜>/naver_blog_exposure.json`)은 `.gitignore` 대상이고 이 기계에만 있다.
블로그 검색 API 는 최신 1,000건까지만 줘서 **빠뜨린 주는 영영 비므로** 세 겹으로 지킨다:

  1. **압축 패널(git 추적)** `data/panel/digital_exposure_blog_weekly.csv` — 스냅샷에서 숫자 열만 뽑은 것(주 약 20KB).
     같은 (날짜, 거점, 질의) 는 덮어쓴다 — 재실행해도 중복이 안 쌓인다. Bronze 가 있으면 `rebuild_from_bronze` 로 복구된다.
  2. **빈 주 방지** — 「이번 ISO 주에 스냅샷이 없으면 받는다」(`is_due`). 작업이 매일·로그온 때 돌아서 월요일에 컴퓨터가
     꺼져 있었어도 그 주 안에 켜지는 날 받는다. 그래도 빈 주가 생기면 `missing_weeks` 가 로그·`--status` 에 올린다.
  3. **오프사이트 복사** — 날짜별 Bronze 스냅샷과 패널 CSV 를 동기화 폴더(기본 개인 OneDrive)로 복사하고 해시로 확인한다.
     `PLACEOS_OFFSITE_DIR=<경로>` 로 바꾸고 `PLACEOS_OFFSITE_DIR=off` 로 끈다.

패널은 공개 검색 API 의 **집계값**(total·건수·일평균 게시율·정밀도)뿐이다 — 본문·스니펫·작성자는 담지 않는다.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import os
import re
import shutil
from pathlib import Path

from data.collectors.common import DATA_ROOT

SNAP = "naver_blog_exposure.json"
PANEL_PATH = DATA_ROOT / "panel" / "digital_exposure_blog_weekly.csv"
COLUMNS = ["collected_at", "slug", "suffix", "token", "total", "n", "capped", "oldest",
           "window_days", "rate_per_day", "precision", "error"]
_KEY = ("collected_at", "slug", "suffix")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


# ── 패널 CSV ─────────────────────────────────────────────────────────────────

def snapshot_rows(snapshot: dict) -> list[dict]:
    """스냅샷(`{collected_at, hubs:{slug:{token, queries:{접미어:{...}}}}}`) → 패널 행. 숫자만, 본문 없음."""
    day = snapshot["collected_at"]
    rows = []
    for slug, h in sorted((snapshot.get("hubs") or {}).items()):
        for suffix, q in sorted((h.get("queries") or {}).items()):
            rows.append({"collected_at": day, "slug": slug, "suffix": suffix, "token": h.get("token", ""),
                         "total": q.get("total"), "n": q.get("n"), "capped": int(bool(q.get("capped"))),
                         "oldest": q.get("oldest"), "window_days": q.get("window_days"),
                         "rate_per_day": q.get("rate_per_day"), "precision": q.get("precision"),
                         "error": q.get("error") or ""})
    return rows


def read_panel(path: Path = PANEL_PATH) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_panel(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: tuple(str(r.get(k, "")) for k in _KEY)):
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in COLUMNS})
    os.replace(tmp, path)  # 쓰다 끊겨도 기존 파일이 남는다


def upsert_panel(new_rows: list[dict], path: Path = PANEL_PATH) -> int:
    """같은 (날짜, 거점, 질의) 는 덮어쓰고 나머지는 보존. 반환: 쓴 뒤 전체 행 수."""
    keys = {tuple(str(r[k]) for k in _KEY) for r in new_rows}
    kept = [r for r in read_panel(path) if tuple(str(r.get(k, "")) for k in _KEY) not in keys]
    merged = kept + new_rows
    _write_panel(merged, path)
    return len(merged)


def rebuild_from_bronze(bronze_platform: Path, path: Path = PANEL_PATH) -> int:
    """모든 날짜 폴더의 스냅샷에서 패널을 다시 짓는다(복구·최초 적재). 반환: 행 수."""
    import json

    rows: dict[tuple, dict] = {}
    for day in sorted(snapshot_dates(bronze_platform)):
        snap = json.loads((bronze_platform / day.isoformat() / SNAP).read_text(encoding="utf-8"))
        snap.setdefault("collected_at", day.isoformat())
        for r in snapshot_rows(snap):
            rows[tuple(str(r[k]) for k in _KEY)] = r
    _write_panel(list(rows.values()), path)
    return len(rows)


# ── 빈 주 ────────────────────────────────────────────────────────────────────

def snapshot_dates(bronze_platform: Path) -> list[dt.date]:
    out = []
    if bronze_platform.is_dir():
        for d in bronze_platform.iterdir():
            if _DATE.fullmatch(d.name) and (d / SNAP).exists():
                out.append(dt.date.fromisoformat(d.name))
    return sorted(out)


def iso_week(d: dt.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def is_due(dates: list[dt.date], today: dt.date) -> bool:
    """이번 ISO 주(월~일)에 받은 스냅샷이 없으면 받을 때다."""
    return iso_week(today) not in {iso_week(d) for d in dates}


def missing_weeks(dates: list[dt.date], today: dt.date) -> list[str]:
    """첫 스냅샷의 주부터 **지난주까지** 스냅샷이 없는 ISO 주. 이번 주는 아직 보충할 수 있어 세지 않는다."""
    if not dates:
        return []
    have = {iso_week(d) for d in dates}
    monday = min(dates) - dt.timedelta(days=min(dates).weekday())
    this_monday = today - dt.timedelta(days=today.weekday())
    out = []
    while monday < this_monday:
        if iso_week(monday) not in have:
            out.append(iso_week(monday))
        monday += dt.timedelta(days=7)
    return out


# ── 오프사이트 복사 ──────────────────────────────────────────────────────────

def offsite_dir(home: Path | None = None) -> Path | None:
    """복사 대상. 환경변수 > 개인 OneDrive 기본 경로. `off` 이거나 둘 다 없으면 None."""
    env = os.environ.get("PLACEOS_OFFSITE_DIR", "").strip()
    if env.lower() == "off":
        return None
    if env:
        return Path(env)
    one = (home or Path.home()) / "OneDrive"
    return one / "PlaceOS-backup" / "digital-exposure" if one.is_dir() else None


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def offsite_copy(bronze_platform: Path, panel_path: Path, dest: Path) -> dict:
    """날짜별 스냅샷 전부 + 패널 CSV 를 dest 로 복사(내용이 같으면 건너뜀)하고 복사 뒤 해시로 확인한다.

    매번 전부 훑으므로 동기화 폴더가 비워져도 다음 실행에 복구된다. 실패는 모아서 돌려주고 멈추지 않는다.
    """
    pairs = [(bronze_platform / d.isoformat() / SNAP, dest / "bronze" / "platform13" / d.isoformat() / SNAP)
             for d in snapshot_dates(bronze_platform)]
    if panel_path.exists():
        pairs.append((panel_path, dest / panel_path.name))
    res = {"dest": str(dest), "copied": 0, "skipped": 0, "failed": []}
    for src, dst in pairs:
        try:
            if dst.exists() and _sha(dst) == _sha(src):
                res["skipped"] += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if _sha(dst) != _sha(src):
                raise OSError("복사 뒤 해시 불일치")
            res["copied"] += 1
        except OSError as exc:
            res["failed"].append(f"{src.name}: {type(exc).__name__}")
    return res
