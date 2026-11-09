"""트윈 건물 한 지번의 월별 가스 사용량 — 건축HUB 건물에너지정보 실시간 조회 (2026-11-09 사용자 요청).

원천: 국토교통부 건축HUB 건물에너지정보 서비스(공공데이터포털 15135963) `BldEngyHubService/getBeGasUsgInfo`.
국가건물에너지 통합관리시스템이 모은 **지번 단위 · 월별** 사용량이다. 키는 서버의 `DATA_GO_KR_SERVICE_KEY`
(건축물대장 실시간 조회와 같은 공공데이터포털 계정 키)이고, 그 계정에 **이 서비스 활용신청**이 돼 있어야 한다.
안 돼 있으면 예외 없이 `status: refused` 와 원천 사유를 돌려준다 — 신청이 승인되면 재배포 없이 그날부터 값이 나온다.

## 확인한 것 · 확인 못 한 것

- 오퍼레이션 이름(`getBeGasUsgInfo` · 전기 `getBeElctyUsgInfo`) · 요청변수(`sigunguCd` · `bjdongCd` · `bun` · `ji` · `useYm`) ·
  응답의 `useYm` · `useQty` 는 공개 코드의 호출 예로 맞췄다(이 저장소의 실행 환경은 data.go.kr 명세 페이지에 닿지 않는다).
  공식 활용가이드로 대조하지 못했다 — 배포 뒤 프로덕션 응답으로 확인하고 응답에 `fields`(첫 행의 키)를 실어 드러낸다.
- `type=json` 이어도 XML 로 온다는 보고가 있어 XML · JSON 둘 다 읽는다.
- `useYm` 을 빼면 여러 달이 오는지 모른다 — 먼저 한 번 빼고 불러 두 달 이상이 오면 그것을 쓰고, 아니면 최근 달부터 한 달씩 묻는다.
- **단위**는 응답에 단위 필드가 있으면 싣고, 없으면 싣지 않는다(공개 코드 주석에는 MJ 라고 적혀 있으나 확인하지 못했다).

## 이 값이 아닌 것

- 지번 합계다 — 같은 지번에 건물이 여럿이면 합이고, 집합건물은 호실을 가를 수 없다.
- 단독주택 · 200세대 미만 공동주택은 원천에 없다(빈 응답은 「0 을 썼다」가 아니라 「자료 없음」이다).
- 가스는 난방 계절을 탄다 — 여름에 적은 것은 공실 신호가 아니다. 공실 판정에 쓰지 않는다(표시용).
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from app.core.config import settings

BASE = "https://apis.data.go.kr/1613000/BldEngyHubService"
OPS = {"gas": "getBeGasUsgInfo", "electricity": "getBeElctyUsgInfo"}
SOURCE = "국토교통부 건축HUB 건물에너지정보(국가건물에너지 통합관리시스템) — 실시간 조회"
APPLY_URL = "https://www.data.go.kr/data/15135963/openapi.do"
MONTHS = 18                 # 한 달씩 물을 때 거슬러 올라가는 달 수(공표 시차 몇 달 + 12개월)
_WORKERS = 6
_TIMEOUT_S = 8.0
_TTL_S = 24 * 3600.0        # 월 자료 — 하루 재사용
_FAIL_BACKOFF_S = 15.0
_ATTEMPTS = 2
_CACHE_MAX = 512
_UNIT_KEYS = ("unit", "useQtyUnit", "unitNm", "useUnit")
_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()
_last_fail = 0.0
log = logging.getLogger("building_energy_live")


class EnergyError(Exception):
    """원천이 정상 HTTP 로 오류 코드를 돌려줬다(키 미등록 · 미신청 · 트래픽 초과 등)."""


def jibun_of(pnu: str) -> dict | None:
    """PNU 19자리 → 요청변수. 산 지번(PNU 11번째 '2')은 원천에 대지구분 변수가 확인되지 않아 묻지 않는다."""
    if not re.fullmatch(r"\d{19}", pnu or "") or pnu[10] != "1":
        return None
    return {"sigunguCd": pnu[0:5], "bjdongCd": pnu[5:10], "bun": pnu[11:15], "ji": pnu[15:19]}


def months_back(today: date, n: int = MONTHS) -> list[str]:
    """지난달부터 n 달 — ['202610', '202609', …]."""
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append(f"{y}{m:02d}")
    return out


def parse(raw: bytes) -> tuple[list[dict], int]:
    """응답 바이트 → (행, totalCount). XML · JSON 둘 다. 오류 코드는 EnergyError."""
    text = raw.lstrip()
    if text.startswith(b"{"):
        doc = json.loads(text)
        resp = doc.get("response") or doc
        header = resp.get("header") or {}
        code, msg = str(header.get("resultCode") or "00"), str(header.get("resultMsg") or "")
        body = resp.get("body") or {}
        items = body.get("items") or {}
        item = items.get("item") if isinstance(items, dict) else items
        rows = [] if item is None else (item if isinstance(item, list) else [item])
        total = int(body.get("totalCount") or len(rows))
    else:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            raise EnergyError(f"응답을 읽지 못함({type(e).__name__})") from e
        auth = root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg")
        if auth:   # 게이트웨이 오류(OpenAPI_ServiceResponse) — 키 미등록 · 미신청 등
            raise EnergyError(auth.strip())
        code, msg = (root.findtext(".//resultCode") or "00").strip(), (root.findtext(".//resultMsg") or "").strip()
        rows = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]
        total = int((root.findtext(".//totalCount") or "0").strip() or 0) or len(rows)
    if code not in ("00", "0", "000", "03"):     # 03 = 데이터 없음
        raise EnergyError(f"{code} {msg}".strip())
    return rows, total


def _get(op: str, params: dict, key: str) -> list[dict]:
    q = urllib.parse.urlencode({"serviceKey": key, "_type": "json", "type": "json", "numOfRows": 100, "pageNo": 1, **params})
    req = urllib.request.Request(f"{BASE}/{op}?{q}", headers={"User-Agent": "PlaceOS-twin-energy/1.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as r:
        rows, _ = parse(r.read())
    return rows


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def summarise(rows: list[dict]) -> dict:
    """행 → 월별 합(지번 합계 · 최근 달이 끝). 순수 함수 — 시험은 여기를 본다."""
    by: dict[str, dict] = {}
    unit = None
    for r in rows:
        ym = re.sub(r"\D", "", str(r.get("useYm") or ""))[:6]
        q = _num(r.get("useQty"))
        if len(ym) != 6 or q is None:
            continue
        m = by.setdefault(ym, {"ym": ym, "qty": 0.0, "n": 0})
        m["qty"] = round(m["qty"] + q, 3)
        m["n"] += 1
        unit = unit or next((str(r[k]).strip() for k in _UNIT_KEYS if str(r.get(k) or "").strip()), None)
    months = sorted(by.values(), key=lambda m: m["ym"])
    return {"months": months, "unit": unit, "fields": sorted(rows[0].keys()) if rows else []}


def _fetch_all(op: str, jib: dict, key: str, today: date) -> tuple[list[dict], str, list[str]]:
    """(행, 방식, 물은 달). 먼저 useYm 없이 — 두 달 이상이면 그것으로, 아니면 한 달씩."""
    try:
        rows = _get(op, jib, key)
        if len({str(r.get("useYm") or "") for r in rows}) >= 2:
            return rows, "all", []
    except EnergyError as e:
        # 「필수값 누락」류라면 한 달씩으로 넘어간다. 키 거절은 한 달씩 해도 같다 — 그대로 올린다.
        if re.search(r"KEY|등록|인증|승인|LIMIT|초과", str(e), re.I):
            raise
    yms = months_back(today)
    with ThreadPoolExecutor(max_workers=_WORKERS) as ex:
        parts = list(ex.map(lambda ym: _get(op, {**jib, "useYm": ym}, key), yms))
    return [r for p in parts for r in p], "monthly", yms


def energy(pnu: str, kind: str = "gas", today: date | None = None) -> dict:
    """한 지번의 월별 사용량. 예외를 내지 않는다 — 실패하면 status 에 사유."""
    global _last_fail
    op = OPS.get(kind)
    base = {"source": SOURCE, "kind": kind, "apply_url": APPLY_URL, "months": [], "unit": None, "fields": [], "window": None}
    jib = jibun_of(pnu) if op else None
    if jib is None:
        return {**base, "status": "no_pnu"}
    key = settings.data_go_kr_service_key
    if not key:
        return {**base, "status": "no_key"}
    ck = f"{kind}:{pnu}"
    now = time.monotonic()
    with _lock:
        hit = _cache.get(ck)
        if hit and now - hit[0] < _TTL_S:
            return hit[1]
        if now - _last_fail < _FAIL_BACKOFF_S:
            return {**base, "status": "backoff"}
    try:
        for attempt in range(1, _ATTEMPTS + 1):
            try:
                rows, how, asked = _fetch_all(op, jib, key, today or date.today())
                break
            except EnergyError:
                raise
            except Exception as e:   # 네트워크 — 새 인스턴스 첫 연결이 늦는 일이 있어 한 번 더
                if attempt == _ATTEMPTS:
                    raise
                log.warning("energy live %s attempt %d failed: %s: %s — retrying", ck, attempt, type(e).__name__, e)
    except EnergyError as e:
        log.warning("energy live %s refused: %s", ck, e)
        with _lock:
            _last_fail = time.monotonic()
        return {**base, "status": "refused", "error": str(e)[:160]}
    except Exception as e:
        log.warning("energy live %s failed: %s: %s", ck, type(e).__name__, e)
        with _lock:
            _last_fail = time.monotonic()
        return {**base, "status": "error", "error": type(e).__name__}
    s = summarise(rows)
    # 물은 기간 — 그 안에서 값이 없는 달은 「자료 없음」(0 을 쓴 게 아니다)
    span = sorted(asked) if asked else [m["ym"] for m in s["months"]]
    out = {**base, **s, "status": "ok", "query": how, "window": [span[0], span[-1]] if span else None}
    with _lock:
        if len(_cache) >= _CACHE_MAX:
            _cache.pop(next(iter(_cache)))
        _cache[ck] = (time.monotonic(), out)
    return out
