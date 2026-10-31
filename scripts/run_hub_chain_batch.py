"""거점 체인 무인 배치 — 세션 밖에서 혼자 돌고, 언제 죽어도 이어받는다.

## 왜 이 스크립트인가

2026-08-30 에 같은 사고를 **세 번** 겪었다: Claude Code 세션이 끝나면 그 안에서 띄운
백그라운드 수집이 함께 죽는다(금촌 대장 300/831 · 인허가 5거점 0행 · 상권 마스터).
토큰 만료도 같은 종류의 죽음이다. 그래서 이 스크립트는 **세션에 매달리지 않는다** —
`pythonw`/detached 로 띄우면 세션이 사라져도 계속 돈다.

## 지키는 것 셋 (2026-08-30 지시)

1. **덮개를 닫아도 돈다** — `scripts/keep_awake.ps1` 로 감싸 실행한다(아래 §실행).
   이 노트북은 Modern Standby(S0)라 전원 설정만으로는 안 잔다고 보장 못 한다.
2. **토큰이 만료돼도 훼손되지 않는다** — 모든 단계가 재개 가능하다. 수집기는 이미 받은
   것을 건너뛰고, 각 거점이 끝날 때마다 상태를 파일에 적는다. 중간에 죽으면 다음 실행이
   그 지점부터 잇는다. **부분 결과를 완료로 적지 않는다.**
3. **배터리 5% 미만이면 정리하고 멈춘다** — 거점 하나를 시작하기 전에 전원을 본다.
   AC 가 없고 5% 미만이면 진행분을 저장하고 정상 종료한다(강제 종료를 기다리지 않는다).
4. **실패한 단계 뒤는 돌리지 않는다**(2026-10-28) — 종전에는 단계가 실패해도 다음 단계로 넘어가
   `calibration.json` 까지 만들었고, `stage_done` 이 그것만 보고 「완료」로 쳐서 **다시는 안 돌렸다.**
   그날 gg3 배치 9거점 중 3곳이 그랬다 — 단대오거리(층별개요 실패 → 정밀커버리지 5.5% · 대표 공실
   미산출) · 신흥(공실유닛 없음) · 영통(분모 재계산 누락). 이제 실패하면 그 거점을 거기서 멈추고
   `gold/{slug}/chain_failed.json` 을 남긴다 → `stage_done` 이 그 단계부터 다시 민다. 표식은 체인이 **끝까지
   갔을 때만** 지운다(중간에 죽거나 `--skip-ledger` 로 일찍 돌아가도 남는다). 같은 단계가 3번 연달아 실패하면
   그 거점은 건너뛰고 재개 작업도 되살리지 않는다 — 사람이 원인을 본 뒤 표식을 지운다.
   시작조차 못 한 실패(0xC0000142 · 자식 프로세스 DLL 초기화 실패)는 그 자리에서 다시 부른다.
5. **쿼터가 끝나면 그날은 대장을 부르지 않는다**(2026-10-28) — 대장 수집기는 쿼터가 끝나도 받은 데까지 저장하고
   exit 0 으로 끝난다. 그래서 대장 단계 뒤에 **받은 건물 수**(429 로 못 받은 `rate_limited` 행은 빼고 — 수집기가
   재개 때 다시 받는 행이다)를 다시 재서, 잘려 있으면 Gold 를 세우지 않고, 한 동도 더 못 받았으면 남은 거점은
   대장 없이 할 일(표식 재빌드 · 인허가 재빌드 · 앵커 보정)만 민 뒤 상태파일에 `quota_day` 를 남긴다 → 재개
   작업(`resume_hub_chain.py`)이 날이 바뀔 때까지 되살리지 않는다. 그날 12:28 재개 배치는 25거점을 거점마다
   2.5분씩 429 백오프로 헛돌며 잘린 대장 위에 Gold 를 세우고 있었다.

## 경기 인허가 (2026-10-28)

경기 거점은 분자 보강(상가정보가 놓친 영업 업소)을 경기데이터드림 `GENRESTRT` 에서 받는다
(`data/collectors/gg_licensing.py`). 이 API 는 시군 필터가 없어 **전량 스캔(≈490콜)** 이라 거점마다
부르지 않고 배치 앞에서 한 번에 받는다 — 그러려면 대상 동을 만들 점포가 먼저 있어야 해서, 점포·폴리곤이
없는 거점은 그 앞에서 받는다(상가정보·V-World 는 건축HUB 와 쿼터가 따로다). 인허가가 Gold 보다 늦게
들어오면 `stage_done` 이 Gold 를 낡은 것으로 보고 다시 세운다(인허가 없이 만든 공실은 과대다).

## 상태

`reports/hub_chain_batch.json` — 거점별 마지막 완료 단계와 시각. 사람이 읽을 로그는
`data/logs/hub-chain-batch.log`. 진행 판정은 이 파일이 아니라 **산출물**이 기준이다
(`scripts/chain_status.py`) — 이 파일은 이력이지 진실이 아니다.

## 실행

    # 무인으로 걸어둘 때 (권장) — 죽으면 10분 안에 스스로 되살아난다
    python scripts/resume_hub_chain.py --install

    # 한 번만 돌릴 때. 절전 억제는 이 스크립트가 스스로 건다(덮개를 닫아도 된다)
    python -u scripts/run_hub_chain_batch.py --batch seoul2

⚠ `keep_awake.ps1` 로 감싸지 않아도 된다(08-31 부터). 작업 스케줄러가 부른 PowerShell 이
  배터리 절약 모드에서 영구히 멈추는 것을 두 번 겪어, 절전 억제를 이 파일 안으로 옮겼다.

    --batch seoul2   서울 미커버 자치구 12거점 (SEOUL_BATCH2_HUBS)
    --batch gg2      경기 2차 13거점
    --batch gg3      경기 3차 50거점(2026-10-28 · 59곳까지)
    --batch gj       광주광역시 13상권(2026-10-30 등록 · 10-31 서빙)
    --hubs a,b,c     직접 지정
    --skip-ledger    대장을 건너뛴다(쿼터 0 · 점포·폴리곤만)
"""
from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

STATE = ROOT / "reports" / "hub_chain_batch.json"
LOG = ROOT / "data" / "logs" / "hub-chain-batch.log"
BATTERY_FLOOR = 5          # % — 이 아래면 새 거점을 시작하지 않는다
LICENSE_BATTERY_FLOOR = 20 # % — 인허가 전량 스캔(≈490콜)은 AC 가 없으면 이만큼은 있어야 시작한다

# 자식 프로세스가 **시작조차 못 한** 종료코드 — 코드가 아니라 환경 탓이라 다시 부르면 대개 선다.
#   0xC0000142 STATUS_DLL_INIT_FAILED — 2026-10-28 gg3 배치 9거점에서 3번(분모 재계산 · 공실유닛 · 층별개요).
#   detached 배치가 콘솔 없는 자식을 띄울 때 DLL 초기화가 물리는 자리다(이 노트북은 DRM·보안 모듈이
#   모든 프로세스에 주입된다). 자식은 CREATE_NO_WINDOW 로 띄워 콘솔 할당 자체를 없앤다.
TRANSIENT_EXIT = {0xC0000142}
RETRIES = 3
RETRY_WAIT_S = 15
CREATE_NO_WINDOW = 0x08000000

# do_hub 가 돌려주는 특수 값 — 대장을 **한 동도 못 받았다**(건축HUB 일일 쿼터 소진). 배치를 오늘은 멈추고
# `quota_day` 를 남긴다 → resume_hub_chain 이 날이 바뀔 때까지 되살리지 않는다. 2026-10-28 에 쿼터가 끝난 뒤에도
# 배치가 거점마다 대장을 2.5분씩 헛돌며(429 백오프) 잘린 대장 위에 Gold 를 세웠고, 재개 작업이 그 배치를
# 다시 띄웠다(그날 12:19 배치 완료 → 12:28 재개 → 25거점 헛돎).
QUOTA = "quota"

# 단계 → 실패하면 어디서부터 다시 미는가(stage_done 의 단계 이름)
REDO_FROM = {
    "폴리곤": "none", "점포": "none",
    "대장(전유부)": "stores", "층별개요": "stores",
    "건물속성": "ledger", "분모 재계산": "ledger", "Page 마스터": "ledger", "건물 이력": "ledger",
    "공실유닛": "ledger", "층 단위 빈 자리": "ledger",
    "앵커 보정": "master",
}


def say(msg: str) -> None:
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


class _SPS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def keep_awake(hold: bool = True) -> bool:
    """덮개를 닫아도 계속 돌게 시스템 유휴 판정을 막는다. 화면은 붙잡지 않는다.

    종전에는 `keep_awake.ps1` 로 감싸 실행했다. 그런데 08-31 에 **작업 스케줄러가
    부른 PowerShell 이 두 번 다 영구히 멈췄다**(배터리 절약 모드에서 conhost 를 띄운
    채 대기). 감시자가 감시 대상보다 먼저 죽으면 무인 운전이 아니다. 그래서 절전
    억제를 여기로 옮겼다 — 이제 이 파일 하나만 살아 있으면 된다.

    ⚠ 스레드 단위 상태다. 메인 스레드에서 걸고, 그 스레드가 사는 동안 유지된다.
    """
    try:
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED if hold else ES_CONTINUOUS
        return ctypes.windll.kernel32.SetThreadExecutionState(flags) != 0
    except Exception:                                    # noqa: BLE001
        return False


def power() -> tuple[bool, int]:
    """(AC 연결 여부, 배터리 %). 못 읽으면 (True, 100) — 못 읽었다고 멈추지 않는다."""
    try:
        s = _SPS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
            return True, 100
        return s.ACLineStatus == 1, int(s.BatteryLifePercent)
    except Exception:                                        # noqa: BLE001
        return True, 100


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".json.tmp")          # 저장 도중 죽어도 기존 파일이 남는다
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE)


def run(mod: list[str], label: str) -> bool:
    """파이썬 모듈 하나를 돌린다. 실패해도 예외를 던지지 않고 False 를 준다 —
    한 거점이 막혀도 배치 전체가 서면 안 된다. 시작조차 못 한 실패(TRANSIENT_EXIT)는
    RETRIES 번까지 다시 부른다."""
    env_note = " ".join(mod)
    say(f"    → {label}: {env_note}")
    for attempt in range(1, RETRIES + 1):
        try:
            r = subprocess.run([sys.executable, "-u", "-m", *mod], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=3600,
                               creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                               env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
        except subprocess.TimeoutExpired:
            say(f"    ✗ {label}: 1시간 초과 — 이 거점은 여기서 멈춘다(재실행하면 이어받는다)")
            return False
        if r.returncode == 0:
            return True
        code = r.returncode & 0xFFFFFFFF
        if code in TRANSIENT_EXIT and attempt < RETRIES:
            say(f"    ↻ {label}: 시작 실패(exit={code:#x}) — {RETRY_WAIT_S}초 뒤 다시 ({attempt}/{RETRIES})")
            time.sleep(RETRY_WAIT_S)
            continue
        tail = (r.stdout or "")[-300:] + (r.stderr or "")[-300:]
        say(f"    ✗ {label}: exit={r.returncode} · {tail.strip()[:200]}")
        return False
    return False


def _marker(slug: str) -> Path:
    return ROOT / "data" / "gold" / slug / "chain_failed.json"


# 같은 단계가 이만큼 **연달아** 실패하면 그 거점은 사람이 봐야 한다 — 재개 작업이 10분마다 같은 실패를
# 되풀이하지 않게 배치·재개 대상에서 뺀다(표식 파일을 지우면 다시 시도한다).
GIVE_UP_AFTER = 3


def _read_marker(slug: str) -> dict | None:
    p = _marker(slug)
    if not p.exists():
        return None
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
        return rec if isinstance(rec, dict) else {"redo_from": "none", "attempts": 1}
    except (json.JSONDecodeError, OSError):
        return {"redo_from": "none", "attempts": 1}   # 표식이 깨졌으면 처음부터 — 완료로 치지 않는다


def mark_failed(slug: str, label: str) -> str:
    """실패한 단계를 산출물 옆에 남긴다 — 상태파일(이력)이 아니라 거점 Gold 폴더에 둬야
    `stage_done`(산출물 기준)이 본다. 같은 단계가 또 실패하면 횟수를 올린다. 돌려주는 값은 다시 밀 단계."""
    redo = REDO_FROM.get(label, "none")
    prev = _read_marker(slug) or {}
    attempts = int(prev.get("attempts") or 1) + 1 if prev.get("step") == label else 1
    p = _marker(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"step": label, "redo_from": redo, "attempts": attempts,
                             "at": datetime.now().isoformat(timespec="seconds")},
                            ensure_ascii=False), encoding="utf-8")
    return redo


def failed_from(slug: str) -> str | None:
    """실패 표식이 가리키는 단계. 없으면 None."""
    rec = _read_marker(slug)
    return (rec.get("redo_from") or "none") if rec else None


def gave_up(slug: str) -> bool:
    """같은 단계가 GIVE_UP_AFTER 번 연달아 실패했나 — 그러면 배치·재개가 이 거점을 건너뛴다."""
    rec = _read_marker(slug)
    return bool(rec) and int(rec.get("attempts") or 1) >= GIVE_UP_AFTER


def clear_failed(slug: str) -> None:
    _marker(slug).unlink(missing_ok=True)


def latest_licensing(slug: str) -> Path | None:
    """거점의 최신 인허가 원본(bronze/{slug}/{날짜}/licensing_biz.json). 날짜 폴더명이 곧 순서다."""
    found = sorted((ROOT / "data" / "bronze").glob(f"{slug}/*/licensing_biz.json"))
    return found[-1] if found else None


def is_gyeonggi(slug: str) -> bool:
    """경기 거점인가 — 도시 레지스트리(sido)로 판정한다. page_hubs 의 배치 dict 이름으로 가르면
    다음 배치(GYEONGGI_BATCH4_HUBS …)가 생길 때 조용히 빠진다."""
    from data.config import page_hubs as ph
    hub = ph.get_hub(slug)
    if hub is None:
        return False
    if str(ROOT / "apps" / "backend") not in sys.path:
        sys.path.insert(0, str(ROOT / "apps" / "backend"))
    try:
        from app.data import cities
    except Exception:                                        # noqa: BLE001
        return False
    city = cities.CITIES.get(getattr(hub, "city", "seoul"))
    return bool(city and city.sido == "경기도")


def hubs_of(batch: str) -> list[str]:
    from data.config import page_hubs as ph
    if batch == "seoul2":
        return list(ph.SEOUL_BATCH2_HUBS)
    if batch == "gg2":
        return [k for k in ph.GYEONGGI_HUBS
                if k not in ("hwajeong", "geumchon", "ilsan", "westerndom",
                             "tanhyeon", "unjeong", "yadang")]
    if batch == "gg3":
        return list(ph.GYEONGGI_BATCH3_HUBS)     # 경기 3차 50거점(2026-10-28 · 59곳까지)
    if batch == "gj":
        return list(ph.GWANGJU_HUBS)             # 광주광역시 13상권(2026-10-30)
    raise SystemExit(f"모르는 배치: {batch}")


def ledger_gap(slug: str) -> int:
    """대장 후보 대비 **아직 안 받은 동수.** 0 이면 완주, -1 이면 판단 불가.

    ⚠ **파일이 있다고 대장이 끝난 게 아니다.** 수집기는 150동마다 gold 를 저장하므로
      중간에 죽어도 `building_vacancy.json` 은 남는다. 그런데 종전 `stage_done` 은
      그 존재만으로 "ledger 완료"로 보고 대장 단계를 건너뛰어 파이프라인부터 돌렸다.
      2026-09-01 에 **kkachisan 450/797(56%) · sangbong 600/859(70%) 이 잘린 채
      anchor 까지 찍혔다** — sangbong 은 0.2분 만에 '완료'로 기록됐다. 배치가 죽고
      감시자가 되살릴 때마다 재현되는 구조였다(잃은 데이터는 없다. 판정만 틀렸다).

    후보 수는 수집기와 **같은 방식**으로 센다(점포를 건물로 묶은 수). 수집기는 대상
    전량에 행을 쓰므로(못 받은 건물도 `no_ledger`·`non_commercial` 로 남는다) 완주하면
    행 수 == 후보 수다 — 09-01 실측에서 완주한 7거점이 정확히 100% 로 맞았다.

    점포 원본을 읽어야 해서 거점당 수 MB 를 파싱한다. 몇 초 걸리지만, 이 몇 초가
    "받은 줄 알았는데 안 받은" 거점을 막는다.
    """
    c = ledger_counts(slug)
    return -1 if c is None else max(0, c[0] - c[1])


# 수집기가 「못 받았다」고 적는 행 — building_vacancy._RETRY_METHODS 와 같다. 재개 때 수집기가 이 행을 버리고
# 다시 받으므로 **받은 건물이 아니다.** 2026-10-28 에 쿼터가 끝난 거점 36곳이 이 행 5개짜리 대장을 남겼는데,
# 종전 셈은 그것을 받은 5동으로 쳐 「진전이 있었다」고 읽었다.
RETRY_METHODS = {"rate_limited"}


def ledger_counts(slug: str) -> tuple[int, int, int] | None:
    """(후보 건물 수, 받은 건물 수, 429 로 못 받은 행 수). 점포 원본이 없거나 못 읽으면 None.

    대장 파일이 아직 없으면 받은 것은 0 이다. 후보 수는 수집기와 같은 방식으로 센다(`ledger_gap`)."""
    try:
        import contextlib
        import io
        from data.collectors.building_vacancy import group_by_building
        from data.collectors.common import load_latest
        stores = load_latest(slug, "stores_raw.json")
        if not stores:
            return None
        with contextlib.redirect_stdout(io.StringIO()):      # 「[group] 건물 N동 …」 은 판정의 부산물이다
            cand = len(group_by_building(stores))
        gold = ROOT / "data" / "gold" / slug / "building_vacancy.json"
        rows = json.loads(gold.read_text(encoding="utf-8")) if gold.exists() else []
        limited = sum(1 for r in rows if isinstance(r, dict) and r.get("capacity_method") in RETRY_METHODS)
        return cand, len(rows) - limited, limited
    except Exception:                                        # noqa: BLE001
        return None                  # 판단이 안 되면 완주로도 미완으로도 몰지 않는다


_ORDER = {"none": 0, "stores": 1, "ledger": 2, "master": 3, "anchor": 4}


def licensing_stale(slug: str) -> bool:
    """인허가가 Page 마스터보다 늦게 들어왔나 — 그러면 분자 보강(`_licensed_pip`) 없이 선 Gold 다.

    ⚠ 대조 기준은 인허가를 **실제로 읽는** `page_building_master.geojson` 이다. 종전에는 calibration.json 과
    견줬는데, 앵커 보정만 다시 돌면(실패 표식 'master' · 인자 없는 `calibrate_vacancy`) calibration 이 새로워져
    인허가가 빠진 마스터가 「신선」으로 보였다(2026-10-28 리뷰)."""
    lic = latest_licensing(slug)
    master = ROOT / "data" / "gold" / slug / "page_building_master.geojson"
    return lic is not None and master.exists() and lic.stat().st_mtime > master.stat().st_mtime


def artifact_stage(slug: str) -> str:
    """산출물만으로 판정한 단계 — 실패 표식은 보지 않는다(do_hub 가 체인 도중에 다시 잴 때 쓴다)."""
    gold = ROOT / "data" / "gold" / slug
    if ledger_gap(slug) > 0:
        # 대장이 잘렸다. 뒤 단계 산출물이 이미 있어도 **대장부터 다시** 세운다 —
        # 잘린 분모로 만든 공실률·앵커는 틀린 값이지 '조금 부족한 값'이 아니다.
        return "stores"
    if (gold / "calibration.json").exists():
        stage = "anchor"
    elif (gold / "page_building_master.geojson").exists():
        stage = "master"
    elif (gold / "building_vacancy.json").exists():
        stage = "ledger"
    elif has_stores(slug):
        stage = "stores"
    else:
        stage = "none"
    if _ORDER[stage] >= _ORDER["master"] and licensing_stale(slug):
        stage = "ledger"             # Gold 가 인허가보다 먼저 섰다 — 공실이 과대다. 다시 세운다
    return stage


def stage_done(slug: str) -> str:
    """산출물로 판정한 마지막 완료 단계. 상태파일이 아니라 파일이 기준이다.

    산출물 · 실패 표식 · 인허가 신선도 중 **가장 앞 단계**를 돌려준다 — 하나가 다른 하나를 가리지 않는다
    (종전에는 표식이 있으면 인허가 신선도를 보지 않아, 표식 'master' 가 마스터 재빌드를 건너뛰게 했다)."""
    stage = artifact_stage(slug)
    redo = failed_from(slug)
    if redo and _ORDER.get(redo, 0) < _ORDER[stage]:
        stage = redo                 # 앞선 실행이 이 단계에서 실패했다 — 뒤 산출물이 있어도 완료가 아니다(§지키는 것 4)
    return stage


def do_hub(slug: str, skip_ledger: bool, quota_out: bool = False) -> str:
    """거점 하나를 체인 끝까지 민다. 반환은 도달한 단계(또는 QUOTA).

    한 단계라도 실패하면 **거기서 멈추고** 표식을 남긴다(§지키는 것 4) — 실패한 단계 뒤를 돌리면
    낡거나 빈 입력으로 Gold·앵커가 서고, 그 `calibration.json` 이 거점을 「완료」로 보이게 한다.
    표식은 체인이 **끝까지 갔을 때만** 지운다 — 시작에서 지우면 `--skip-ledger` 로 일찍 돌아가거나 중간에 죽은
    거점이 옛 Gold 위에서 「완료」로 보인다(2026-10-28 리뷰).

    `quota_out` — 오늘 대장 쿼터가 끝났다. 대장(건축HUB)을 부르는 단계는 건너뛰고, 대장이 필요 없는 일
    (표식이 가리킨 재빌드 · 인허가 신선도 재빌드 · 앵커 보정)은 그대로 민다.
    """
    done = stage_done(slug)
    mark = _read_marker(slug)
    say(f"  ■ {slug} (현재 {done})"
        + (f" · 실패 표식 「{mark.get('step', '?')}」 {mark.get('attempts', 1)}회" if mark else ""))

    def step(mod: list[str], label: str) -> bool:
        if run(mod, label):
            return True
        redo = mark_failed(slug, label)
        say(f"    ⏸ {slug}: 「{label}」 실패 — 뒤 단계를 멈춘다(다음 실행이 '{redo}' 부터 다시 민다)")
        return False

    if done == "none":
        if not step(["data.collectors.vworld_bldg", slug], "폴리곤"):
            return "none"
        if not step(["data.collectors.building_vacancy", slug, "--no-ledger"], "점포"):
            return "none"
        done = artifact_stage(slug)  # 표식은 그대로 둔다 — 체인이 끝날 때 지운다

    if skip_ledger:
        return done

    # 대장을 새로 받았으면 뒤 단계는 **낡았다.** 그때는 산출물이 있어도 다시 세운다 —
    # 안 그러면 새 분자·분모가 지도와 앵커에 반영되지 않는다. 2026-09-01 에 kkachisan·
    # sangbong 이 그 상태였다: 잘린 대장을 이어 받아 797·859동을 채웠는데, 이미 있던
    # master·calibration 때문에 `done`이 곧장 "anchor" 로 뛰어 파이프라인 넷과 앵커
    # 보정이 통째로 건너뛰어졌다(calibration 이 00:11·22:14 자로 남았다). 잘린 분모로
    # 만든 값이 그대로 서빙될 뻔했다.
    rebuilt = False
    if done in ("stores",):
        if quota_out:
            return "stores"          # 오늘은 대장 쿼터가 끝났다 — 건축HUB 를 부르지 않는다
        c0 = ledger_counts(slug)
        if not step(["data.collectors.building_vacancy", slug], "대장(전유부)"):
            return "stores"
        if not step(["data.collectors.floor_capacity", slug], "층별개요"):
            return "stores"
        c1 = ledger_counts(slug)
        if c1 is None:
            return "stores"          # 판단 불가 — 다음 실행이 다시 잰다
        # 수집기는 쿼터가 끝나도 받은 데까지 저장하고 exit 0 으로 끝난다 — 종료코드로는 「다 받았다」와
        # 「쿼터가 끝났다」를 못 가른다. 그래서 **받은 건물 수**(429 행 제외)로 잰다. 대장이 아직 잘려 있으면
        # Gold 를 세우지 않고(잘린 분모로 만든 공실률·앵커는 틀린 값이다), 한 동도 더 못 받았으면 그날은 멈춘다.
        cand, got, limited = c1
        if got < cand:
            if got <= (c0[1] if c0 else 0):
                why = (f"429 로 못 받은 {limited}동 — 건축HUB 쿼터 소진" if limited
                       else "응답 없음 — 키·네트워크를 확인할 것")
                say(f"    ⏸ {slug}: 대장을 한 동도 더 못 받았다({got}/{cand}동) — {why}")
                return QUOTA
            say(f"    ⏸ {slug}: 대장 {cand - got}동이 아직 남았다({got}/{cand}) — Gold 는 대장이 다 찬 뒤에 세운다")
            return "stores"
        rebuilt = True
        done = artifact_stage(slug)

    if rebuilt or done in ("ledger",):
        steps = [
            ("data.pipelines.build_building_attrs", "건물속성"),
            ("data.pipelines.recalc_floor_ouln", "분모 재계산"),
            ("data.pipelines.build_page_master", "Page 마스터"),
            # 건물 영업이력 — 런타임에 읽히는 Gold 다(Dockerfile 이 data/gold 를 COPY). 2026-10-28 경기 3차 50거점에 인허가가
            # 들어오자 이 단계가 배치에 없어 이력이 비었다(가드 tests/test_building_history.test_history_covers_all_page_master_districts).
            # 인허가가 없는 거점은 빌더가 exit 1 이라 부르지 않는다 — 부르면 실패 표식으로 영영 막힌다.
            *([("data.pipelines.build_building_history", "건물 이력")] if latest_licensing(slug) else []),
            ("data.pipelines.build_vacant_units", "공실유닛"),
            # 층 단위 빈 자리 — 창업자 흐름 R3 가 읽는다. 2026-10-27 고양·파주 9거점이 이 단계 없이 서빙돼
            # R3 가 비었다(가드 tests/test_floor_vacancies.test_every_served_hub_has_floor_inventory).
            ("data.pipelines.build_vacant_floor_units", "층 단위 빈 자리"),
        ]
        for mod, label in steps:
            if not step([mod, slug], label):
                return "ledger"
        # Gold 를 다시 세웠으면 앵커 보정도 다시 한다 — `calibration.json` 이 이미 있어
        # 산출물 판정이 "anchor" 를 돌려줘도(실패 표식·인허가 갱신으로 다시 세운 경우) 그것은 옛 Gold 의 값이다.
        rebuilt = True
        done = artifact_stage(slug)

    if rebuilt or done in ("master",):
        if not step(["data.pipelines.calibrate_vacancy", slug], "앵커 보정"):
            return "master"
    clear_failed(slug)               # 체인이 끝까지 갔다 — 표식이 가리킨 단계부터 다시 밀었다
    return stage_done(slug)


def has_stores(slug: str) -> bool:
    return bool(list((ROOT / "data" / "bronze").glob(f"{slug}/*/stores_raw.json")))


def license_upfront(hubs: list[str]) -> None:
    """경기 거점의 인허가를 배치 앞에서 **한 번에** 받는다(§경기 인허가).

    실패해도 배치는 계속 간다 — Gold 는 인허가 없이 서고(공실 과대), 다음 실행에서 인허가가
    들어오면 `stage_done` 의 신선도 판정이 다시 세운다. 그 사실은 로그 끝줄에 남긴다.
    """
    need = [s for s in hubs if is_gyeonggi(s) and latest_licensing(s) is None]
    if not need:
        return
    for s in need:               # 대상 동을 만들 점포가 먼저다 — 없으면 그 거점만 받는다
        if not has_stores(s):
            say(f"  ■ {s} — 인허가 대상 동을 만들 점포·폴리곤 먼저")
            if not run(["data.collectors.vworld_bldg", s], "폴리곤") \
                    or not run(["data.collectors.building_vacancy", s, "--no-ledger"], "점포"):
                say(f"    ⏸ {s}: 점포·폴리곤 실패 — 인허가에서 뺀다(거점 차례에 다시 받는다)")
    need = [s for s in need if has_stores(s)]
    if need:
        run(["data.collectors.gg_licensing", *need], f"인허가(경기 {len(need)}거점 · 전량 스캔 1회)")


def licensing_gap(hubs: list[str]) -> list[str]:
    """인허가 없이 Gold 가 선 경기 거점 — 공실이 과대일 수 있다."""
    return [s for s in hubs if is_gyeonggi(s) and latest_licensing(s) is None
            and (ROOT / "data" / "gold" / s / "calibration.json").exists()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="seoul2")
    ap.add_argument("--hubs", default="")
    ap.add_argument("--skip-ledger", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="수집하지 않고 남은 일만 판정한다. 종료코드 0=남음 · 3=전부 완료")
    a = ap.parse_args()

    hubs = [h.strip() for h in a.hubs.split(",") if h.strip()] or hubs_of(a.batch)

    if a.check:
        # 감시자(resume_hub_chain.ps1)가 부른다. **산출물로만** 판정한다 —
        # 상태파일은 이력이지 진실이 아니고, 배치가 죽은 자리에서는 특히 그렇다.
        done = {s: stage_done(s) for s in hubs}
        stuck = {s for s in hubs if gave_up(s)}
        left = [s for s, v in done.items() if v != "anchor" and s not in stuck]
        for s, v in done.items():
            print(f"  {s:<14}{v}" + ("  ⛔ 사람 확인(같은 단계 연속 실패)" if s in stuck else ""))
        print(f"남은 거점 {len(left)}/{len(hubs)}" + (f" — {' '.join(left)}" if left else "")
              + (f" · 사람 확인 {len(stuck)}곳 — {' '.join(sorted(stuck))}" if stuck else ""))
        return 0 if left else 3

    st = load_state()
    awake = keep_awake()
    say(f"=== 배치 시작 · 거점 {len(hubs)} · skip_ledger={a.skip_ledger} · "
        f"절전억제={'걸림' if awake else '실패(덮개를 열어 둘 것)'} ===")
    # 인허가 전량 스캔(≈490콜)은 거점 하나보다 길다 — 배터리가 낮으면 시작하지 않는다(§지키는 것 3).
    # 스테이지는 완주해야 저장되므로 도중에 꺼지면 스캔이 통째로 날아간다.
    ac, pct = power()
    if ac or pct >= LICENSE_BATTERY_FLOOR:
        license_upfront(hubs)
    else:
        say(f"  (배터리 {pct}% · AC 없음 — 인허가 전량 스캔은 다음 실행에 넘긴다)")
    quota_out, quota_why = False, ""

    for i, slug in enumerate(hubs, 1):
        ac, pct = power()
        if not ac and pct < BATTERY_FLOOR:
            say(f"⚠ 배터리 {pct}% (AC 없음) — 새 거점을 시작하지 않는다. "
                f"진행분 저장하고 정상 종료 ({i-1}/{len(hubs)} 완료)")
            st["stopped_reason"] = f"battery {pct}%"
            st["stopped_at"] = datetime.now().isoformat(timespec="seconds")
            save_state(st)
            keep_awake(False)
            return 0
        if not ac:
            say(f"  (배터리 {pct}% — AC 없음. 2~7배 느리다)")

        if gave_up(slug):
            mark = _read_marker(slug) or {}
            say(f"  ⛔ {slug}: 「{mark.get('step', '?')}」 이 {mark.get('attempts')}번 연달아 실패 — 건너뛴다. "
                f"사람이 원인을 본 뒤 gold/{slug}/chain_failed.json 을 지우면 다시 시도한다")
            continue

        t0 = time.time()
        reached = do_hub(slug, a.skip_ledger, quota_out=quota_out)
        if reached == QUOTA:
            # 오늘 대장은 끝났다. 남은 거점 중 대장이 필요 없는 일(표식 재빌드 · 인허가 재빌드 · 앵커 보정)은 마저 민다.
            quota_out, quota_why = True, slug
            reached = stage_done(slug)
            say(f"  ⏸ 건축HUB 대장 쿼터가 오늘은 끝났다({slug}) — 남은 거점은 대장 없이 할 일만 민다")
        st[slug] = {"stage": reached, "at": datetime.now().isoformat(timespec="seconds"),
                    "minutes": round((time.time() - t0) / 60, 1)}
        save_state(st)                       # 거점 하나가 끝날 때마다 저장한다
        say(f"  ✓ {slug} → {reached} ({st[slug]['minutes']}분) [{i}/{len(hubs)}]")

    if quota_out:
        st["stopped_reason"] = f"quota ({quota_why})"
        st["stopped_at"] = datetime.now().isoformat(timespec="seconds")
        st["quota_day"] = date.today().isoformat()          # resume_hub_chain 이 오늘은 되살리지 않는다
        say("⏸ 대장 쿼터 소진 — 재개 작업이 날이 바뀐 뒤 잇는다")
    st["finished_at"] = datetime.now().isoformat(timespec="seconds")
    save_state(st)
    keep_awake(False)                    # 놓아주지 않으면 이 프로세스가 죽을 때까지 막힌다
    stuck = [s for s in hubs if gave_up(s)]
    if stuck:
        say(f"⛔ 같은 단계가 {GIVE_UP_AFTER}번 연달아 실패해 건너뛴 거점 {len(stuck)}곳 — {' '.join(stuck)} "
            f"(재개 작업도 이 거점은 되살리지 않는다 · 원인을 본 뒤 chain_failed.json 을 지울 것)")
    failed = [s for s in hubs if failed_from(s) and not gave_up(s)]
    if failed:
        say(f"⚠ 단계가 실패해 멈춘 거점 {len(failed)}곳 — {' '.join(failed)} "
            f"(gold/{{slug}}/chain_failed.json · 다음 실행이 그 단계부터 다시 민다)")
    gap = licensing_gap(hubs)
    if gap:
        say(f"⚠ 인허가 없이 Gold 가 선 경기 거점 {len(gap)}곳 — 공실이 과대일 수 있다: {' '.join(gap)} "
            f"(`python -m data.collectors.gg_licensing <slug…>` 뒤 재개하면 다시 세운다)")
    say("=== 배치 완료 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
