"""LSTM 확정 감시 — 다음 분기가 공표되면 사전등록된 확정 재학습을 무인으로 돌린다.

## 왜

LSTM 두 게이트(방향·오차)는 사전등록상 `protocol.confirm_after`(=20262) **이후 분기**
holdout 으로만 닫힌다(docs/finding-lstm-delta-target-2026-09-26.md §0-B ③ ·
docs/finding-lstm-regularization-prereg-2026-09-28.md §5). 그 분기가 원천에 공표되기
전에는 할 일이 없고, 공표된 뒤에는 **판단이 들어가지 않는 작업만** 남는다 — 수집 →
Gold → 사전등록 그리드 재학습 → 판정. 그래서 무인으로 건다(autorun 스킬 §4).

공표 시점은 원천마다 다르고 예고가 없다. 2026-10-04 실측: 2026Q3 는 TRDAR 점포·추정매출,
R-ONE 공실률 모두 `INFO-200 해당하는 데이터가 없습니다` 였다(2026Q2 는 셋 다 있음).

## 하루 한 번 하는 일 (작업 스케줄러 → pythonw · 몇 초)

1. 파이프라인이 이미 돌고 있으면(PID 파일 + 시작시각 대조) 아무것도 안 한다
2. **기다릴 분기** = 서빙 forecast holdout 의 마지막 분기 다음(지금 20263).
   Gold 최대 분기가 아니라 holdout 을 본다 — 수집·Gold 까지 됐는데 재학습이 실패하면
   Gold 는 이미 그 분기를 갖지만 확정은 아직이다. 그때도 같은 분기를 다시 기다린다.
3. 공표 확인 5콜 — TRDAR 점포·추정매출 + R-ONE 현행 통계표 셋. **전부** 있어야 진행한다.
   점포는 타깃(`vac_proxy`)의 재료이고, 추정매출·R-ONE 은 다음 분기 예측 창의 입력이다 —
   없는 채로 돌리면 서빙 예측이 결측으로 오염된다. 하나라도 없으면 한 줄 기록하고 끝.
4. 공표됐으면 파이프라인을 detached 로 띄운다. 이 작업 자신은 바로 끝난다.

## 파이프라인 (`--pipeline`, detached · 절전 억제를 스스로 건다)

  수집    seoul_trdar --platform13 (+ flpop · income-ix) · rone_rent
  Gold    build_gold --platform13-timeseries — LSTM 입력 하나만.
          ⚠ `--platform13` 은 Program 컨텍스트 CSV 까지 다시 써서 trend·demand 빌더를
            그 뒤에 다시 돌려야 한다. 이 확정과 무관한 산출물은 건드리지 않는다.
  점검    기존 (거점·분기) 쌍이 하나도 안 사라졌는가 · 기다린 분기가 거점의 90%+ 에
          생겼고 그 행의 학습 피처가 유한한가. 아니면 Gold 를 실행 전 것으로 되돌리고 멈춘다.
          (`latest_bronze` 는 가장 최근 날짜 폴더가 이긴다 — 부분 수집본이 Gold 를 만들 수 있다)
  재학습  train_lstm --grid reg-0928 — **사전등록 그리드 그대로**(조기종료 · 약 3분)
  판정    kpi_baseline --json · pppp_status 를 보고서에 옮겨 적는다
  기록    reports/lstm_confirm_<분기>_<날짜>.json — 끝나면 이 예약 작업을 끈다(분기당 한 번)

## 하지 않는 것 — 고치지 않는다, 기록만 한다

- **커밋·푸시·배포.** 재학습은 git 추적 서빙 산출물(`ml/artifacts/vacancy_lstm.pt` ·
  `data/gold/platform_vacancy_forecast.json`)을 로컬에서 바꾼다. 프로덕션에 닿으려면
  사람이 결과를 보고 커밋한다(main 머지 = 배포).
- **결과 해석.** `열위`·`구분불가`·후보 0 이면 사전등록 ⑥(지속성을 못 넘을 때 화면에 무엇을
  보일지)을 정해야 한다 — 창업자 결정이다.
- **GNN 재학습 · 블로그 수집.** `refresh_platform` 은 둘 다 돈다. 이 확정과 무관하다.
- 실패한 단계를 다른 방법으로 우회하지 않는다. 같은 파이프라인을 다음 날 다시 걸 뿐이고,
  `MAX_ATTEMPTS` 번 실패하면 멈추고 사람을 기다린다.

## 실행

    python scripts/lstm_confirm_watch.py --check       # 공표 확인만 (5콜 · 아무것도 안 쓴다)
    python scripts/lstm_confirm_watch.py               # 예약 작업이 부르는 한 번
    python scripts/lstm_confirm_watch.py --install     # 매일 09:17 + 로그온 시 · 놓친 실행은 깨어나서
    python scripts/lstm_confirm_watch.py --uninstall
    python scripts/lstm_confirm_watch.py --status      # 상태 파일 · 작업 등록 상태

돌아와서 읽을 자리: `data/logs/lstm-confirm-watch.log` · `reports/lstm_confirm_*.json` ·
`python scripts/pppp_status.py`(Platform 의 LSTM 게이트 줄에 감시 상태가 붙는다).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# ⚠ Windows 예약작업 이름은 인프라 ID 라 SpaceOS 를 쓴다(2026-09-12 개명 규칙 — 경로·ID 는 그대로).
TASK_NAME = "SpaceOS-LSTM-ConfirmWatch"
DAILY_AT = "09:17"

LOGS = ROOT / "data" / "logs"
LOG = LOGS / "lstm-confirm-watch.log"
STATE = LOGS / "lstm-confirm-watch.state.json"
GOLD_BACKUP = LOGS / "lstm-confirm-watch.gold-backup"
PIDFILE = ROOT / "reports" / "lstm_confirm_watch.pid"
REPORTS = ROOT / "reports"
FORECAST_JSON = ROOT / "data" / "gold" / "platform_vacancy_forecast.json"
GOLD_TS = ROOT / "data" / "gold" / "platform13" / "platform_district_timeseries"

# 사전등록 그리드 — 바꾸면 '확정'이 아니라 새 실험이다(prereg-2026-09-28 §5·§7).
GRID = "reg-0928"
MAX_ATTEMPTS = 3      # 같은 분기 파이프라인 실패 상한 — 넘으면 멈추고 사람을 기다린다
MIN_HUB_RATIO = 0.9   # 기다린 분기 행이 있어야 하는 거점 비율(거점이 늘어도 깨지지 않게 비율로)

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

_HOUR = 3600
# (표시명, python 인자, 필수, 제한시간 초). 수집기는 호출 단위 실패를 삼키고 0 으로 끝나므로
# 종료코드보다 **수집 뒤 Gold 점검**이 진짜 관문이다.
STEPS: tuple[tuple[str, tuple[str, ...], bool, int], ...] = (
    # stor 는 (상권코드 × 분기) 직접 쿼리다 — 352코드 × 23분기. 배터리면 몇 시간이 걸린다.
    ("TRDAR 점포·추정매출·영역", ("-u", "-m", "data.collectors.seoul_trdar", "--platform13"), True, 8 * _HOUR),
    ("TRDAR 길단위인구", ("-u", "-m", "data.collectors.seoul_trdar", "--platform13-flpop"), False, 3 * _HOUR),
    ("TRDAR 상권변화지표", ("-u", "-m", "data.collectors.seoul_trdar", "--platform13-income-ix"), False, 3 * _HOUR),
    ("R-ONE 공실률·임대료", ("-u", "-m", "data.collectors.rone_rent"), True, _HOUR),
    ("Gold 시계열(LSTM 입력 하나만)",
     ("-u", "-m", "data.pipelines.build_gold", "--platform13-timeseries"), True, _HOUR),
)
TRAIN_STEP: tuple[str, tuple[str, ...], bool, int] = (
    "LSTM 확정 재학습", ("-u", "-m", "ml.training.train_lstm", "--grid", GRID), True, 2 * _HOUR)


# ── 기록 ─────────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def say(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)   # pythonw 에서는 stdout 이 없어 조용히 넘어간다
    try:                      # 기록 실패는 감시 실패가 아니다
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_state(path: Path = STATE) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict[str, Any], path: Path = STATE) -> None:
    """임시 파일에 쓰고 바꿔 끼운다 — 쓰는 도중 재부팅돼도 상태 파일이 깨지지 않게."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def pipeline_log(target: str) -> Path:
    return LOGS / f"lstm-confirm-{target}.out.log"


def _redact(msg: str, *secrets: str) -> str:
    for s in secrets:
        if s:
            msg = msg.replace(s, "***")
    return msg


# ── 분기 ─────────────────────────────────────────────────────────────────────

def next_quarter(q: str) -> str:
    """'20262' → '20263' · '20264' → '20271' (STDR_YYQU_CD 형식)."""
    y, n = int(q[:4]), int(q[4:])
    return f"{y + 1}1" if n == 4 else f"{y}{n + 1}"


def rone_time_id(q: str) -> str:
    """'20263' → '202603' — R-ONE `WRTTIME_IDTFR_ID`(2026-10-04 실측: '202602' = 2026년 2분기)."""
    return f"{q[:4]}0{q[4:]}"


def target_quarter(forecast_path: Path = FORECAST_JSON) -> str | None:
    """기다릴 분기 = 서빙 forecast holdout 의 마지막 분기 다음. 못 읽으면 None."""
    try:
        d = json.loads(forecast_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    qs = [str(r["quarter"]) for r in (d.get("holdout") or {}).values()
          if isinstance(r, dict) and r.get("quarter")]
    last = max(qs) if qs else (d.get("protocol") or {}).get("confirm_after")
    return next_quarter(str(last)) if last else None


# ── 공표 확인 ────────────────────────────────────────────────────────────────

def parse_seoul(body: dict, service: str, q: str) -> bool | None:
    """True = 그 분기 행이 있다 · False = INFO-200(없음) · None = 판정 불가(인증·서비스 오류)."""
    if service in body:
        p = body[service] or {}
        rows = p.get("row") or []
        return int(p.get("list_total_count") or 0) > 0 and any(
            str(r.get("STDR_YYQU_CD")) == q for r in rows)
    code = (body.get("RESULT") or {}).get("CODE")
    return False if code == "INFO-200" else None


def parse_rone(body: dict, q: str) -> bool | None:
    """R-ONE SttsApiTblData 응답 판정. 의미는 parse_seoul 과 같다."""
    blk = body.get("SttsApiTblData")
    if blk:
        try:
            total = int(blk[0]["head"][0]["list_total_count"])
            rows = blk[1].get("row", []) if len(blk) > 1 else []
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        return total > 0 and any(str(r.get("WRTTIME_IDTFR_ID")) == rone_time_id(q) for r in rows)
    code = (body.get("RESULT") or {}).get("CODE")
    return False if code == "INFO-200" else None


def _get_json(url: str, ctx: ssl.SSLContext | None = None) -> dict:
    with urllib.request.urlopen(url, timeout=30, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))


def probe(q: str) -> dict[str, Any]:
    """5콜로 공표 여부를 묻는다. 아무것도 쓰지 않는다. 값: True / False / None(판정 불가)."""
    from data.collectors.common import load_env
    from data.collectors.rone_rent import ssl_context
    from data.config.rone_districts import SERIES_TABLES

    load_env()
    skey = os.environ.get("SEOUL_OPENAPI_KEY", "").strip()
    rkey = os.environ.get("REB_RONE_API_KEY", "").strip()
    out: dict[str, Any] = {"quarter": q, "at": now_iso(), "sources": {}, "errors": {}}

    # 두 서비스 모두 분기만으로 경로 필터가 된다(2026-10-04 실측 — stor 20262 75,912행).
    for name, service in (("trdar_stor", "VwsmTrdarStorQq"), ("trdar_selng", "VwsmTrdarSelngQq")):
        try:
            if not skey:
                raise RuntimeError("SEOUL_OPENAPI_KEY 미설정")
            body = _get_json(f"http://openapi.seoul.go.kr:8088/{skey}/json/{service}/1/5/{q}")
            out["sources"][name] = parse_seoul(body, service, q)
        except Exception as exc:  # noqa: BLE001 — 판정 불가로 적고 다음 원천으로
            out["sources"][name] = None
            out["errors"][name] = _redact(str(exc), skey)[:200]

    ctx = ssl_context()
    for series, tables in SERIES_TABLES.items():
        # 목록은 시기순이다 — 마지막이 표본개편(2024Q3) 이후 현행 통계표.
        sid, name = tables[-1], f"rone_{series}"
        try:
            if not rkey:
                raise RuntimeError("REB_RONE_API_KEY 미설정")
            url = ("https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
                   f"?KEY={rkey}&Type=json&pIndex=1&pSize=5&STATBL_ID={sid}"
                   f"&DTACYCLE_CD=QY&WRTTIME_IDTFR_ID={rone_time_id(q)}")
            out["sources"][name] = parse_rone(_get_json(url, ctx), q)
        except Exception as exc:  # noqa: BLE001
            out["sources"][name] = None
            out["errors"][name] = _redact(str(exc), rkey)[:200]

    out["published"] = bool(out["sources"]) and all(v is True for v in out["sources"].values())
    return out


def probe_line(p: dict[str, Any]) -> str:
    mark = {True: "✓", False: "✗", None: "?"}
    s = " · ".join(f"{k} {mark[v]}" for k, v in p.get("sources", {}).items())
    if p.get("errors"):
        s += " · 판정불가: " + "; ".join(f"{k}={v}" for k, v in p["errors"].items())
    return s


# ── 중복 실행 방지 (resume_hub_chain 과 같은 방식 — WMI 를 쓰지 않는다) ────────────

def _start_time(pid: int) -> datetime | None:
    """PID 의 프로세스 시작시각. 죽었으면 None. 재부팅 뒤 PID 재사용을 시작시각으로 가른다."""
    import ctypes
    import ctypes.wintypes as wt

    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        creation = wt.FILETIME()
        rest = (wt.FILETIME * 3)()
        if not k32.GetProcessTimes(h, ctypes.byref(creation), *[ctypes.byref(x) for x in rest]):
            return None
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        utc = datetime(1601, 1, 1) + timedelta(microseconds=ticks / 10)
        return utc + (datetime.now() - datetime.utcnow())
    finally:
        k32.CloseHandle(h)


def running_pid() -> int | None:
    try:
        rec = json.loads(PIDFILE.read_text(encoding="utf-8"))
        started = datetime.fromisoformat(rec["started"])
        actual = _start_time(int(rec["pid"]))
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return None
    if actual is None or abs((actual - started).total_seconds()) > 5:
        return None
    return int(rec["pid"])


def keep_awake(hold: bool = True) -> bool:
    """시스템 유휴 판정을 막는다(화면은 안 붙잡는다). 메인 스레드가 사는 동안 유지된다."""
    try:
        import ctypes
        flags = (0x80000000 | 0x00000001) if hold else 0x80000000   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        return ctypes.windll.kernel32.SetThreadExecutionState(flags) != 0
    except Exception:  # noqa: BLE001
        return False


def power() -> dict[str, Any]:
    """AC 연결·배터리 % — 기록용. 배터리면 수집이 몇 배 느리다(autorun §1)."""
    try:
        import ctypes

        class _SPS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                        ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                        ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
        s = _SPS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
            return {"ac": s.ACLineStatus == 1, "battery_pct": int(s.BatteryLifePercent)}
    except Exception:  # noqa: BLE001
        pass
    return {"ac": None, "battery_pct": None}


# ── 예약 작업 한 번 ──────────────────────────────────────────────────────────

def decide(state: dict[str, Any], target: str | None, busy_pid: int | None) -> str:
    """'busy' | 'no_target' | 'done' | 'gave_up' | 'probe' — 순수 함수(테스트 대상)."""
    if busy_pid:
        return "busy"
    if not target:
        return "no_target"
    if state.get("target") == target:
        if state.get("status") == "done":
            return "done"
        if int(state.get("attempts", 0)) >= MAX_ATTEMPTS:
            return "gave_up"
    return "probe"


def launch(target: str) -> int:
    """파이프라인을 detached 로 띄운다 — 부른 작업·세션이 끝나도 계속 돈다."""
    LOGS.mkdir(parents=True, exist_ok=True)
    fh = pipeline_log(target).open("a", encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        [sys.executable, "-u", str(Path(__file__).resolve()), "--pipeline", "--target", target],
        cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
    )
    started = _start_time(proc.pid) or datetime.now()
    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(json.dumps({"pid": proc.pid, "started": started.isoformat(), "target": target}),
                       encoding="utf-8")
    return proc.pid


def tick() -> int:
    state = load_state()
    target = target_quarter()
    pid = running_pid()
    action = decide(state, target, pid)
    if action == "busy":
        say(f"파이프라인 실행 중 (PID {pid}) — 건드리지 않는다.")
        return 0
    if action == "no_target":
        say(f"기다릴 분기를 못 정했다 — {FORECAST_JSON.relative_to(ROOT)} 를 못 읽었다.")
        return 1
    if action == "done":
        say(f"{target} 확정 실행은 이미 끝났다 — {state.get('report')}. 예약 작업을 끈다.")
        disable_task()
        return 0
    if action == "gave_up":
        say(f"{target} 파이프라인이 {MAX_ATTEMPTS}번 실패했다 — 멈추고 사람을 기다린다. "
            f"마지막 기록: {state.get('report')}")
        disable_task()
        return 0

    p = probe(target)
    if state.get("target") != target:
        state = {"target": target, "attempts": 0}
    state.update(last_probe=p, last_check=p["at"])
    if not p["published"]:
        state["status"] = "waiting"
        save_state(state)
        say(f"{target} 미공표 — {probe_line(p)}")
        return 0
    say(f"{target} 공표 확인 — {probe_line(p)} → 파이프라인 기동")
    new_pid = launch(target)
    state.update(status="launched", pid=new_pid, launched=now_iso())
    save_state(state)
    say(f"파이프라인 PID {new_pid} · 로그 {pipeline_log(target).relative_to(ROOT)}")
    return 0


# ── 파이프라인 ───────────────────────────────────────────────────────────────

def run_step(name: str, args: tuple[str, ...], timeout_s: int, target: str) -> dict[str, Any]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "OMP_NUM_THREADS": "1"}
    t0 = time.time()
    with pipeline_log(target).open("a", encoding="utf-8") as fh:
        fh.write(f"\n━━ {name} · {' '.join(args)} · {now_iso()} ━━\n")
        fh.flush()
        try:
            rc = subprocess.run([sys.executable, *args], cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, env=env, timeout=timeout_s,
                                creationflags=CREATE_NO_WINDOW).returncode
        except subprocess.TimeoutExpired:
            rc = -1
            fh.write(f"[watch] 제한시간 {timeout_s}s 초과 — 중단\n")
    dt = round(time.time() - t0)
    say(f"  {name}: {'완료' if rc == 0 else f'실패(rc={rc})'} · {dt}s")
    return {"name": name, "args": list(args), "rc": rc, "seconds": dt}


def load_gold_frame():
    """학습과 같은 로더로 읽는다(파생 피처 포함). 못 읽으면 None."""
    try:
        from ml.training.datasets import load_gold
        return load_gold()
    except Exception:  # noqa: BLE001 — Gold 없음·R-ONE 열 없음은 점검 실패로 드러난다
        return None


def gold_pairs(df) -> dict[str, set[str]]:
    if df is None:
        return {}
    return {str(d): set(map(str, g["quarter"])) for d, g in df.groupby("district_id")}


def gold_check(before: dict[str, set[str]], after, target: str,
               features: tuple[str, ...] | None = None) -> dict[str, Any]:
    """재학습 전 관문. 순수 함수(테스트 대상) — after 는 load_gold() 모양의 DataFrame."""
    if features is None:
        from ml.training.datasets import SEQ_FEATURES
        features = SEQ_FEATURES
    if after is None:
        return {"ok": False, "problems": ["Gold 를 못 읽었다"], "hubs": 0}
    import numpy as np

    pairs = gold_pairs(after)
    problems: list[str] = []
    lost = sorted(f"{d}@{q}" for d, qs in before.items() for q in qs if q not in pairs.get(d, set()))
    if lost:
        problems.append(f"기존 (거점·분기) {len(lost)}쌍이 사라졌다 — 부분 수집본이 최신 Bronze 가 "
                        f"됐을 수 있다 (예: {', '.join(lost[:5])})")
    hubs = sorted(pairs)
    with_t = [d for d in hubs if target in pairs[d]]
    rows = after[after["quarter"].astype(str) == target]
    vals = rows[list(features)].to_numpy(dtype=float) if len(rows) else np.empty((0, len(features)))
    finite = int(np.isfinite(vals).all(axis=1).sum()) if len(rows) else 0
    n = len(hubs) or 1
    if len(with_t) / n < MIN_HUB_RATIO:
        problems.append(f"{target} 행이 {len(with_t)}/{len(hubs)}거점에만 있다 (기준 {MIN_HUB_RATIO:.0%})")
    if finite / n < MIN_HUB_RATIO:
        problems.append(f"{target} 행 중 학습 피처가 전부 유한한 것이 {finite}/{len(hubs)}거점 "
                        f"(기준 {MIN_HUB_RATIO:.0%}) — 원천 일부가 아직 비어 있다")
    return {"ok": not problems, "problems": problems, "hubs": len(hubs),
            "hubs_with_target": len(with_t), "finite_target_rows": finite, "lost_pairs": len(lost),
            "max_quarter": max((q for qs in pairs.values() for q in qs), default=None)}


def _gold_files() -> list[Path]:
    return [p for p in (GOLD_TS.with_suffix(".parquet"), GOLD_TS.with_suffix(".csv")) if p.exists()]


def backup_gold() -> None:
    shutil.rmtree(GOLD_BACKUP, ignore_errors=True)
    GOLD_BACKUP.mkdir(parents=True, exist_ok=True)
    for f in _gold_files():
        shutil.copy2(f, GOLD_BACKUP / f.name)


def restore_gold() -> None:
    for f in GOLD_BACKUP.glob("platform_district_timeseries.*"):
        shutil.copy2(f, GOLD_TS.parent / f.name)


def training_summary(started: datetime) -> dict[str, Any]:
    """이번 실행이 쓴 시행 보고서에서 선택 결과를, forecast 에서 서빙 교체 여부를 읽는다."""
    from ml.training.lstm_grids import serves

    out: dict[str, Any] = {}
    cands = sorted(REPORTS.glob(f"lstm_trials_{GRID}_*.json"), key=lambda p: p.stat().st_mtime)
    fresh = [p for p in cands if datetime.fromtimestamp(p.stat().st_mtime) >= started]
    if fresh:
        rep = json.loads(fresh[-1].read_text(encoding="utf-8"))
        sel = rep.get("selection") or {}
        out.update(trials_report=str(fresh[-1].relative_to(ROOT)).replace("\\", "/"),
                   selection={k: sel.get(k) for k in ("eligible", "trials", "fallback", "chosen")},
                   served=serves(GRID, sel) if "fallback" in sel else None)
    try:
        fc = json.loads(FORECAST_JSON.read_text(encoding="utf-8"))
        out["forecast_trained_at"] = fc.get("trained_at")
        out["holdout_max_quarter"] = max((str(r["quarter"]) for r in (fc.get("holdout") or {}).values()
                                          if isinstance(r, dict) and r.get("quarter")), default=None)
    except (OSError, json.JSONDecodeError):
        pass
    return out


def _run_capture(args: list[str], timeout_s: int = 900) -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=timeout_s,
                       creationflags=CREATE_NO_WINDOW)
    return r.returncode, r.stdout


def kpi_summary() -> dict[str, Any]:
    """kpi_baseline --json 의 LSTM 판정. 종료코드 1(실력 아닌 축 있음)은 정상 결과다."""
    _, out = _run_capture(["scripts/kpi_baseline.py", "--json"])
    try:
        lstm = (json.loads(out) or {}).get("lstm") or {}
    except json.JSONDecodeError:
        return {"error": "kpi_baseline --json 을 못 읽었다", "raw": out[-500:]}
    keep = ("verdict", "gate_verdict", "baseline_label", "skill_pp", "skill_ci95_pp", "model_acc",
            "baseline_acc", "model_mae", "baseline_mae", "mae_skill", "mae_skill_ci95")
    return {"n": lstm.get("n"),
            "direction": {k: v for k, v in (lstm.get("direction") or {}).items() if k in keep},
            "error": {k: v for k, v in (lstm.get("error") or {}).items() if k in keep},
            "confirmation": lstm.get("confirmation")}


def pppp_platform_lines() -> list[str]:
    _, out = _run_capture(["scripts/pppp_status.py"])
    lines, on = [], False
    for ln in out.splitlines():
        if ln.startswith("Platform"):
            on = True
        elif on and not ln.strip():
            break
        if on:
            lines.append(ln[:300])
    return lines


def git_changes() -> list[str]:
    r = subprocess.run(["git", "status", "--porcelain", "--", "ml/artifacts/vacancy_lstm.pt",
                        "data/gold/platform_vacancy_forecast.json", "reports"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=CREATE_NO_WINDOW)
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def interpret(rep: dict[str, Any]) -> tuple[list[str], list[str]]:
    """보고서 요약과 사람이 할 일. 해석은 하지 않는다 — 판정 코드가 낸 값을 옮길 뿐이다."""
    t = rep["target"]
    tr = rep.get("training") or {}
    k = rep.get("kpi") or {}
    cf = k.get("confirmation") or {}
    dv = (k.get("direction") or {}).get("gate_verdict")
    ev = (k.get("error") or {}).get("gate_verdict")
    summary = [f"{t} 확정 실행 — 결과 {rep['outcome']}: {rep['reason']}"]
    todo: list[str] = []
    if rep["outcome"] != "done":
        todo.append(f"로그를 읽는다: {pipeline_log(t).relative_to(ROOT)} — 고치지 않고 기록만 했다")
        return summary, todo
    sel = tr.get("selection") or {}
    summary.append(f"재학습 후보 {sel.get('eligible')}/{sel.get('trials')} · 선택 trial {sel.get('chosen')} "
                   f"· 서빙 교체 {'예' if tr.get('served') else '아니오'}")
    summary.append(f"게이트 판정({cf.get('after')} 이후 분기 holdout {cf.get('n_fresh')}건) — "
                   f"방향 {dv} · 오차 {ev}")
    if not tr.get("served"):
        todo.append("후보 0 — 서빙본이 그대로라 확정 표본이 생기지 않았다. 사전등록 §6: "
                    "모델을 더 돌리기 전에 ⑥(지속성을 못 넘을 때 화면 문구)을 먼저 정한다")
    elif dv == "실력" and ev == "실력":
        todo.append("두 게이트가 닫혔다 — CLAUDE.md KPI① 표·finding 문서를 이 보고서 값으로 갱신")
    else:
        todo.append("실력이 아닌 축이 있다 — `구분불가`면 다음 분기를 더 기다릴지, `열위`면 "
                    "사전등록 ⑥(화면 문구)을 정한다 · 창업자 결정")
    todo.append("결과를 보고 커밋: ml/artifacts/vacancy_lstm.pt · data/gold/platform_vacancy_forecast.json · "
                f"{tr.get('trials_report', 'reports/lstm_trials_*.json')} · 이 보고서 → PR (main 머지 = 배포)")
    todo.append("다음 분기도 기다리려면: python scripts/lstm_confirm_watch.py --install")
    return summary, todo


def finish(rep: dict[str, Any], state: dict[str, Any], outcome: str, reason: str) -> int:
    rep.update(outcome=outcome, reason=reason, finished=now_iso())
    rep["summary_ko"], rep["next_steps"] = interpret(rep)
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"lstm_confirm_{rep['target']}_{datetime.now():%Y-%m-%d}.json"
    path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    state.update(status=outcome, report=rel, finished=rep["finished"], reason=reason)
    save_state(state)
    for line in rep["summary_ko"]:
        say(line)
    say(f"보고서: {rel}")
    if outcome == "done" or int(state.get("attempts", 0)) >= MAX_ATTEMPTS:
        disable_task()
    try:
        PIDFILE.unlink()
    except OSError:
        pass
    return 0 if outcome == "done" else 1


def pipeline(target: str) -> int:
    keep_awake(True)
    state = load_state()
    if state.get("target") != target:
        state = {"target": target, "attempts": 0}
    state["attempts"] = int(state.get("attempts", 0)) + 1
    started = datetime.now()
    state.update(status="running", started=started.isoformat(timespec="seconds"))
    save_state(state)
    say(f"━━ {target} 확정 파이프라인 시작 (시도 {state['attempts']}/{MAX_ATTEMPTS}) ━━")
    rep: dict[str, Any] = {"target": target, "attempt": state["attempts"], "grid": GRID,
                           "started": state["started"], "probe": state.get("last_probe"),
                           "power_at_start": power(), "steps": []}

    before = gold_pairs(load_gold_frame())
    backup_gold()
    for name, args, critical, timeout_s in STEPS:
        r = run_step(name, args, timeout_s, target)
        rep["steps"].append(r)
        if r["rc"] != 0 and critical:
            return finish(rep, state, "failed", f"필수 단계 실패: {name}")

    chk = gold_check(before, load_gold_frame(), target)
    rep["gold_check"] = chk
    if not chk["ok"]:
        restore_gold()
        return finish(rep, state, "failed",
                      "Gold 점검 실패 — 실행 전 Gold 로 되돌렸다: " + " / ".join(chk["problems"]))

    name, args, _, timeout_s = TRAIN_STEP
    r = run_step(name, args, timeout_s, target)
    rep["steps"].append(r)
    if r["rc"] != 0:
        return finish(rep, state, "failed", "재학습 실패")

    rep["training"] = training_summary(started)
    rep["kpi"] = kpi_summary()
    rep["pppp_platform"] = pppp_platform_lines()
    rep["tracked_changes"] = git_changes()
    return finish(rep, state, "done", "수집 → Gold → 재학습 → 판정 완료")


# ── 작업 스케줄러 ────────────────────────────────────────────────────────────

def _schtasks(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], capture_output=True, text=True,
                          encoding="cp949", errors="replace")


def disable_task() -> None:
    r = _schtasks("/Change", "/TN", TASK_NAME, "/DISABLE")
    say(f"예약 작업 '{TASK_NAME}' " + ("껐다" if r.returncode == 0 else
        f"끄기 실패 — 상태 파일이 다음 실행을 막는다: {(r.stdout + r.stderr).strip()[:120]}"))


def install() -> int:
    """resume_hub_chain.install 과 같은 경로 — schtasks /IT + XML 왕복(관리자 권한 없이)."""
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    action = f'"{exe}" "{Path(__file__).resolve()}"'
    r = _schtasks("/Create", "/TN", TASK_NAME, "/TR", action, "/SC", "DAILY", "/ST", DAILY_AT, "/IT", "/F")
    if r.returncode != 0:
        say(f"작업 등록 실패: {(r.stdout + r.stderr).strip()[:200]}")
        return r.returncode
    xml = REPORTS / f".{TASK_NAME}.xml"
    q = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME, "/XML", "ONE"], capture_output=True)
    s = q.stdout.decode("utf-16" if q.stdout[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8",
                        errors="replace")
    who = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}".strip("\\")
    for old, new in (("<DisallowStartIfOnBatteries>true<", "<DisallowStartIfOnBatteries>false<"),
                     ("<StopIfGoingOnBatteries>true<", "<StopIfGoingOnBatteries>false<"),
                     ("<StopOnIdleEnd>true<", "<StopOnIdleEnd>false<"),
                     ("<StartWhenAvailable>false<", "<StartWhenAvailable>true<"),
                     ("<MultipleInstancesPolicy>IgnoreNew<", "<MultipleInstancesPolicy>StopExisting<")):
        s = s.replace(old, new)
    if "<StartWhenAvailable>" not in s:
        s = s.replace("</Settings>", "    <StartWhenAvailable>true</StartWhenAvailable>\n  </Settings>")
    # 판정·기동은 몇 초다. 10분을 넘겼다면 일하는 중이 아니라 물린 것이다 —
    # 파이프라인은 이 작업의 자식이 아니라 detached 라 여기서 죽지 않는다.
    limit = "<ExecutionTimeLimit>PT10M</ExecutionTimeLimit>"
    if "<ExecutionTimeLimit>" in s:
        s = re.sub(r"<ExecutionTimeLimit>[^<]*</ExecutionTimeLimit>", limit, s)
    else:
        s = s.replace("</Settings>", f"    {limit}\n  </Settings>")
    if "<LogonTrigger>" not in s and who:
        s = s.replace("</Triggers>", f"    <LogonTrigger>\n      <Enabled>true</Enabled>\n"
                                     f"      <UserId>{who}</UserId>\n    </LogonTrigger>\n  </Triggers>")
    xml.write_text(s, encoding="utf-16")
    r2 = _schtasks("/Create", "/TN", TASK_NAME, "/XML", str(xml), "/F")
    xml.unlink(missing_ok=True)
    if r2.returncode != 0:
        say(f"작업 '{TASK_NAME}' 등록 — 매일 {DAILY_AT} (⚠ 배터리·로그온·놓친 실행 설정은 못 넣었다: "
            f"{(r2.stdout + r2.stderr).strip()[:150]})")
    else:
        say(f"작업 '{TASK_NAME}' 등록 — 매일 {DAILY_AT} + 로그온 시 · 놓친 실행은 깨어나서 · 배터리에서도")
    return 0


def uninstall() -> int:
    r = _schtasks("/Delete", "/TN", TASK_NAME, "/F")
    say(f"작업 해제 {'완료' if r.returncode == 0 else '실패'} — 돌고 있는 파이프라인은 그대로 둔다")
    return r.returncode


def status() -> int:
    st = load_state()
    print(json.dumps({k: v for k, v in st.items() if k != "last_probe"}, ensure_ascii=False, indent=2))
    if st.get("last_probe"):
        print("마지막 확인:", st["last_probe"].get("at"), "·", probe_line(st["last_probe"]))
    r = _schtasks("/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V")
    keys = ("Status", "Next Run Time", "Last Run Time", "Last Result", "상태", "다음 실행 시간",
            "마지막 실행 시간", "마지막 결과")
    for ln in r.stdout.splitlines():
        if any(ln.strip().startswith(k) for k in keys):
            print(ln.strip())
    if r.returncode != 0:
        print(f"예약 작업 '{TASK_NAME}' 없음")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--check", action="store_true", help="공표 확인만 (아무것도 안 쓴다)")
    ap.add_argument("--pipeline", action="store_true", help="(내부) 파이프라인 — tick 이 띄운다")
    ap.add_argument("--target", help="--check · --pipeline 대상 분기 (기본: 기다릴 분기)")
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
    if a.check:
        q = a.target or target_quarter()
        if not q:
            print("기다릴 분기를 못 정했다")
            return 1
        p = probe(q)
        print(f"{q} {'공표됨' if p['published'] else '미공표'} — {probe_line(p)}")
        return 0
    if a.pipeline:
        if not a.target:
            ap.error("--pipeline 에는 --target 이 필요하다")
        return pipeline(a.target)
    return tick()


if __name__ == "__main__":
    # pythonw 에는 stderr 가 없다 — 예외가 나면 흔적 없이 사라진다(2026-10-04 첫 예약 실행이
    # 로그 한 줄 없이 끝났다). 무인 진입점은 죽어도 **왜 죽었는지**를 로그에 남겨야 한다.
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001
        import traceback
        say("예외로 끝났다 — 고치지 않고 기록만 한다:\n" + traceback.format_exc())
        raise SystemExit(1)
