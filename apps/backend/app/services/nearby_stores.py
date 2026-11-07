"""이 자리 반경 안 점포 — `GET /commercial-districts/{id}/nearby-stores`.

## 경쟁 강도는 상대 위치로만 말한다

참고 지수(같은 업종×10 + 그중 체인×5 + 비슷한 업종×4)는 매출·성과로 검증한 값이 아니다. 그래서 임계값을 두지 않고, 같은
지수를 **이 상권의 빈 자리 전체**에 계산해 백분위를 낸다(KPI 규칙 1 — 임계값은 발명하지 않고 기준에서 유도한다).
층 반영은 경쟁 점포 자체의 층에 참고 가중치를 곱한다(1층 1 · 2층 .75 · 3층↑ .5 · 지하 .7 · 층 미상 1).

## 이 값이 아닌 것

거리는 **직선**이다. 도로망이 없어 보행 거리·길 건너 보정을 만들지 않는다. 상가정보 좌표는 건물 단위라 같은 건물 점포는
거리가 같다. `is_chain`·`brand` 는 체인 추정이고 가맹 여부 확인값이 아니다.

## 캐시

점포는 거점당 최대 수만 행이라 최근 8거점만 들고 있는다. 백분위 분포는 (거점, 업종, 세부 업종, 반경, 층 반영)마다 한 번 만든다.
"""
from __future__ import annotations

import bisect
import gzip
import importlib.util
import json
import math
from functools import lru_cache
from pathlib import Path

from app.services import building_floors, business_fit, floor_vacancy, industry_detail, vacant_inventory
from app.services import districts as districts_svc

ROOT = Path(__file__).resolve().parents[4]
_GOLD = ROOT / "data" / "gold"
_BRANDS = _GOLD / "platform_store_brands.json"
_COLOC = _GOLD / "platform_industry_colocation.json"

MIN_RADIUS_M = 10
MAX_RADIUS_M = 150
_STORES_MAX = 200
_MIN_COMPARED = 5           # 비교 자리가 이보다 적으면 백분위를 내지 않는다
_BASEMENT_UNKNOWN = -99
_M_PER_LAT = 111_320.0
_CELL_LAT = 0.002           # 약 222m — 최대 반경 150m 면 이웃 1칸이면 된다
_CELL_LNG = 0.0025          # 약 220m(서울 위도)
_SAME_BUILDING_M = 5.0
_W_SAME, _W_CHAIN, _W_SIMILAR = 10.0, 5.0, 4.0
_FLOOR_W = {"f1": 1.0, "f2": 0.75, "f3p": 0.5, "basement": 0.7, "unknown": 1.0}
REL_SAME, REL_SIMILAR, REL_COLOCATED, REL_OTHER = 0, 1, 2, 3
_REL_NAME = ("same", "similar", "colocated", "other")


@lru_cache(maxsize=1)
def _store_industries():
    spec = importlib.util.spec_from_file_location("placeos_store_industries", ROOT / "data/config/store_industries.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("점포 업종 사상표를 찾을 수 없습니다")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _floor_band(floor: int | None) -> str:
    if floor is None:
        return "unknown"
    if floor < 0:
        return "basement"
    return "f1" if floor <= 1 else ("f2" if floor == 2 else "f3p")


class _Hub:
    """거점 점포 묶음 + 격자 색인. 만든 뒤에는 읽기만 한다."""

    def __init__(self, doc: dict, center: tuple[float, float] | None):
        f = {k: i for i, k in enumerate(doc["fields"])}
        self.rows = doc["rows"]
        self.categories = doc.get("categories") or {}
        self.as_of = doc.get("as_of")
        self.f = f
        self.grid: dict[tuple[int, int], list[int]] = {}
        la, ln = f["lat"], f["lng"]
        for i, r in enumerate(self.rows):
            if r[la] is None or r[ln] is None:
                continue
            self.grid.setdefault((int(r[la] / _CELL_LAT), int(r[ln] / _CELL_LNG)), []).append(i)
        # 수집 반경 추정 — 거점 중심에서 가장 먼 점포까지. 원이 이 밖으로 나가면 그쪽 점포는 애초에 없다.
        self.center = center
        self.reach_m = 0.0
        if center:
            k = math.cos(math.radians(center[0]))
            self.reach_m = max((math.hypot((r[la] - center[0]) * _M_PER_LAT, (r[ln] - center[1]) * _M_PER_LAT * k)
                                for r in self.rows if r[la] is not None), default=0.0)

    def within(self, lat: float, lng: float, radius: float) -> list[tuple[float, int]]:
        """(거리 m, 행 번호) 가까운 순."""
        k = math.cos(math.radians(lat))
        ci, cj = int(lat / _CELL_LAT), int(lng / _CELL_LNG)
        la, ln = self.f["lat"], self.f["lng"]
        out: list[tuple[float, int]] = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for i in self.grid.get((ci + di, cj + dj), ()):
                    r = self.rows[i]
                    d = math.hypot((r[la] - lat) * _M_PER_LAT, (r[ln] - lng) * _M_PER_LAT * k)
                    if d <= radius:
                        out.append((d, i))
        out.sort()
        return out


def _center_of(slug: str) -> tuple[float, float] | None:
    d = districts_svc.PAGES_BY_ID.get(slug)
    c = (d or {}).get("center")
    if isinstance(c, (list, tuple)) and len(c) == 2:
        return float(c[0]), float(c[1])
    if isinstance(c, dict) and "lat" in c:
        return float(c["lat"]), float(c["lng"])
    return None


@lru_cache(maxsize=8)
def _read_hub(slug: str, mtime: float) -> _Hub | None:
    try:
        with gzip.open(_GOLD / slug / "stores_lite.json.gz", "rt", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    return _Hub(doc, _center_of(slug))


def _hub(slug: str) -> _Hub | None:
    try:
        stamp = (_GOLD / slug / "stores_lite.json.gz").stat().st_mtime
    except OSError:
        return None
    return _read_hub(slug, stamp)


@lru_cache(maxsize=1)
def _brand_names(mtime: float) -> dict[str, str]:
    try:
        doc = json.loads(_BRANDS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v.get("name") or k for k, v in (doc.get("brands") or {}).items()}


@lru_cache(maxsize=1)
def _coloc_doc(mtime: float) -> dict:
    try:
        return json.loads(_COLOC.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _stamp(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _colocated_top(slug: str, industry: str | None, detail_key: str | None) -> tuple[list[dict], bool]:
    """(함께 모이는 업종 상위, 세부 업종 기준인가). 도시 범위가 그 업종을 못 재면 빈 목록이다."""
    d = districts_svc.PAGES_BY_ID.get(slug)
    if not d or not industry:
        return [], False
    scope = (_coloc_doc(_stamp(_COLOC)).get("scopes") or {}).get(districts_svc.page_city(d).id) or {}
    if detail_key:
        top = ((scope.get("details") or {}).get(detail_key) or {}).get("top")
        if top:
            return top, True
    return ((scope.get("industries") or {}).get(industry) or {}).get("top") or [], False


def colocated_top(district_id: str, industry: str | None) -> list[dict]:
    """함께 모이는 업종 상위(관측 lift) — Program 네트워킹·실행 카드가 「보완 업종 이웃」으로 쓴다.

    도시 범위 Gold 라 그 도시가 이 업종을 못 재면 빈 목록이다. 관측일 뿐 인과·매출 효과가 아니다
    (platform_industry_colocation.json 의 note).
    """
    top, _ = _colocated_top(district_id, industry, None)
    return [{"key": t.get("key"), "label": t.get("label"), "lift": t.get("lift"), "n_both": t.get("n_both")}
            for t in top]


def colocation_note() -> str | None:
    return _coloc_doc(_stamp(_COLOC)).get("note")


@lru_cache(maxsize=32)
def _relations(slug: str, mtime: float, industry: str | None, detail_key: str | None) -> tuple:
    """행마다 관계 코드. 같은 거점·업종에는 다시 계산하지 않는다."""
    hub = _hub(slug)
    if hub is None:
        return (bytes(), frozenset(), frozenset())
    si = _store_industries()
    f = hub.f
    names = hub.categories
    detail = industry_detail.get(detail_key) if detail_key else None
    source_names = set((detail or {}).get("source_names") or ())
    top, top_is_detail = _colocated_top(slug, industry, detail_key)
    top_keys = {t["key"] for t in top}
    detail_name_to_key: dict[str, str] = {}
    if top_is_detail:
        for it in industry_detail.catalog():
            for nm in it["source_names"]:
                detail_name_to_key[nm] = it["key"]

    def is_same(row: list) -> bool:
        if source_names:
            return names.get(row[f["scls"]]) in source_names
        return bool(industry) and si.industry_of(row[f["scls"]]) == industry

    same_mcls = {r[f["mcls"]] for r in hub.rows if is_same(r)}
    out = bytearray(len(hub.rows))
    same_names: set[str] = set()
    similar_names: set[str] = set()
    for i, r in enumerate(hub.rows):
        scls = r[f["scls"]]
        if is_same(r):
            out[i] = REL_SAME
            same_names.add(names.get(scls) or "")
        elif r[f["mcls"]] in same_mcls or (detail and si.industry_of(scls) == detail["parent"]):
            out[i] = REL_SIMILAR
            similar_names.add(names.get(scls) or "")
        elif top_is_detail and detail_name_to_key.get(names.get(scls) or "") in top_keys:
            out[i] = REL_COLOCATED
        elif not top_is_detail and si.industry_of(scls) in top_keys:
            out[i] = REL_COLOCATED
        else:
            out[i] = REL_OTHER
    return bytes(out), frozenset(same_names - {""}), frozenset(similar_names - {""})


def _hub_stamp(slug: str) -> float:
    return _stamp(_GOLD / slug / "stores_lite.json.gz")


def _empty_counts() -> dict:
    return {"same": 0, "same_chain": 0, "similar": 0, "colocated": 0, "other": 0, "total": 0}


def _counts(hub: _Hub, rel: bytes, hits: list[tuple[float, int]]) -> dict:
    c = _empty_counts()
    bi = hub.f["brand"]
    for _, i in hits:
        code = rel[i]
        c[_REL_NAME[code]] += 1
        c["total"] += 1
        if code == REL_SAME and hub.rows[i][bi]:
            c["same_chain"] += 1
    return c


def _index(hub: _Hub, rel: bytes, hits: list[tuple[float, int]], floor_weighted: bool) -> float:
    """참고 지수. 시안 산식 그대로이되 임계값으로 해석하지 않는다."""
    bi, fi = hub.f["brand"], hub.f["floor"]
    total = 0.0
    for _, i in hits:
        code = rel[i]
        if code not in (REL_SAME, REL_SIMILAR):
            continue
        w = _FLOOR_W[_floor_band(hub.rows[i][fi])] if floor_weighted else 1.0
        if code == REL_SAME:
            total += _W_SAME * w
            if hub.rows[i][bi]:
                total += _W_CHAIN * w
        else:
            total += _W_SIMILAR * w
    return round(total, 2)


def _sites(slug: str) -> list[tuple[float, float]]:
    """비교 대상 — 이 상권의 빈 자리(건물 유닛 · 층 매물)의 서로 다른 좌표."""
    seen: set[tuple[float, float]] = set()
    for src in ((vacant_inventory.load(slug) or {}).get("units") or [],
                (floor_vacancy.load(slug) or {}).get("units") or []):
        for u in src:
            if u.get("lat") is not None and u.get("lng") is not None:
                seen.add((round(float(u["lat"]), 6), round(float(u["lng"]), 6)))
    return sorted(seen)


@lru_cache(maxsize=64)
def _distribution(slug: str, mtime: float, industry: str | None, detail_key: str | None,
                  radius: int, floor_weighted: bool) -> tuple[float, ...]:
    hub = _hub(slug)
    if hub is None:
        return ()
    rel = _relations(slug, mtime, industry, detail_key)[0]
    return tuple(sorted(_index(hub, rel, hub.within(la, ln, radius), floor_weighted) for la, ln in _sites(slug)))


def _relative(slug: str, mtime: float, industry: str | None, detail_key: str | None, radius: int,
              floor_weighted: bool, value: float) -> dict:
    dist = _distribution(slug, mtime, industry, detail_key, radius, floor_weighted)
    n = len(dist)
    note = (f"이 상권 빈 자리 {n}곳과 비교한 상대 위치입니다. 매출·성과로 검증된 값이 아닙니다."
            + (" 층 가중치는 참고 가중치입니다." if floor_weighted else ""))
    if n < _MIN_COMPARED:
        return {"percentile": None, "band": None, "index": value, "compared_sites": n,
                "note": f"비교할 빈 자리가 {n}곳뿐이라 상대 위치를 내지 않습니다."}
    lo, hi = bisect.bisect_left(dist, value), bisect.bisect_right(dist, value)
    pct = round((lo + (hi - lo) / 2) / n * 100, 1)
    band = "여유 쪽" if pct <= 100 / 3 else ("붐비는 쪽" if pct >= 200 / 3 else "중간")
    return {"percentile": pct, "band": band, "index": value, "compared_sites": n, "note": note}


def nearby(district_id: str, lat: float, lng: float, radius: int = 100, industry: str | None = None,
           detail_key: str | None = None, floor_weighted: bool = False, building_id: str | None = None) -> dict | None:
    """반경 안 점포 요약. 거점·점포 자료가 없으면 None. 모르는 업종은 ValueError(→ 422)."""
    slug = vacant_inventory.slug_of(district_id)
    if slug is None:
        return None
    if industry is not None and business_fit.get(industry) is None:
        raise ValueError("알 수 없는 업종")
    detail = None
    if detail_key is not None:
        detail = industry_detail.get(detail_key)
        if detail is None:
            raise ValueError("알 수 없는 세부 업종")
        if industry and detail["parent"] != industry:
            raise ValueError("세부 업종과 업종이 일치하지 않습니다")
        industry = detail["parent"]
    radius = max(MIN_RADIUS_M, min(MAX_RADIUS_M, int(radius)))
    hub = _hub(slug)
    if hub is None:
        return None

    stamp = _hub_stamp(slug)
    rel, same_names, similar_names = _relations(slug, stamp, industry, detail_key)
    hits = hub.within(lat, lng, radius)
    f = hub.f
    counts = _counts(hub, rel, hits)
    split = {"basement": 0, "f1": 0, "f2": 0, "f3p": 0, "unknown": 0}
    chains: dict[str, int] = {}
    brand_names = _brand_names(_stamp(_BRANDS))
    for _, i in hits:
        r = hub.rows[i]
        split[_floor_band(r[f["floor"]])] += 1
        if r[f["brand"]]:
            b = brand_names.get(r[f["brand"]], r[f["brand"]])
            chains[b] = chains.get(b, 0) + 1

    pnu = building_floors.pnu_of(building_id) if building_id else None
    stores = []
    for d, i in hits[:_STORES_MAX]:
        r = hub.rows[i]
        brand = r[f["brand"]]
        floor = r[f["floor"]]
        stores.append({
            "name": r[f["name"]],
            "brand": brand_names.get(brand, brand) if brand else None,
            "is_chain": bool(brand),
            "cat": hub.categories.get(r[f["scls"]]) or hub.categories.get(r[f["mcls"]]),
            "relation": _REL_NAME[rel[i]],
            "lat": r[f["lat"]], "lng": r[f["lng"]],
            "floor": floor, "floor_label": ("지하" if floor == _BASEMENT_UNKNOWN else None),
            "distance_m": round(d, 1),
            "same_building": (r[f["lno"]] == pnu) if pnu else d <= _SAME_BUILDING_M,
        })

    nearest_same = None
    if industry:
        k = math.cos(math.radians(lat))
        best: tuple[float, int] | None = None
        for i, code in enumerate(rel):
            if code != REL_SAME:
                continue
            r = hub.rows[i]
            if r[f["lat"]] is None:
                continue
            dist = math.hypot((r[f["lat"]] - lat) * _M_PER_LAT, (r[f["lng"]] - lng) * _M_PER_LAT * k)
            if best is None or dist < best[0]:
                best = (dist, i)
        if best:
            r = hub.rows[best[1]]
            nearest_same = {"name": r[f["name"]], "distance_m": round(best[0], 1), "floor": r[f["floor"]]}

    top, _ = _colocated_top(slug, industry, detail_key)
    notes = ["거리는 직선입니다. 도로망이 없어 보행 거리·길 건너 보정은 하지 않았습니다.",
             "상가정보 좌표는 건물 단위라 같은 건물 점포는 거리가 같습니다.",
             "체인은 상호로 추정한 값이고 가맹 여부를 확인한 값이 아닙니다."]
    if split["unknown"]:
        notes.append(f"반경 안 {counts['total']}곳 중 {split['unknown']}곳은 층을 모릅니다.")
    if not industry:
        notes.append("업종을 고르지 않아 같은 업종·비슷한 업종을 나누지 않았습니다.")
    elif detail and not detail["source_names"]:
        notes.append("이 세부 업종을 식별할 상가정보 분류가 없어 상위 업종으로 셌습니다.")
    if not top and industry:
        notes.append("함께 모이는 업종은 이 도시 표본에서 조건을 넘은 쌍이 없습니다.")

    edge = bool(hub.center and hub.reach_m and (
        math.hypot((lat - hub.center[0]) * _M_PER_LAT,
                   (lng - hub.center[1]) * _M_PER_LAT * math.cos(math.radians(lat))) + radius > hub.reach_m))
    if edge:
        notes.append("이 반경 일부가 수집 범위 밖입니다. 그쪽 점포는 세지 못했습니다.")
    value = _index(hub, rel, hits, floor_weighted)
    return {
        "center": {"lat": lat, "lng": lng},
        "radius": radius,
        "basis": "직선",
        "floor_weighted": floor_weighted,
        "edge_truncated": edge,
        "store_as_of": hub.as_of,
        "counts": counts,
        "floor_split": split,
        "by_radius": {str(r0): _counts(hub, rel, hub.within(lat, lng, r0)) for r0 in (50, 100)},
        "nearest_same": nearest_same,
        "chains": [{"brand": b, "n": n} for b, n in sorted(chains.items(), key=lambda kv: (-kv[1], kv[0]))],
        "relative": (_relative(slug, stamp, industry, detail_key, radius, floor_weighted, value) if industry else
                     {"percentile": None, "band": None, "index": None, "compared_sites": 0,
                      "note": "업종을 고르면 이 상권 빈 자리들과 비교합니다."}),
        "stores": stores,
        "relations": {
            "same": sorted(same_names), "similar": sorted(similar_names),
            "colocated": [{"name": t.get("label"), "lift": t.get("lift")} for t in top],
        },
        "notes": notes,
    }


def clear_cache() -> None:
    for fn in (_read_hub, _relations, _distribution, _brand_names, _coloc_doc):
        fn.cache_clear()
