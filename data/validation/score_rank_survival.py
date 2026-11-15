"""상권 순위 ↔ 개업 뒤 24개월 생존 — 동시점 대조 (사전등록 2026-11-15 · **참고 판정**).

입력: `data/gold/platform_survival_cohorts.json`(정제 · 거점 × 업종 칸) × `reports/ranking_snapshot_<날짜>.json`(동결한 `fit` · `same_share`).
규칙의 정본: docs/prereg-platform-rank-survival-2026-11-15.md §7 — **칸을 계산하기 전에 고정**했고 결과를 본 뒤 고치지 않는다.

  ρ_fit    eligible 거점(칸 n ≥ 30 · 순위·same_share 둘 다 있음)에서 fit 과 24개월 생존 비율의 Spearman(동률은 평균 순위)
  ρ_share  같은 거점에서 same_share 와 생존 비율의 Spearman
  Δρ       ρ_fit − ρ_share — 게이트 값. 구간은 거점을 복원 추출하는 부트스트랩(1,000회 · seed 20261115) 95% 백분위수
  판정     eligible 거점 < 20 → 검정불가 · 하한 > 0 → 실력 · 0 을 품음 → 구분불가 · 상한 < 0 → 열위
  주 업종  restaurant(음식점) 하나가 게이트 · cafe · clinic · convenience 는 같은 계산을 **관측**으로만 낸다

⚠ **이 값은 참고다.** 순위는 현재(2026-10) 점포 스냅샷으로 만든 점수라 과거 코호트와의 동시점 대조에는 생존자 편향이 낀다
  (사전등록 §8-1 — same_share 에 더 직접적이라 Δρ 에는 fit 에 불리한 방향이지만 예측 실력의 증거는 아니다). 판정 이름이
  `실력` 이어도 「순위가 맞다」가 아니다 — 게이트는 동결한 순위로 동결일 이후 개업의 생존을 재는 전방 검증(2028-11 이후)이 닫는다.
  출력에는 항상 `kind`(참고·동시점)가 붙는다.

실행:
  python -m data.validation.score_rank_survival
  python -m data.validation.score_rank_survival --json reports/rank_survival_2026-11-15.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
SURVIVAL = _ROOT / "data" / "gold" / "platform_survival_cohorts.json"
SNAPSHOT_DATE = "2026-11-15"
SNAPSHOT = _ROOT / "reports" / f"ranking_snapshot_{SNAPSHOT_DATE}.json"
PRIMARY = "restaurant"
MIN_HUBS = 20
REPS, SEED = 1000, 20261115
TOP_K = 10
KIND = "참고(동시점 · 누수 가능) — 게이트는 전방 검증(2028-11 이후)"
SKILL, UNRESOLVED, WORSE, UNTESTABLE = "실력", "구분불가", "열위", "검정불가"


def _ranks(xs: list[float]) -> list[float]:
    """평균 순위(동률은 순위의 평균)."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman ρ — 표본이 3 미만이거나 한쪽이 상수면 None(0 으로 채우지 않는다)."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / (sxx * syy) ** 0.5


def delta_rho(rows: list[dict]) -> tuple[float | None, float | None, float | None]:
    rate = [r["rate"] for r in rows]
    a = spearman([r["fit"] for r in rows], rate)
    b = spearman([r["share"] for r in rows], rate)
    return a, b, (None if a is None or b is None else a - b)


def bootstrap(rows: list[dict], reps: int = REPS, seed: int = SEED) -> list[float] | None:
    """거점을 복원 추출한 Δρ 의 95% 백분위수 구간. 한쪽이 상수가 된 재표본은 버린다."""
    rng = random.Random(seed)
    n = len(rows)
    ds = []
    for _ in range(reps):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        d = delta_rho(sample)[2]
        if d is not None:
            ds.append(d)
    if len(ds) < reps // 2:
        return None
    ds.sort()
    return [round(ds[int(0.025 * len(ds))], 4), round(ds[min(len(ds) - 1, int(0.975 * len(ds)))], 4)]


def top_k_gap(rows: list[dict], key: str, k: int = TOP_K) -> float | None:
    """key 상위 k 거점의 평균 생존 − 나머지의 평균 생존(관측). 나머지가 비면 None."""
    if len(rows) <= k:
        return None
    srt = sorted(rows, key=lambda r: -r[key])
    top, rest = srt[:k], srt[k:]
    return round(sum(r["rate"] for r in top) / k - sum(r["rate"] for r in rest) / len(rest), 4)


def judge(res: dict) -> dict:
    """게이트 판정 — 사전등록 §7 그대로. 결과를 보고 고치지 않는다."""
    n = res["n_hubs"]
    if n < MIN_HUBS:
        return {"verdict": UNTESTABLE, "reason": f"eligible 거점 {n} < {MIN_HUBS} — 사전등록 최소"}
    if res["ci95"] is None or res["delta"] is None:
        return {"verdict": UNTESTABLE, "reason": "Δρ 를 정의할 수 없다(한쪽 점수가 상수)"}
    lo, hi = res["ci95"]
    detail = {"delta": round(res["delta"], 3), "ci95": [lo, hi], "n_hubs": n}
    if lo > 0:
        return {"verdict": SKILL, **detail}
    if hi < 0:
        return {"verdict": WORSE, **detail}
    return {"verdict": UNRESOLVED, **detail}


def industry_rows(survival: dict, snapshot: dict, key: str) -> tuple[list[dict], dict]:
    """한 업종의 eligible 거점 줄과 제외 사유 수."""
    dist = {d["district_id"]: d for d in (snapshot.get("industries", {}).get(key, {}).get("districts") or [])}
    rows, excl = [], {"hub_not_in_snapshot": 0, "no_fit": 0, "no_same_share": 0, "not_eligible": 0}
    for slug, hub in survival["hubs"].items():
        cell = hub["industries"].get(key)
        if not cell or not cell["eligible"]:
            excl["not_eligible"] += 1
            continue
        d = dist.get(slug)
        if d is None:
            excl["hub_not_in_snapshot"] += 1
            continue
        if d.get("fit") is None:
            excl["no_fit"] += 1
            continue
        if d.get("same_share") is None:
            excl["no_same_share"] += 1
            continue
        rows.append({"hub": slug, "fit": d["fit"], "share": d["same_share"], "rate": cell["rate"], "n": cell["n"]})
    return rows, excl


def _sens_survival(survival: dict, gap_key: str) -> dict:
    """민감도(G=30·180)의 (n, 생존 수) 칸을 주 분석과 같은 모양으로 — eligible 은 같은 최소 표본(n ≥ min_n)으로 다시 가른다."""
    min_n = survival["rules"]["min_n"]
    hubs = {}
    for slug, inds in survival["sensitivity"][gap_key].items():
        hubs[slug] = {"industries": {k: {"n": c["n"], "survived": c["survived"], "eligible": c["n"] >= min_n,
                                         "rate": round(c["survived"] / c["n"], 4) if c["n"] >= min_n else None}
                                     for k, c in inds.items()}}
    return {"hubs": hubs, "rules": survival["rules"]}


def score(survival: dict, snapshot: dict, reps: int = REPS, seed: int = SEED) -> dict:
    out: dict[str, dict] = {}
    for key in sorted(survival["rules"]["mapping"]):
        rows, excl = industry_rows(survival, snapshot, key)
        a, b, d = delta_rho(rows) if rows else (None, None, None)
        out[key] = {
            "label": snapshot.get("industries", {}).get(key, {}).get("label"),
            "n_hubs": len(rows), "excluded": excl,
            "rho_fit": None if a is None else round(a, 4), "rho_share": None if b is None else round(b, 4),
            "delta": d, "ci95": bootstrap(rows, reps, seed) if len(rows) >= 3 else None,
            "top10_gap_fit": top_k_gap(rows, "fit"), "top10_gap_share": top_k_gap(rows, "share"),
            "median_cohort_n": sorted(r["n"] for r in rows)[len(rows) // 2] if rows else None,
        }
    # 관측(판정 없음): 병합 간격 민감도 — 같은 계산을 G=30·180 칸으로. 구간은 주 업종만(계산량)
    sens: dict[str, dict] = {}
    for gk in sorted(survival.get("sensitivity", {})):
        s_surv = _sens_survival(survival, gk)
        sens[gk] = {}
        for key in sorted(survival["rules"]["mapping"]):
            rows, _ = industry_rows(s_surv, snapshot, key)
            a, b, d = delta_rho(rows) if rows else (None, None, None)
            sens[gk][key] = {"n_hubs": len(rows),
                             "rho_fit": None if a is None else round(a, 4), "rho_share": None if b is None else round(b, 4),
                             "delta": None if d is None else round(d, 4),
                             "ci95": bootstrap(rows, reps, seed) if key == PRIMARY and len(rows) >= 3 else None}
    res = {"kind": KIND, "primary": PRIMARY, "snapshot": snapshot.get("frozen_on"),
           "rules": {"gap_days": survival["rules"]["gap_days"], "min_n": survival["rules"]["min_n"],
                     "cohort": survival["rules"]["cohort"], "horizon_days": survival["rules"]["horizon_days"]},
           "industries": out, "sensitivity": sens}
    res["gate"] = judge(out[PRIMARY]) if PRIMARY in out else {"verdict": UNTESTABLE, "reason": "주 업종 칸이 없다"}
    return res


def _fmt(x) -> str:
    return "—" if x is None else f"{x:+.3f}"


def _print(res: dict) -> None:
    g = res["gate"]
    detail = (f"Δρ {g['delta']:+.3f} [{g['ci95'][0]:+.3f}, {g['ci95'][1]:+.3f}] · eligible 거점 {g['n_hubs']}"
              if "delta" in g else g["reason"])
    print(f"[rank-survival] {res['kind']}")
    print(f"  주 업종 {res['primary']} → {g['verdict']} — {detail}")
    for k, v in res["industries"].items():
        print(f"  {k:12s} 거점 {v['n_hubs']:3d} · ρ_fit {_fmt(v['rho_fit'])} · ρ_share {_fmt(v['rho_share'])} · "
              f"Δρ {_fmt(v['delta'])} {v['ci95']} · 상위10−나머지 fit {_fmt(v['top10_gap_fit'])} / share {_fmt(v['top10_gap_share'])}")
    for gk, inds in res.get("sensitivity", {}).items():
        p = inds.get(res["primary"], {})
        print(f"  민감도 {gk}: {res['primary']} Δρ {_fmt(p.get('delta'))} {p.get('ci95')} · 거점 {p.get('n_hubs')} (관측)")


def main() -> None:
    ap = argparse.ArgumentParser(description="상권 순위 ↔ 24개월 생존 — 동시점 대조(참고)")
    ap.add_argument("--survival", default=str(SURVIVAL))
    ap.add_argument("--snapshot", default=str(SNAPSHOT))
    ap.add_argument("--json", help="결과 JSON 저장 경로")
    ap.add_argument("--reps", type=int, default=REPS)
    a = ap.parse_args()
    if not Path(a.survival).exists():
        raise SystemExit(f"[rank-survival] 생존 산출물이 없다: {a.survival} — python -m data.pipelines.build_platform_survival")
    res = score(json.loads(Path(a.survival).read_text(encoding="utf-8")),
                json.loads(Path(a.snapshot).read_text(encoding="utf-8")), reps=a.reps)
    _print(res)
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
