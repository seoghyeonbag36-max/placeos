"""층 단위 공실 라벨 채점 — `make_roadview_sample --floors` 표본의 가중 추정 (2026-10-11).

`data/validation/floor_sample_<tag>/` 의 `labels.csv`(라벨러가 채운 것) · `key.csv`(계층·가중치) ·
`design.json`(계층 크기)을 읽어 표본 설계(design.json `inference`)가 정한 대로 잰다.

  화면 빈 층 정밀도  계층 vacant_confirmed·vacant_probable 안에서 라벨이 공실인 비율
                     엄격 = 공실만 · 관대 = 공실 + 부분공실 — 둘 다 보고한다
  층 공실률          모든 계층의 라벨을 N_h 로 가중한 공실 비율(엄격·관대)
  재현율(놓친 공실)  공실로 라벨된 층 중 화면 빈 층 목록에 든 비율(가중)

규칙
  · 가중치는 계층 안 **응답 수**로 다시 잡는다: w_h = N_h / m_h (m_h = 그 계층에서 `불명`·빈칸을 뺀 수).
    `불명` 은 채점에서 빠진다 — 그 층들이 무작위로 빠졌다는 가정이다(가정이 깨지면 편향).
  · 구간은 **지번(pnu) 단위 군집 부트스트랩**(계층 안에서 지번을 복원 추출)이다 — 같은 지번의
    여러 층은 서로 닮아 독립 표본보다 정보가 적다.
  · 응답이 없는 계층이 있으면 그 계층은 추정에서 빠지고 결과에 `missing_strata` 로 남는다 —
    빈 계층을 0 으로 채우지 않는다.
  · `label_method` 별(현장·로드뷰 …) 응답 수와 엄격 정밀도를 따로 낸다. 거리뷰는 촬영 시점이
    오래됐을 수 있어 현장 라벨과 섞어 읽지 않는다.

판정 — KPI① 「빈 층 판정 실력」(사전등록 2026-10-19 · 라벨 0/458 인 상태에서 고정)
  창업자 앱의 첫 약속(「계약하기 전에 어느 건물 몇 층이 비었는지」)을 재는 축이다. 정밀도가 높다는
  사실만으로는 정보가 없다 — 빈 층이 흔한 틀이면 아무 층이나 골라도 정밀도가 높다(KPI 규칙 1).
  그래서 **정밀도 − 무정보 기준**의 95% 구간으로 판정한다.
    무정보 기준  두 규칙 중 **강한 쪽**: ① 틀의 모든 층을 빈 층이라 내민다 → 층 공실률
                 ② 층 띠 하나(1층 또는 2층↑)의 모든 층을 내민다 → 그 띠의 층 공실률.
                 층 번호만 보는 규칙이라 공실 판정 모델의 정보를 쓰지 않는다(LSTM 09-30 개정과 같은 원칙).
    게이트       엄격 정밀도 실력(`precision_lift_strict`) — 구간 하한 > 0 이면 실력 · 0 을 품으면
                 구분불가 · 상한 < 0 이면 열위 · 라벨없음·표본부족이면 검정불가.
    관측(판정 없음)  관대 정밀도 실력 · 재현율 − 목록 비율(같은 크기의 무작위 목록이 잡는 몫) · 방법별 응답.
  70%·95% 같은 절대선은 게이트로 쓰지 않는다. 라벨을 본 뒤 기준을 바꾸려면 새 사전등록이 필요하다
  → docs/finding-kpi-identity-alignment-2026-10-19.md §4

실행:
  python -m data.validation.score_floor_labels --tag 20261011
  python -m data.validation.score_floor_labels --tag 20261011 --json reports/floor_labels_20261011.json
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_OUT = Path(__file__).resolve().parent
LISTED = ("vacant_confirmed", "vacant_probable")     # 화면의 빈 층 목록
VALID = ("공실", "부분공실", "영업")                    # 채점 대상 라벨 — 불명·빈칸은 미응답
_MIN_PER_STRATUM = 10                                  # 이보다 적으면 그 계층 추정은 표본부족
KPI_SAMPLE_TAG = "20261011"                            # 사전등록한 표본 — 458층 · 8계층(2026-10-11 추출)
# 판정 이름은 KPI① 의 다른 축과 같다(apps/backend/app/services/forecast_skill.py).
SKILL, UNRESOLVED, WORSE, UNTESTABLE = "실력", "구분불가", "열위", "검정불가"


def _read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


def load(sample_dir: Path) -> tuple[list[dict], dict]:
    """labels.csv × key.csv 조인 → 채점 행(라벨 있는 것만)과 design."""
    labels = {r["id"]: r for r in _read_csv(sample_dir / "labels.csv")}
    keys = _read_csv(sample_dir / "key.csv")
    design = json.loads((sample_dir / "design.json").read_text(encoding="utf-8"))
    rows = []
    for k in keys:
        lab = labels.get(k["id"]) or {}
        actual = (lab.get("label_actual") or "").strip()
        rows.append({"id": k["id"], "pnu": k["pnu"], "stratum": k["stratum"], "cls": k["cls"],
                     "band": k["band"], "actual": actual,
                     "method": (lab.get("label_method") or "").strip() or "미기재",
                     "use": (lab.get("label_use") or "").strip()})
    return rows, design


def _estimate(rows: list[dict], strata_N: dict[str, int]) -> dict:
    """응답 행(라벨 VALID)과 계층 크기 → 가중 추정치. 계층별 응답 수로 가중치를 다시 잡는다."""
    by_h: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_h[r["stratum"]].append(r)
    tot = {"strict": 0.0, "broad": 0.0, "N": 0.0}
    listed = {"strict": 0.0, "broad": 0.0, "N": 0.0}
    by_band: dict[str, dict[str, float]] = defaultdict(lambda: {"strict": 0.0, "broad": 0.0, "N": 0.0})
    for h, rs in by_h.items():
        n_pop = strata_N.get(h, 0)
        if not rs or not n_pop:
            continue
        m = len(rs)
        strict = sum(r["actual"] == "공실" for r in rs) / m
        broad = sum(r["actual"] in ("공실", "부분공실") for r in rs) / m
        tot["strict"] += n_pop * strict
        tot["broad"] += n_pop * broad
        tot["N"] += n_pop
        band = by_band[h.split("|")[1] if "|" in h else h]
        band["strict"] += n_pop * strict
        band["broad"] += n_pop * broad
        band["N"] += n_pop
        if h.split("|")[0] in LISTED:
            listed["strict"] += n_pop * strict
            listed["broad"] += n_pop * broad
            listed["N"] += n_pop

    def ratio(a: float, b: float) -> float | None:
        return round(a / b, 4) if b else None

    def raw(a: float, b: float) -> float | None:
        return a / b if b else None

    def strongest(kind: str) -> float | None:
        """무정보 기준 — 「틀 전체」·「층 띠 하나」의 모든 층을 빈 층이라 내미는 규칙 중 정밀도가 높은 쪽."""
        cands = [raw(tot[kind], tot["N"])] + [raw(b[kind], b["N"]) for b in by_band.values()]
        cands = [c for c in cands if c is not None]
        return max(cands) if cands else None

    def lift(a: float | None, b: float | None) -> float | None:
        return round(a - b, 4) if a is not None and b is not None else None

    share = raw(listed["N"], tot["N"])        # 같은 크기 무작위 목록의 기대 재현율
    base_s, base_b = strongest("strict"), strongest("broad")
    return {
        "baseline_strict": round(base_s, 4) if base_s is not None else None,
        "baseline_broad": round(base_b, 4) if base_b is not None else None,
        "precision_lift_strict": lift(raw(listed["strict"], listed["N"]), base_s),
        "precision_lift_broad": lift(raw(listed["broad"], listed["N"]), base_b),
        "recall_lift_strict": lift(raw(listed["strict"], tot["strict"]), share),
        "recall_lift_broad": lift(raw(listed["broad"], tot["broad"]), share),
        "precision_strict": ratio(listed["strict"], listed["N"]),
        "precision_broad": ratio(listed["broad"], listed["N"]),
        "floor_vacancy_strict": ratio(tot["strict"], tot["N"]),
        "floor_vacancy_broad": ratio(tot["broad"], tot["N"]),
        "recall_strict": ratio(listed["strict"], tot["strict"]),
        "recall_broad": ratio(listed["broad"], tot["broad"]),
        "listed_share_of_frame": ratio(listed["N"], tot["N"]),
    }


def _bootstrap(rows: list[dict], strata_N: dict[str, int], reps: int, seed: int) -> dict:
    """계층 안에서 지번을 복원 추출하는 군집 부트스트랩 — 지표별 95% 백분위 구간."""
    rng = random.Random(seed)
    clusters: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        clusters[r["stratum"]][r["pnu"]].append(r)
    draws: dict[str, list[float]] = defaultdict(list)
    for _ in range(reps):
        sample: list[dict] = []
        for h, by_pnu in clusters.items():
            keys = list(by_pnu)
            for _k in keys:
                sample.extend(by_pnu[rng.choice(keys)])
        for name, v in _estimate(sample, strata_N).items():
            if v is not None:
                draws[name].append(v)
    out = {}
    for name, vs in draws.items():
        vs.sort()
        lo, hi = vs[int(0.025 * (len(vs) - 1))], vs[int(0.975 * (len(vs) - 1))]
        out[name] = [round(lo, 4), round(hi, 4)]
    return out


def judge(res: dict) -> dict:
    """사전등록(2026-10-19) 게이트 — 엄격 정밀도 실력(정밀도 − 강한 무정보 기준)의 군집 부트스트랩 95% 구간."""
    if res["verdict"] != "추정가능":
        why = ("라벨이 아직 없다" if res["verdict"] == "라벨없음"
               else f"응답 없는 계층 {len(res['missing_strata'])} · 응답 {_MIN_PER_STRATUM} 미만 계층 "
                    f"{len(res['thin_strata'])}")
        return {"verdict": UNTESTABLE, "basis": "precision_lift_strict",
                "reason": f"표본 {res['verdict']} — 응답 {res['answered']}/{res['drawn']} · {why}"}
    point = res["estimates"].get("precision_lift_strict")
    ci = res["ci95_cluster_bootstrap"].get("precision_lift_strict")
    if point is None or not ci:
        return {"verdict": UNTESTABLE, "basis": "precision_lift_strict",
                "reason": "화면 빈 층 계층에 응답이 없어 정밀도 실력을 못 낸다"}
    lo, hi = ci
    verdict = SKILL if lo > 0 else WORSE if hi < 0 else UNRESOLVED
    return {"verdict": verdict, "basis": "precision_lift_strict",
            "lift_pp": round(point * 100, 1), "ci95_pp": [round(lo * 100, 1), round(hi * 100, 1)],
            "precision_strict": res["estimates"].get("precision_strict"),
            "baseline_strict": res["estimates"].get("baseline_strict"),
            "reason": "엄격 정밀도 − 강한 무정보 기준(틀 전체·층 띠 하나의 층 공실률 중 높은 쪽)"}


def score(sample_dir: Path, reps: int = 1000, seed: int = 20261011) -> dict:
    rows, design = load(sample_dir)
    strata_N = {h: int(s.get("N") or 0) for h, s in design.get("strata", {}).items()}
    answered = [r for r in rows if r["actual"] in VALID]
    per_stratum = {}
    for h in strata_N:
        drawn = [r for r in rows if r["stratum"] == h]
        got = [r for r in answered if r["stratum"] == h]
        per_stratum[h] = {"N": strata_N[h], "drawn": len(drawn), "answered": len(got),
                          "unknown": sum(r["actual"] == "불명" for r in drawn),
                          "strict": (round(sum(r["actual"] == "공실" for r in got) / len(got), 4)
                                     if got else None)}
    missing = [h for h, s in per_stratum.items() if s["N"] and not s["answered"]]
    thin = [h for h, s in per_stratum.items() if s["N"] and 0 < s["answered"] < _MIN_PER_STRATUM]
    by_method: dict[str, dict] = {}
    for meth in sorted({r["method"] for r in answered}):
        rs = [r for r in answered if r["method"] == meth]
        listed = [r for r in rs if r["cls"] in LISTED]
        by_method[meth] = {"answered": len(rs), "listed_answered": len(listed),
                           "listed_strict_raw": (round(sum(r["actual"] == "공실" for r in listed)
                                                       / len(listed), 4) if listed else None)}
    point = _estimate(answered, strata_N) if answered else {}
    verdict = ("라벨없음" if not answered else
               "표본부족" if missing or thin else "추정가능")
    res = {
        "sample": sample_dir.name, "verdict": verdict,
        "drawn": len(rows), "answered": len(answered),
        "unknown": sum(r["actual"] == "불명" for r in rows),
        "blank": sum(not r["actual"] for r in rows),
        "estimates": point,
        "ci95_cluster_bootstrap": _bootstrap(answered, strata_N, reps, seed) if answered else {},
        "per_stratum": per_stratum, "missing_strata": missing, "thin_strata": thin,
        "by_method": by_method,
        "note": ("엄격=공실만, 관대=공실+부분공실. 가중치는 계층 응답 수로 다시 잡았다(w=N_h/m_h). "
                 "구간은 지번 단위 군집 부트스트랩. 표본부족이면 해당 계층의 응답을 더 받기 전에 "
                 "수치를 인용하지 않는다."),
    }
    res["gate"] = judge(res)
    return res


def _print(res: dict) -> None:
    print(f"[floor-score] {res['sample']} · 판정 {res['verdict']} · 응답 {res['answered']}/{res['drawn']}"
          f" (불명 {res['unknown']} · 빈칸 {res['blank']})")
    g = res["gate"]
    detail = (f"실력 {g['lift_pp']:+.1f}%p [{g['ci95_pp'][0]:+.1f}, {g['ci95_pp'][1]:+.1f}]"
              if "lift_pp" in g else g["reason"])
    print(f"  KPI① 빈 층 판정 실력(사전등록 2026-10-19) → {g['verdict']} — {detail}")
    ci = res["ci95_cluster_bootstrap"]
    for k, v in res["estimates"].items():
        print(f"  {k:24s} {v}  95% {ci.get(k)}")
    for h, s in res["per_stratum"].items():
        print(f"  {h:24s} N={s['N']:6d} 뽑음 {s['drawn']:4d} 응답 {s['answered']:4d} 엄격 {s['strict']}")
    if res["missing_strata"] or res["thin_strata"]:
        print(f"  ⚠ 응답 없는 계층 {res['missing_strata']} · 응답 {_MIN_PER_STRATUM} 미만 {res['thin_strata']}")
    for m, s in res["by_method"].items():
        print(f"  방법 {m}: 응답 {s['answered']} · 빈 층 목록 응답 {s['listed_answered']} "
              f"· 엄격 정밀도(가중 전) {s['listed_strict_raw']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="층 단위 공실 라벨 채점")
    ap.add_argument("--tag", required=True, help="floor_sample_<tag> 의 tag")
    ap.add_argument("--json", help="결과 JSON 저장 경로")
    ap.add_argument("--reps", type=int, default=1000)
    args = ap.parse_args()
    d = _OUT / f"floor_sample_{args.tag}"
    if not (d / "labels.csv").exists():
        raise SystemExit(f"[floor-score] 표본이 없다: {d} — make_roadview_sample --floors --tag {args.tag}")
    res = score(d, reps=args.reps)
    _print(res)
    if args.json:
        Path(args.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
