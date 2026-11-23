"""시군구 전체 점포 전수 → 등록 거점이 덮는 몫 · 덮지 못한 행정동 · 신규 거점 후보 (Page 도시 전체 Phase 0).

고양·파주 확장(2026-11-23 사용자 결정 ①)의 첫 단계다. 거점 9곳(+보류 11곳)이 도시 점포의 몇 %를 덮는지 **분모부터 센다.**
- 점포 원천: 소상공인 상가정보 `storeListInDong` (`divId=signguCd`) — 부산 조사(`run_busan_research.fetch_stores`)와 같은 호출.
- 후보 중심은 **관측된 점포 한 곳의 좌표**다(추정 중심 생성 금지 — `audit_regional_hub_candidates` 와 같은 원칙).
- 후보 판정은 hub-chain §0 두 단계(건물당 점포 >10 기각 · top10 지번 집중도 >25% 주의). 판정은 **등록 전 탐색**이다 —
  대장·앵커·Gold 를 통과하기 전에는 서빙하지 않는다. 이 스크립트는 레지스트리·Gold 를 고치지 않는다.

    python scripts/citywide_store_census.py --city goyang            # 수집(없는 페이지만) + 분석
    python scripts/citywide_store_census.py --city paju --analyze-only
    python scripts/citywide_store_census.py --city goyang --root <키·bronze 가 있는 트리>   # 워크트리에서 돌릴 때

출력: reports/citywide_census_{city}.json (거점별 커버 · 행정동 표 · 후보). 원본 페이지: bronze/_citywide_census/{city}/ (gitignore).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SELF_ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
# hub-chain §0 · 규칙(신규 거점은 기존 거점과 1.0km 이상 이격)
MAX_STORES_PER_BUILDING = 10.0
TOP10_CAUTION_PCT = 25.0
MIN_SEPARATION_M = 1000.0
CANDIDATE_RADIUS_M = 500.0
MIN_CANDIDATE_STORES = 300
MAX_PICKS = 20
CELL_M = 250.0


def sgg_codes(city: str) -> list[str]:
    """도시 레지스트리의 시군구 코드 — 한 곳(`apps/backend/app/data/cities.py`)만 믿는다."""
    sys.path.insert(0, str(SELF_ROOT / "apps/backend"))
    from app.data import cities
    return sorted(cities.by_id(city).sgg_codes)


def fetch_city(city: str, root: Path) -> list[dict]:
    """시군구마다 전 페이지. 받은 페이지는 다시 받지 않는다(재개). 예외 메시지에 키가 실리지 않게 종류만 남긴다."""
    import requests
    sys.path.insert(0, str(root))
    from data.collectors.common import BRONZE, load_env
    from data.collectors.building_vacancy import BASE_SDSC
    load_env()
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "")
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY 없음 — 키가 있는 트리를 --root 로 지정")
    out = BRONZE / "_citywide_census" / city
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    seen: set[str] = set()
    for sgg in sgg_codes(city):
        total, page = None, 1
        got = 0
        while total is None or got < total:
            path = out / f"{sgg}_{page:04d}.json"
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
            else:
                try:
                    r = requests.get(BASE_SDSC + "/storeListInDong", params=dict(
                        serviceKey=key, divId="signguCd", key=sgg, type="json", numOfRows=1000, pageNo=page), timeout=40)
                    if r.status_code != 200:
                        raise SystemExit(f"상가정보 HTTP {r.status_code} (sgg={sgg} page={page})")
                    payload = r.json()
                except requests.RequestException as exc:
                    raise SystemExit(f"상가정보 네트워크 오류 {type(exc).__name__} (sgg={sgg} page={page})") from None
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                time.sleep(0.2)
            body = payload.get("body") or {}
            items = body.get("items") or []
            if total is None:
                total = int(body.get("totalCount") or 0)
                print(f"{city} {sgg} total={total}", flush=True)
            if not items:
                break
            for it in items:
                sid = str(it.get("bizesId") or "")
                if sid and sid not in seen:
                    seen.add(sid)
                    rows.append(it)
            got += len(items)
            page += 1
    return rows


def load_cached(city: str, root: Path) -> list[dict]:
    sys.path.insert(0, str(root))
    from data.collectors.common import BRONZE
    rows, seen = [], set()
    for path in sorted((BRONZE / "_citywide_census" / city).glob("*.json")):
        for it in (json.loads(path.read_text(encoding="utf-8")).get("body") or {}).get("items") or []:
            sid = str(it.get("bizesId") or "")
            if sid and sid not in seen:
                seen.add(sid)
                rows.append(it)
    return rows


def _xy(lon: float, lat: float, lat0: float = 37.7) -> tuple[float, float]:
    return lon * 111320 * math.cos(math.radians(lat0)), lat * 111000


def analyze(city: str, rows: list[dict], root: Path) -> dict:
    import numpy as np
    sys.path.insert(0, str(root))
    from data.config.page_hubs import ACTIVE_HUBS, ALL_HUBS
    from data.config.rone_districts import DISTRICT_RONE, SHARED_RONE

    pts = [(float(r["lon"]), float(r["lat"]), r) for r in rows if r.get("lon") and r.get("lat")]
    skipped = len(rows) - len(pts)
    xy = np.array([_xy(lo, la) for lo, la, _ in pts])
    n = len(pts)
    hubs = {s: h for s, h in ALL_HUBS.items() if h.city == city}
    hub_xy = {s: _xy(h.cx, h.cy) for s, h in hubs.items()}

    def dist_to(point: tuple[float, float]):
        return np.hypot(xy[:, 0] - point[0], xy[:, 1] - point[1])

    # 거점별 · 가까운 쪽 귀속(점포 한 곳은 한 거점에만 센다 — partition_with 와 같은 원칙)
    d_hub = {s: dist_to(p) for s, p in hub_xy.items()}
    names = list(hubs)
    mat = np.vstack([d_hub[s] for s in names]) if names else np.empty((0, n))
    nearest = mat.argmin(axis=0) if names else np.zeros(n, dtype=int)
    nearest_d = mat.min(axis=0) if names else np.full(n, np.inf)
    covered_store = np.zeros(n, dtype=bool)
    hub_rows = []
    for i, s in enumerate(names):
        h = hubs[s]
        mine = (nearest == i)
        in_store_r = mine & (nearest_d <= h.stores_radius_m)
        in_poly_r = mine & (nearest_d <= h.radius_m)
        state = "서빙" if s in ACTIVE_HUBS else (f"보류({h.deferred})" if h.deferred else "등록만")
        # 거점 천장 둘을 서빙 여부와 따로 적는다(2026-11-23 사용자 결정 ②) — 3D 트윈 담당이 이 두 칸으로 대상을 고른다
        rone = "공유" if s in SHARED_RONE else ("정확" if s in DISTRICT_RONE else "없음")
        hub_rows.append(dict(slug=s, name=h.name, state=state, ceiling_planned_store=h.deferred or "",
                             ceiling_rone_anchor=rone, rone_series=DISTRICT_RONE.get(s, ""),
                             stores_in_collection_radius=int(in_store_r.sum()),
                             stores_in_polygon_radius=int(in_poly_r.sum()), radius_m=h.radius_m,
                             stores_radius_m=h.stores_radius_m))
        if state == "서빙":
            covered_store |= in_store_r
    served_cov = covered_store.copy()
    reg_cov = np.zeros(n, dtype=bool)
    for i, s in enumerate(names):
        reg_cov |= (nearest == i) & (nearest_d <= hubs[s].stores_radius_m)

    # 행정동 표
    by_dong: dict[str, dict] = defaultdict(lambda: dict(stores=0, served=0, registered=0))
    for k, (_, _, r) in enumerate(pts):
        key = f"{r.get('signguNm') or ''} {r.get('adongNm') or ''}".strip()
        by_dong[key]["stores"] += 1
        by_dong[key]["served"] += int(served_cov[k])
        by_dong[key]["registered"] += int(reg_cov[k])
    dongs = sorted(({"dong": k, **v, "uncovered_by_served": v["stores"] - v["served"],
                     "served_pct": round(100 * v["served"] / v["stores"], 1)} for k, v in by_dong.items()),
                   key=lambda d: -d["uncovered_by_served"])

    # 신규 후보 — 서빙 거점 밖 점포를 250m 격자로 세어 반경 500m 합이 큰 곳부터. 중심은 관측된 점포 좌표.
    # 후보 점수는 **등록 거점(보류 포함)이 아직 덮지 않은** 점포로만 센다 — 보류 거점 곁(화정·마두 등)은 이미 이름이 있는 자리다.
    # 서빙 거점 밖 전체(미커버 집계)는 위 표가 따로 보인다.
    remaining = ~reg_cov
    dead = np.zeros(n, dtype=bool)  # 이격 규칙에 막혀 후보가 못 되는 자리 — 합산에서만 뺀다(미커버 집계에는 남는다)
    blocked = [p for p in hub_xy.values()]  # 등록 거점 전부와 1.0km 이상(보류·등록만도 포함)
    picks = []
    x0, y0 = xy[:, 0].min(), xy[:, 1].min()
    gx = ((xy[:, 0] - x0) // CELL_M).astype(int)
    gy = ((xy[:, 1] - y0) // CELL_M).astype(int)
    k = int(round(CANDIDATE_RADIUS_M / CELL_M))
    pad = k + 1  # np.roll 이 가장자리에서 감기지 않게 합 반경보다 넓은 여백
    W, H = gx.max() + 2 * pad + 1, gy.max() + 2 * pad + 1
    offs = [(dx, dy) for dx in range(-k, k + 1) for dy in range(-k, k + 1) if math.hypot(dx, dy) <= k + 0.01]

    def far_enough(p) -> bool:
        return all(math.hypot(p[0] - b[0], p[1] - b[1]) >= MIN_SEPARATION_M for b in blocked)

    for _ in range(4000):
        if len(picks) >= MAX_PICKS:
            break
        live = remaining & ~dead
        grid = np.zeros((W, H))
        np.add.at(grid, (gx[live] + pad, gy[live] + pad), 1)
        score = np.zeros_like(grid)
        for dx, dy in offs:  # 반경 ≈500m 원판 합(격자 근사)
            score += np.roll(np.roll(grid, dx, axis=0), dy, axis=1)
        idx = int(np.argmax(score))
        cx_, cy_ = np.unravel_index(idx, score.shape)
        if score[cx_, cy_] < MIN_CANDIDATE_STORES:
            break
        cell = (x0 + (cx_ - pad + .5) * CELL_M, y0 + (cy_ - pad + .5) * CELL_M)
        near = np.where((dist_to(cell) <= CANDIDATE_RADIUS_M) & live)[0]
        # 중심은 관측된 점포 한 곳 — 무게중심에 가장 가까운 점포부터 보되, **최종 중심점**이 이격 규칙(≥1.0km)을 지켜야 한다.
        # (격자 중심에서만 재면 중심점이 500m 까지 움직여 946m 후보가 통과한다 — 2026-11-23 주교동)
        wc = xy[near].mean(axis=0) if len(near) else np.array(cell)
        order = near[np.argsort(np.hypot(xy[near, 0] - wc[0], xy[near, 1] - wc[1]))] if len(near) else near
        center_i = next((int(i) for i in order if far_enough(tuple(xy[i]))), None)
        if center_i is None:
            dead |= dist_to(cell) <= CELL_M  # 이 자리는 등록 거점 곁이라 후보가 못 된다 — 다른 자리를 본다
            continue
        cxy = tuple(xy[center_i])
        d = dist_to(cxy)
        inside = np.where(d <= CANDIDATE_RADIUS_M)[0]
        blds = Counter(pts[i][2].get("bldMngNo") for i in inside if pts[i][2].get("bldMngNo"))
        ratio = len(inside) / len(blds) if blds else float("nan")
        top10 = 100 * sum(c for _, c in blds.most_common(10)) / len(inside)
        verdict = ("기각(계획상가 밀집)" if ratio > MAX_STORES_PER_BUILDING else
                   "주의(지번 집중)" if top10 > TOP10_CAUTION_PCT else "통과")
        r0 = pts[center_i][2]
        picks.append(dict(rank=len(picks) + 1, label=f"{r0.get('signguNm') or ''} {r0.get('adongNm') or ''} ({r0.get('ldongNm') or ''})".strip(),
                          lon=pts[center_i][0], lat=pts[center_i][1], observed_center_bizes_id=r0.get("bizesId"),
                          stores_500m=int(len(inside)), new_stores_500m=int((remaining & (d <= CANDIDATE_RADIUS_M)).sum()),
                          buildings=len(blds), stores_per_building=round(ratio, 2), top10_pct=round(top10, 1), verdict=verdict,
                          nearest_registered_m=round(min(math.hypot(cxy[0] - b[0], cxy[1] - b[1]) for b in blocked))))
        blocked.append(cxy)
        remaining &= ~(d <= 700)
    return dict(city=city, observed_at=datetime.now(KST).isoformat(timespec="seconds"), stores=n, stores_without_coordinates=skipped,
                served_hub_cover=dict(stores=int(served_cov.sum()), pct=round(100 * served_cov.mean(), 1)),
                registered_hub_cover=dict(stores=int(reg_cov.sum()), pct=round(100 * reg_cov.mean(), 1)),
                hubs=hub_rows, dongs=dongs, candidates=picks,
                method=dict(source="소상공인 상가정보 storeListInDong divId=signguCd", cover_rule="가까운 쪽 거점의 stores_radius_m 안",
                            candidate_rule=f"250m 격자·반경 {int(CANDIDATE_RADIUS_M)}m 합 ≥{MIN_CANDIDATE_STORES} · 최종 중심점이 등록 거점·앞선 후보와 ≥{int(MIN_SEPARATION_M)}m · 중심=관측 점포",
                            verdict_rule="hub-chain §0 (건물당 점포>10 기각 · top10>25% 주의)", seed=False),
                limitations=["탐색용 — 상권 경계·대장·앵커 검증 전에는 서빙하지 않는다.",
                             "상가정보는 영업 중 점포 스냅샷이다. 공실·폐업 건물은 대장 단계에서 센다.",
                             "읍면 지역은 점포가 드물어 후보 임계(300점포/500m)에 못 미칠 수 있다 — 그 행정동은 표에서 보인다."])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--city", required=True, choices=["goyang", "paju"])
    ap.add_argument("--root", default=str(SELF_ROOT), help="키(.env)·bronze 가 있는 트리 — 기본은 이 트리")
    ap.add_argument("--analyze-only", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    rows = load_cached(a.city, root) if a.analyze_only else fetch_city(a.city, root)
    if not rows:
        raise SystemExit("점포 0건 — 수집부터")
    result = analyze(a.city, rows, root)
    out = SELF_ROOT / "reports" / f"citywide_census_{a.city}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{a.city} 점포 {result['stores']:,} · 서빙 거점이 덮는 몫 {result['served_hub_cover']['pct']}% · "
          f"등록 거점 {result['registered_hub_cover']['pct']}% · 후보 {len(result['candidates'])}곳 → {out.relative_to(SELF_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
