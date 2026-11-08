"""일반건축물 전용면적 추정 — 층 바닥면적 × 상업층 전용률 (2026-11-08 사용자 결정).

일반건축물은 건축물대장에 전용면적이 없다(층별개요의 층 바닥면적뿐 — 계단·화장실·복도 포함).
근거 비율은 `data/gold/platform_exclusive_ratio.json`(`data/pipelines/build_exclusive_ratio.py`) — 같은 대장의
집합건물 상업층에서 잰 `Σ 전유면적 ÷ 층 바닥면적` 의 지번 분포다.

## 이 값이 아닌 것

- 실측이 아니다. 집합건물 상업층 비율을 일반건축물에 빌려 쓰는 **추정**이다 — 응답에 `basis` 를 늘 같이 싣고, 화면은 「추정」.
- 범위(`low`~`high`)는 근거 지번들 가운데 절반(p25~p75)이다. 이 층이 그 안에 있다는 보증은 아니다.
- Gold 가 없거나 표본이 없으면 `None` — 비율을 지어내지 않는다.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).resolve().parents[4] / "data" / "gold" / "platform_exclusive_ratio.json"


@lru_cache(maxsize=1)
def ratio() -> dict | None:
    """근거 비율 문서. 파일이 없거나 표본이 없으면 None."""
    try:
        doc = json.loads(_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not doc.get("n_lots") or doc.get("median") is None:
        return None
    return doc


def basis_text(doc: dict) -> str:
    hubs = len(doc.get("hubs") or {})
    return (f"집합건물 상업층 {doc['n_lots']}개 지번({hubs}개 거점)의 대장 전유면적 ÷ 층 바닥면적 중앙값 "
            f"{doc['median'] * 100:.1f}% · 가운데 절반 {doc['p25'] * 100:.0f}~{doc['p75'] * 100:.0f}% — 일반건축물 실측 아님")


def estimate(floor_area_m2: float | None) -> dict | None:
    """층 바닥면적 → 전용면적 추정 {m2, low, high, ratio, basis}. 바닥면적이나 근거가 없으면 None."""
    doc = ratio()
    if doc is None or not floor_area_m2 or floor_area_m2 <= 0:
        return None
    return {
        "m2": round(floor_area_m2 * doc["median"], 1),
        "low": round(floor_area_m2 * doc["p25"], 1),
        "high": round(floor_area_m2 * doc["p75"], 1),
        "ratio": doc["median"],
        "basis": basis_text(doc),
    }
