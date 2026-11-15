"""지원 공고 매칭 정밀도 채점 — `support_sample` 표본의 짝 단위 정밀도 차 (사전등록 2026-11-15).

`data/validation/support_sample_<tag>/` 의 `labels.csv`(라벨러가 채운 것) · `key.csv`(팔·짝 · 라벨러에게 숨긴다) ·
`design.json` 을 읽는다. 사전등록: docs/prereg-program-support-precision-2026-11-15.md — **라벨이 0 인 상태에서 고정**했다.

  정밀도   `맞을 수 있음` ÷ (`맞을 수 있음` + `맞지 않음`) — 두 팔(M 매칭이 보여 준 공고 · C 걸러진 공고) 각각
           `판단 불가`·빈칸은 채점에서 빠진다(비율은 보고).
  게이트   짝 단위 정밀도 차 lift = P_M − P_C. **두 줄 모두 유효 라벨인 짝만** 쓴다.
           구간은 짝을 복원 추출하는 부트스트랩(1,000회 · seed 20261115)의 95% 백분위수 구간.
             유효한 짝 < 20 이거나 라벨 없음 → 검정불가
             구간 하한 > 0 → 실력 · 0 을 품음 → 구분불가 · 상한 < 0 → 열위
  관측     팔별 절대 정밀도 · 판단 불가 비율 · 단계별 · 원천별(M). 판정이 아니다.

70%·95% 같은 절대선은 게이트가 아니다(KPI 규칙 1). 라벨을 본 뒤 기준을 바꾸려면 새 사전등록이 필요하다.
판정 이름은 KPI① 의 다른 축과 같다(apps/backend/app/services/forecast_skill.py).

실행:
  python -m data.validation.score_support_labels                 # 사전등록 표본(KPI_SAMPLE_TAG)
  python -m data.validation.score_support_labels --tag 20261115 --json reports/support_labels_20261115.json
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
KPI_SAMPLE_TAG = "20261115"                      # 사전등록한 표본 이름 — 동결일이 달라도 이 이름으로 둔다
OK, NO, UNKNOWN = "맞을 수 있음", "맞지 않음", "판단 불가"
VALID = (OK, NO)                                 # 채점 대상 라벨
MIN_PAIRS = 20                                   # 유효한 짝이 이보다 적으면 검정불가
REPS, SEED = 1000, 20261115
SKILL, UNRESOLVED, WORSE, UNTESTABLE = "실력", "구분불가", "열위", "검정불가"


def _read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


def load(sample_dir: Path) -> tuple[list[dict], dict]:
    """labels.csv × key.csv 조인 → 행(라벨이 비어도 포함)과 design."""
    labels = {r["id"]: r for r in _read_csv(sample_dir / "labels.csv")}
    rows = []
    for k in _read_csv(sample_dir / "key.csv"):
        lab = (labels.get(k["id"]) or {}).get("라벨", "")
        rows.append({"id": k["id"], "pair": k["pair_id"], "arm": k["arm"], "stage": k["stage"],
                     "source": k["source"], "label": (lab or "").strip()})
    design = json.loads((sample_dir / "design.json").read_text(encoding="utf-8"))
    return rows, design


def _pairs(rows: list[dict]) -> dict[str, dict[str, dict]]:
    by: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        by[r["pair"]][r["arm"]] = r
    return by


def _precision(rows: list[dict]) -> dict:
    valid = [r for r in rows if r["label"] in VALID]
    ok = sum(r["label"] == OK for r in valid)
    return {"rows": len(rows), "valid": len(valid), "ok": ok,
            "unknown": sum(r["label"] == UNKNOWN for r in rows),
            "precision": round(ok / len(valid), 4) if valid else None}


def _bootstrap(diffs: list[int], reps: int, seed: int) -> list[float] | None:
    if not diffs:
        return None
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps))
    return [round(means[int(0.025 * reps)], 4), round(means[min(reps - 1, int(0.975 * reps))], 4)]


def judge(res: dict) -> dict:
    """게이트 판정 — 사전등록 규칙 그대로. 결과를 보고 고치지 않는다."""
    n = res["pairs"]["both_valid"]
    if not res["answered"]:
        return {"verdict": UNTESTABLE, "reason": "라벨 없음 — 라벨은 사람 몫이다(labels.csv · GUIDE.md)"}
    if n < MIN_PAIRS:
        return {"verdict": UNTESTABLE, "reason": f"유효한 짝 {n} < {MIN_PAIRS} — 사전등록 최소"}
    lo, hi = res["ci95"]
    lift = res["lift"]
    detail = {"lift_pp": round(lift * 100, 1), "ci95_pp": [round(lo * 100, 1), round(hi * 100, 1)], "n_pairs": n}
    if lo > 0:
        return {"verdict": SKILL, **detail}
    if hi < 0:
        return {"verdict": WORSE, **detail}
    return {"verdict": UNRESOLVED, **detail}


def score(sample_dir: Path, reps: int = REPS, seed: int = SEED) -> dict:
    rows, design = load(sample_dir)
    answered = [r for r in rows if r["label"] in VALID]
    by_pair = _pairs(rows)
    both = [p for p in by_pair.values()
            if "M" in p and "C" in p and p["M"]["label"] in VALID and p["C"]["label"] in VALID]
    diffs = [int(p["M"]["label"] == OK) - int(p["C"]["label"] == OK) for p in both]
    arm = {a: _precision([r for r in rows if r["arm"] == a]) for a in ("M", "C")}
    res = {
        "sample": sample_dir.name, "drawn": len(rows), "answered": len(answered),
        "unknown": sum(r["label"] == UNKNOWN for r in rows),
        "blank": sum(not r["label"] for r in rows),
        "pairs": {"total": len(by_pair), "both_valid": len(both)},
        "arms": arm,
        "lift": round(sum(diffs) / len(diffs), 4) if diffs else None,
        "ci95": _bootstrap(diffs, reps, seed),
        "by_stage": {s: {a: _precision([r for r in rows if r["arm"] == a and r["stage"] == s]) for a in ("M", "C")}
                     for s in sorted({r["stage"] for r in rows})},
        "by_source_M": {s: _precision([r for r in rows if r["arm"] == "M" and r["source"] == s])
                        for s in sorted({r["source"] for r in rows if r["arm"] == "M"})},
        "design": {k: design.get(k) for k in ("frozen_at", "n_pairs", "n_dropped", "source_status", "districts")},
        "note": ("정밀도 = 맞을 수 있음 ÷ (맞을 수 있음 + 맞지 않음), 판단 불가·빈칸 제외. 게이트는 두 줄 모두 유효한 짝의 "
                 "정밀도 차(M − C)이고 구간은 짝 부트스트랩이다. C 는 「q 에는 걸러졌지만 다른 질의에는 보인 공고」라 "
                 "걸러내는 규칙의 변별력을 잰다. 업종은 거르는 기준이 아니라 이 지표가 재지 않는다."),
    }
    res["verdict"] = ("라벨없음" if not answered else "표본부족" if len(both) < MIN_PAIRS else "추정가능")
    res["gate"] = judge(res)
    return res


def _print(res: dict) -> None:
    g = res["gate"]
    print(f"[support-score] {res['sample']} · 응답 {res['answered']}/{res['drawn']} "
          f"(판단 불가 {res['unknown']} · 빈칸 {res['blank']}) · 유효한 짝 {res['pairs']['both_valid']}/{res['pairs']['total']}")
    detail = (f"실력 {g['lift_pp']:+.1f}%p [{g['ci95_pp'][0]:+.1f}, {g['ci95_pp'][1]:+.1f}] · n={g['n_pairs']}"
              if "lift_pp" in g else g["reason"])
    print(f"  Program 지원 공고 매칭 정밀도(사전등록 2026-11-15) → {g['verdict']} — {detail}")
    for a, label in (("M", "매칭이 보여 준"), ("C", "걸러진")):
        s = res["arms"][a]
        print(f"  {a} {label} 공고: 정밀도 {s['precision']} (유효 {s['valid']}/{s['rows']} · 판단 불가 {s['unknown']})")


def main() -> None:
    ap = argparse.ArgumentParser(description="지원 공고 매칭 정밀도 채점")
    ap.add_argument("--tag", default=KPI_SAMPLE_TAG, help="support_sample_<tag> 의 tag")
    ap.add_argument("--json", help="결과 JSON 저장 경로")
    ap.add_argument("--reps", type=int, default=REPS)
    args = ap.parse_args()
    d = _OUT / f"support_sample_{args.tag}"
    if not (d / "labels.csv").exists():
        raise SystemExit(f"[support-score] 표본이 없다: {d} — python -m data.validation.support_sample --freeze")
    res = score(d, reps=args.reps)
    _print(res)
    if args.json:
        Path(args.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
