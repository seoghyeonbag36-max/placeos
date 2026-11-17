"""신규 개업 위치 — 음식점 인허가(개업일)가 대로변·중로·이면 필지 중 어디에 몰리는가.

연구 질문(docs/finding-digital-premium-inputs-2026-11-17.md): 「입지 선택 비중」의 입력. 개업일 = 인허가일(APVPERMYMD).
인허가 행 → 건물 PNU 는 `probe_licensing_parcel_join.assign_rows`(영업·폐업 전부), PNU → 도로접면 군은
`data/collectors/vworld_landchar.py` 의 결과(`data/bronze/landchar/landchar_seoul.json`)다.

    python scripts/analyze_opening_location.py garosugil hongdae gangnam --out reports/new_opening_location_2026-11-17.json
    python scripts/analyze_opening_location.py $(서울 81거점 slug) --out reports/new_opening_location_81hubs_<날짜>.json   # 거점 이질성 포함

결과의 `_pooled`(합산) · `_heterogeneity`(거점별 전→후 변화, 탐색적) · `_errors`(분석 못 한 거점 — 하나가 실패해도 나머지는 계속).

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
import math
import statistics
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


def heterogeneity(res: dict, min_n: int = 30) -> dict:
    """거점별로 대로변 비중이 쿠팡이츠 전(2016~2018) → 후(2021~2026) 에 바뀌었나 — **탐색적**.

    두 비율 차이의 z(점추정 ÷ 표준오차). |z| > 1.96 이면 「증가/감소」. 구간별 개업 n 이 min_n 미만인 거점은 뺀다.
    ⚠ 거점이 많으면 우연만으로도 약 5% 가 |z|>1.96 이다(`expected_by_chance`) — 그 수와 비교해서 읽는다.
    ⚠ 개시 시점(구별 시차)과 연결하지 않은 단순 전·후 비교다. 인과가 아니다.
    """
    pre, post = PERIODS[0][0], PERIODS[2][0]
    rows = []
    for slug, r in res.items():
        if slug.startswith("_"):
            continue
        a, b = r["by_period"][pre], r["by_period"][post]
        if a["n"] < min_n or b["n"] < min_n:
            continue
        p1, p2 = a["대로변"], b["대로변"]
        se = math.sqrt(p1 * (1 - p1) / a["n"] + p2 * (1 - p2) / b["n"])
        rows.append({"slug": slug, "pre": p1, "post": p2, "delta": round(p2 - p1, 3), "n_pre": a["n"], "n_post": b["n"],
                     "z": round((p2 - p1) / se, 2) if se > 0 else 0.0})
    deltas = sorted(r["delta"] for r in rows)
    q = statistics.quantiles(deltas, n=4) if len(deltas) >= 2 else [None, None, None]
    return {"hubs": len(rows), "min_n": min_n, "increase": sum(r["z"] > 1.96 for r in rows),
            "decrease": sum(r["z"] < -1.96 for r in rows), "no_difference": sum(abs(r["z"]) <= 1.96 for r in rows),
            "expected_by_chance_each_direction": round(0.025 * len(rows), 1),
            "delta_quartiles": [round(x, 3) if x is not None else None for x in q],
            "median_delta": round(statistics.median(deltas), 3) if deltas else None,
            "rows": sorted(rows, key=lambda r: r["delta"])}


def analyze(slugs: list[str], parcels: dict) -> dict:
    out = {}
    errors: dict[str, str] = {}
    pooled_year = collections.defaultdict(collections.Counter)
    pooled_base = collections.Counter()
    for slug in slugs:
        try:
            meta, items = assign_rows(slug)
        except Exception as exc:  # noqa: BLE001 — 거점 하나의 자료 문제로 81거점 전체가 죽으면 안 된다. 종류만 남긴다
            errors[slug] = type(exc).__name__
            continue
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
    out["_pooled"] = {"hubs": len(out), "baseline_share": shares(pooled_base),
                      "by_year": {str(y): shares(c) for y, c in sorted(pooled_year.items())},
                      "by_period": {name: shares(sum((pooled_year[y] for y in range(a, b + 1)), collections.Counter()))
                                    for name, a, b in PERIODS}}
    out["_heterogeneity"] = heterogeneity(out)
    out["_errors"] = errors
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
        if name in ("_heterogeneity", "_errors"):
            continue
        base = r["baseline_share"]
        print(f"\n## {name}  기준선(건물 필지 {r.get('building_parcels', '합산')}): {_fmt(base)}")
        if "food_openings_in_buildings" in r:
            print(f"   음식점 개업(건물에 붙은 행) {r['food_openings_in_buildings']} · 개업연도 없음 {r['opening_year_missing']} · 접도 미상 필지 {r['parcel_without_landchar']}")
        for p, s in r["by_period"].items():
            print(f"   {p:22s}{_fmt(s, base)}")
    h = res["_heterogeneity"]
    print(f"\n## 거점 이질성(탐색적) — 대로변 비중 쿠팡이츠 전 → 후, 구간 n≥{h['min_n']} 인 {h['hubs']}거점")
    print(f"   증가(z>1.96) {h['increase']} · 감소(z<-1.96) {h['decrease']} · 차이 없음 {h['no_difference']} · 우연 기대치(방향당) {h['expected_by_chance_each_direction']}")
    print(f"   변화량 중앙 {h['median_delta']} · 사분위 {h['delta_quartiles']}")
    if res["_errors"]:
        print(f"   ⚠ 분석 실패 거점 {len(res['_errors'])}: {res['_errors']}")
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
