"""트윈 호실 ↔ 상가정보 점포 대조 — 집합건물 호실별 영업 여부 (2026-11-09 사용자 요청).

상가정보(소상공인시장진흥공단)의 점포는 층(`flrNo`) · 호(`hoNo`)를 갖고, 건축물대장 전유부는 호실(`hoNm`)을 갖는다.
같은 지번 · 같은 층 · 같은 호(표기 정규화)면 그 호실에 「영업 점포 있음」을 단다.

## 원천(먼저 되는 쪽)

1. **실시간** — 서버의 `DATA_GO_KR_SERVICE_KEY` 로 상가정보 `storeListInRadius`(건물 중심 반경 = 외곽선 끝까지 + 30m ·
   60~200m)를 불러 `lnoCd == 지번` 만 남긴다. 계획상가처럼 큰 건물도 점포 좌표(건물 단위)가 반경 안에 들게 한다.
   6시간 캐시 · 네트워크 오류 한 번 재시도 · 실패 대기 15초 · 예외 없음.
2. **Gold** — `{거점}/stores_lite.json.gz` 의 그 지번 점포. 호수(`ho`)는 2026-11-09 파이프라인부터 실린다 — 재빌드 전 판에는
   없어서 층 단위 점포 목록만 주고 호실 대조는 하지 않는다.

## 이 값이 아닌 것

- 「점포 기록 없음」은 **공실이 아니다** — 상가정보에 안 잡히는 업종(사무실 · 창고 등) · 갱신 지연 · 호 표기 차이가 있다. 화면은
  「기록 없음 — 공실 가능 · 현장 미확인」으로만 말한다.
- 호 표기 맞추기는 정규화(공백 · 「호」 · 「n층」 접두 · 앞자리 0 제거) 뒤 같은 문자열일 때만이다. 어긋나면 맞추지 않는다.
"""
from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
import urllib.parse
import urllib.request

from app.core.config import settings
from app.services import nearby_stores, vacant_inventory

URL = "http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius"
SOURCE_LIVE = "소상공인시장진흥공단 상가(상권)정보 — 실시간 조회"
SOURCE_GOLD = "소상공인시장진흥공단 상가(상권)정보 — 수집본(Gold)"
RADIUS_M, RADIUS_PAD_M, RADIUS_MAX_M = 60, 30, 200
_MAX_PAGES = 3
_TIMEOUT_S, _TTL_S, _FAIL_BACKOFF_S, _ATTEMPTS = 8.0, 6 * 3600.0, 15.0, 2
_BASEMENT_UNKNOWN = -99
_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = threading.Lock()
_last_fail = 0.0
log = logging.getLogger("store_units")


def ho_key(raw: object) -> str | None:
    """호 표기 정규화 — '101호' · ' 101 ' · '1층101호' · '0101' → '101', 'A호' → 'a'. 비면 None."""
    s = re.sub(r"\s+", "", str(raw if raw is not None else "")).lower()
    s = re.sub(r"^(지하|지|b)?\d+층", "", s)
    s = s.removesuffix("호")
    s = s.lstrip("0") or ("0" if s else "")
    return s or None


def store_floor(raw: object) -> int | None:
    """상가정보 flrNo → 층(지하 음수 · 「지」 → -99 · 해석 불가 None) — 파이프라인 build_stores_lite.store_floor 와 같은 규칙."""
    s = str(raw if raw is not None else "").strip()
    if re.fullmatch(r"\d+", s):
        n = int(s)
        return n if 0 < n <= 99 else None
    m = re.fullmatch(r"[Bb](\d+)", s)
    if m and int(m.group(1)) > 0:
        return -int(m.group(1))
    if s in ("지", "지하", "B", "b"):
        return _BASEMENT_UNKNOWN
    return None


def radius_for(lat: float, lng: float, ring: list | None) -> int:
    """건물 중심 → 외곽선 가장 먼 꼭짓점 + 여유(m), RADIUS_M~RADIUS_MAX_M. ring 은 [lat, lng] 목록."""
    k = math.cos(math.radians(lat))
    far = 0.0
    for p in ring or []:
        try:
            far = max(far, math.hypot((float(p[0]) - lat) * 111_320.0, (float(p[1]) - lng) * 111_320.0 * k))
        except (TypeError, ValueError, IndexError):
            continue
    return int(min(RADIUS_MAX_M, max(RADIUS_M, far + RADIUS_PAD_M)))


def _fetch_live(lat: float, lng: float, key: str, radius: int = RADIUS_M) -> list[dict]:
    items: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        q = urllib.parse.urlencode({"serviceKey": key, "type": "json", "numOfRows": 1000, "pageNo": page,
                                    "radius": radius, "cx": round(lng, 6), "cy": round(lat, 6)})
        req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": "PlaceOS-twin-stores/1.0"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as r:
            raw = r.read()
        try:
            doc = json.loads(raw)
        except ValueError:
            msg = re.search(rb"<returnAuthMsg>([^<]+)</returnAuthMsg>", raw)
            raise RuntimeError(msg.group(1).decode("utf-8", "replace") if msg else "응답이 JSON 이 아님")
        header = doc.get("header") or {}
        if str(header.get("resultCode") or "00") not in ("00", "0", "03"):     # 03 = 데이터 없음
            raise RuntimeError(f"{header.get('resultCode')} {header.get('resultMsg') or ''}".strip())
        body = doc.get("body") or {}
        got = list(body.get("items") or [])
        items += got
        if not got or len(items) >= int(body.get("totalCount") or 0):
            break
    return items


def _live(pnu: str, lat: float, lng: float, radius: int = RADIUS_M) -> tuple[str, list[dict] | None, str | None]:
    """(status, 그 지번 점포 | None, 오류). status: ok · no_key · backoff · error."""
    global _last_fail
    key = settings.data_go_kr_service_key
    if not key:
        return "no_key", None, None
    now = time.monotonic()
    with _lock:
        hit = _cache.get(pnu)
        if hit and now - hit[0] < _TTL_S:
            return "ok", hit[1], None
        if now - _last_fail < _FAIL_BACKOFF_S:
            return "backoff", None, None
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            items = _fetch_live(lat, lng, key, radius)
            break
        except Exception as e:   # 네트워크 · 키 거절 — 트윈은 그대로
            log.warning("stores live %s attempt %d failed: %s: %s", pnu, attempt, type(e).__name__, e)
            if attempt == _ATTEMPTS:
                with _lock:
                    _last_fail = time.monotonic()
                return "error", None, str(e)[:120] or type(e).__name__
    rows = [{"name": str(i.get("bizesNm") or "").strip(), "ind": (str(i.get("indsSclsNm") or "").strip() or None),
             "floor": store_floor(i.get("flrNo")), "ho": (str(i.get("hoNo") or "").strip() or None)}
            for i in items if str(i.get("lnoCd") or "") == pnu]
    with _lock:
        if len(_cache) >= 512:
            _cache.pop(next(iter(_cache)))
        _cache[pnu] = (time.monotonic(), rows)
    return "ok", rows, None


def stores_for(district_id: str, pnu: str, lat: float, lng: float, ring: list | None = None) -> dict:
    """그 지번 점포 + 원천. 실시간이 안 되면 Gold(호수 있으면 호실 대조 가능)."""
    status, rows, err = _live(pnu, lat, lng, radius_for(lat, lng, ring)) if pnu else ("no_pnu", None, None)
    if rows is not None:
        return {"status": "ok", "source": SOURCE_LIVE, "live_status": status, "error": None, "as_of": None,
                "has_ho": True, "stores": rows}
    slug = vacant_inventory.slug_of(district_id)
    gold, as_of, has_ho = nearby_stores.lot_stores(slug, pnu) if slug else ([], None, False)
    return {"status": "gold" if slug else "none", "source": SOURCE_GOLD, "live_status": status, "error": err,
            "as_of": as_of, "has_ho": has_ho, "stores": gold}


def annotate(floors: list[dict], found: dict) -> dict:
    """트윈 층 · 호실에 점포를 단다(제자리). 반환은 응답 `stores_live` 요약.

    - 호실(전유부)이 있는 층: 같은 층 · 같은 호 점포를 그 호실의 `store` 로. 층이 없거나 건물에 없는 층인 점포는 그 호가
      건물에서 하나뿐일 때만.
    - `store_checked` — 「맞는 점포 없음」에 뜻이 있는가. 그 층에 있을 수 있는 점포(같은 층 · 층 미상) 가운데 **호수가 빈 점포가
      하나라도 있으면** 그 점포가 어느 호실인지 모르므로 False 다(상가정보는 층 · 호를 비워 두는 행이 많다 —
      docs/finding-anchor-population.md: 층 공란 35.8% · 그 행의 호 100% 공란).
    - 모든 층: 그 층 점포 목록을 `stores` 로(호실이 없는 일반건축물 층도 이 층에 무엇이 영업 중인지 보인다).
    """
    stores = found.get("stores") or []
    has_ho = bool(found.get("has_ho"))
    by_lv = {f["lv"]: f for f in floors}
    with_ho = [s for s in stores if ho_key(s.get("ho"))] if has_ho else []
    # 호수가 빈 점포가 있을 수 있는 층 — 층을 알면 그 층, 모르면(또는 건물에 없는 층이면) 모든 층
    blind_lv: set = set()
    blind_all = not has_ho
    for s in stores:
        if has_ho and ho_key(s.get("ho")):
            continue
        if s["floor"] in by_lv:
            blind_lv.add(s["floor"])
        else:
            blind_all = True
    units_total = matched = unchecked = 0
    for f in floors:
        f["stores"] = [{"name": s["name"], "ind": s["ind"], "ho": s.get("ho")} for s in stores if s["floor"] == f["lv"]] or None
        checked = not blind_all and f["lv"] not in blind_lv
        for u in f.get("units") or []:
            units_total += 1
            u["store"] = None
            u["store_checked"] = checked
    if with_ho:
        # 호 키 → (층, 호실) — 층 미상 점포는 건물에서 그 호가 하나뿐일 때만 맞춘다
        where: dict[str, list[tuple[int, dict]]] = {}
        for f in floors:
            for u in f.get("units") or []:
                k = ho_key(u.get("ho"))
                if k:
                    where.setdefault(k, []).append((f["lv"], u))
        for s in with_ho:
            k = ho_key(s.get("ho"))
            if k not in where:
                continue
            cands = [c for c in where[k] if c[0] == s["floor"]] if s["floor"] in by_lv else (where[k] if len(where[k]) == 1 else [])
            for _, u in cands[:1]:
                if u["store"] is None:
                    u["store"] = {"name": s["name"], "ind": s["ind"]}
                    u["store_checked"] = True
                    matched += 1
    for f in floors:
        unchecked += sum(1 for u in (f.get("units") or []) if not u["store_checked"])
    return {"status": found.get("status"), "source": found.get("source"), "live_status": found.get("live_status"),
            "error": found.get("error"), "as_of": found.get("as_of"), "has_ho": has_ho,
            "n_stores": len(stores), "n_with_ho": len(with_ho), "units_total": units_total,
            "units_matched": matched, "units_unchecked": unchecked}
