"""매주 월요일 블로그 노출 스냅샷 1회 — 작업 스케줄러 → pythonw (콘솔·PowerShell 없이).

연구 패널(docs/finding-digital-premium-inputs-2026-11-17.md §4)의 독립변수. 네이버 블로그 검색 API 는 최신
1,000건까지만 줘서 **과거로 못 돌아가는 유일한 변수**이므로 빠뜨린 주는 영영 비는 칸이다.

    python scripts/digital_exposure_weekly.py              # 지금 1회 (6일 안에 받은 스냅샷이 있으면 건너뜀)
    python scripts/digital_exposure_weekly.py --force      # 있어도 다시 받는다 (같은 날짜 파일을 덮어쓴다)
    python scripts/digital_exposure_weekly.py --install    # 작업 스케줄러 등록 — 매주 월 10:10 + 놓친 실행은 깨어나서
    python scripts/digital_exposure_weekly.py --uninstall
    python scripts/digital_exposure_weekly.py --status

⚠ **작업 스케줄러에는 `.env`·`data/bronze` 가 있는 체크아웃(메인 작업 폴더)의 이 파일을 등록한다.** worktree 에는
  둘 다 없다. 저장소 루트는 이 파일 위치에서 구하므로, 등록은 그 폴더에서 `--install` 로 한다.
⚠ 결과 파일 `data/bronze/platform13/<날짜>/naver_blog_exposure.json` 은 `.gitignore`(data/bronze/*) 대상이라
  이 기계에만 남는다. 백업은 별도(문서 §6).
⚠ pythonw 에는 stdout 이 없다 — 모든 출력은 reports/logs/digital_exposure_weekly.log 로 간다.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "reports" / "logs" / "digital_exposure_weekly.log"
SNAP = "naver_blog_exposure.json"
TASK_NAME = "PlaceOS-DigitalExposure-Weekly"
WEEKLY_AT = "10:10"
SKIP_IF_NEWER_THAN_DAYS = 6  # 주 1회 — 놓친 실행을 깨어나서 보충해도 같은 주에 두 번 받지 않는다


def snapshot_age_days(bronze_platform: Path, today: dt.date) -> int | None:
    """가장 최근 스냅샷(날짜 폴더 YYYY-MM-DD 안의 naver_blog_exposure.json)이 며칠 전인지. 없으면 None."""
    best: dt.date | None = None
    if bronze_platform.is_dir():
        for d in bronze_platform.iterdir():
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.name) and (d / SNAP).exists():
                day = dt.date.fromisoformat(d.name)
                best = day if best is None or day > best else best
    return None if best is None else (today - best).days


def summarize(snapshot: dict) -> dict:
    """로그용 한 줄 요약 — 거점 수 · 질의 수 · 오류 수 · 정밀도 중앙."""
    qs = [q for h in (snapshot.get("hubs") or {}).values() for q in h.get("queries", {}).values()]
    prec = [q["precision"] for q in qs if q.get("precision") is not None]
    return {"hubs": len(snapshot.get("hubs") or {}), "queries": len(qs),
            "errors": sum(1 for q in qs if q.get("error")), "empty": sum(1 for q in qs if q.get("n") == 0),
            "precision_median": round(statistics.median(prec), 3) if prec else None}


def run(force: bool) -> int:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh, contextlib.redirect_stdout(fh), contextlib.redirect_stderr(fh):
        print(f"\n=== {dt.datetime.now().isoformat(timespec='seconds')} digital_exposure_weekly ===", flush=True)
        try:
            age = snapshot_age_days(ROOT / "data" / "bronze" / "platform13", dt.date.today())
            if not force and age is not None and age < SKIP_IF_NEWER_THAN_DAYS:
                print(f"건너뜀 — 최근 스냅샷이 {age}일 전이다(<{SKIP_IF_NEWER_THAN_DAYS}일)", flush=True)
                return 0
            from data.collectors import naver_digital_exposure as nde
            from data.collectors.common import load_env

            load_env()
            snap = nde.collect_blog_exposure()
            if not snap:
                print("실패 — 수집 0건(키 없음 또는 전부 실패)", flush=True)
                return 2
            s = summarize(snap)
            print("요약:", json.dumps(s, ensure_ascii=False), flush=True)
            if s["errors"]:
                print(f"⚠ 오류 {s['errors']}질의 — 스냅샷은 저장했으나 그 칸은 비어 있다", flush=True)
                return 1
            return 0
        except Exception as exc:  # noqa: BLE001 — pythonw 는 예외가 나도 흔적이 없다. 종류와 위치만 남긴다(키 노출 방지)
            tb = exc.__traceback__
            where = f"{Path(tb.tb_frame.f_code.co_filename).name}:{tb.tb_lineno}" if tb else "?"
            print(f"예외 {type(exc).__name__} @ {where}", flush=True)
            return 3


# ── 작업 스케줄러 (lstm_confirm_watch.install 과 같은 경로 — schtasks /IT + XML 왕복, 관리자 권한 없이) ──

def _schtasks(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], capture_output=True, text=True, encoding="cp949", errors="replace")


def install() -> int:
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    action = f'"{exe}" "{Path(__file__).resolve()}"'
    r = _schtasks("/Create", "/TN", TASK_NAME, "/TR", action, "/SC", "WEEKLY", "/D", "MON", "/ST", WEEKLY_AT, "/IT", "/F")
    if r.returncode != 0:
        print(f"작업 등록 실패: {(r.stdout + r.stderr).strip()[:200]}")
        return r.returncode
    q = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME, "/XML", "ONE"], capture_output=True)
    s = q.stdout.decode("utf-16" if q.stdout[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8", errors="replace")
    for old, new in (("<DisallowStartIfOnBatteries>true<", "<DisallowStartIfOnBatteries>false<"),
                     ("<StopIfGoingOnBatteries>true<", "<StopIfGoingOnBatteries>false<"),
                     ("<StopOnIdleEnd>true<", "<StopOnIdleEnd>false<"),
                     ("<StartWhenAvailable>false<", "<StartWhenAvailable>true<")):
        s = s.replace(old, new)
    if "<StartWhenAvailable>" not in s:
        s = s.replace("</Settings>", "    <StartWhenAvailable>true</StartWhenAvailable>\n  </Settings>")
    # 1,620콜 × (0.12s + 응답) ≈ 8~10분. 1시간을 넘기면 일하는 중이 아니라 물린 것이다.
    limit = "<ExecutionTimeLimit>PT1H</ExecutionTimeLimit>"
    if "<ExecutionTimeLimit>" in s:
        s = re.sub(r"<ExecutionTimeLimit>[^<]*</ExecutionTimeLimit>", limit, s)
    else:
        s = s.replace("</Settings>", f"    {limit}\n  </Settings>")
    xml = ROOT / "reports" / "logs" / f".{TASK_NAME}.xml"
    xml.parent.mkdir(parents=True, exist_ok=True)
    xml.write_text(s, encoding="utf-16")
    r2 = _schtasks("/Create", "/TN", TASK_NAME, "/XML", str(xml), "/F")
    xml.unlink(missing_ok=True)
    if r2.returncode != 0:
        print(f"작업 '{TASK_NAME}' 등록 — 매주 월 {WEEKLY_AT} (⚠ 배터리·놓친 실행 설정은 못 넣었다: {(r2.stdout + r2.stderr).strip()[:150]})")
    else:
        print(f"작업 '{TASK_NAME}' 등록 — 매주 월 {WEEKLY_AT} · 놓친 실행은 깨어나서 · 배터리에서도 · 제한 1시간")
    return 0


def uninstall() -> int:
    r = _schtasks("/Delete", "/TN", TASK_NAME, "/F")
    print(f"작업 해제 {'완료' if r.returncode == 0 else '실패'}")
    return r.returncode


def status() -> int:
    age = snapshot_age_days(ROOT / "data" / "bronze" / "platform13", dt.date.today())
    print("최근 스냅샷:", "없음" if age is None else f"{age}일 전")
    r = _schtasks("/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V")
    keys = ("Status", "Next Run Time", "Last Run Time", "Last Result", "상태", "다음 실행 시간", "마지막 실행 시간", "마지막 결과")
    for ln in r.stdout.splitlines():
        if any(ln.strip().startswith(k) for k in keys):
            print(ln.strip())
    if r.returncode != 0:
        print(f"예약 작업 '{TASK_NAME}' 없음")
    if LOG.exists():
        print("로그 끝:", *LOG.read_text(encoding="utf-8").splitlines()[-4:], sep="\n  ")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.install:
        return install()
    if a.uninstall:
        return uninstall()
    if a.status:
        return status()
    return run(a.force)


if __name__ == "__main__":
    sys.exit(main())
