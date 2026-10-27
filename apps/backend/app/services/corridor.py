"""상권 흐름(파주-고양-서울) 서빙 — `gold/platform_corridor.json` 직접 로드 + 거점 값 합침.

## 무엇을 합치나

산출물은 이동 집계만 갖는다(data/pipelines/build_corridor). 서빙은 마디의 거점에 다른 화면과
**같은 값**을 붙인다 — 같은 값을 두 엔드포인트가 따로 만들면 어긋날 자리만 늘어난다.

- 임대료 = `business_fit` 과 같은 R-ONE 1층 평당 월임대료(`posting_inputs`) · 공유 표본이면 표시
- 입지 적합도·순위 = 업종을 골라 물으면 `business_fit.fit_by_district` 의 값 그대로
- 공실률은 **싣지 않는다** — 화면이 `/commercial-districts` 응답에서 합친다(business_fit 과 같은 이유:
  거점 요약은 상권마다 격자를 다시 계산해 무겁다)

산출물이 없으면 None — 라우터가 404 로 물러나고 화면은 「흐름 데이터 없음」을 밝힌다.
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

from app.services import business_fit, districts as districts_svc, posting_inputs

_GOLD = Path(__file__).resolve().parents[4] / "data" / "gold"
_JSON = _GOLD / "platform_corridor.json"
_TTL_SECONDS = 300.0
_cache: dict[str, object] = {}


def _load() -> dict | None:
    now = time.monotonic()
    if _cache.get("data") is not None and now - float(_cache.get("at", 0.0)) < _TTL_SECONDS:
        return _cache["data"]  # type: ignore[return-value]
    if not _JSON.exists():
        return None
    _cache["data"] = json.loads(_JSON.read_text(encoding="utf-8"))
    _cache["at"] = now
    return _cache["data"]  # type: ignore[return-value]


def is_available() -> bool:
    return _load() is not None


def list_corridors() -> list[dict]:
    data = _load() or {}
    return [{"id": c["id"], "name": c["name"], "segments": c["segments"], "period": c["period"]}
            for c in (data.get("corridors") or {}).values()]


def _hub(slug: str, fits: dict[str, dict]) -> dict:
    page = districts_svc.PAGES_BY_ID.get(slug) or {}
    row = posting_inputs.for_district(slug) or {}
    per_m2 = row.get("rent_per_m2_krw_thousand")
    fit = fits.get(slug) or {}
    return {
        "id": slug,
        "name": page.get("name") or slug,
        # business_fit._rent_1f 와 같은 환산(천원/㎡ → 만원/평)
        "rent_1f_per_pyeong": round(per_m2 * 3.3058 / 10, 1) if per_m2 else None,
        "rent_shared": posting_inputs.is_shared_rone(slug),
        "fit": fit.get("fit"),
        "fit_rank": fit.get("fit_rank"),
        # 순위는 잣대마다 따로다(서울 · 고양·파주) — 화면이 「서울 3위」처럼 묶음과 함께 읽는다
        "rank_group_name": fit.get("rank_group_name"),
        "rank_n": fit.get("rank_n"),
    }


def get(corridor_id: str, industry: str | None = None) -> dict | None:
    data = _load() or {}
    doc = (data.get("corridors") or {}).get(corridor_id)
    if doc is None:
        return None
    doc = copy.deepcopy(doc)
    fits: dict[str, dict] = {}
    if industry:
        res = business_fit.fit_by_district(industry) or {}
        fits = {r["district_id"]: r for r in res.get("districts") or []}
        doc["industry"] = res.get("industry")
        doc["rank_groups"] = res.get("rank_groups")
    served = set(districts_svc.PAGES_BY_ID)
    for nd in doc.get("nodes") or []:
        # 서빙 목록에 없는 거점(보류·미빌드)은 마디에서 뺀다 — 화면이 누를 수 없는 거점을 내지 않는다
        nd["hubs"] = [_hub(s, fits) for s in nd.get("hubs") or [] if s in served]
    doc["hub_nodes"] = {s: n for s, n in (doc.get("hub_nodes") or {}).items() if s in served}
    return doc
