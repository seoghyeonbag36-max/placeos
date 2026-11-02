"""[Platform] 거점별 실측 범위 외곽선 — gold/platform_hub_outlines.json.

`/heatmap/vacancy` 의 100m 격자 셀 합집합의 외곽선이다. 프론트 `lib/hubBoundary.ts computeHubBoundary` 와
같은 뜻(4-이웃 조각 · 내부가 왼쪽인 변 추적 · 핀치는 오른쪽 우선 · `v > 0` 으로 셀을 거르지 않음)이고, 한 직선 위의
꼭짓점만 줄여 싣는다. 조각을 감싸 하나로 덮지 않는다 — 안 잰 곳을 잰 것처럼 그리게 된다.
**공식 상권 경계가 아니다.** 합성 그리드 폴백 거점은 싣지 않는다.

실행: python -m data.pipelines.build_hub_outlines
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from data.collectors.common import GOLD
from data.config.page_hubs import ACTIVE_HUBS

OUT = "platform_hub_outlines.json"
NOTE = ("100m 격자 실측 셀의 외곽선이다. 공식 상권 경계가 아니고, 건축물대장 실측이 닿은 범위를 그린 것이다. "
        "조각이 여럿이면 그 사이는 재지 않은 곳이다.")

Cell = tuple[int, int]
Point = tuple[int, int]
_NB = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _groups(filled: set[Cell]) -> list[list[Cell]]:
    seen: set[Cell] = set()
    groups: list[list[Cell]] = []
    for start in sorted(filled):
        if start in seen:
            continue
        seen.add(start)
        stack, group = [start], []
        while stack:
            i, j = stack.pop()
            group.append((i, j))
            for di, dj in _NB:
                nb = (i + di, j + dj)
                if nb in filled and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        groups.append(group)
    return groups


def _rings(group: list[Cell], filled: set[Cell]) -> list[list[Point]]:
    """marching edges — 방향 0 동·1 북·2 서·3 남. 내부가 항상 왼쪽이라 외곽은 양수, 구멍은 음수 면적이다."""
    edges: list[dict] = []
    for i, j in group:
        if (i, j - 1) not in filled:
            edges.append({"f": (i, j), "t": (i + 1, j), "d": 0, "u": False})
        if (i + 1, j) not in filled:
            edges.append({"f": (i + 1, j), "t": (i + 1, j + 1), "d": 1, "u": False})
        if (i, j + 1) not in filled:
            edges.append({"f": (i + 1, j + 1), "t": (i, j + 1), "d": 2, "u": False})
        if (i - 1, j) not in filled:
            edges.append({"f": (i, j + 1), "t": (i, j), "d": 3, "u": False})
    out: dict[Point, list[dict]] = {}
    for e in edges:
        out.setdefault(e["f"], []).append(e)

    rings: list[list[Point]] = []
    for seed in edges:
        if seed["u"]:
            continue
        seed["u"] = True
        ring, cur, d = [seed["f"]], seed["t"], seed["d"]
        while cur != seed["f"]:
            ring.append(cur)
            nxt = None
            for want in ((d + 3) % 4, d, (d + 1) % 4, (d + 2) % 4):
                nxt = next((e for e in out.get(cur, []) if not e["u"] and e["d"] == want), None)
                if nxt:
                    break
            if nxt is None:
                break
            nxt["u"] = True
            cur, d = nxt["t"], nxt["d"]
        if len(ring) >= 4:
            rings.append(ring)
    return rings


def _shoelace(ring: list[Point]) -> int:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))


def _drop_collinear(ring: list[Point]) -> list[Point]:
    n = len(ring)
    return [ring[k] for k in range(n)
            if (ring[k][0] - ring[k - 1][0]) * (ring[(k + 1) % n][1] - ring[k][1])
            != (ring[k][1] - ring[k - 1][1]) * (ring[(k + 1) % n][0] - ring[k][0])]


def _inside_bbox(inner: list[Point], outer: list[Point]) -> bool:
    return (min(p[0] for p in outer) <= min(p[0] for p in inner)
            and max(p[0] for p in inner) <= max(p[0] for p in outer)
            and min(p[1] for p in outer) <= min(p[1] for p in inner)
            and max(p[1] for p in inner) <= max(p[1] for p in outer))


def outline(cells: list[dict]) -> dict | None:
    """히트맵 셀(i·j·lat·lng·dlat·dlng) → `{cells, components, largest_share, pieces}`. 셀이 없으면 None."""
    if not cells:
        return None
    c0 = cells[0]
    dlat, dlng = c0["dlat"], c0["dlng"]
    lat0, lng0 = c0["lat"] - c0["j"] * dlat, c0["lng"] - c0["i"] * dlng
    filled = {(c["i"], c["j"]) for c in cells}

    def to_latlng(ring: list[Point]) -> list[list[float]]:
        return [[round(lat0 + y * dlat, 5), round(lng0 + x * dlng, 5)] for x, y in _drop_collinear(ring)]

    groups = _groups(filled)
    pieces: list[dict] = []
    for group in groups:
        rings = _rings(group, filled)
        outers = [r for r in rings if _shoelace(r) > 0]
        holes = [r for r in rings if _shoelace(r) < 0]
        built = [{"cells": 0, "outer": to_latlng(o), "holes": []} for o in outers]
        if not built:
            continue
        built[0]["cells"] = len(group)        # 핀치로 외곽이 둘이면 첫 외곽에 몰아준다(hubBoundary.ts 와 같다)
        for h in holes:
            idx = next((k for k, o in enumerate(outers) if _inside_bbox(h, o)), 0)
            built[idx]["holes"].append(to_latlng(h))
        pieces.extend(built)
    pieces.sort(key=lambda p: -p["cells"])
    return {"cells": len(filled), "components": len(groups),
            "largest_share": round(100 * max(map(len, groups)) / len(filled), 1), "pieces": pieces}


def _heatmap_service():
    backend = Path(__file__).resolve().parents[2] / "apps" / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from app.services import districts
    return districts


def run(log=print) -> dict:
    svc = _heatmap_service()
    hubs: dict[str, dict] = {}
    skipped: list[str] = []
    for slug in ACTIVE_HUBS:
        hm = svc.get_vacancy_heatmap(slug)
        doc = outline(hm["cells"]) if hm and hm.get("vacancy_source") == "gold" else None
        if doc is None:
            skipped.append(slug)
        else:
            hubs[slug] = doc
    out = {"note": NOTE, "source": "건축물대장 실측 100m 격자(/heatmap/vacancy 셀)",
           "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "hubs": hubs}
    path = GOLD / OUT
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"[outlines] {len(hubs)}거점 · 뺀 곳 {skipped} · {path.stat().st_size / 1e6:.2f}MB")
    return {"hubs": len(hubs), "skipped": skipped}


if __name__ == "__main__":
    run()
