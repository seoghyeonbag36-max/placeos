"""Page 정확도 스냅샷 — 재빌드 전후를 **같은 지표로** 대 보기 위한 읽기 전용 도구.

화면이 내보내는 정렬 격차(`aligned_gap_pp` = calibration.json `rone_aligned.mid` 대표값 −
R-ONE 앵커, services/gold_vacancy.py §앵커 대조)를 서빙 거점(`page_hubs.ACTIVE_HUBS`)마다
모으고, 마스터의 층 근거(상업층·확인 점유층)를 합산한다. Gold 만 읽고 아무것도 고치지 않는다.

  python scripts/page_accuracy_snapshot.py --out reports/page_accuracy_<날짜>.json
  python scripts/page_accuracy_snapshot.py --compare reports/page_accuracy_baseline_2026-10-10.json

⚠ 비교 전에 **앵커가 같은지** 먼저 본다(--compare 가 찍는다). R-ONE 분기가 바뀐 뒤의 차이는
데이터 효과가 아니라 기준선 이동이다.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.config.page_hubs import ACTIVE_HUBS  # noqa: E402

GOLD = ROOT / "data" / "gold"
_MID_KEYS = ("buildings", "vacancy_floor_hi_pct", "vacancy_floor_lo_pct", "vacancy_area_pct",
             "anchor_pct", "gap_pp")
_TOTAL_KEYS = ("buildings", "with_com_floors", "com_floors", "occ_floors", "unknown_n",
               "with_com_no_occ")


def _load(p: Path) -> dict | list | None:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _hub(slug: str) -> dict:
    cal = _load(GOLD / slug / "calibration.json") or {}
    mid = (cal.get("rone_aligned") or {}).get("mid") or {}
    out = {"anchor_source": cal.get("anchor_source"),
           "mid": {k: mid.get(k) for k in _MID_KEYS}}
    master = _load(GOLD / slug / "page_building_master.geojson") or {}
    t = dict.fromkeys(_TOTAL_KEYS, 0)
    for f in master.get("features", []):
        p = f.get("properties", {})
        com, occ = p.get("com_floors") or [], p.get("occ_floors") or []
        t["buildings"] += 1
        t["with_com_floors"] += bool(com)
        t["with_com_no_occ"] += bool(com) and not occ
        t["com_floors"] += len(com)
        t["occ_floors"] += len(occ)
        t["unknown_n"] += p.get("unknown_n") or 0
    out["master"] = t
    for name in ("vacant_floor_units", "vacant_units"):
        blob = _load(GOLD / slug / f"{name}.json")
        units = blob.get("units") if isinstance(blob, dict) else blob
        out[name] = len(units) if isinstance(units, list) else None
    return out


def _agg(vals: list) -> dict | None:
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"n": len(vals), "median": round(st.median(vals), 2), "mean": round(st.mean(vals), 2)}


def snapshot() -> dict:
    hubs = {s: _hub(s) for s in sorted(ACTIVE_HUBS)}
    gaps = [h["mid"]["gap_pp"] for h in hubs.values()]
    tot = {k: sum(h["master"][k] for h in hubs.values()) for k in _TOTAL_KEYS}
    band = sum(1 for h in hubs.values()
               if None not in (h["mid"]["vacancy_floor_hi_pct"], h["mid"]["vacancy_floor_lo_pct"],
                               h["mid"]["anchor_pct"])
               and h["mid"]["vacancy_floor_hi_pct"] <= h["mid"]["anchor_pct"] <= h["mid"]["vacancy_floor_lo_pct"])
    summary = {
        "hubs": len(hubs),
        "aligned_gap_pp": _agg(gaps),
        "gap_over": sum(1 for g in gaps if g is not None and g > 0),
        "gap_abs_gt10": sum(1 for g in gaps if g is not None and abs(g) > 10),
        "gap_abs_le3": sum(1 for g in gaps if g is not None and abs(g) <= 3),
        "anchor_in_floor_band": band,
        "aligned_vacancy_pct": _agg([h["mid"]["vacancy_area_pct"] for h in hubs.values()]),
        "master_totals": tot,
        "confirmed_floor_share_pct": round(100 * tot["occ_floors"] / tot["com_floors"], 2)
        if tot["com_floors"] else None,
        "vacant_floor_units": sum(h["vacant_floor_units"] or 0 for h in hubs.values()),
    }
    return {"summary": summary, "hubs": hubs}


def compare(before: dict, after: dict) -> list[str]:
    lines = ["## 요약 (전 → 후)"]
    for k, v in before["summary"].items():
        lines.append(f"- {k}: {v} → {after['summary'].get(k)}")
    moved = [(s, h["mid"]["anchor_pct"], after["hubs"].get(s, {}).get("mid", {}).get("anchor_pct"))
             for s, h in before["hubs"].items()
             if h["mid"]["anchor_pct"] != after["hubs"].get(s, {}).get("mid", {}).get("anchor_pct")]
    lines.append(f"\n## 앵커가 바뀐 거점: {len(moved)} — 이 거점의 격차 차이는 데이터 효과가 아니다")
    lines += [f"- {m}" for m in moved]
    rows = []
    for s, h in before["hubs"].items():
        gb, ga = h["mid"]["gap_pp"], after["hubs"].get(s, {}).get("mid", {}).get("gap_pp")
        if gb is not None and ga is not None:
            rows.append((s, gb, ga, round(ga - gb, 2)))
    if rows:
        d = [r[3] for r in rows]
        lines.append(f"\n## 거점별 정렬 격차 변화(후−전, %p): 중앙 {st.median(d):+.2f} · "
                     f"|격차| 줄어듦 {sum(1 for r in rows if abs(r[2]) < abs(r[1]))} · "
                     f"늘어남 {sum(1 for r in rows if abs(r[2]) > abs(r[1]))}")
        lines += ["| 거점 | 전 | 후 | Δ |", "|---|---:|---:|---:|"]
        lines += [f"| {s} | {b} | {a} | {x:+.2f} |"
                  for s, b, a, x in sorted(rows, key=lambda r: -abs(r[3]))[:20]]
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", help="스냅샷 JSON 저장 경로")
    ap.add_argument("--compare", help="이 기준선과 현재 Gold 를 비교한다")
    args = ap.parse_args()
    snap = snapshot()
    if args.out:
        Path(args.out).write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.compare:
        print("\n".join(compare(json.loads(Path(args.compare).read_text(encoding="utf-8")), snap)))
    else:
        print(json.dumps(snap["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
