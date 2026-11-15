"""[Platform] 순위 스냅샷 동결 — 서빙 중인 `fit` · `same_share` 를 그대로 남긴다 (2026-11-15).

## 왜 남기나

「상권 순위가 개업 뒤 24개월 생존을 따르는가」(사전등록 docs/prereg-platform-rank-survival-2026-11-15.md)의 **게이트는 전방 검증**이다.
순위는 현재 점포 스냅샷으로 만든 점수라, 과거 코호트와 대조하면 생존자 편향(누수)이 낀다(사전등록 §8-1). 누수를 피하는 길은
**오늘의 순위를 얼려 두고, 오늘 이후 개업한 업소의 생존으로 잰다** 뿐이다 — 가장 이른 시점은 2028-11. 그때 모델이 재학습돼 순위가
바뀌어 있어도 **오늘의 순위를 오늘의 결과로** 잴 수 있게 이 파일을 남긴다.

실행: python scripts/freeze_ranking_snapshot.py [--out reports/ranking_snapshot_<날짜>.json]

## 무엇이 들었나

순위 모델이 있는 업종(`model_label` 이 있는 것)마다 `business_fit.fit_by_district` 의 거점별 줄:
`fit` · `fit_rank` · `rank_group`(잣대 × 시도) · `same_n` · `sample_n` · `same_share` · `fit_model`.
`provenance` 는 코드·모델 산출물·거점별 컨텍스트 CSV(= `same_share` 의 입력) 해시다.

이 스크립트는 JSON 만 쓰고 서빙 데이터를 바꾸지 않는다. **생존·폐업 같은 결과 값은 이 파일에 없다** — 순위만 얼린다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "apps" / "backend"))


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else None


def _git_head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_ROOT, capture_output=True,
                              text=True, timeout=20).stdout.strip() or None
    except Exception:
        return None


def row_of(r: dict) -> dict:
    """fit_by_district 의 거점 줄 → 스냅샷에 남길 필드만."""
    keep = ("district_id", "name", "gu", "fit", "fit_rank", "rank_group", "rank_n", "fit_model", "same_n", "sample_n", "same_share")
    return {k: r.get(k) for k in keep}


def snapshot(industries: list[dict], fit_by_district) -> dict:
    """industries = business_fit.INDUSTRIES · fit_by_district = business_fit.fit_by_district — 순수 변환(테스트가 가짜를 넣는다)."""
    out: dict[str, dict] = {}
    for item in industries:
        if not item.get("model_label"):
            continue                                              # 순위 모델이 없는 업종은 순위가 없다
        res = fit_by_district(item["key"])
        if res is None:
            continue
        out[item["key"]] = {
            "label": item["label"], "model_covered": bool(res.get("model_covered")),
            "fit_model": res.get("fit_model"),
            "rank_groups": [{k: g.get(k) for k in ("key", "fit_model", "name", "ranked_n", "mean_fit")}
                            for g in res.get("rank_groups", [])],
            "districts": [row_of(r) for r in res.get("districts", [])],
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    from app.services import business_fit as B

    gold = _ROOT / "data" / "gold"
    contexts = sorted(gold.glob("*/program_content_context.csv"))
    ctx_digest = hashlib.sha256("".join(f"{p.parent.name}:{_sha(p)}" for p in contexts).encode()).hexdigest()[:16]
    snap = snapshot(B.INDUSTRIES, B.fit_by_district)
    report = {
        "frozen_on": a.date,
        "what": "서빙 중인 상권 순위 점수 동결 — 결과(생존·폐업) 값은 없다. 전방 검증(2028-11 이후)이 이 파일을 쓴다.",
        "prereg": "docs/prereg-platform-rank-survival-2026-11-15.md",
        "provenance": {
            "git_head": _git_head(),
            "business_fit_py": _sha(_ROOT / "apps/backend/app/services/business_fit.py"),
            "industry_recommend_json": _sha(gold / "platform_industry_recommend.json"),
            "context_csv_files": len(contexts), "context_csv_digest": ctx_digest,
        },
        "industries": snap,
    }
    out = Path(a.out) if a.out else _ROOT / "reports" / f"ranking_snapshot_{a.date}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n = {k: (v["model_covered"], sum(r["fit"] is not None for r in v["districts"]), len(v["districts"])) for k, v in snap.items()}
    print(f"[ranking-snapshot] {a.date} · 업종 {len(snap)} · (모델 커버, fit 있는 거점, 전체 거점) {n}")
    print(f"  → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
