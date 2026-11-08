"""[Page] 일반건축물 전용면적 추정 근거 — 상업층 전용률(전유면적 ÷ 층 바닥면적) Gold (2026-11-08).

## 왜

일반건축물(공실 층 대부분)은 건축물대장에 전용면적이 없다 — 층별개요의 **층 바닥면적**(계단·화장실·복도 포함)뿐이다.
사용자가 「일반건축물 전용면적 추정」을 화면에 올리기로 했다(2026-11-08). 추정 비율을 지어내지 않으려면 근거 표본이 필요하다.

## 근거 — 같은 대장, 집합건물 상업층

한 지번에 전유부(호실별 전유면적)와 층별개요(층 바닥면적)가 **둘 다** 있는 집합건물에서, 같은 층의
`Σ 상업 전유면적 ÷ 층 바닥면적` 을 잰다. 층 바닥면적에는 그 층의 계단·화장실·복도가 들어 있으므로, 이 비율이
「층 바닥면적 중 호실(전용)로 쓰이는 몫」이다.

- 입력: `data/gold/{거점}/building_floors.json.gz`(층 행 · 호실 행). 대장 원본은 이미 Gold 로 접혀 있다.
- 짝: 같은 지번 · 같은 층(지상/지하 · 층 번호). **동이 둘 이상인 지번은 뺀다**(층 행의 동과 호실의 동을 못 맞춘다).
- 거르기: 비율 0.3 미만(층 일부만 상업 전유 — 주거 전유가 빠진 층) · 1.0 초과(층·호 기재 불일치)는 뺀다.
- **지번 하나 = 한 표** — 지번마다 층 비율의 중앙값을 낸 뒤 지번들 사이 분포를 쓴다(층이 많은 한 건물이 끌고 가지 않게).
- 불확실성: 지번 군집 부트스트랩(1,000회 · seed 20261108) 중앙값 95% 구간.

## 이 값이 아닌 것

- 일반건축물을 잰 값이 아니다 — 집합건물 상업층에서 잰 비율을 일반건축물 층에 **빌려 쓰는 추정**이다. 화면은 늘 「추정」.
- 표본은 층별개요와 전유부가 둘 다 있는 지번뿐이라 작다(2026-11-08 기준 33지번 · 3거점). 수집 PC 에서 집합건물 지번의
  층별개요를 더 받아 `build_building_floors` → 이 스크립트를 다시 돌리면 표본이 는다.
- 공용면적을 나눠 붙인 계약면적·분양면적 비율이 아니다(그건 전유공용면적의 공용 행 — `build_expos_units.pub_m2`).

실행: python -m data.pipelines.build_exclusive_ratio
"""
from __future__ import annotations

import gzip
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

GOLD = Path(__file__).resolve().parents[1] / "gold"
OUT = GOLD / "platform_exclusive_ratio.json"
R_MIN, R_MAX = 0.3, 1.0
SEED, N_BOOT = 20261108, 1000


def _q(v: list[float], p: float) -> float:
    s = sorted(v)
    return s[int(p * (len(s) - 1))]


def floor_ratios(doc: dict) -> dict[str, list[float]]:
    """한 거점 문서 → {지번: [층별 Σ전유 ÷ 층 바닥면적, ...]} (거르기 전 원값)."""
    ff, uf = doc.get("floor_fields") or [], doc.get("unit_fields") or []
    out: dict[str, list[float]] = {}
    for pnu, lot in (doc.get("lots") or {}).items():
        if not lot.get("units") or not lot.get("floors"):
            continue
        floors = [dict(zip(ff, r)) for r in lot["floors"]]
        if len({f.get("dong") or "" for f in floors}) > 1:
            continue
        plate: dict[tuple, float] = defaultdict(float)
        for f in floors:
            if f.get("kind") in ("G", "B") and isinstance(f.get("no"), int):
                plate[(f["kind"], f["no"])] += float(f.get("area_m2") or 0)
        excl: dict[tuple, float] = defaultdict(float)
        for u in (dict(zip(uf, r)) for r in lot["units"]):
            if u.get("kind") in ("G", "B") and isinstance(u.get("no"), int) and (u.get("area_m2") or 0) > 0:
                excl[(u["kind"], u["no"])] += float(u["area_m2"])
        rs = [a / plate[k] for k, a in excl.items() if plate.get(k, 0) > 0]
        if rs:
            out[pnu] = rs
    return out


def summarise(per_lot: dict[tuple[str, str], list[float]]) -> dict:
    """{(거점, 지번): [층 비율]} → 지번 한 표 분포 요약. 표본이 없으면 n_lots=0 과 None 들."""
    kept = {k: [r for r in v if R_MIN <= r <= R_MAX] for k, v in per_lot.items()}
    kept = {k: v for k, v in kept.items() if v}
    lot_med = [statistics.median(v) for v in kept.values()]
    n_floors = sum(len(v) for v in kept.values())
    if not lot_med:
        return {"n_lots": 0, "n_floors": 0, "median": None, "p25": None, "p75": None, "median_ci95": None, "hubs": {}}
    rnd = random.Random(SEED)
    boot = sorted(statistics.median([rnd.choice(lot_med) for _ in lot_med]) for _ in range(N_BOOT))
    hubs: dict[str, int] = defaultdict(int)
    for hub, _ in kept:
        hubs[hub] += 1
    r4 = lambda x: round(x, 4)  # noqa: E731
    return {
        "n_lots": len(lot_med), "n_floors": n_floors,
        "median": r4(statistics.median(lot_med)), "p25": r4(_q(lot_med, 0.25)), "p75": r4(_q(lot_med, 0.75)),
        "median_ci95": [r4(boot[int(0.025 * N_BOOT)]), r4(boot[int(0.975 * N_BOOT) - 1])],
        "hubs": dict(sorted(hubs.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def run() -> dict:
    per_lot: dict[tuple[str, str], list[float]] = {}
    for p in sorted(GOLD.glob("*/building_floors.json.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            doc = json.load(fh)
        for pnu, rs in floor_ratios(doc).items():
            per_lot[(p.parent.name, pnu)] = rs
    stats = summarise(per_lot)
    doc = {
        "what": "상업층 전용률 — Σ 상업 전유면적 ÷ 층 바닥면적(같은 지번 · 같은 층 · 건축물대장)",
        "use": "일반건축물 층의 전용면적 추정 = 층 바닥면적 × median (범위 p25~p75). 화면은 늘 「추정」으로 표시한다.",
        "source": "data/gold/*/building_floors.json.gz — 전유부(전유 · 상업용도) × 층별개요가 둘 다 있는 집합건물 지번",
        "method": (f"동 하나인 지번만 · 층 비율 {R_MIN}~{R_MAX} 만 · 지번마다 층 비율 중앙값(지번 한 표) · "
                   f"지번 군집 부트스트랩 {N_BOOT}회(seed {SEED}) 중앙값 95% 구간"),
        "caveat": "집합건물 상업층에서 잰 비율을 일반건축물에 빌려 쓰는 추정이다. 일반건축물을 잰 값이 아니다.",
        **stats,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"상업층 전용률: 지번 {stats['n_lots']} · 층 {stats['n_floors']} · 중앙 {stats['median']} "
          f"(가운데 절반 {stats['p25']}~{stats['p75']} · 95% {stats['median_ci95']}) · 거점 {stats['hubs']} → {OUT.name}")
    return doc


if __name__ == "__main__":
    run()
