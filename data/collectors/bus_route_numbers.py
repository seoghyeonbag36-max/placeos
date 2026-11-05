"""서울 교통카드 원본의 버스 번호를 Bronze → Silver → Gold로 보존한다."""
from __future__ import annotations

import json
import os
from pathlib import Path

from data.collectors.common import load_env
from data.collectors.seoul_bus_stops import RIDERSHIP_SERVICE, _pages

ROOT = Path(__file__).resolve().parents[1]


def build() -> None:
    load_env()
    key = os.environ.get("SEOUL_OPENAPI_KEY", "").strip()
    if not key:
        raise RuntimeError("SEOUL_OPENAPI_KEY가 없습니다")
    window = json.loads((ROOT / "gold/page_bus_stops.json").read_text(encoding="utf-8"))["window"]
    day = window["end"].replace("-", "")
    bronze = ROOT / f"bronze/seoul_bus_routes/{day}.json"
    if bronze.exists():
        rows = json.loads(bronze.read_text(encoding="utf-8"))
    else:
        rows = _pages(key, RIDERSHIP_SERVICE, day)
        if not rows:
            raise RuntimeError("버스 번호 원본이 없습니다")
        bronze.parent.mkdir(parents=True, exist_ok=True)
        bronze.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    routes: dict[str, set[str]] = {}
    for row in rows:
        stop, number = str(row.get("STOPS_ID", "")).strip(), str(row.get("RTE_NO", "")).strip()
        if stop and number:
            routes.setdefault(stop, set()).add(number)
    if not routes:
        raise RuntimeError("원본에서 정류소와 버스 번호를 연결하지 못했습니다")
    silver = ROOT / f"silver/seoul_bus_routes/{day}.json"
    silver.parent.mkdir(parents=True, exist_ok=True)
    silver.write_text(json.dumps({k: sorted(v) for k, v in routes.items()}, ensure_ascii=False), encoding="utf-8")
    gold = ROOT / "gold/page_bus_routes.json"
    if gold.exists():
        raise RuntimeError("기존 Gold를 덮어쓰지 않습니다")
    gold.write_text(json.dumps({"source": f"서울열린데이터광장 {RIDERSHIP_SERVICE}",
                                "as_of": window["end"], "routes": json.loads(silver.read_text(encoding="utf-8"))},
                               ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"버스 번호: {len(routes)}개 정류소 · 기준일 {window['end']}")


if __name__ == "__main__":
    build()
