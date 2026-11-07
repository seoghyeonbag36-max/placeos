"""[Program] 전국 행사 Gold — 문화포털·TourAPI Bronze → Silver → gold/platform_events_national.json (2026-11-07).

왜: 행사 Gold(`platform_events.json`)는 서울 문화행사(culturalEventInfo)라 서울 밖 77거점(경기 59 · 광주 13 ·
전주 5)이 비어 있었다. 11-07 실측으로 문화포털이 서울 밖 34거점에 1km 안 행사를, TourAPI 가 10거점에 준다
(docs/renewal-program-2026-11-07.md §2-2). 서빙은 services/events.py 가 두 Gold 를 합친다.

입력(Bronze — data/collectors/culture_portal.py · tourapi_festivals.py):
  data/bronze/national_events/<as_of>/culture_portal.json     쪽마다 원응답 XML
  data/bronze/national_events/<as_of>/tourapi_festivals.json  쪽마다 원응답 JSON + 분류체계 코드
출력:
  data/silver/national_events.json            정규화한 행사 목록(거점 배정 전 · 끝난 행사 포함)
  data/gold/platform_events_national.json     거점별 — 반경 RADIUS_M 안 · 끝난 행사 제외 · 가까운 순 최대 MAX_PER_HUB

Gold 계약(백엔드가 그대로 읽는다 — services/events.py):
  {"source", "built_at", "as_of", "radius_m", "max_per_hub", "note", "sources": [...],
   "districts": {slug: [{"id","n","lat","lng","ic","when","category","place","org","fee","target","link","distance_m","src"}]}}

지어내지 않는 것: 상세 URL(목록 응답에 없다 — link 는 null) · 요금·대상·주최(목록에 없다) · 시각(`tm` 없음).
사진은 넘기지 않는다 — TourAPI 사진은 공공누리 1·3유형(3유형 변경 금지)이다.
버리는 것(건수는 sources[].dropped 에 남는다): 좌표 없음 · 날짜를 못 읽음 · 엉터리 날짜(종료가 기준일 + 3년 뒤,
시작 > 종료 — 11-07 문화포털에 종료 9405년 행이 있었다) · 기준일 전에 끝남 · 두 원천 사이 중복.

실행: python -m data.pipelines.build_national_events --as-of 2026-11-07
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from data.collectors.common import BRONZE, GOLD, SILVER

RADIUS_M = 3000
MAX_PER_HUB = 40
DEDUP_M = 300
PLAUSIBLE_YEARS = 3

GOLD_NAME = "platform_events_national.json"
SILVER_NAME = "national_events.json"

_YMD = re.compile(r"^(\d{4})(\d{2})(\d{2})$")


# ── 순수 함수(테스트 대상) ──────────────────────────────────────────────────
def parse_ymd(s: object) -> date | None:
    m = _YMD.match(str(s or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def unescape_twice(s: object) -> str:
    """문화포털 제목은 이중 이스케이프로 온다(`&amp;lt;` → XML 해석 뒤에도 `&lt;`)."""
    return html.unescape(html.unescape(str(s or ""))).strip()


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def icon_for(category: str | None) -> str:
    c = category or ""
    if "축제" in c:
        return "🎪"
    if "전시" in c or "미술" in c:
        return "🖼"
    if any(k in c for k in ("공연", "연극", "뮤지컬", "음악", "콘서트", "국악", "무용", "클래식")):
        return "🎭"
    if any(k in c for k in ("교육", "체험", "강연", "강좌")):
        return "📚"
    return "✨"


def norm_title(t: str) -> str:
    return re.sub(r"[\s\[\]()<>「」『』\"'·•,.!?~\-_/:]", "", t or "").lower()


def check_dates(start: date | None, end: date | None, as_of: date) -> str | None:
    """버릴 이유. 괜찮으면 None."""
    if start is None or end is None:
        return "날짜 없음"
    if start > end or end.year > as_of.year + PLAUSIBLE_YEARS:
        return "엉터리 날짜"
    if end < as_of:
        return "기준일 전에 끝남"
    return None


def event_record(*, src: str, sid: str, title: str, lat: float, lng: float, start: date, end: date,
                 category: str | None, place: str | None) -> dict:
    return {"id": f"{'cp' if src == 'culture-portal' else 'ta'}-{sid}", "n": title, "lat": round(lat, 6),
            "lng": round(lng, 6), "ic": icon_for(category), "when": f"{start.isoformat()}~{end.isoformat()}",
            "category": category or None, "place": place or None, "org": None, "fee": None, "target": None,
            "link": None, "src": src}


def normalize_culture(rows: list[dict], as_of: date, drop: Counter) -> list[dict]:
    out = []
    for r in rows:
        try:
            lng, lat = float(r.get("gpsX") or "nan"), float(r.get("gpsY") or "nan")
        except ValueError:
            lng = lat = float("nan")
        if not (math.isfinite(lat) and math.isfinite(lng)) or lat == 0 or lng == 0:
            drop["좌표 없음"] += 1
            continue
        start, end = parse_ymd(r.get("startDate")), parse_ymd(r.get("endDate"))
        if (why := check_dates(start, end, as_of)):
            drop[why] += 1
            continue
        title = unescape_twice(r.get("title"))
        if not title:
            drop["제목 없음"] += 1
            continue
        out.append(event_record(src="culture-portal", sid=str(r.get("seq")), title=title, lat=lat, lng=lng,
                                start=start, end=end, category=(r.get("realmName") or "").strip() or None,
                                place=unescape_twice(r.get("place")) or None))
    return out


def normalize_tour(rows: list[dict], codes: dict[str, str], as_of: date, drop: Counter) -> list[dict]:
    out = []
    for r in rows:
        try:
            lng, lat = float(r.get("mapx") or "nan"), float(r.get("mapy") or "nan")
        except ValueError:
            lng = lat = float("nan")
        if not (math.isfinite(lat) and math.isfinite(lng)) or lat == 0 or lng == 0:
            drop["좌표 없음"] += 1
            continue
        start, end = parse_ymd(r.get("eventstartdate")), parse_ymd(r.get("eventenddate"))
        if (why := check_dates(start, end, as_of)):
            drop[why] += 1
            continue
        title = unescape_twice(r.get("title"))
        if not title:
            drop["제목 없음"] += 1
            continue
        category = codes.get(str(r.get("lclsSystm3") or "")) or codes.get(str(r.get("lclsSystm2") or "")) or "축제·행사"
        place = " ".join(x for x in (str(r.get("addr1") or "").strip(), str(r.get("addr2") or "").strip()) if x)
        out.append(event_record(src="tourapi", sid=str(r.get("contentid")), title=title, lat=lat, lng=lng,
                                start=start, end=end, category=category, place=place or None))
    return out


def dedup(events: list[dict]) -> tuple[list[dict], Counter]:
    """중복 — 정규화한 제목 + 같은 시작일 + DEDUP_M 안이면 먼저 온 것(문화포털)만 남긴다. 지운 수는 원천별."""
    kept: list[dict] = []
    seen: dict[tuple[str, str], list[dict]] = {}
    removed: Counter = Counter()
    for e in events:
        key = (norm_title(e["n"]), e["when"].split("~")[0])
        if any(haversine_m(e["lat"], e["lng"], k["lat"], k["lng"]) <= DEDUP_M for k in seen.get(key, [])):
            removed[e["src"]] += 1
            continue
        seen.setdefault(key, []).append(e)
        kept.append(e)
    return kept, removed


def assign(events: list[dict], hubs: dict[str, tuple[float, float]], *, radius_m: int = RADIUS_M,
           max_per_hub: int = MAX_PER_HUB) -> dict[str, list[dict]]:
    """hubs: slug → (위도, 경도). 반경 안 행사를 가까운 순으로, 최대 max_per_hub. 없으면 [](덮었고 0건)."""
    out: dict[str, list[dict]] = {}
    for slug, (hlat, hlng) in hubs.items():
        near = []
        for e in events:
            d = haversine_m(hlat, hlng, e["lat"], e["lng"])
            if d <= radius_m:
                near.append({**e, "distance_m": int(round(d))})
        near.sort(key=lambda e: (e["distance_m"], e["id"]))
        out[slug] = near[:max_per_hub]
    return out


# ── Bronze 읽기 ────────────────────────────────────────────────────────────
def _culture_rows(doc: dict) -> list[dict]:
    from data.collectors.culture_portal import parse_page
    rows: list[dict] = []
    for p in doc.get("pages") or []:
        _, items = parse_page(p["body"])
        rows += items
    return rows


def _tour_rows(doc: dict) -> tuple[list[dict], dict[str, str]]:
    from data.collectors.tourapi_festivals import parse_page
    rows: list[dict] = []
    for p in doc.get("pages") or []:
        body = p["body"]
        _, items = parse_page(body if isinstance(body, str) else json.dumps(body, ensure_ascii=False))
        rows += items
    codes: dict[str, str] = {}
    lc = (doc.get("lcls_codes") or {}).get("body")
    if lc:
        _, items = parse_page(lc if isinstance(lc, str) else json.dumps(lc, ensure_ascii=False), op="lclsSystmCode2")
        for it in items:
            if it.get("lclsSystm3Cd"):
                codes[str(it["lclsSystm3Cd"])] = str(it.get("lclsSystm3Nm") or "")
            if it.get("lclsSystm2Cd"):
                codes.setdefault(str(it["lclsSystm2Cd"]), str(it.get("lclsSystm2Nm") or ""))
    return rows, codes


def _hubs() -> dict[str, tuple[float, float]]:
    from data.config.page_hubs import ACTIVE_HUBS
    return {slug: (h.cy, h.cx) for slug, h in ACTIVE_HUBS.items()}


def build(as_of: date, bronze_root: Path = BRONZE, silver_root: Path = SILVER, gold_root: Path = GOLD) -> dict:
    folder = bronze_root / "national_events" / as_of.isoformat()
    culture_doc = json.loads((folder / "culture_portal.json").read_text(encoding="utf-8"))
    tour_doc = json.loads((folder / "tourapi_festivals.json").read_text(encoding="utf-8"))

    c_drop, t_drop = Counter(), Counter()
    c_rows = _culture_rows(culture_doc)
    t_rows, codes = _tour_rows(tour_doc)
    culture = normalize_culture(c_rows, as_of, c_drop)
    tour = normalize_tour(t_rows, codes, as_of, t_drop)
    merged, removed = dedup(culture + tour)          # 문화포털 먼저 — 중복이면 문화포털을 남긴다
    if removed["culture-portal"]:
        c_drop["중복"] += removed["culture-portal"]
    if removed["tourapi"]:
        t_drop["중복(문화포털과 같은 행사 포함)"] += removed["tourapi"]

    silver_root.mkdir(parents=True, exist_ok=True)
    (silver_root / SILVER_NAME).write_text(json.dumps(
        {"as_of": as_of.isoformat(), "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "events": merged}, ensure_ascii=False), encoding="utf-8")

    districts = assign(merged, _hubs())
    sources = []
    for doc, rows, kept, dropped in ((culture_doc, c_rows, culture, c_drop), (tour_doc, t_rows, tour, t_drop)):
        sources.append({
            "id": doc["source_id"], "name": doc["name"], "endpoint": doc["endpoint"],
            "dataset_page": doc["dataset_page"], "license": doc["license"], "fetched_at": doc["fetched_at"],
            "rows": len(rows), "kept": len(kept) - removed[doc["source_id"]],
            "dropped": dict(dropped),
        })
    gold = {
        "source": "문화포털 기간별 문화정보 + 한국관광공사 TourAPI 행사정보",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(), "radius_m": RADIUS_M, "max_per_hub": MAX_PER_HUB,
        "note": ("기준일에 끝난 행사 제외(서빙은 오늘 기준으로 다시 거른다) · 거리는 거점 중심 직선 · 시각·요금·주최·상세 링크는 "
                 "목록 응답에 없어 비워 둔다 · TourAPI 사진은 공공누리 1·3유형이라 싣지 않는다"),
        "sources": sources,
        "districts": districts,
    }
    gold_root.mkdir(parents=True, exist_ok=True)
    path = gold_root / GOLD_NAME
    path.write_text(json.dumps(gold, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {"gold": gold, "path": path}


def summarize(gold: dict) -> dict[str, Any]:
    """시도별 1km·3km 안 행사가 1건 이상인 거점 수 — 보고서의 11-07 근접 실측과 대조한다."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "backend"))
    from app.data.cities import CITIES
    from data.config.page_hubs import ACTIVE_HUBS

    near1, near3, loaded = Counter(), Counter(), Counter()
    for slug, evs in gold["districts"].items():
        sido = CITIES[ACTIVE_HUBS[slug].city].sido
        loaded[sido] += 1
        if any(e["distance_m"] <= 1000 for e in evs):
            near1[sido] += 1
        if evs:
            near3[sido] += 1
    return {"hubs": dict(loaded), "within_1000m": dict(near1), "within_3000m": dict(near3),
            "events_assigned": sum(len(v) for v in gold["districts"].values())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = ap.parse_args()
    out = build(args.as_of)
    gold = out["gold"]
    for s in gold["sources"]:
        print(f"[national_events] {s['id']}: 행 {s['rows']} · 남김 {s['kept']} · 버림 {s['dropped']}")
    print(f"[national_events] {json.dumps(summarize(gold), ensure_ascii=False)}")
    print(f"[national_events] Gold {out['path']} ({out['path'].stat().st_size:,}B)")


if __name__ == "__main__":
    main()
