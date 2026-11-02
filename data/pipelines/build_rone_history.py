"""[Posting] 거점별 R-ONE 분기 시계열 — gold/platform_rone_history.json.

bronze `platform13` 최신 판의 소규모 임대료(천원/㎡ · 사실상 1층 기준)와 중대형·소규모 공실률을 거점별로 편다.
거점 ↔ 표본 규칙은 수집기가 쓴 `data/config/rone_districts` 그대로다 — `SHARED_RONE` 거점은 인접 표본을 빌려 쓴 값이라
`source: rone-shared` 와 `shared_from` 으로 밝힌다. 같은 분기가 통계표 둘에 걸치면(표본개편 경계) 최신 통계표를 쓴다
(`build_posting_inputs._rent_only` 와 같다). **없는 값은 null 이다 — 폴백값(10.0 등)으로 채우지 않는다.**

실행: python -m data.pipelines.build_rone_history
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from data.collectors.common import GOLD, load_latest
from data.config.page_hubs import ACTIVE_HUBS
from data.config.rone_districts import DISTRICT_RONE, SHARED_RONE
from data.pipelines.build_posting_inputs import SLUG13

OUT = "platform_rone_history.json"
SERIES = {"rent_per_m2": "rone_rent_small.json", "vacancy_mid_pct": "rone_vac_mid.json",
          "vacancy_small_pct": "rone_vac_small.json"}
FIRST_QUARTER = "20211"


def series_by_hub(rows: list[dict]) -> dict[str, dict[str, float]]:
    """행 목록 → {거점: {분기: 값}}. 분기 안에서는 통계표 id 가 가장 큰 행이 이긴다."""
    picked: dict[tuple[str, str], tuple[str, float]] = {}
    for r in rows:
        d, q, v = r.get("district_id"), str(r.get("quarter")), r.get("value")
        if d is None or v is None or q < FIRST_QUARTER:
            continue
        key, cand = (d, q), (str(r.get("statbl_id")), float(v))
        if key not in picked or cand[0] > picked[key][0]:
            picked[key] = cand
    out: dict[str, dict[str, float]] = {}
    for (d, q), (_, v) in picked.items():
        out.setdefault(d, {})[q] = round(v, 2)
    return out


def build_doc(raw: dict[str, list[dict]], floor_factor: dict) -> dict:
    by_series = {k: series_by_hub(rows) for k, rows in raw.items()}
    quarters = sorted({q for s in by_series.values() for per in s.values() for q in per})
    hubs: dict[str, dict] = {}
    for slug in ACTIVE_HUBS:
        cls = DISTRICT_RONE.get(slug)
        entry: dict = {"rone_cls": cls, "source": "rone-shared" if slug in SHARED_RONE else "rone"}
        if slug in SHARED_RONE:
            entry["shared_from"] = cls
        for key, per_hub in by_series.items():
            per = per_hub.get(slug)
            entry[key] = [per.get(q) for q in quarters] if per else None
        hubs[slug] = entry
    return {
        "quarters": quarters, "rent_unit": "천원/㎡·월 (R-ONE 소규모상가, 사실상 1층 기준)", "vacancy_unit": "%",
        "floor_factor": floor_factor,
        "source": "한국부동산원 R-ONE 상업용부동산 임대동향",
        "note": ("표본 상권의 통계이고 거점 실측이 아니다. 2024Q3 표본개편 전후로 값이 뛸 수 있다. rone-shared 는 인접 표본을 "
                 "빌린 값이다. 층 계수는 실측이 아니라 계수다. null 은 표본에 값이 없다는 뜻이다."),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "hubs": hubs,
    }


def run(log=print) -> dict:
    raw = {k: load_latest(SLUG13, name) or [] for k, name in SERIES.items()}
    posting = json.loads((GOLD / "platform_posting_inputs.json").read_text(encoding="utf-8"))
    doc = build_doc(raw, posting["floor_factor"])
    path = GOLD / OUT
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    no_rent = [s for s, h in doc["hubs"].items() if not h["rent_per_m2"]]
    log(f"[rone-history] {len(doc['hubs'])}거점 · {len(doc['quarters'])}분기 {doc['quarters'][0]}~{doc['quarters'][-1]} · "
        f"임대 없음 {no_rent} · {path.stat().st_size / 1e6:.2f}MB")
    return {"quarters": doc["quarters"], "no_rent": no_rent}


if __name__ == "__main__":
    run()
