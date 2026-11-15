"""[Platform] 개업 뒤 24개월 생존 — 인허가 정제본 → 거점 × 업종 칸 (사전등록 2026-11-15).

입력:  data/silver/building_history/<거점>/licensing_lots.json  (LocalData 인허가의 지번 단위 정제본 · 서울 서빙 거점)
산출:  data/gold/platform_survival_cohorts.json

**규칙은 docs/prereg-platform-rank-survival-2026-11-15.md 가 정본이다** — 이 파일은 그것을 그대로 코드로 옮긴 것이고,
결과를 본 뒤 고치지 않는다(바꾸려면 새 사전등록). 요지:

  정제   같은 (지번 PNU, 정규화한 상호)의 기록을 개업일 순으로 보고, 폐업일이 있는 업소와 다음 기록의 간격이
         G(=90일, 겹침 포함) 이하면 한 업소로 잇는다. 업소의 폐업일 = 이어 붙인 기록 중 가장 늦은 것(하나라도 열려 있으면 영업 중).
         앞 기록이 열려 있으면 묶지 않는다. 상호가 비면 묶지 않는다. 폐업일 < 개업일인 기록은 무효로 빼고 센다.
  코호트 업소의 개업일이 2016-01-01 이상 2024-07-01 미만. (이어짐은 개업일이 옛날로 잡혀 코호트 밖 — 승계를 신규 개업으로 세지 않는다)
  생존   개업일부터 730일 안에 폐업일이 없다. 영업 중(폐업일 없음)은 생존이다.
  칸     (거점, 업종) — 업종은 사전등록 §4 의 업태 대응표. 모호한 업태는 어느 업종에도 넣지 않고 비중을 보고한다.
         n ≥ 30 인 칸만 비율·구간을 낸다(`eligible`). 그 아래는 n 만 남기고 비율을 만들지 않는다.
  구간   Wilson 95% (코호트가 전원 24개월 추적을 채워 Kaplan–Meier 와 같다).
  민감도 G=30 · G=180 은 같은 칸을 (n, 생존 수)만 따로 남긴다 — 판정은 G=90 만.

⚠ 이 산출물은 **정제된 값**이다. 정제 전 기록을 「생존율」로 내보내지 않는다(결정 문서 §3).
⚠ 생존 ≠ 성공이다. 순위와의 대조는 `data/validation/score_rank_survival.py` — 동시점 대조는 누수가 있어 참고 판정이다.

실행: PLACEOS_SILVER_ROOT=<정제본 루트> python -m data.pipelines.build_platform_survival
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from data.collectors.common import GOLD, SILVER  # noqa: E402
from data.config.page_hubs import ACTIVE_HUBS  # noqa: E402

OUT = GOLD / "platform_survival_cohorts.json"
PREREG = "docs/prereg-platform-rank-survival-2026-11-15.md"

GAP_DAYS = 90                      # 주 분석(사전등록 §2-2)
SENS_GAPS = (30, 180)              # 민감도
COHORT_START = date(2016, 1, 1).toordinal()
COHORT_END = date(2024, 7, 1).toordinal()   # 미만
HORIZON_DAYS = 730
MIN_N = 30

# 사전등록 §4 — 업태(`industry_type`) → business_fit 업종 키. 여기에 없는 업태는 미매핑(어느 업종에도 넣지 않는다).
MAPPING: dict[str, tuple[str, ...]] = {
    "restaurant": ("한식", "분식", "경양식", "일식", "중국식", "외국음식전문점(인도,태국등)", "뷔페식", "식육(숯불구이)",
                   "김밥(도시락)", "횟집", "냉면집", "패밀리레스트랑", "탕류(보신용)", "패스트푸드", "통닭(치킨)"),
    "cafe": ("커피숍", "까페", "제과점영업", "과자점", "아이스크림", "전통찻집", "떡카페", "키즈카페", "라이브카페"),
    "clinic": ("의원", "치과의원", "한의원", "병원"),
    "convenience": ("편의점",),
}
_INDUSTRY_OF = {t: k for k, ts in MAPPING.items() for t in ts}
_YMD = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_NAME_STRIP = re.compile(r"\(주\)|㈜|\(유\)|\(합\)")


def norm_name(s: object) -> str:
    """정규화 = 공백 제거 + (주)·㈜·(유)·(합) 제거."""
    return re.sub(r"\s+", "", _NAME_STRIP.sub("", str(s or "")))


def to_ord(s: object) -> int | None:
    m = _YMD.match(str(s or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).toordinal()
    except ValueError:
        return None


def industry_of(industry_type: object) -> str | None:
    return _INDUSTRY_OF.get(str(industry_type or "").strip())


def merge_spells(records: list[dict], gap: int = GAP_DAYS) -> tuple[list[dict], int]:
    """records = [{pnu, name, start(ord), end(ord|None), it}] → (업소 목록, 무효 기록 수).

    업소 = {pnu, start, end|None, it(첫 기록의 업태)}. 규칙은 사전등록 §2 — 위 모듈 docstring.
    """
    invalid = 0
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    singles: list[dict] = []
    for r in records:
        if r["end"] is not None and r["end"] < r["start"]:
            invalid += 1
            continue
        nm = norm_name(r["name"])
        if not nm:
            singles.append({"pnu": r["pnu"], "start": r["start"], "end": r["end"], "it": r["it"]})   # 상호가 비면 묶지 않는다
        else:
            groups[(r["pnu"], nm)].append(r)
    out = list(singles)
    for (pnu, _nm), lst in groups.items():
        lst.sort(key=lambda x: (x["start"], x["end"] if x["end"] is not None else 10**9))
        cur = {"pnu": pnu, "start": lst[0]["start"], "end": lst[0]["end"], "it": lst[0]["it"]}
        for r in lst[1:]:
            if cur["end"] is not None and r["start"] - cur["end"] <= gap:
                # 이어진 기록 — 끝은 가장 늦은 것, 하나라도 열려 있으면 열린 채(앞 기록 안에 든 짧은 기록은 끝을 당기지 않는다)
                cur["end"] = None if r["end"] is None else max(cur["end"], r["end"])
                continue
            out.append(cur)                      # 앞 기록이 열려 있으면 묶지 않는다
            cur = {"pnu": pnu, "start": r["start"], "end": r["end"], "it": r["it"]}
        out.append(cur)
    return out, invalid


def in_cohort(start: int) -> bool:
    return COHORT_START <= start < COHORT_END


def survived(start: int, end: int | None) -> bool:
    """730일 안에 폐업일이 없다. 영업 중(폐업일 없음)은 생존이다."""
    return end is None or (end - start) > HORIZON_DAYS


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def cell_of(k: int, n: int) -> dict:
    """칸 하나. n < MIN_N 이면 비율·구간을 만들지 않는다(0 으로 채우지 않는다)."""
    if n < MIN_N:
        return {"n": n, "survived": k, "eligible": False, "rate": None, "ci95": None}
    lo, hi = wilson(k, n)
    return {"n": n, "survived": k, "eligible": True, "rate": round(k / n, 4), "ci95": [round(lo, 4), round(hi, 4)]}


def hub_cells(rows: list[dict], gap: int = GAP_DAYS) -> tuple[dict, dict]:
    """한 거점의 silver rows → ({업종: 칸}, 커버리지). rows 는 {pnu, record{start_date,end_date,industry_type,business_name}}."""
    recs, bad_date = [], 0
    for r in rows:
        rec = r["record"]
        s, e = to_ord(rec.get("start_date")), to_ord(rec.get("end_date"))
        if s is None:
            bad_date += 1
            continue
        recs.append({"pnu": r["pnu"], "name": rec.get("business_name"), "start": s, "end": e,
                     "it": (rec.get("industry_type") or "").strip()})
    spells, invalid = merge_spells(recs, gap)
    cohort = [s for s in spells if in_cohort(s["start"])]
    by_ind: dict[str, list[int]] = {k: [0, 0] for k in MAPPING}        # [생존, n]
    unmapped = 0
    for s in cohort:
        ind = industry_of(s["it"])
        if ind is None:
            unmapped += 1
            continue
        by_ind[ind][1] += 1
        by_ind[ind][0] += survived(s["start"], s["end"])
    cov = {"records": len(rows), "bad_date": bad_date, "invalid": invalid, "spells": len(spells),
           "cohort_spells": len(cohort), "cohort_unmapped": unmapped,
           "cohort_mapped": len(cohort) - unmapped}
    return {k: cell_of(v[0], v[1]) for k, v in by_ind.items()}, cov


def seoul_hubs() -> list[str]:
    return sorted(s for s, h in ACTIVE_HUBS.items() if h.city == "seoul")


def build(silver_root: Path = SILVER, out: Path = OUT) -> dict:
    hubs: dict[str, dict] = {}
    sens: dict[str, dict] = {f"gap{g}": {} for g in SENS_GAPS}
    missing: list[str] = []
    total = Counter()
    for slug in seoul_hubs():
        p = silver_root / "building_history" / slug / "licensing_lots.json"
        if not p.exists():
            missing.append(slug)
            continue
        rows = json.loads(p.read_text(encoding="utf-8"))["rows"]
        cells, cov = hub_cells(rows, GAP_DAYS)
        hubs[slug] = {"industries": cells, "coverage": cov}
        total.update({k: v for k, v in cov.items()})
        for g in SENS_GAPS:
            c_g, _ = hub_cells(rows, g)
            sens[f"gap{g}"][slug] = {k: {"n": v["n"], "survived": v["survived"]} for k, v in c_g.items()}
    doc = {
        "schema": "platform-survival/1", "prereg": PREREG,
        "rules": {"gap_days": GAP_DAYS, "sensitivity_gaps": list(SENS_GAPS),
                  "cohort": ["2016-01-01", "2024-07-01"], "horizon_days": HORIZON_DAYS, "min_n": MIN_N,
                  "interval": "wilson95", "mapping": {k: list(v) for k, v in MAPPING.items()}},
        "hubs": hubs, "sensitivity": sens,
        "diagnostics": {"hubs_built": len(hubs), "hubs_missing_silver": missing, "totals": dict(total),
                        "note": "거점 반경이 겹쳐 같은 기록이 여러 거점에 든다 — 합계는 거점 간 중복을 포함한다(사전등록 §1·§8-4)."},
    }
    out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description="Platform 개업 뒤 24개월 생존 — 거점 × 업종 칸")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    doc = build(out=Path(a.out))
    d = doc["diagnostics"]
    elig = Counter()
    for h in doc["hubs"].values():
        for k, c in h["industries"].items():
            elig[k] += c["eligible"]
    print(f"[platform-survival] 거점 {d['hubs_built']} (정제본 없음 {len(d['hubs_missing_silver'])}) · "
          f"n≥{MIN_N} 칸 {dict(elig)} → {a.out}")
    return 1 if d["hubs_missing_silver"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
