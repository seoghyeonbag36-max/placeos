"""토지이음 행위제한 남은 콜 무인 재개 — 일일 한도(약 1,000콜)가 풀린 뒤 이어 받고 Gold 를 다시 짓는다.

    python scripts/eum_landuse_resume.py --install    # 작업 스케줄러: 매일 00:20 (놓친 실행은 깨어나서 · 배터리에서도)
    python scripts/eum_landuse_resume.py --status
    python scripts/eum_landuse_resume.py              # 한 번 돈다(예약 작업이 pythonw 로 부르는 것)
    python scripts/eum_landuse_resume.py --uninstall

한 번 돌 때: ① 남은 콜 수를 센다 → ② `data.collectors.eum_landuse --stage eum`(받은 파일은 건너뛴다 ·
한도에 걸리면 바로 멈춘다) → ③ 남은 콜이 0 이면 `build_use_check_inputs` → `use_check_vacant_summary` 를 돌리고
**스스로 예약을 지운다.** 0 이 아니면 다음 날 밤에 또 돈다.

⚠ 커밋·PR·배포는 하지 않는다 — 다시 지은 `data/gold/page_use_check_inputs.json` 과 보고서는 사람이 확인하고 올린다
  (LSTM 확정 감시와 같은 원칙 · 메모리 lstm-confirm-watch-task).
⚠ 원천(.env · bronze · 빈 층 Gold)은 메인 체크아웃을 가리킨다 — 이 스크립트가 있는 체크아웃이 worktree 여도 된다.
⚠ pythonw 에는 stdout·stderr 가 없다 — 모든 기록은 로그 파일로 간다(최상위 예외 포함).
⚠ 예약은 **이 파일의 경로**로 등록된다. 다 받기 전에는 이 체크아웃(worktree)을 지우거나 이 파일이 없는 브랜치로 바꾸지 말 것 —
  그러면 로그 없이 실패한다. 그래도 7일(END_AFTER_DAYS) 뒤에는 예약이 스스로 끝난다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 원천 루트 — worktree 에서 돌아도 메인 체크아웃의 data 를 본다(.claude/worktrees/<이름>/ 두 단계 위).
MAIN = ROOT.parents[2] if ROOT.parent.name == "worktrees" else ROOT
MAIN_DATA = Path(os.environ.get("PLACEOS_MAIN_DATA") or MAIN / "data")
CITY, DATE = "seoul", "2026-11-15"
RUN_DIR = MAIN_DATA / "bronze" / "landuse" / CITY / DATE
LOG = RUN_DIR / "resume.log"
STATE = RUN_DIR / "resume_state.json"
TASK_NAME = "PlaceOS-EumLanduse-Resume"
DAILY_AT = "00:20"
END_AFTER_DAYS = 7   # 예약 상한(일) — 다 받으면 그 전에 스스로 지운다


def say(msg: str) -> None:
    line = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    try:
        print(line, flush=True)
    except Exception:  # noqa: BLE001 — pythonw 에는 stdout 이 없다
        pass


def keep_awake() -> bool:
    try:
        import ctypes
        return ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001) != 0  # ES_CONTINUOUS|SYSTEM_REQUIRED
    except Exception:  # noqa: BLE001
        return False


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update({"PLACEOS_ENV_FILE": str(MAIN_DATA / ".env"), "PLACEOS_BRONZE_ROOT": str(MAIN_DATA / "bronze"),
                "PLACEOS_SILVER_ROOT": str(MAIN_DATA / "silver"), "PLACEOS_GOLD_SRC": str(MAIN_DATA / "gold"),
                "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    return env


def missing_calls() -> dict[str, int]:
    """구별 남은 토지이음 콜 — 수집기와 같은 묶음 규칙으로 센다."""
    os.environ["PLACEOS_BRONZE_ROOT"] = str(MAIN_DATA / "bronze")
    sys.path.insert(0, str(ROOT))
    from data.collectors import eum_landuse as e

    miss: dict[str, int] = {}
    for gu, codes in sorted(e.parcel_codes(RUN_DIR).items()):
        codes = sorted(codes)
        for i in range(0, len(codes), e.UCODE_CHUNK):
            chunk = codes[i:i + e.UCODE_CHUNK]
            tag = hashlib.sha1(",".join(chunk).encode()).hexdigest()[:8]
            for act in e.ACT_NAMES:
                if not (RUN_DIR / "eum" / gu / f"{act}__{tag}.xml").exists():
                    miss[gu] = miss.get(gu, 0) + 1
    return miss


def run(args: list[str], tag: str, timeout: int) -> int:
    py = Path(sys.executable)
    if py.name.lower() == "pythonw.exe":  # 자식은 콘솔 python 으로 — 출력은 로그 파일로 받는다
        py = py.with_name("python.exe")
    say(f"▶ {tag}: {' '.join(args)}")
    with LOG.open("a", encoding="utf-8") as f:
        r = subprocess.run([str(py), "-u", *args], cwd=ROOT, env=child_env(), stdout=f, stderr=subprocess.STDOUT,
                           timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    say(f"■ {tag}: 종료코드 {r.returncode}")
    return r.returncode


def write_state(**kw) -> None:
    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"runs": []}
    st["runs"].append({"at": dt.datetime.now().isoformat(timespec="seconds"), **kw})
    st.update({k: v for k, v in kw.items() if k in ("status", "missing")})
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def tick() -> int:
    keep_awake()
    before = missing_calls()
    say(f"남은 콜 {sum(before.values())} {before}")
    if sum(before.values()):
        run(["-m", "data.collectors.eum_landuse", "--city", CITY, "--date", DATE, "--stage", "eum", "--workers", "2"],
            "토지이음 재개", timeout=3 * 3600)
    after = missing_calls()
    if sum(after.values()):
        say(f"아직 남은 콜 {sum(after.values())} {after} — 한도·오류로 멈췄다. 다음 날 밤에 다시 돈다")
        write_state(status="partial", missing=after)
        return 0
    rc = run(["-m", "data.pipelines.build_use_check_inputs", "--city", CITY, "--date", DATE], "Gold 재빌드", 1800)
    rc2 = run(["scripts/use_check_vacant_summary.py", "--city", CITY, "--date", DATE], "빈 층 분포", 3600) if rc == 0 else -1
    write_state(status="done" if rc == 0 and rc2 == 0 else "build_failed", missing={},
                gold=str(ROOT / "data" / "gold" / "page_use_check_inputs.json"),
                report=str(ROOT / "reports" / f"use_check_vacant_{CITY}_{DATE}.json"))
    if rc == 0 and rc2 == 0:
        say("완료 — Gold·보고서를 다시 지었다. 커밋·PR 은 사람이 한다. 예약 작업을 지운다")
        uninstall()
    return 0 if rc == 0 else 1


# ── 작업 스케줄러 ────────────────────────────────────────────────────────────

def _schtasks(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], capture_output=True, text=True, encoding="cp949", errors="replace")


def install(start_date: str) -> int:
    """매일 00:20 · 놓친 실행은 깨어나서 · 배터리에서도 · 3시간 상한. 관리자 권한 없이(현재 사용자 대화형)."""
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    who = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}".strip("\\")
    # 상한 — 이 스크립트는 이 체크아웃(worktree 일 수 있다) 경로로 등록된다. 체크아웃이 지워지거나 브랜치가 바뀌면 pythonw 가
    # 파일을 못 열어 로그 한 줄 없이 실패하고 스스로 지우지도 못한다. 그래도 매일 밤 영원히 깨지 않게 끝나는 날을 둔다.
    end_date = (dt.date.fromisoformat(start_date) + dt.timedelta(days=END_AFTER_DAYS)).isoformat()
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>PlaceOS 토지이음 행위제한 남은 콜 재개 → Gold 재빌드 (scripts/eum_landuse_resume.py · 끝나면 스스로 지운다)</Description></RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start_date}T{DAILY_AT}:00</StartBoundary>
      <EndBoundary>{end_date}T23:59:00</EndBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals><Principal id="Author"><UserId>{who}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <WakeToRun>true</WakeToRun>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <ExecutionTimeLimit>PT4H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec><Command>{exe}</Command><Arguments>"{Path(__file__).resolve()}"</Arguments><WorkingDirectory>{ROOT}</WorkingDirectory></Exec>
  </Actions>
</Task>
"""
    p = RUN_DIR / f".{TASK_NAME}.xml"
    p.write_text(xml, encoding="utf-16")
    r = _schtasks("/Create", "/TN", TASK_NAME, "/XML", str(p), "/F")
    p.unlink(missing_ok=True)
    say(f"작업 '{TASK_NAME}' " + (f"등록 — {start_date} 부터 {end_date} 까지 매일 {DAILY_AT}" if r.returncode == 0
                                  else f"등록 실패: {(r.stdout + r.stderr).strip()[:200]}"))
    return r.returncode


def uninstall() -> int:
    r = _schtasks("/Delete", "/TN", TASK_NAME, "/F")
    say(f"작업 '{TASK_NAME}' 해제 {'완료' if r.returncode == 0 else '실패 · ' + (r.stdout + r.stderr).strip()[:120]}")
    return r.returncode


def status() -> int:
    print(STATE.read_text(encoding="utf-8") if STATE.exists() else "상태 파일 없음(아직 안 돌았다)")
    r = _schtasks("/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V")
    keys = ("Status", "Next Run Time", "Last Run Time", "Last Result", "상태", "다음 실행 시간", "마지막 실행 시간", "마지막 결과")
    for ln in r.stdout.splitlines():
        if any(ln.strip().startswith(k) for k in keys):
            print(ln.strip())
    if r.returncode != 0:
        print(f"예약 작업 '{TASK_NAME}' 없음")
    print(f"남은 콜: {missing_calls()}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--start-date", default=(dt.date.today() + dt.timedelta(days=1)).isoformat(),
                    help="첫 실행 날짜(기본 내일) — 한도는 자정에 풀린다")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.install:
        return install(a.start_date)
    if a.uninstall:
        return uninstall()
    if a.status:
        return status()
    return tick()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001
        say("예외로 끝났다:\n" + traceback.format_exc())
        raise SystemExit(1)
