"""블로그 `total` 증가분 점검 — 스냅샷 사이 Δtotal ÷ Δ일 이 `rate_per_day` 보다 거점 노출을 잘 재는가.

배경: 주 1회 스냅샷의 `rate_per_day` 는 최신 1,000건이 덮는 창(중앙 9일, 25%는 5일 이하)의 평균이라 주를 빈틈없이 못 덮는다.
스냅샷 사이 `total`(질의 일치 문서 수)의 증가분은 **빈틈없는 유입량**이 될 수 있으나 `total` 이 안정적인지 모른다(검증 안 함).
이 모듈이 그 검증이다. 실행기(scripts/digital_exposure_weekly.py)가 매 스냅샷 뒤 돌려 `reports/digital_exposure_total_delta.json` 을 갱신한다.

## 사전등록 (2026-11-17 — 데이터를 보기 **전**에 고정. 바꾸려면 이 파일과 문서를 같은 PR 에서, 이유와 함께)
스냅샷 ≥ 4개(= 증가분 3구간, 약 3~4주)에서만 판정한다. 그 전은 「표본부족」이다.

  게이트 G1 (단조성)  Δtotal < 0 인 (거점·질의·구간) 비율 < 5%.   → total 이 줄어든다면 색인 변동이라 증가분이 유입량이 아니다.
  게이트 G2 (순위 지속) 연속 두 구간의 거점 간 Spearman 의 중앙값 ≥ 0.70. → 구간마다 순위가 뒤집히면 증가분은 잡음이다.
  판정 (게이트 통과 시)  1차 대상 = 두 질의 모두 정밀도 ≥ 0.5 인 거점(최신 스냅샷).
      Δρ = ρ(증가분, 데이터랩 수준) − ρ(rate_per_day, 데이터랩 수준) 의 거점 단위 짝 부트스트랩(2,000회, 시드 20261117) 95% 구간:
        하한 > 0 → 「개선」 · 상한 < 0 → 「열위」 · 그 외 → 「구분불가」.
      1차 대상이 20거점 미만이면 「표본부족」.
  게이트 실패 → 「열위」 (증가분을 쓰지 않는다).
  기준선(무정보 대신): rate_per_day 의 데이터랩 Spearman — 2026-11-17 실측 0.365(81거점) · 0.403(정밀도 필터 45거점).
  전 81거점 결과는 2차(참고)로 같이 싣는다.

⚠ 데이터랩 수준 = 최근 12개월 월 ratio ÷ 기준어 ratio 의 평균(`--datalab-long` 이 기준어를 보존한다). 블로그와 데이터랩은 같은 거점 키워드를 쓴다.
⚠ 「개선」이어도 인과·타당성의 증명이 아니다 — 같은 거점 순위를 데이터랩과 더 잘 맞춘다는 뜻일 뿐이다.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

from data.collectors import digital_exposure_panel as panel

MIN_SNAPSHOTS = 4
G1_MAX_NEGATIVE_SHARE = 0.05
G2_MIN_RANK_PERSISTENCE = 0.70
PRECISION_MIN = 0.5
MIN_PRIMARY_HUBS = 20
BOOTSTRAP_B = 2000
SEED = 20261117


# ── 통계 ────────────────────────────────────────────────────────────────────

def ranks(xs: list[float]) -> list[float]:
    """평균 순위(동률은 평균)."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3 or len(x) != len(y):
        return None
    try:
        return statistics.correlation(ranks(x), ranks(y))
    except statistics.StatisticsError:  # 한쪽이 상수
        return None


def paired_bootstrap_diff(a: list[float], b: list[float], c: list[float], b_n: int = BOOTSTRAP_B,
                          seed: int = SEED) -> tuple[float, float, float] | None:
    """ρ(a,c) − ρ(b,c) 의 점추정과 95% 구간(거점 단위 복원추출). 계산 못 하면 None."""
    n = len(a)
    base_a, base_b = spearman(a, c), spearman(b, c)
    if n < 3 or base_a is None or base_b is None:
        return None
    rng = random.Random(seed)
    diffs = []
    for _ in range(b_n):
        idx = [rng.randrange(n) for _ in range(n)]
        ra, rb = spearman([a[i] for i in idx], [c[i] for i in idx]), spearman([b[i] for i in idx], [c[i] for i in idx])
        if ra is not None and rb is not None:
            diffs.append(ra - rb)
    if len(diffs) < b_n // 2:
        return None
    diffs.sort()
    return base_a - base_b, diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs)) - 1]


# ── 패널 → 증가분 ───────────────────────────────────────────────────────────

def _num(v) -> float | None:
    try:
        return float(v) if v not in ("", None) else None
    except (TypeError, ValueError):
        return None


def clean_rows(rows: list[dict]) -> list[dict]:
    """오류 행·total 없는 행을 뺀다. 날짜는 date 로."""
    out = []
    for r in rows:
        total = _num(r.get("total"))
        if r.get("error") or total is None:
            continue
        out.append({"date": dt.date.fromisoformat(r["collected_at"]), "slug": r["slug"], "suffix": r["suffix"],
                    "total": total, "rate": _num(r.get("rate_per_day")), "precision": _num(r.get("precision"))})
    return out


def intervals(rows: list[dict]) -> dict[tuple[dt.date, dt.date], dict[tuple[str, str], float]]:
    """연속한 스냅샷 날짜 쌍 → {(거점, 질의): Δtotal ÷ Δ일}. 두 날짜 모두에 값이 있는 키만."""
    dates = sorted({r["date"] for r in rows})
    by = {(r["date"], r["slug"], r["suffix"]): r["total"] for r in rows}
    keys = {(r["slug"], r["suffix"]) for r in rows}
    out = {}
    for d0, d1 in zip(dates, dates[1:]):
        days = (d1 - d0).days
        if days < 1:
            continue
        out[(d0, d1)] = {k: (by[(d1, *k)] - by[(d0, *k)]) / days for k in keys if (d0, *k) in by and (d1, *k) in by}
    return out


def negative_share(iv: dict) -> dict:
    vals = [v for per in iv.values() for v in per.values()]
    return {"n": len(vals), "negative": sum(1 for v in vals if v < 0), "zero": sum(1 for v in vals if v == 0),
            "share_negative": round(sum(1 for v in vals if v < 0) / len(vals), 4) if vals else None}


def rank_persistence(iv: dict) -> dict:
    """연속 두 구간에서 (거점·질의) 별 증가율 순위의 Spearman — 양쪽 구간 모두 증가율 > 0 인 키만."""
    ks = sorted(iv)
    rhos = []
    for i1, i2 in zip(ks, ks[1:]):
        common = [k for k in iv[i1] if k in iv[i2] and iv[i1][k] > 0 and iv[i2][k] > 0]
        r = spearman([iv[i1][k] for k in common], [iv[i2][k] for k in common])
        if r is not None:
            rhos.append(round(r, 3))
    return {"pairs": rhos, "median": round(statistics.median(rhos), 3) if rhos else None}


def _gmean(xs: list[float]) -> float | None:
    xs = [x for x in xs if x and x > 0]
    return math.exp(statistics.mean(math.log(x) for x in xs)) if xs else None


def hub_vectors(rows: list[dict], iv: dict) -> dict[str, dict]:
    """거점별 {flow: 전체 기간 증가분의 기하평균, rate: rate_per_day 의 기하평균, precision_ok: 최신 스냅샷 두 질의 정밀도 ≥ 0.5}."""
    by_hub_flow = defaultdict(list)
    for per in iv.values():
        for (slug, _s), v in per.items():
            by_hub_flow[slug].append(v)
    by_hub_rate = defaultdict(list)
    for r in rows:
        if r["rate"]:
            by_hub_rate[r["slug"]].append(r["rate"])
    latest = max((r["date"] for r in rows), default=None)
    prec = defaultdict(list)
    for r in rows:
        if r["date"] == latest:
            prec[r["slug"]].append(r["precision"])
    return {s: {"flow": _gmean(by_hub_flow.get(s, [])), "rate": _gmean(by_hub_rate.get(s, [])),
                "precision_ok": len(p) >= 2 and all(x is not None and x >= PRECISION_MIN for x in p)}
            for s, p in prec.items()}


def datalab_levels(long_path: Path, last_months: int = 12) -> dict[str, float]:
    """`--datalab-long` 결과 → {거점: 최근 12개월 mean(ratio ÷ 기준어 ratio)}. 기준어가 0 인 달은 뺀다."""
    d = json.loads(long_path.read_text(encoding="utf-8"))
    out = {}
    for b in d["batches"]:
        anchor = {p["period"]: p["ratio"] for p in b["anchor"]}
        for slug, series in b["series"].items():
            v = [p["ratio"] / anchor[p["period"]] for p in series[-last_months:] if anchor.get(p["period"])]
            if v and statistics.mean(v) > 0:
                out[slug] = statistics.mean(v)
    return out


def _compare(vec: dict, level: dict, subset: list[str]) -> dict:
    hubs = [s for s in subset if vec[s]["flow"] and vec[s]["rate"] and s in level]
    flow, rate, dl = [vec[s]["flow"] for s in hubs], [vec[s]["rate"] for s in hubs], [level[s] for s in hubs]
    res = {"hubs": len(hubs), "rho_flow_datalab": None, "rho_rate_datalab": None, "diff": None, "ci95": None}
    if len(hubs) < 3:
        return res
    res["rho_flow_datalab"] = round(spearman(flow, dl) or 0, 3)
    res["rho_rate_datalab"] = round(spearman(rate, dl) or 0, 3)
    bs = paired_bootstrap_diff(flow, rate, dl)
    if bs:
        res["diff"], res["ci95"] = round(bs[0], 3), [round(bs[1], 3), round(bs[2], 3)]
    return res


def analyze(panel_rows: list[dict], datalab: dict[str, float]) -> dict:
    rows = clean_rows(panel_rows)
    dates = sorted({r["date"] for r in rows})
    iv = intervals(rows)
    out = {"dates": [d.isoformat() for d in dates], "n_snapshots": len(dates), "n_intervals": len(iv),
           "preregistered": {"min_snapshots": MIN_SNAPSHOTS, "G1_max_negative_share": G1_MAX_NEGATIVE_SHARE,
                             "G2_min_rank_persistence": G2_MIN_RANK_PERSISTENCE, "precision_min": PRECISION_MIN,
                             "min_primary_hubs": MIN_PRIMARY_HUBS, "bootstrap": {"B": BOOTSTRAP_B, "seed": SEED},
                             "baseline_rho_rate_vs_datalab": {"all_81": 0.365, "precision_filtered_45": 0.403}},
           "G1_negative": negative_share(iv) if iv else None, "G2_rank_persistence": rank_persistence(iv) if len(iv) >= 2 else None}
    if len(dates) < MIN_SNAPSHOTS:
        out["verdict"] = "표본부족"
        out["reason"] = f"스냅샷 {len(dates)}개 < {MIN_SNAPSHOTS}개 — 증가분 {MIN_SNAPSHOTS - 1}구간(약 3~4주)이 쌓이면 판정한다"
        return out
    g1 = out["G1_negative"]["share_negative"]
    g2 = out["G2_rank_persistence"]["median"] if out["G2_rank_persistence"] else None
    vec = hub_vectors(rows, iv)
    primary = sorted(s for s, v in vec.items() if v["precision_ok"])
    out["secondary_all_hubs"] = _compare(vec, datalab, sorted(vec))
    out["primary_precision_filtered"] = _compare(vec, datalab, primary)
    if g1 is None or g1 >= G1_MAX_NEGATIVE_SHARE or g2 is None or g2 < G2_MIN_RANK_PERSISTENCE:
        out["verdict"] = "열위"
        out["reason"] = f"게이트 실패 — G1 음수 비율 {g1} (<{G1_MAX_NEGATIVE_SHARE}) · G2 순위 지속 {g2} (≥{G2_MIN_RANK_PERSISTENCE}). 증가분은 유입량으로 안정적이지 않다"
        return out
    p = out["primary_precision_filtered"]
    if p["hubs"] < MIN_PRIMARY_HUBS or not p["ci95"]:
        out["verdict"] = "표본부족"
        out["reason"] = f"1차 대상 {p['hubs']}거점 < {MIN_PRIMARY_HUBS} 또는 구간 계산 불가"
        return out
    lo, hi = p["ci95"]
    out["verdict"] = "개선" if lo > 0 else ("열위" if hi < 0 else "구분불가")
    out["reason"] = f"Δρ {p['diff']} · 95% 구간 [{lo}, {hi}] (거점 {p['hubs']})"
    return out


def run(panel_path: Path = panel.PANEL_PATH, long_path: Path | None = None, out_path: Path | None = None) -> dict:
    from data.collectors.common import BRONZE

    if long_path is None:
        files = sorted((BRONZE / "platform13").glob("*/naver_datalab_hub_trend_long.json"))
        long_path = files[-1] if files else None
    level = datalab_levels(long_path) if long_path else {}
    res = analyze(panel.read_panel(panel_path), level)
    res["computed_at"] = dt.date.today().isoformat()
    res["datalab_source"] = str(long_path.name if long_path else None)
    if out_path is None:
        out_path = Path(__file__).resolve().parents[2] / "reports" / "digital_exposure_total_delta.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r.get(k) for k in ("n_snapshots", "verdict", "reason")}, ensure_ascii=False))
