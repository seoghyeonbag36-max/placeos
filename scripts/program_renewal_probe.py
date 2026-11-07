# -*- coding: utf-8 -*-
"""Program 리뉴얼 보고서(docs/renewal-program-2026-11-07.md)의 실측 수치를 다시 뽑는다.

문서에 적힌 숫자는 낡는다. 인용하기 전에 이 스크립트를 다시 돌린다.

- 서빙 거점(`data/config/page_hubs.ACTIVE_HUBS`)의 시도별 수
- 행사 Gold(`data/gold/platform_events.json`) — 시도별 커버리지 · 기준일에 이미 끝난 행사 · 걸어갈 거리(300m) 안 행사
- `--live` — 외부 API 1콜씩. 엔드포인트가 살아 있는지, 공용 키(`DATA_GO_KR_SERVICE_KEY`)에 활용신청이
  돼 있는지만 본다. **키 값은 출력하지 않는다**(응답 코드·오류 문자열·건수만).

Program 게이트 셋(상권 콘텐츠 컨텍스트 · 수요신호 · 검색 트렌드 라벨)은 여기서 다시 세지 않는다 —
단일 출처는 `python scripts/pppp_status.py` 다.

실행:
    python scripts/program_renewal_probe.py --as-of 2026-11-07
    python scripts/program_renewal_probe.py --as-of 2026-11-07 --live > reports/program_renewal_probe_2026-11-07.json

worktree 에서 돌릴 때: 공용 키 파일은 git 밖이라 worktree 에 없다. `--root <메인 체크아웃>` 을 주면 그 체크아웃의
산출물과 키 로더(`data.collectors.common.load_env`)를 쓴다.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _use_root(root: Path) -> None:
    global ROOT
    ROOT = root.resolve()
    sys.path.insert(0, str(ROOT / "apps" / "backend"))
    sys.path.insert(0, str(ROOT))


_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def walkable_m() -> int:
    """LLM 컨텍스트가 '걸어갈 거리'로 보는 값 — `services/marketing._WALKABLE_M` 을 소스에서 읽는다.

    import 하지 않는 이유: marketing 은 LLM SDK 등 서빙 의존성을 끌고 온다. 값을 여기 따로 적으면
    둘이 어긋난다(2026-11-07 첫 판이 300 으로 적어 실제 500 과 달랐다).
    """
    src = (ROOT / "apps" / "backend" / "app" / "services" / "marketing.py").read_text(encoding="utf-8")
    m = re.search(r"^_WALKABLE_M\s*=\s*(\d+)", src, re.M)
    if not m:
        raise SystemExit("services/marketing.py 에서 _WALKABLE_M 을 찾지 못했다 — 이름이 바뀌었으면 이 스크립트도 고친다")
    return int(m.group(1))


def hubs_by_sido() -> tuple[dict[str, str], collections.Counter]:
    from app.data.cities import CITIES
    from data.config.page_hubs import ACTIVE_HUBS

    sido = {slug: CITIES[h.city].sido if h.city in CITIES else f"?{h.city}" for slug, h in ACTIVE_HUBS.items()}
    return sido, collections.Counter(sido.values())


def events_coverage(sido: dict[str, str], as_of: dt.date) -> dict:
    gold = json.loads((ROOT / "data" / "gold" / "platform_events.json").read_text(encoding="utf-8"))
    dist = gold.get("districts") or {}
    walk = walkable_m()
    with_ev, zero, missing, near = (collections.Counter() for _ in range(4))
    total = ended = 0
    hubs_all_ended = 0
    for slug, s in sido.items():
        evs = dist.get(slug)
        if evs is None:
            missing[s] += 1
            continue
        if not evs:
            zero[s] += 1
            continue
        with_ev[s] += 1
        if any((e.get("distance_m") if e.get("distance_m") is not None else 10**9) <= walk for e in evs):
            near[s] += 1
        n_end = 0
        for e in evs:
            total += 1
            dates = _DATE.findall(e.get("when") or "")
            if dates and dt.date(*map(int, dates[-1])) < as_of:
                n_end += 1
        ended += n_end
        hubs_all_ended += int(n_end == len(evs))
    return {
        "source": gold.get("source"), "as_of": gold.get("as_of"),
        "hubs_with_events": dict(with_ev), "hubs_loaded_zero": dict(zero), "hubs_not_in_gold": dict(missing),
        "walkable_m": walk, "hubs_event_within_walkable": dict(near),
        "events_total_served": total, "events_ended_by_as_of": ended,
        "events_ended_share": round(ended / total, 3) if total else None,
        "hubs_every_event_ended": hubs_all_ended,
    }


def _get(url: str, params: dict, *, key: str | None, key_name: str = "serviceKey") -> tuple[int | None, str]:
    q = dict(params)
    if key is not None:
        q[key_name] = key
    try:
        with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(q)}", timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # 네트워크 오류는 결과로 남긴다 — 통과로 세지 않는다
        return None, f"{type(e).__name__}"


def _brief(body: str) -> str:
    m = re.search(r'"errMsg"\s*:\s*"([^"]+)"|<errMsg>([^<]+)</errMsg>|"msg"\s*:\s*"([^"]+)"|"reqErr"\s*:\s*"([^"]+)"', body)
    if m:
        return next(g for g in m.groups() if g)
    m = re.search(r'"totalCount"\s*:\s*(\d+)|<totalCount>(\d+)</totalCount>', body)
    return f"totalCount={next(g for g in m.groups() if g)}" if m else body[:120].replace("\n", " ")


def live_probes() -> list[dict]:
    from data.collectors.common import load_env

    load_env()
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY") or None
    k_start = "https://apis.data.go.kr/B552735/kisedKstartupService01"
    tour = "https://apis.data.go.kr/B551011/KorService2/searchFestival2"
    tour_q = {"numOfRows": 200, "pageNo": 1, "MobileOS": "ETC", "MobileApp": "PlaceOS", "_type": "json",
              "eventStartDate": "20261101"}
    probes = [
        ("K-Startup 공고 · 키 없이", f"{k_start}/getAnnouncementInformation01", {"page": 1, "perPage": 1, "returnType": "json"}, None),
        ("K-Startup 없는 오퍼레이션 · 키 없이(대조)", f"{k_start}/getNoSuchOperation01", {"page": 1, "perPage": 1, "returnType": "json"}, None),
        ("K-Startup 공고 · 공용 키", f"{k_start}/getAnnouncementInformation01", {"page": 1, "perPage": 1, "returnType": "json"}, key),
        ("정부24 공공서비스(혜택) 목록 · 공용 키", "https://api.odcloud.kr/api/gov24/v3/serviceList", {"page": 1, "perPage": 1, "returnType": "JSON"}, key),
        ("기업마당 지원사업 · 키 없이", "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do", {"dataType": "json", "searchCnt": 1}, None),
        ("TourAPI 축제 · 공용 키", tour, tour_q, key),
        ("문화포털 기간별 문화정보 · 공용 키", "https://apis.data.go.kr/B553457/cultureinfo/period2", {"numOfRows": 1, "pageNo": 1}, key),
    ]
    out = []
    for label, url, params, k in probes:
        status, body = _get(url, params, key=k)
        row = {"probe": label, "url": url, "http": status, "result": _brief(body)}
        if label.startswith("TourAPI") and status == 200:
            try:
                items = json.loads(body)["response"]["body"]["items"]
                items = items.get("item", []) if isinstance(items, dict) else []
                by = collections.Counter(_sido_norm((it.get("addr1") or "?").split(" ")[0]) for it in items)
                row["by_sido"] = dict(by.most_common())
                row["fields"] = sorted(items[0].keys()) if items else []
                pts = [(float(it["mapy"]), float(it["mapx"])) for it in items if it.get("mapx") and it.get("mapy")]
                row["hub_proximity"] = hub_proximity(pts, *_sido_map())
            except (KeyError, ValueError):
                pass
        out.append(row)
    total, pts, by = culture_points(key)
    out.append({"probe": "문화포털 전량 · 시도·거점 근접", "total": total, "with_coords": len(pts),
                "by_area": dict(by.most_common()), "hub_proximity": hub_proximity(pts, *_sido_map())})
    return out


def _sido_map() -> tuple[dict[str, str]]:
    return (hubs_by_sido()[0],)


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math

    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def hub_proximity(points: list[tuple[float, float]], sido: dict[str, str], radii=(1_000, 3_000)) -> dict:
    """좌표가 있는 행사 목록이 서빙 거점 중심에서 몇 m 안에 몇 거점을 덮는가 — 시도별."""
    from data.config.page_hubs import ACTIVE_HUBS

    out = {f"within_{r}m": collections.Counter() for r in radii}
    for slug, h in ACTIVE_HUBS.items():
        if not points:
            break
        d = min(_haversine_m(h.cy, h.cx, lat, lng) for lat, lng in points)
        for r in radii:
            if d <= r:
                out[f"within_{r}m"][sido[slug]] += 1
    return {k: dict(v) for k, v in out.items()}


def culture_points(key: str | None) -> tuple[int, list[tuple[float, float]], collections.Counter]:
    """문화포털 기간별 문화정보 전량 — 이 API 의 쪽 인자는 `numOfrows`·`PageNo` 다(대소문자 그대로. `numOfRows` 는 10건으로 무시된다)."""
    pts: list[tuple[float, float]] = []
    by = collections.Counter()
    total, page = None, 1
    while True:
        status, body = _get("https://apis.data.go.kr/B553457/cultureinfo/period2",
                            {"numOfrows": 100, "PageNo": page}, key=key)
        if status != 200:
            break
        if total is None:
            m = re.search(r"<totalCount>(\d+)</totalCount>", body)
            total = int(m.group(1)) if m else 0
        items = re.findall(r"<item>(.*?)</item>", body, re.S)
        for it in items:
            area = re.search(r"<area>(.*?)</area>", it)
            by[_sido_norm(area.group(1)) if area else "?"] += 1
            x, y = re.search(r"<gpsX>([\d.]+)</gpsX>", it), re.search(r"<gpsY>([\d.]+)</gpsY>", it)
            if x and y:
                pts.append((float(y.group(1)), float(x.group(1))))
        if not items or page * 100 >= (total or 0) or page >= 30:
            break
        page += 1
    return total or 0, pts, by


_SIDO_SHORT = {"서울": "서울특별시", "경기": "경기도", "경북": "경상북도", "경남": "경상남도", "전북": "전북특별자치도",
               "충남": "충청남도", "충북": "충청북도", "강원": "강원특별자치도", "제주": "제주특별자치도"}


def _sido_norm(token: str) -> str:
    return _SIDO_SHORT.get(token, token)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=dt.date.today().isoformat(), help="'이미 끝난 행사'를 가르는 기준일 (YYYY-MM-DD)")
    ap.add_argument("--live", action="store_true", help="외부 API 1콜씩 (공용 키 활용신청 여부 확인)")
    ap.add_argument("--root", default=None, help="산출물·키 로더를 읽을 체크아웃 (기본: 이 스크립트의 저장소)")
    args = ap.parse_args()
    as_of = dt.date.fromisoformat(args.as_of)
    _use_root(Path(args.root) if args.root else ROOT)

    sido, by = hubs_by_sido()
    result = {
        "as_of": as_of.isoformat(),
        "root": "script repo" if not args.root else "given --root",
        "served_hubs": sum(by.values()),
        "served_hubs_by_sido": dict(by.most_common()),
        "events": events_coverage(sido, as_of),
    }
    if args.live:
        result["live_probes"] = live_probes()
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
