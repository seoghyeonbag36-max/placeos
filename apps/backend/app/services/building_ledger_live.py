"""트윈 건물 한 채의 건축물대장 실시간 조회 — 승강기 · 층별개요 용도별 행 (2026-11-09 사용자 요청).

Gold(`building_floors.json.gz`)는 층별개요를 **층당 한 줄로 접고** 표제부의 승강기 수를 싣지 않는다. 트윈 창을 열 때
그 건물 한 지번만 건축HUB(`BldRgstHubService`)에 물어 두 가지를 채운다.

- 표제부(`getBrTitleInfo`) — 승용 승강기 수(`rideUseElvtCnt`) · 비상용 승강기 수(`emgenUseElvtCnt`). 같은 지번에 동이 여럿이면
  연면적이 가장 큰 주건축물(수집 파이프라인 `build_building_floors.load_titles` 와 같은 규칙).
- 층별개요(`getBrFlrOulnInfo`) — 층마다 용도별 행(예: 1층 소매점 · 주차장 · 계단실). 계단실 · 승강기 관련 행의 넓이를 따로 센다.

키는 서버의 `DATA_GO_KR_SERVICE_KEY`(공공데이터포털 공용 키 · Program 원천과 같은 키)다 — 그 계정에 건축HUB 활용신청이
돼 있어야 한다. 키가 없거나 거절되면 예외 없이 `status` 로 사유를 돌려준다(트윈은 그대로 보인다).

## 이 값이 아닌 것

- 승강기 **위치**는 대장에 없다 — 개수만 실측이다. 배치도의 승강기 칸 자리 · 크기는 개략이다.
- 계단 **개수**는 대장에 없다. 층별개요에 계단실 행이 있으면 그 층의 계단실 넓이만 실측이다.
- 필드 이름은 공식 활용가이드로 확인하지 못했다(2026-11-09) — 응답에 없으면 `elevators=None` · `fields_missing` 으로 밝힌다.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request

from app.core.config import settings

BASE = "http://apis.data.go.kr/1613000/BldRgstHubService"
SOURCE = "건축물대장(건축HUB) 표제부 · 층별개요 — 실시간 조회"
_TIMEOUT_S = 8.0
_TTL_S = 6 * 3600.0          # 대장은 자주 안 바뀐다 — 같은 지번은 6시간 재사용
_FAIL_BACKOFF_S = 60.0       # 실패 뒤 잠시 다시 치지 않는다(키 거절 · 장애 때 트윈마다 기다리지 않게)
_MAX_PAGES = 5
_CACHE_MAX = 512
_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()
_last_fail = 0.0
log = logging.getLogger("building_ledger_live")


class LedgerError(Exception):
    """건축HUB 가 정상 HTTP 로 오류 코드를 돌려줬다(키 미등록 · 트래픽 초과 등)."""


def jibun_of(pnu: str) -> dict | None:
    """PNU(19자리) → 건축HUB 지번 파라미터. 수집기 `building_vacancy._jibun` 과 같은 규칙(산 구분 1→0 대지 · 2→1 산)."""
    if not re.fullmatch(r"\d{19}", pnu or ""):
        return None
    return {"sigunguCd": pnu[0:5], "bjdongCd": pnu[5:10], "platGbCd": str(max(int(pnu[10]) - 1, 0)),
            "bun": pnu[11:15], "ji": pnu[15:19]}


def _items(doc: dict) -> list[dict]:
    resp = doc.get("response") or {}
    header = resp.get("header") or {}
    code = str(header.get("resultCode") or "00")
    if code not in ("00", "0", "000"):
        raise LedgerError(f"{code} {header.get('resultMsg') or ''}".strip())
    items = ((resp.get("body") or {}).get("items") or {})
    item = items.get("item") if isinstance(items, dict) else None
    if item is None:
        return []
    return item if isinstance(item, list) else [item]


def _fetch(op: str, jibun: dict, key: str) -> list[dict]:
    rows: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        q = urllib.parse.urlencode({"serviceKey": key, "_type": "json", "numOfRows": 100, "pageNo": page, **jibun})
        req = urllib.request.Request(f"{BASE}/{op}?{q}", headers={"User-Agent": "PlaceOS-twin-ledger/1.0"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as r:
            raw = r.read()
        try:
            doc = json.loads(raw)
        except ValueError:
            # 키 오류는 JSON 대신 XML 로 온다(OpenAPI_ServiceResponse) — 사유 문구만 뽑는다
            msg = re.search(rb"<returnAuthMsg>([^<]+)</returnAuthMsg>", raw) or re.search(rb"<errMsg>([^<]+)</errMsg>", raw)
            raise LedgerError(msg.group(1).decode("utf-8", "replace") if msg else "응답이 JSON 이 아님")
        got = _items(doc)
        rows += got
        total = int(((doc.get("response") or {}).get("body") or {}).get("totalCount") or 0)
        if not got or len(rows) >= total:
            break
    return rows


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _int_or_none(v) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def main_title(rows: list[dict]) -> dict | None:
    """같은 지번 여러 동 중 대표 — 주건축물 우선 · 연면적 최대."""
    if not rows:
        return None
    return max(rows, key=lambda r: ("부속" not in str(r.get("mainAtchGbCdNm") or ""), _num(r.get("totArea"))))


def floor_level(row: dict) -> int | None:
    """층별개요 행 → 층 번호(지하 음수). 옥탑·미상은 None."""
    gb = str(row.get("flrGbCdNm") or "")
    no = _int_or_none(row.get("flrNo"))
    if no is None or no <= 0:
        return None
    if "지하" in gb:
        return -no
    if "지상" in gb:
        return no
    return None


_STAIR = re.compile(r"계단")
_EV = re.compile(r"승강기|엘리베이터|엘레베이터|승강로")


def summarise(titles: list[dict], floor_rows: list[dict]) -> dict:
    """표제부 · 층별개요 행 → 트윈에 실을 값(순수 함수 — 시험은 여기를 본다)."""
    t = main_title(titles)
    ride = _int_or_none((t or {}).get("rideUseElvtCnt"))
    emer = _int_or_none((t or {}).get("emgenUseElvtCnt"))
    elevators = None if (ride is None and emer is None) else {"passenger": ride or 0, "emergency": emer or 0}
    dong = str((t or {}).get("dongNm") or "").strip()
    floors: dict[str, dict] = {}
    for r in floor_rows:
        if dong and str(r.get("dongNm") or "").strip() not in ("", dong):
            continue   # 같은 지번 다른 동의 행은 뺀다
        lv = floor_level(r)
        if lv is None:
            continue
        purps, etc, area = str(r.get("mainPurpsCdNm") or "").strip(), str(r.get("etcPurps") or "").strip(), _num(r.get("area"))
        f = floors.setdefault(str(lv), {"parts": [], "stair_m2": 0.0, "ev_m2": 0.0})
        f["parts"].append({"purps": purps or None, "etc": (etc if etc and etc != purps else None), "area_m2": round(area, 2)})
        text = f"{purps} {etc}"
        if _STAIR.search(text):
            f["stair_m2"] = round(f["stair_m2"] + area, 2)
        if _EV.search(text):
            f["ev_m2"] = round(f["ev_m2"] + area, 2)
    for f in floors.values():
        f["parts"].sort(key=lambda p: -p["area_m2"])
        f["stair_m2"] = f["stair_m2"] or None
        f["ev_m2"] = f["ev_m2"] or None
    return {
        "elevators": elevators,
        "fields_missing": t is not None and elevators is None,
        "title": None if t is None else {
            "dong": dong or None, "grnd": _int_or_none(t.get("grndFlrCnt")), "ugrnd": _int_or_none(t.get("ugrndFlrCnt")),
            "height_m": _num(t.get("heit")) or None, "tot_area_m2": _num(t.get("totArea")) or None,
            "strct": str(t.get("strctCdNm") or "").strip() or None, "n_titles": len(titles),
        },
        "floors": floors or None,
    }


def ledger(pnu: str) -> dict:
    """한 지번의 실시간 대장 요약. 예외를 내지 않는다 — 실패하면 status 에 사유."""
    global _last_fail
    base = {"source": SOURCE, "elevators": None, "fields_missing": False, "title": None, "floors": None}
    jib = jibun_of(pnu)
    if jib is None:
        return {**base, "status": "no_pnu"}
    key = settings.data_go_kr_service_key
    if not key:
        return {**base, "status": "no_key"}
    now = time.monotonic()
    with _lock:
        hit = _cache.get(pnu)
        if hit and now - hit[0] < _TTL_S:
            return hit[1]
        if now - _last_fail < _FAIL_BACKOFF_S:
            return {**base, "status": "backoff"}
    try:
        titles = _fetch("getBrTitleInfo", jib, key)
        floor_rows = _fetch("getBrFlrOulnInfo", jib, key)
    except LedgerError as e:
        log.warning("ledger live %s refused: %s", pnu, e)
        with _lock:
            _last_fail = time.monotonic()
        return {**base, "status": "refused", "error": str(e)[:120]}
    except Exception as e:  # 네트워크 · 형식 오류 — 트윈은 그대로
        log.warning("ledger live %s failed: %s: %s", pnu, type(e).__name__, e)
        with _lock:
            _last_fail = time.monotonic()
        return {**base, "status": "error", "error": type(e).__name__}
    out = {**base, **summarise(titles, floor_rows), "status": "ok"}
    with _lock:
        if len(_cache) >= _CACHE_MAX:
            _cache.pop(next(iter(_cache)))
        _cache[pnu] = (time.monotonic(), out)
    return out
