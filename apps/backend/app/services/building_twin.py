"""3D 트윈 입력 — `GET /buildings/{id}/twin?district=`.

## 층 상태는 두 근거를 잇는다

- `rule_kind` = 프론트 `placeFloors` 와 같은 규칙(occupied·uncertain·vacant·noncom). 층 미상 점포를 낮은 층부터 앉힌다.
- `status` = 그 위에 `/floor-vacancies` 의 층·certainty 를 얹은 값. **`vacant_*` 는 매물 목록에 있는 층뿐이다** — 그래야
  트윈과 매물 목록이 서로 다른 빈 층을 말하지 않는다. 규칙으로는 비었지만 목록에 없는 층(면적 근거 없음 · 만실 건물로 분류된
  건물의 남은 층)은 `uncertain` 으로 내리고 `rule_kind` 로 그 사실을 남긴다.

지하는 대장 층별개요로만 안다. 점포 판정 근거가 없으므로 `unknown` 이다. 근거 없는 건물(`polygon_only`)의 층은 전부 `unknown`
이고 절대 「비었다」고 칠하지 않는다.

## 이 값이 아닌 것

- 공실 판정은 스냅샷이다. 상가정보 점포 대조일 뿐 현장 확인이 아니다(라벨 0/458 — 정확도 검정불가).
- 층고는 원천에 없다. `height_source="estimated"` 면 층수 × 3.3m 다.
- 창호·외장·내부 형상은 실측이 아니다. 호실은 면적·호 번호뿐이고 위치가 없다.
"""
from __future__ import annotations

import math

from app.services import (building_floors, building_history, building_vacancy, floor_vacancy, posting_inputs,
                          rent_layer, vacancy_class, vacant_inventory)

_FLOOR_HEIGHT_M = 3.3
_NEIGHBOR_RADIUS_M = 120.0
_NEIGHBOR_MAX = 60
_MAX_FLOORS = 150           # 층수 오기로 수천 층이 그려지지 않게 막는 상한
_HISTORY_MAX = 80
_M_PER_LAT = 111_320.0


def _ring_latlng(feature: dict) -> list[list[float]]:
    coords = ((feature.get("geometry") or {}).get("coordinates") or [[]])[0]
    return [[round(c[1], 6), round(c[0], 6)] for c in coords]


def _centroid(ring: list[list[float]]) -> tuple[float, float]:
    pts = ring[:-1] if len(ring) > 2 and ring[0] == ring[-1] else ring
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def place_floors(com: list[int], occ: list[int], unknown_n: int, top: int) -> dict[int, str]:
    """프론트 `placeFloors` 와 같은 규칙. 상한(렌더용 20층)만 없다."""
    occ_set, com_set = set(occ), set(com)
    uncertain: set[int] = set()
    spare = unknown_n
    for f in com:
        if spare <= 0:
            break
        if f not in occ_set:
            uncertain.add(f)
            spare -= 1
    out: dict[int, str] = {}
    for f in range(1, top + 1):
        if f not in com_set:
            out[f] = "noncom"
        elif f in occ_set:
            out[f] = "occupied"
        elif f in uncertain:
            out[f] = "uncertain"
        else:
            out[f] = "vacant"
    return out


def _floor_label(lv: int) -> str:
    return f"{lv}F" if lv > 0 else f"B{-lv}"


def _ledger_by_level(rows: list[dict]) -> dict[int, dict]:
    """대장 층 행 → 층별 {area_m2, purps, etc, multi_dong}. 주부속 부속 행은 면적에 넣지 않는다."""
    agg: dict[int, dict] = {}
    for r in rows:
        kind, no = r.get("kind"), r.get("no")
        if kind not in ("G", "B") or not isinstance(no, int) or no <= 0 or r.get("atch"):
            continue
        lv = no if kind == "G" else -no
        a = agg.setdefault(lv, {"area_m2": 0.0, "best": -1.0, "purps": None, "dongs": set()})
        area = float(r.get("area_m2") or 0.0)
        a["area_m2"] += area
        a["dongs"].add(r.get("dong") or "")
        if area > a["best"]:
            a["best"], a["purps"] = area, r.get("purps")
    return agg


def _rent(rent_per_m2: float | None, lv: int, area_m2: float | None) -> tuple[int | None, float | None]:
    """(층 전체 월임대 추정 만원, 평당 만원). `/heatmap/rent` 의 listings 와 같은 식이다."""
    if not rent_per_m2:
        return None, None
    factor = posting_inputs.floor_factor(_floor_label(lv))
    per = rent_layer._per_pyeong(rent_per_m2, factor)
    return (rent_layer._monthly(rent_per_m2, area_m2, factor) if area_m2 else None), per


def _floors(props: dict, pnu: str, listed: dict[int, dict], lot: dict | None, doc: dict | None,
            rent_per_m2: float | None) -> tuple[list[dict], int, int, bool]:
    com = sorted(int(f) for f in props.get("com_floors") or [])
    occ = [int(f) for f in props.get("occ_floors") or []]
    unknown_n = int(props.get("unknown_n") or 0)
    polygon_only = props.get("source") == "polygon_only" or not com
    floor_rows, unit_rows = building_floors.rows_of(doc, lot) if (lot and doc) else ([], [])
    ledger = _ledger_by_level(floor_rows)

    master_floors = int(props.get("floors") or 0)
    grnd = int((lot or {}).get("grnd") or 0)
    top = max(master_floors, max(com, default=0))
    # 층수 원천이 셋이다(폴리곤·상업층·대장 표제부). 어긋나면 숨기지 않고 표시한다.
    conflict = bool(master_floors and com and max(com) > master_floors) or bool(grnd and top and grnd != top)
    if top == 0:
        top = grnd or max((lv for lv in ledger if lv > 0), default=0)
    top = min(top, _MAX_FLOORS)
    below = max(int((lot or {}).get("ugrnd") or 0), max((-lv for lv in ledger if lv < 0), default=0))
    below = min(below, 20)

    kinds = place_floors(com, occ, unknown_n, top) if not polygon_only else {}
    units_by_level: dict[int, list[dict]] = {}
    for u in unit_rows:
        no = u.get("no")
        if u.get("kind") in ("G", "B") and isinstance(no, int) and no > 0:
            lv = no if u["kind"] == "G" else -no
            units_by_level.setdefault(lv, []).append(
                {"ho": u.get("ho"), "area_m2": u.get("area_m2"), "purps": u.get("purps")})

    floors: list[dict] = []
    for lv in [*range(top, 0, -1), *range(-1, -below - 1, -1)]:
        kind = kinds.get(lv)
        vfu = listed.get(lv)
        if vfu:
            status = "vacant_confirmed" if vfu.get("certainty") == "confirmed" else "vacant_probable"
        elif kind == "occupied":
            status = "occupied"
        elif kind == "noncom":
            status = "noncom"
        elif kind in ("uncertain", "vacant"):
            status = "uncertain"
        else:
            status = "unknown"
        row = ledger.get(lv) or {}
        area = (vfu or {}).get("area_m2") or (round(row["area_m2"], 1) if row.get("area_m2") else None)
        multi = len(row.get("dongs") or ()) > 1
        est, per = (None, None)
        if status in ("vacant_confirmed", "vacant_probable", "uncertain"):
            est, per = _rent(rent_per_m2, lv, area)
        floors.append({
            "lv": lv, "label": _floor_label(lv), "status": status, "rule_kind": kind,
            "area_m2": area,
            "area_source": (None if not area else ("대장 층별개요(같은 지번 여러 동 합계)" if multi else "대장 층별개요")),
            "purps": (vfu or {}).get("purps") or row.get("purps"),
            "rent_est_manwon": est, "rent_per_pyeong": per,
            "unit_id": (vfu or {}).get("id"),
            "units": units_by_level.get(lv),
        })
    return floors, top, below, conflict


def _rate(vacant: float, total: float) -> float | None:
    return round(vacant / total * 100, 1) if total else None


def _vacancy_stats(floors: list[dict]) -> tuple[list[dict], dict]:
    """공실률을 기준별로. 기준이 달라 값이 벌어지는 것 자체가 정보라 하나로 뭉치지 않는다."""
    # 분모는 상업층이다. 비상업층·판정 불가 층은 넣지 않는다.
    com = [f for f in floors if f["status"] in ("vacant_confirmed", "vacant_probable", "occupied", "uncertain")]
    conf = [f for f in com if f["status"] == "vacant_confirmed"]
    both = [f for f in com if f["status"] in ("vacant_confirmed", "vacant_probable")]
    stats: list[dict] = []

    def row(basis: str, label: str, vac: float, total: float, note: str) -> None:
        stats.append({"basis": basis, "label": label, "vacant": round(vac, 1), "total": round(total, 1),
                      "rate_pct": _rate(vac, total), "note": note})

    if com:
        row("floors_confirmed", "층 수 · 확정만", len(conf), len(com), "상업층 중 공실확정 층의 비율")
        row("floors_both", "층 수 · 확정+의심", len(both), len(com), "층 미상 점포가 다른 층에 있다면 비는 층까지 포함")
        area_of = lambda fs: sum(f["area_m2"] or 0.0 for f in fs)     # noqa: E731
        if all(f["area_m2"] for f in com):
            row("area_confirmed", "면적 · 확정만", area_of(conf), area_of(com), "대장 층별개요 면적(㎡)")
            row("area_both", "면적 · 확정+의심", area_of(both), area_of(com), "대장 층별개요 면적(㎡)")
        n_units = sum(len(f["units"] or ()) for f in com)
        if n_units:
            row("units_floor", "호실 수 · 공실 층의 호실(추정)",
                sum(len(f["units"] or ()) for f in both), n_units,
                "전유부 호실과 공실 판정은 연결돼 있지 않다 — 빈 층에 있는 호실 수를 센 추정이다")
    rates = [s["rate_pct"] for s in stats if s["rate_pct"] is not None]
    return stats, {"min": min(rates) if rates else None, "max": max(rates) if rates else None}


def _history(slug: str, building_id: str, pnu: str) -> dict:
    """이 거점 파일만 읽는다 — `get_history` 는 전 거점 파일을 돌아 느리다."""
    path = building_history._GOLD_DIR / slug / "building_history.json"
    empty = {"source": "none", "lot_buildings": None, "items": [], "items_total": 0, "summary": None}
    if not path.exists():
        return empty
    hit = building_history._load_history(path)
    data = hit["data"]
    lot = (data.get("buildings") or {}).get(building_id) or pnu
    rows = (data.get("lots") or {}).get(lot) or []
    if not rows:
        return empty
    n = hit["lot_counts"].get(lot, 1)
    ordered = sorted(rows, key=lambda r: r.get("start_date") or "", reverse=True)
    ended = sorted((r["end_date"] for r in rows if r.get("end_date")), reverse=True)
    return {
        "source": "localdata" if n <= 1 else "localdata_lot",
        "lot_buildings": n,
        "items": [{"start": r.get("start_date"), "end": r.get("end_date"),
                   "industry": r.get("industry_type"), "name": r.get("business_name")}
                  for r in ordered[:_HISTORY_MAX]],
        "items_total": len(rows),
        "summary": {"total": len(rows), "closed": len(ended), "last_closed": ended[0] if ended else None,
                    "note": "지번 단위 인허가 이력이다. 층·호실을 모르고, 인허가 대상 업종만 있다."},
    }


def _neighbors(target_id: str, lat: float, lng: float, features: list[dict]) -> list[dict]:
    """대상 120m 안 — 실측 외곽선·층수만. 난수 건물을 채우지 않는다."""
    k = math.cos(math.radians(lat))
    found: list[tuple[float, dict]] = []
    for f in features:
        p = f.get("properties") or {}
        if p.get("id") == target_id:
            continue
        coords = ((f.get("geometry") or {}).get("coordinates") or [[]])[0]
        if not coords:
            continue
        clat, clng = coords[0][1], coords[0][0]
        d = math.hypot((clat - lat) * _M_PER_LAT, (clng - lng) * _M_PER_LAT * k)
        if d <= _NEIGHBOR_RADIUS_M:
            found.append((d, f))
    found.sort(key=lambda t: t[0])
    out = []
    for _, f in found[:_NEIGHBOR_MAX]:
        p = f["properties"]
        floors = int(p.get("floors") or 0)
        height = float(p.get("height") or 0) or None
        out.append({"id": p.get("id"), "ring": _ring_latlng(f), "floors": floors,
                    "height_m": height or (round(floors * _FLOOR_HEIGHT_M, 1) if floors else None),
                    "height_source": "vworld" if height else ("estimated" if floors else None),
                    "vac_class": p.get("vac_class") or "unknown"})
    return out


def twin(district_id: str, building_id: str) -> dict | None:
    """건물 하나의 트윈 입력. 거점·건물을 모르면 None(→ 404)."""
    slug = vacant_inventory.slug_of(district_id)
    if slug is None:
        return None
    fc = building_vacancy.building_vacancy_geojson(slug)
    if fc is None or not fc.get("features"):
        return None
    features = fc["features"]
    pnu = building_floors.pnu_of(building_id)
    # 유닛 id(vu-·vfu-)로 들어오면 그 지번의 대표 폴리곤(층수가 가장 큰 것)을 고른다 — 층 매물과 같은 규칙이다.
    wanted = building_id if not building_id.startswith(("vu-", "vfu-")) else None
    if wanted:
        feature = next((f for f in features if (f.get("properties") or {}).get("id") == wanted), None)
    else:
        same = [f for f in features if str((f.get("properties") or {}).get("pnu")) == pnu]
        feature = max(same, key=lambda f: f["properties"].get("floors") or 0) if same else None
    if feature is None:
        return None
    props = feature.get("properties") or {}
    ring = _ring_latlng(feature)
    if not ring:
        return None
    lat, lng = _centroid(ring)
    pnu = str(props.get("pnu") or pnu)

    doc = building_floors.load(slug)
    lot = ((doc or {}).get("lots") or {}).get(pnu)
    listed = vacancy_class.floors_by_pnu(slug).get(pnu) or {}
    if props.get("source") == "polygon_only":
        listed = {}
    row = posting_inputs.for_district(slug) or {}
    floors, top, below, conflict = _floors(props, pnu, listed, lot, doc, row.get("rent_per_m2_krw_thousand"))
    stats, span = _vacancy_stats(floors)
    height = float(props.get("height") or 0) or None
    inventory = floor_vacancy.load(slug) or {}

    notes = ["공실 판정은 상가정보 점포 대조이고 현장 미확인이다. 정확도는 아직 검정하지 못했다(현장 라벨 0/458).",
             "임대 추정은 R-ONE × 층 계수 × 대장 면적이고 호가가 아니다. 한 층에 호실이 여럿이면 그 층 전체 금액이다.",
             "형상은 V-World 외곽선, 층수는 대장 기준이다. 창호·외장·내부는 실측이 아니다."]
    if not lot:
        notes.append("이 지번의 대장 층별 자료가 없어 층 면적·용도·지하층을 모른다.")
    if conflict:
        notes.append("층수 원천(폴리곤·상업층·대장 표제부)이 서로 다르다. 큰 값으로 그렸다.")
    if (props.get("source") == "polygon_only"):
        notes.append("대장·점포 근거가 없는 건물이라 층 상태를 판정하지 않았다.")
    if not height:
        notes.append(f"건물 높이 자료가 없어 층수 × {_FLOOR_HEIGHT_M}m 로 추정했다.")

    return {
        "id": props.get("id"),
        "name": (lot or {}).get("bld_nm") or props.get("name"),
        "road_addr": props.get("road_addr") or (lot or {}).get("road"),
        "lat": round(lat, 6), "lng": round(lng, 6),
        "ring": ring,
        "floors_above": top, "floors_below": below, "floors_conflict": conflict,
        "height_m": height or (round(top * _FLOOR_HEIGHT_M, 1) if top else None),
        "height_source": "vworld" if height else "estimated",
        "approval_date": (lot or {}).get("use_apr"),
        "built_at": inventory.get("built_at"),
        "vac_class": props.get("vac_class") or "unknown",
        "representative_industry": (props.get("industry") or "").strip() or None,
        "lot_buildings": (next(iter(listed.values()))["bldgs_on_pnu"] if listed else None),
        "sources": ["V-World 건물 외곽선", "건축물대장 층별개요·표제부", "소상공인 상가정보 점포 대조",
                    *(["건축물대장 전유부"] if lot and lot.get("units") else [])],
        "floors": floors,
        "neighbors": _neighbors(str(props.get("id")), lat, lng, features),
        "vacancy_stats": stats,
        "range": span,
        "history": _history(slug, str(props.get("id")), pnu),
        "notes": notes,
    }
