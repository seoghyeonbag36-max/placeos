"""블로그 노출 스냅샷을 **ISO 주마다 1회** 받는 실행기 — 작업 스케줄러 → pythonw (콘솔·PowerShell 없이).

연구 패널(docs/finding-digital-premium-inputs-2026-11-17.md §4·§7)의 독립변수. 네이버 블로그 검색 API 는 최신 1,000건까지만 줘서
**과거로 못 돌아가는 유일한 변수**이므로 빠뜨린 주는 영영 비는 칸이다. 그래서 세 겹으로 지킨다:

  1. **매일 + 로그온 때 돈다.** 「이번 ISO 주(월~일)에 스냅샷이 없으면 받는다」 — 월요일에 컴퓨터가 꺼져 있었어도 그 주 안에
     켜지는 날 받는다. 이미 있으면 건너뛴다(몇 초).
  2. **빈 주 경고.** 첫 스냅샷부터 지난주까지 빠진 ISO 주를 로그·`--status` 에 올린다.
  3. **오프사이트 복사.** 매 실행마다 날짜별 Bronze 스냅샷과 패널 CSV 를 동기화 폴더(기본 개인 OneDrive)로 복사한다(해시 확인).
     `PLACEOS_OFFSITE_DIR=<경로>` 로 바꾸고 `off` 로 끈다. 지워져도 다음 실행에 복구된다.

스냅샷을 받은 날에는 `total` 증가분 점검(`data/pipelines/digital_exposure_total_delta.py` — 사전등록 판정)을 돌려
`reports/digital_exposure_total_delta.json` 을 갱신한다. 스냅샷 4개(약 3~4주)가 쌓이기 전에는 「표본부족」이다.

    python scripts/digital_exposure_weekly.py              # 지금 (이번 주 스냅샷이 있으면 건너뛰고 점검·복사만)
    python scripts/digital_exposure_weekly.py --force      # 이번 주 것이 있어도 다시 받는다 (같은 날짜면 덮어쓴다)
    python scripts/digital_exposure_weekly.py --analyze    # total 증가분 점검만
    python scripts/digital_exposure_weekly.py --install    # 작업 스케줄러 등록 — 매일 10:10 + 로그온 + 놓친 실행 보충
    python scripts/digital_exposure_weekly.py --uninstall
    python scripts/digital_exposure_weekly.py --status

⚠ **작업 스케줄러에는 `.env`·`data/bronze` 가 있는 체크아웃(메인 작업 폴더)의 이 파일을 등록한다.** worktree 에는 둘 다 없다.
⚠ 결과 파일 `data/bronze/platform13/<날짜>/naver_blog_exposure.json` 은 `.gitignore`(data/bronze/*) 대상이다 —
  git 에는 압축 패널 `data/panel/digital_exposure_blog_weekly.csv` 만 올라가고, 원본은 오프사이트 복사가 지킨다.
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
BRONZE_P13 = ROOT / "data" / "bronze" / "platform13"
TASK_NAME = "PlaceOS-DigitalExposure-Weekly"
DAILY_AT = "10:10"
DELTA_REPORT = ROOT / "reports" / "digital_exposure_total_delta.json"


def summarize(snapshot: dict) -> dict:
    """로그용 한 줄 요약 — 거점 수 · 질의 수 · 오류 수 · 정밀도 중앙."""
    qs = [q for h in (snapshot.get("hubs") or {}).values() for q in h.get("queries", {}).values()]
    prec = [q["precision"] for q in qs if q.get("precision") is not None]
    return {"hubs": len(snapshot.get("hubs") or {}), "queries": len(qs),
            "errors": sum(1 for q in qs if q.get("error")), "empty": sum(1 for q in qs if q.get("n") == 0),
            "precision_median": round(statistics.median(prec), 3) if prec else None}


def snapshot_age_days(bronze_platform: Path, today: dt.date) -> int | None:
    from data.collectors import digital_exposure_panel as panel

    ds = panel.snapshot_dates(bronze_platform)
    return None if not ds else (today - ds[-1]).days


def _maintenance(today: dt.date, took_snapshot: bool) -> int:
    """패널 동기 · 빈 주 경고 · (새 스냅샷이면) 증가분 점검 · 오프사이트 복사. 반환: 0 정상 / 1 경고."""
    from data.collectors import digital_exposure_panel as panel

    code = 0
    dates = panel.snapshot_dates(BRONZE_P13)
    in_panel = {r["collected_at"] for r in panel.read_panel()}
    if {d.isoformat() for d in dates} - in_panel:  # Bronze 에 있는데 패널에 없는 날짜 → 다시 짓는다(멱등)
        print(f"패널 재구성 — {panel.rebuild_from_bronze(BRONZE_P13)}행", flush=True)
    gaps = panel.missing_weeks(dates, today)
    if gaps:
        print(f"⚠ 빈 주 {len(gaps)}개: {', '.join(gaps)} — 되돌릴 수 없다(그 주의 블로그 창은 지나갔다)", flush=True)
        code = 1
    if took_snapshot:
        try:
            from data.pipelines import digital_exposure_total_delta as td

            r = td.run()
            print("증가분 점검:", json.dumps({k: r.get(k) for k in ("n_snapshots", "verdict", "reason")}, ensure_ascii=False), flush=True)
        except Exception as exc:  # noqa: BLE001 — 점검 실패가 스냅샷 적재를 깨면 안 된다
            print(f"증가분 점검 실패: {type(exc).__name__}", flush=True)
            code = 1
    dest = panel.offsite_dir()
    if dest is None:
        print("오프사이트 복사 꺼짐(대상 없음 또는 PLACEOS_OFFSITE_DIR=off)", flush=True)
    else:
        res = panel.offsite_copy(BRONZE_P13, panel.PANEL_PATH, dest)
        if res["copied"] or res["failed"]:
            print("오프사이트:", json.dumps(res, ensure_ascii=False), flush=True)
        if res["failed"]:
            code = 1
    return code


def run(force: bool) -> int:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh, contextlib.redirect_stdout(fh), contextlib.redirect_stderr(fh):
        print(f"\n=== {dt.datetime.now().isoformat(timespec='seconds')} digital_exposure_weekly ===", flush=True)
        try:
            from data.collectors import digital_exposure_panel as panel

            today = dt.date.today()
            dates = panel.snapshot_dates(BRONZE_P13)
            if not force and not panel.is_due(dates, today):
                print(f"건너뜀 — 이번 주({panel.iso_week(today)}) 스냅샷이 이미 있다(최근 {(today - dates[-1]).days}일 전)", flush=True)
                return _maintenance(today, took_snapshot=False)
            from data.collectors import naver_digital_exposure as nde
            from data.collectors.common import load_env

            load_env()
            snap = nde.collect_blog_exposure()
            if not snap:
                print("실패 — 수집 0건(키 없음 또는 전부 실패)", flush=True)
                _maintenance(today, took_snapshot=False)
                return 2
            s = summarize(snap)
            print("요약:", json.dumps(s, ensure_ascii=False), flush=True)
            code = _maintenance(today, took_snapshot=True)
            if s["errors"]:
                print(f"⚠ 오류 {s['errors']}질의 — 스냅샷은 저장했으나 그 칸은 비어 있다", flush=True)
                return 1
            return code
        except Exception as exc:  # noqa: BLE001 — pythonw 는 예외가 나도 흔적이 없다. 종류와 위치만 남긴다(키 노출 방지)
            tb = exc.__traceback__
            while tb and tb.tb_next:
                tb = tb.tb_next
            where = f"{Path(tb.tb_frame.f_code.co_filename).name}:{tb.tb_lineno}" if tb else "?"
            print(f"예외 {type(exc).__name__} @ {where}", flush=True)
            return 3


def analyze_only() -> int:
    sys.path.insert(0, str(ROOT))
    from data.pipelines import digital_exposure_total_delta as td

    r = td.run()
    print(json.dumps({k: r.get(k) for k in ("n_snapshots", "verdict", "reason")}, ensure_ascii=False))
    return 0


# ── 작업 스케줄러 (lstm_confirm_watch.install 과 같은 경로 — schtasks /IT + XML 왕복, 관리자 권한 없이) ──

def _schtasks(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], capture_output=True, text=True, encoding="cp949", errors="replace")


def install() -> int:
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    action = f'"{exe}" "{Path(__file__).resolve()}"'
    r = _schtasks("/Create", "/TN", TASK_NAME, "/TR", action, "/SC", "DAILY", "/ST", DAILY_AT, "/IT", "/F")
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
    who = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}".strip("\\")
    if "<LogonTrigger>" not in s and who:  # 월요일에 꺼져 있었으면 켠 직후(로그온) 이번 주 것을 받는다
        s = s.replace("</Triggers>", f"    <LogonTrigger>\n      <Enabled>true</Enabled>\n      <UserId>{who}</UserId>\n    </LogonTrigger>\n  </Triggers>")
    xml = ROOT / "reports" / "logs" / f".{TASK_NAME}.xml"
    xml.parent.mkdir(parents=True, exist_ok=True)
    xml.write_text(s, encoding="utf-16")
    r2 = _schtasks("/Create", "/TN", TASK_NAME, "/XML", str(xml), "/F")
    xml.unlink(missing_ok=True)
    if r2.returncode != 0:
        print(f"작업 '{TASK_NAME}' 등록 — 매일 {DAILY_AT} (⚠ 로그온·배터리·놓친 실행 설정은 못 넣었다: {(r2.stdout + r2.stderr).strip()[:150]})")
    else:
        print(f"작업 '{TASK_NAME}' 등록 — 매일 {DAILY_AT} + 로그온 · 놓친 실행은 깨어나서 · 배터리에서도 · 제한 1시간")
    return 0


def uninstall() -> int:
    r = _schtasks("/Delete", "/TN", TASK_NAME, "/F")
    print(f"작업 해제 {'완료' if r.returncode == 0 else '실패'}")
    return r.returncode


def status() -> int:
    sys.path.insert(0, str(ROOT))
    from data.collectors import digital_exposure_panel as panel

    today = dt.date.today()
    dates = panel.snapshot_dates(BRONZE_P13)
    print(f"스냅샷 {len(dates)}개 · 최근 {dates[-1] if dates else '없음'} · 이번 주({panel.iso_week(today)}) {'필요' if panel.is_due(dates, today) else '완료'}")
    gaps = panel.missing_weeks(dates, today)
    print("빈 주:", ", ".join(gaps) if gaps else "없음")
    print("패널 행:", len(panel.read_panel()), "·", panel.PANEL_PATH)
    dest = panel.offsite_dir()
    print("오프사이트:", "꺼짐" if dest is None else f"{dest} ({'폴더 있음' if dest.exists() else '아직 없음 — 첫 복사 때 만든다'})")
    if DELTA_REPORT.exists():
        d = json.loads(DELTA_REPORT.read_text(encoding="utf-8"))
        print(f"증가분 점검({d.get('computed_at')}): {d.get('verdict')} — {d.get('reason')}")
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
    ap.add_argument("--analyze", action="store_true")
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
    if a.analyze:
        return analyze_only()
    return run(a.force)


if __name__ == "__main__":
    sys.exit(main())
