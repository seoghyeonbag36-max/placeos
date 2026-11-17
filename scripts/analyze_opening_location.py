"""신규 개업 위치 — 음식점 인허가(개업일)가 대로변·중로·이면 필지 중 어디에 몰리는가.

연구 질문(docs/finding-digital-premium-inputs-2026-11-17.md): 「입지 선택 비중」의 입력. 개업일 = 인허가일(APVPERMYMD).
인허가 행 → 건물 PNU 는 `probe_licensing_parcel_join.assign_rows`(영업·폐업 전부), PNU → 도로접면 군은
`data/collectors/vworld_landchar.py` 의 결과(`data/bronze/landchar/landchar_seoul.json`)다.

    python scripts/analyze_opening_location.py garosugil hongdae gangnam --out reports/new_opening_location_2026-11-17.json

기준선(무정보): 개업이 건물에 **무작위**로 갔다면 나올 대로변 비율 = 그 거점 **건물 필지 중** 대로변 비율. lift = 관측 ÷ 기준선.
⚠ 개업 = 인허가일 — 폐업한 업소도 포함한다(생존 편향이 아니라 코호트 전체). 인허가 자료가 오래된 폐업 행을 지워 두었다면
  먼 과거 연도는 과소다(미확인 — 연도별 건수 추세로만 의심할 수 있다).
⚠ 접도 군은 **최신 연도 값**이다(2016 이후 군이 바뀐 필지 4/241 = 1.7%, 표본 실측).
⚠ 분모는 거점 폴리곤 안에서 건물에 붙은 행이다. 붙지 않은 행(bbox 안 15~29%)이 대로변에 몰리는지는 모른다.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_licensing_parcel_join import assign_rows  # noqa: E402

from data.collectors.common import BRONZE  # noqa: E402
from data.collectors.vworld_landchar import road_group  # noqa: E402

FOOD = ("일반음식점", "휴게음식점")
GROUPS = ("대로변", "중로", "그외", "미상")
PERIODS = (("2016~2018 (쿠팡이츠 전)", 2016, 2018), ("2019~2020", 2019, 2020), ("2021~2026", 2021, 2026))


def opening_year(row: dict) -> int | None:
    s = str(row.get("APVPERMYMD") or "").strip()[:4]
    return int(s) if s.isdigit() and 1990 <= int(s) <= 2026 else None


def latest_group(parcels: dict, pnu: str) -> str:
    v = (parcels.get(pnu) or {}).get("v")
    if not v:
        return "미상"
    names = [y[1] for y in v["y"] if y[1]]
    return road_group(names[-1]) if names else "미상"


def shares(counter: collections.Counter, known_only: bool = True) -> dict:
    keys = [g for g in GROUPS if not (known_only and g == "미상")]
    n = sum(counter[g] for g in keys)
    return {"n": n, **{g: (round(counter[g] / n, 3) if n else None) for g in keys}}


def analyze(slugs: list[str], parcels: dict) -> dict:
    out = {}
    pooled_year = collections.defaultdict(collections.Counter)
    pooled_base = collections.Counter()
    for slug in slugs:
        meta, items = assign_rows(slug)
        base = collections.Counter(latest_group(parcels, p) for p in meta["building_pnus"])
        by_year = collections.defaultdict(collections.Counter)
        total = unknown_year = no_landchar = 0
        for it in items:
            if not it["pnu"] or it["row"].get("svc") not in FOOD:
                continue
            y = opening_year(it["row"])
            if y is None:
                unknown_year += 1
                continue
            g = latest_group(parcels, it["pnu"])
            no_landchar += g == "미상"
            by_year[y][g] += 1
            total += 1
        for y, c in by_year.items():
            pooled_year[y].update(c)
        pooled_base.update(base)
        out[slug] = {"food_openings_in_buildings": total, "opening_year_missing": unknown_year,
                     "parcel_without_landchar": no_landchar, "building_parcels": sum(base.values()),
                     "baseline_share": shares(base), "by_year": {str(y): shares(c) for y, c in sorted(by_year.items())},
                     "by_period": {name: shares(sum((by_year[y] for y in range(a, b + 1)), collections.Counter()))
                                   for name, a, b in PERIODS}}
    out["_pooled_3hubs"] = {"baseline_share": shares(pooled_base),
                            "by_year": {str(y): shares(c) for y, c in sorted(pooled_year.items())},
                            "by_period": {name: shares(sum((pooled_year[y] for y in range(a, b + 1)), collections.Counter()))
                                          for name, a, b in PERIODS}}
    return out


def _fmt(s: dict, base: dict | None = None) -> str:
    if not s["n"]:
        return "     0"
    lift = f" lift {s['대로변'] / base['대로변']:.2f}" if base and base.get("대로변") else ""
    return f"{s['n']:>6}  대로변 {s['대로변']*100:5.1f}%  중로 {s['중로']*100:5.1f}%  그외 {s['그외']*100:5.1f}%{lift}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("hubs", nargs="+")
    ap.add_argument("--landchar", default=str(BRONZE / "landchar" / "landchar_seoul.json"))
    ap.add_argument("--out")
    a = ap.parse_args()
    parcels = json.loads(Path(a.landchar).read_text(encoding="utf-8"))["parcels"]
    res = analyze(a.hubs, parcels)
    for name, r in res.items():
        base = r["baseline_share"]
        print(f"\n## {name}  기준선(건물 필지 {r.get('building_parcels', '합산')}): {_fmt(base)}")
        if "food_openings_in_buildings" in r:
            print(f"   음식점 개업(건물에 붙은 행) {r['food_openings_in_buildings']} · 개업연도 없음 {r['opening_year_missing']} · 접도 미상 필지 {r['parcel_without_landchar']}")
        for p, s in r["by_period"].items():
            print(f"   {p:22s}{_fmt(s, base)}")
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
