"""서울 빈 층 × 12업종 입점 점검 분포 — 서술 통계(사전등록 채점이 아니다).

    python scripts/use_check_vacant_summary.py --city seoul --date 2026-11-15

빈 층 유닛(Gold vacant_floor_units) 마다 그 층의 대장 행(Bronze bldg_flr_raw · 용도코드 포함)을 붙여
services/use_check.check 를 12업종으로 돌리고, 판정 갈래·대장 호·필지 용도지역 분포를 reports/ 에 남긴다.

⚠ 이 분포는 「규칙이 빈 층을 어떻게 나누나」일 뿐 「규칙이 맞나」가 아니다. 맞는지는 인허가 정답지로
  사전등록(docs/prereg-floor-use-check-2026-11-15.md)대로 따로 잰다 — 그 전에 이 숫자로 규칙을 고치지 않는다.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from app.services import building_ledger_live as bll  # noqa: E402
from app.services import use_check  # noqa: E402
from data.config import page_hubs as ph  # noqa: E402


def floor_parts(slug: str) -> dict[tuple[str, int], list[dict]]:
    """층별개요 원본을 Gold 빌더와 같은 규칙(날짜 오름차순 병합 · 최신이 이김)으로 읽는다.
    ⚠ 최신 날짜 파일 하나만 읽으면 안 된다 — 거점마다 새 건물만 따로 받은 날이 있어 70%가 빈다(11-15 실측)."""
    from data.pipelines.build_vacant_floor_units import _load_floor_rows

    rows = _load_floor_rows(slug)
    out: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for pnu, items in rows.items():
        for r in items or []:
            lv = bll.floor_level(r)
            if lv is None:
                continue
            out[(pnu, lv)].append({"purps": str(r.get("mainPurpsCdNm") or "").strip() or None,
                                   "code": str(r.get("mainPurpsCd") or "").strip() or None,
                                   "area_m2": float(r.get("area") or 0), "etc": None})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--city", default="seoul")
    ap.add_argument("--date", required=True)
    ap.add_argument("--gold-src", type=Path, default=Path(os.environ.get("PLACEOS_GOLD_SRC") or ROOT / "data" / "gold"))
    ap.add_argument("--bronze", type=Path, default=Path(os.environ.get("PLACEOS_BRONZE_ROOT") or ROOT / "data" / "bronze"))
    a = ap.parse_args()

    status = {k: Counter() for k in use_check.INDUSTRY_ACTS}
    reasons = {k: Counter() for k in use_check.INDUSTRY_ACTS}
    ho, zones, n_units, no_parts, hubs = Counter(), Counter(), 0, 0, 0
    inputs = use_check._load() or {}
    names = inputs.get("zone_names", {})
    for slug, hub in ph.ACTIVE_HUBS.items():
        if hub.city != a.city:
            continue
        vfu = a.gold_src / slug / "vacant_floor_units.json"
        if not vfu.exists() or not glob.glob(str(a.bronze / slug / "*" / "bldg_flr_raw.json")):
            continue
        hubs += 1
        parts_by = floor_parts(slug)
        for u in json.loads(vfu.read_text(encoding="utf-8"))["units"]:
            n_units += 1
            parts = parts_by.get((u["pnu"], u["floor"])) or []
            same = [p for p in parts if p["purps"] == u.get("purps")]
            parts = same or parts
            if not parts:
                no_parts += 1
            else:
                main = max(parts, key=lambda p: p["area_m2"])
                ho[use_check.ho_name(use_check.ho_of(main["code"]))] += 1
            uz = [c for c, _ in inputs.get("parcels", {}).get(u["pnu"], []) if c.startswith("UQA") and not c.startswith("UQA0")]
            zones[" + ".join(names.get(c, c) for c in uz) if uz else "(없음)"] += 1
            for ind in use_check.INDUSTRY_ACTS:
                r = use_check.check(u["pnu"], ind, parts=parts or None, area_m2=u.get("area_m2"))
                status[ind][r["regulation_status"]] += 1
                for c in r["checks"]:
                    if c["status"] in ("check", "blocked", "missing"):
                        reasons[ind][f"{c['item']}:{c['status']}"] += 1

    out = {
        "city": a.city, "date": a.date, "hubs": hubs, "units": n_units, "units_without_ledger_floor": no_parts,
        "note": "서술 통계 — 규칙이 빈 층을 어떻게 나누나. 규칙의 실력(인허가 정답지 대조)이 아니다.",
        "inputs_basis": inputs.get("basis"),
        "ledger_ho": dict(ho.most_common()),
        "use_zones": dict(zones.most_common(15)),
        "status_by_industry": {k: dict(v.most_common()) for k, v in status.items()},
        "open_items_by_industry": {k: dict(v.most_common()) for k, v in reasons.items()},
    }
    rep = ROOT / "reports" / f"use_check_vacant_{a.city}_{a.date}.json"
    rep.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("hubs", "units", "units_without_ledger_floor", "ledger_ho", "use_zones")},
                     ensure_ascii=False, indent=1))
    for k, v in out["status_by_industry"].items():
        print(f"{k:12s} {v}")
    print("→", rep)


if __name__ == "__main__":
    main()
