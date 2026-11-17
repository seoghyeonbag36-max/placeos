"""인허가(영업·폐업 전부) → 건물 폴리곤(PNU) 좌표 조인율 프로브.

연구 질문(docs/finding-digital-premium-inputs-2026-11-17.md §3): 접도별 생존율·신규 개업 위치를 만들려면
**폐업 업소**도 필지에 붙어야 한다. 기존 `build_page_master._licensed_pip` 는 영업 중 행만 귀속하므로,
같은 좌표 보정(EPSG:2097 변환 + 지번주소 자가 보정 오프셋)을 폐업 행에도 적용했을 때 얼마나 붙는지 잰다.

    python scripts/probe_licensing_parcel_join.py garosugil hongdae
    python scripts/probe_licensing_parcel_join.py gangnam --out reports/licensing_parcel_join_gangnam.json

`assign_rows(slug)` 는 행마다 배정된 PNU 를 돌려주는 재사용 함수다(신규 개업 위치 분석이 쓴다 — scripts/analyze_opening_location.py).
읽기 전용 — Bronze/Gold 를 바꾸지 않는다. 필요: pyproj · shapely (`pip install pyproj shapely`).

⚠ 분모는 「거점 폴리곤 bbox 안의 행」이다. 인허가는 구 단위로 받아 거점 밖 행이 대부분이다.
⚠ 교차검증: PIP 로 나온 PNU 가 **지번주소로 만든 PNU 와 같은가**(주소가 폴리곤 필지로 풀리는 행만).
⚠ 검증된 것: 영업 중 행의 오프셋이 `_licensed_pip` 와 일치(가로수길 -256.6 vs -256.7m · 홍대 -255.5 vs -255.5m).
  귀속 수는 `_licensed_pip` 가 (업소명, 지번주소) 중복을 먼저 뺀 뒤 세므로 이 프로브보다 작다 — 중복 제외 건수와 크기가 맞다.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from data.collectors.common import BRONZE, load_latest
from data.pipelines import build_page_master as bpm

_DEG_M_LAT = 110540.0
_DEG_M_LON = 111320.0


def _alive(r: dict) -> bool:
    return not (r.get("DCBYMD") or "").strip() and (r.get("TRDSTATEGBN") == "01" or "영업" in str(r.get("TRDSTATENM", "")))


def status_of(r: dict) -> str:
    return "alive" if _alive(r) else ("closed" if (r.get("DCBYMD") or "").strip() else "other")


def _xy(r: dict) -> tuple[float, float] | None:
    try:
        return float(str(r["X"]).strip()), float(str(r["Y"]).strip())
    except (KeyError, ValueError):
        return None


def assign_rows(slug: str) -> tuple[dict, list[dict]]:
    """거점의 인허가 행(날짜별 파일 합집합, MGTNO 기준)마다 건물 PNU 를 배정한다.

    반환: (메타, 행 목록). 행 = {"row": 원본, "status": alive|closed|other, "has_xy": bool,
    "in_bbox": 거점 폴리곤 bbox 안인가, "pnu": PIP 로 붙은 PNU 또는 None, "addr_pnu": 지번주소로 만든 PNU(폴리곤에 있을 때만)}.
    """
    polys = load_latest(slug, "bldg_polygons.geojson")
    stores = [s for s in (load_latest(slug, "stores_raw.json") or []) if s.get("indsLclsNm") not in bpm.NON_STOREFRONT_LCLS]
    dong_code = {v: k for k, v in bpm._build_dong_map(stores).items()}
    sigungu = collections.Counter(s["lnoCd"][0:5] for s in stores if len(s.get("lnoCd", "")) == 19).most_common(1)[0][0]

    rows, seen = [], set()
    for f in sorted(glob.glob(str(BRONZE / slug / "*" / "licensing_biz.json"))):
        for r in json.loads(Path(f).read_text(encoding="utf-8")):
            if r["MGTNO"] not in seen:
                seen.add(r["MGTNO"])
                rows.append(r)

    geoms, pnus, cent = [], [], {}
    for ft in polys["features"]:
        g = shape(ft["geometry"])
        p = ft["properties"].get("pnu", "")
        geoms.append(g)
        pnus.append(p)
        cent[p] = (g.centroid.x, g.centroid.y)
    tree = STRtree(geoms)
    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)
    tr = Transformer.from_crs("EPSG:2097", "EPSG:4326", always_xy=True)

    # 자가 보정 오프셋 — 영업 중 행 중 지번주소가 폴리곤 필지로 풀리는 행의 중위 (build_page_master 와 같은 방법)
    de, dn = [], []
    for r in rows:
        c = _xy(r)
        pnu = bpm._addr_pnu(str(r.get("SITEWHLADDR", "")), dong_code, sigungu)
        if not c or not _alive(r) or pnu not in cent:
            continue
        lon, lat = tr.transform(*c)
        clon, clat = cent[pnu]
        de.append((lon - clon) * _DEG_M_LON * math.cos(math.radians(clat)))
        dn.append((lat - clat) * _DEG_M_LAT)
    de.sort()
    dn.sort()
    off_e, off_n = de[len(de) // 2], dn[len(dn) // 2]

    out = []
    for r in rows:
        item = {"row": r, "status": status_of(r), "has_xy": False, "in_bbox": False, "pnu": None, "addr_pnu": None}
        c = _xy(r)
        if c:
            item["has_xy"] = True
            lon, lat = tr.transform(*c)
            lon -= off_e / (_DEG_M_LON * math.cos(math.radians(lat)))
            lat -= off_n / _DEG_M_LAT
            if minx <= lon <= maxx and miny <= lat <= maxy:
                item["in_bbox"] = True
                hit = tree.query(Point(lon, lat), predicate="within")
                if len(hit):
                    item["pnu"] = pnus[hit[0]]
                    p_adr = bpm._addr_pnu(str(r.get("SITEWHLADDR", "")), dong_code, sigungu)
                    item["addr_pnu"] = p_adr if p_adr in cent else None
        out.append(item)
    meta = {"rows_union": len(rows), "polygons": len(geoms), "offset_m": [round(off_e, 1), round(off_n, 1)],
            "calib_points": len(de), "building_pnus": sorted(set(pnus))}
    return meta, out


def probe(slug: str) -> dict:
    meta, items = assign_rows(slug)
    stat: collections.Counter = collections.Counter()
    for it in items:
        st = it["status"]
        stat[(st, "rows")] += 1
        if not it["has_xy"]:
            stat[(st, "no_xy")] += 1
            continue
        if not it["in_bbox"]:
            continue
        stat[(st, "in_bbox")] += 1
        if it["pnu"]:
            stat[(st, "in_building")] += 1
            if it["addr_pnu"]:
                stat[(st, "addr_n")] += 1
                stat[(st, "addr_same")] += it["addr_pnu"] == it["pnu"]
    out = {k: meta[k] for k in ("rows_union", "polygons", "offset_m", "calib_points")}
    for st in ("alive", "closed"):
        b, h, n = stat[(st, "in_bbox")], stat[(st, "in_building")], stat[(st, "addr_n")]
        out[st] = {"rows": stat[(st, "rows")], "no_xy": stat[(st, "no_xy")], "in_hub_bbox": b, "in_building": h,
                   "building_hit_rate_of_in_bbox": round(h / b, 3) if b else None,
                   "addr_pnu_crosscheck": {"n": n, "same": stat[(st, "addr_same")],
                                           "rate": round(stat[(st, "addr_same")] / n, 3) if n else None}}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("hubs", nargs="+")
    ap.add_argument("--out", help="결과 JSON 경로(없으면 출력만)")
    args = ap.parse_args()
    result = {h: probe(h) for h in args.hubs}
    for h, o in result.items():
        print(h, json.dumps(o, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
