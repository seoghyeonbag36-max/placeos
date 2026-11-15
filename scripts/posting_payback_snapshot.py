"""[Posting] 변경 전·후 스냅샷 — 추천 전략의 회수기간 분포 (2026-11-15).

## 왜 스크립트로 남기나

투자비를 손 계수에서 공정위 정보공개서 실측으로 바꾸면(2026-11-15 결정 ① · P1) 「한 달 안에 본전이에요」가 줄어야 한다.
줄었는지는 **바꾸기 전에 같은 방법으로 한 번 재 둔 값**이 있어야 말할 수 있다(KPI 규칙 1 — 기준선 없이 좋아졌다고 쓰지 않는다).
10-28 의 「296/891」은 손으로 센 값이라 같은 방법으로 다시 셀 수 없었다 — 그래서 서빙 코드를 **실호출**하는 스크립트로 남긴다.
(`posting_cost_sensitivity.py` 의 `_shipped` 와 같은 원칙: 재현하지 말고 부른다. 그러면 프로덕션과 어긋날 수 없다.)

실행: python scripts/posting_payback_snapshot.py [--label before-P1] [--out reports/posting_payback_snapshot_<날짜>.json]

## 무엇을 세나

- **서빙 거점**(`districts.PAGES`)의 공실 유닛마다 `tier_scenarios(unit, 거점)` 를 부른다 — 권리금 0 전제(화면 기본값).
- **추천 전략** = 서빙 코드가 `recommended` 로 표시한 tier(회수 최단). 추천이 없는 유닛(세 tier 모두 자료 부족·회수 불가)은 따로 센다.
- 흐름 R5 머리 문장(`flow/screens/Cost.tsx` · `flow/format.ts` 의 `months`)이 어느 말을 하게 되는지의 분포.
  구간은 `months()` 와 같아야 한다(< 1 → 「한 달 안에」 · 반올림 개월 < 12 → 「약 n개월」 · 그 위 → 「약 n년…」).
  이 구간 맞춤은 복제라서 낡을 수 있다 — 권위 있는 값은 숫자 구간(`roi_bins`)이다.

## 읽는 법

- 이 값은 **지금 서빙 중인 계산**의 분포이지 정답이 아니다(투자비가 손 계수인 채다). 바꾼 뒤 같은 스크립트를 다시 돌려 나란히 본다.
- 목표치는 미리 정하지 않는다(KPI 규칙 1). 「1개월 미만이 0 이 돼야 한다」 같은 선을 여기서 만들지 않는다.
- `provenance` 가 코드·입력 파일의 해시를 싣는다 — 전·후 값이 다른 이유가 투자비 교체인지 입력 갱신인지 가르려는 것이다.
- 이 스크립트는 JSON 을 쓸 뿐 서빙 데이터를 바꾸지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics as st
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "apps" / "backend"))

# 구간 경계(개월). 마지막 구간은 열려 있다.
BIN_EDGES = (1, 3, 6, 12, 24)
BIN_LABELS = ("<1", "1-3", "3-6", "6-12", "12-24", ">=24")


def roi_bin(months: float) -> str:
    for edge, label in zip(BIN_EDGES, BIN_LABELS):
        if months < edge:
            return label
    return BIN_LABELS[-1]


def headline_kind(months: float) -> str:
    """흐름 R5 머리 문장의 말 종류 — `flow/format.ts` 의 `months()` 와 같은 구간(복제)."""
    if months < 1:
        return "한 달 안에"
    total = round(months)
    return "약 n개월" if total < 12 else "약 n년 이상"


def summarize_unit(scenarios: dict) -> dict:
    """한 유닛의 tier 시나리오 → 집계에 필요한 값만. 표시용 반올림 값(`roi_months`)을 쓴다 — 화면이 말하는 값과 같아야 한다."""
    avail = {t: s for t, s in scenarios.items() if s.get("available", True)}
    viable = {t: s for t, s in avail.items() if s.get("viable")}
    rec = next((t for t, s in scenarios.items() if s.get("recommended")), None)
    return {
        "available": sorted(avail),
        "viable": sorted(viable),
        "rec": rec,
        "rec_roi": scenarios[rec]["roi_months"] if rec else None,
        "viable_roi": {t: s["roi_months"] for t, s in viable.items()},
    }


def aggregate(rows: list[dict]) -> dict:
    """rows = [{'city': str, 'hub': str, **summarize_unit()}] → 분포 요약."""
    n = len(rows)
    any_tier = [r for r in rows if r["available"]]          # 자료가 있는 tier 가 하나라도 있는 유닛
    rec_rows = [r for r in rows if r["rec"] is not None]
    rec_roi = [r["rec_roi"] for r in rec_rows]
    pair_roi = [v for r in rows for v in r["viable_roi"].values()]
    tier_avail = Counter(t for r in rows for t in r["available"])
    rec_by_tier = Counter(r["rec"] for r in rec_rows)
    by_city: dict[str, dict] = {}
    for r in rows:
        c = by_city.setdefault(r["city"], {"units": 0, "rec_units": 0, "rec_lt1": 0, "no_tier_units": 0})
        c["units"] += 1
        if r["rec"] is None:
            c["no_tier_units"] += 1
        else:
            c["rec_units"] += 1
            c["rec_lt1"] += r["rec_roi"] < 1
    bins = Counter(roi_bin(m) for m in rec_roi)
    kinds = Counter(headline_kind(m) for m in rec_roi)

    def pct(a: int, b: int) -> float | None:
        return round(a / b * 100, 1) if b else None

    lt1 = bins.get("<1", 0)
    pair_lt1 = sum(1 for m in pair_roi if m < 1)
    return {
        "units": n,
        "units_with_any_tier": len(any_tier),
        "units_with_recommendation": len(rec_rows),
        "units_without_recommendation": n - len(rec_rows),
        # 10-28 finding 의 「추천 전략의 회수가 1개월 미만인 유닛 N 중 M」 — 분모는 「자료가 있는 tier 가 하나라도 있는 유닛」
        # (그 날의 891). 추천이 있는 유닛만의 분모(of_recommended)는 따로 싣는다.
        "recommended_lt1_month": {
            "count": lt1,
            "of_units_with_any_tier": len(any_tier), "pct_of_units_with_any_tier": pct(lt1, len(any_tier)),
            "of_recommended": len(rec_rows), "pct_of_recommended": pct(lt1, len(rec_rows)),
        },
        "recommended_roi_median": round(st.median(rec_roi), 1) if rec_roi else None,
        "roi_bins": {label: bins.get(label, 0) for label in BIN_LABELS},
        "headline_kinds": {k: kinds.get(k, 0) for k in ("한 달 안에", "약 n개월", "약 n년 이상")},
        # 회수되는 tier × 유닛 쌍(10-28 finding 의 「2,122 중 14.3% · 중앙 3.2개월」과 같은 정의)
        "viable_pairs": {
            "count": len(pair_roi), "lt1": pair_lt1, "lt1_pct": pct(pair_lt1, len(pair_roi)),
            "roi_median": round(st.median(pair_roi), 1) if pair_roi else None,
        },
        "tier_available_units": {t: tier_avail.get(t, 0) for t in ("premium", "value", "factory")},
        "recommended_by_tier": {t: rec_by_tier.get(t, 0) for t in ("premium", "value", "factory")},
        "by_city": dict(sorted(by_city.items())),
    }


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else None


def _git_head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_ROOT, capture_output=True,
                              text=True, timeout=20).stdout.strip() or None
    except Exception:
        return None


def collect() -> tuple[list[dict], dict]:
    """서빙 거점의 유닛 전수 → (rows, 진단). 계산이 죽는 유닛은 조용히 빼지 않고 센다."""
    from app.services import districts as D

    rows: list[dict] = []
    hubs_with_units = 0
    errors: list[str] = []
    for d in D.PAGES:
        did = d["id"]
        units = D.resolved_units(did)
        if not units:
            continue
        hubs_with_units += 1
        city = D.page_city(d).short
        for u in units:
            try:
                rows.append({"city": city, "hub": did, **summarize_unit(D.tier_scenarios(u, did))})
            except Exception as e:  # noqa: BLE001 — 어떤 유닛이 왜 죽는지 남긴다(빼먹고 합계만 내지 않는다)
                errors.append(f"{did}: {type(e).__name__}")
    return rows, {"pages": len(D.PAGES), "hubs_with_units": hubs_with_units, "unit_errors": len(errors),
                  "unit_error_samples": sorted(set(errors))[:5]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--label", default="snapshot", help="전·후를 가르는 이름 (예: before-P1 · after-P1)")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows, diag = collect()
    gold = _ROOT / "data" / "gold"
    report = {
        "label": a.label, "date": a.date,
        "what": "서빙 중인 tier_scenarios 를 실호출한 추천 전략 회수기간 분포 — 권리금 0 전제 · 투자비는 손 계수(변경 전)",
        "provenance": {
            "git_head": _git_head(),
            "districts_py": _sha(_ROOT / "apps/backend/app/services/districts.py"),
            "posting_revenue_py": _sha(_ROOT / "apps/backend/app/services/posting_revenue.py"),
            "gold_posting_inputs": _sha(gold / "platform_posting_inputs.json"),
            "gold_posting_revenue": _sha(gold / "platform_posting_revenue.json"),
            "gold_posting_cost_rates": _sha(gold / "platform_posting_cost_rates.json"),
            "gold_posting_store_area": _sha(gold / "platform_posting_store_area.json"),
        },
        "diagnostics": diag,
        "summary": aggregate(rows),
        "reference_1028": {
            "recommended_lt1_month": "296/891 (33%)", "viable_pairs_lt1": "14.3% of 2,122 · 중앙 3.2개월",
            "reproduced": "분자 296 · 회수되는 tier×유닛 2,122 · 14.3% · 중앙 3.2개월은 정확히 같다(2026-11-15 실측)",
            "not_reproduced": "분모 891 — 이 스냅샷에서 만들 수 있는 분모는 tier 자료 있는 유닛(units_with_any_tier)·추천 있는 유닛"
                              "(of_recommended)이고 둘 다 891 이 아니다. 10-28 에 891 이 무엇을 센 값인지 확인되지 않았다 — "
                              "비율은 이 스냅샷의 분모로만 비교한다(전·후는 같은 스크립트라 일관된다)",
        },
    }
    out = Path(a.out) if a.out else _ROOT / "reports" / f"posting_payback_snapshot_{a.date}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    s = report["summary"]
    r = s["recommended_lt1_month"]
    print(f"[{a.label}] PAGES 거점 {diag['hubs_with_units']}곳(유닛이 있는 곳) · 유닛 {s['units']} · tier 자료 있음 {s['units_with_any_tier']}"
          f" · 추천 있음 {s['units_with_recommendation']} · 계산 오류 {diag['unit_errors']}")
    print(f"  추천 전략 회수 1개월 미만: {r['count']}/{r['of_units_with_any_tier']} ({r['pct_of_units_with_any_tier']}%) [10-28 정의]"
          f" · 추천 있는 유닛 대비 {r['pct_of_recommended']}% · 추천 회수 중앙 {s['recommended_roi_median']}개월")
    print(f"  구간: {s['roi_bins']}")
    print(f"  R5 머리 문장: {s['headline_kinds']}")
    print(f"  회수되는 tier×유닛 {s['viable_pairs']['count']} 중 1개월 미만 {s['viable_pairs']['lt1_pct']}% · 중앙 {s['viable_pairs']['roi_median']}개월")
    print(f"  → {out}")
    return 1 if diag["unit_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
