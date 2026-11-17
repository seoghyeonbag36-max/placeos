"""서울 지하철역 마스터(역명·호선·위경도) 수집 — 입지 프리미엄의 「역까지 거리」 재료.

서울 열린데이터광장 `subwayStationMaster`(OA-15442 계열) — 노선별 역 행 784개(수도권 포함), 좌표는 문자열 위·경도.
한 번에 끝난다(1~2콜). 거점·필지까지의 거리 계산은 이 파일의 몫이 아니다(파이프라인에서).

    python -m data.collectors.seoul_subway_stations

Bronze: data/bronze/platform13/<날짜>/seoul_subway_station_master.json (원문 행 그대로)
⚠ 같은 역이 호선마다 행이 따로다(환승역 중복). 역 단위가 필요하면 (BLDN_NM) 으로 묶는다.
"""
from __future__ import annotations

import os

from data.collectors import seoul_trdar as st
from data.collectors.common import load_env, save_json

SERVICE = "subwayStationMaster"
_PAGE = 1000


def collect() -> list[dict]:
    load_env()
    key = os.environ.get("SEOUL_OPENAPI_KEY")
    if not key:
        print("[subway] SEOUL_OPENAPI_KEY 없음 — 수집하지 않는다")
        return []
    rows: list[dict] = []
    start = 1
    while True:
        page, total = st._fetch_page(key, SERVICE, start, start + _PAGE - 1)
        rows += page
        start += _PAGE
        if not page or start > total:
            break
    bad = [r for r in rows if not (r.get("LAT") and r.get("LOT"))]
    print(f"[subway] {len(rows)}행 · 좌표 없는 행 {len(bad)}")
    if rows:
        save_json(rows, "platform13", "seoul_subway_station_master.json")
    return rows


if __name__ == "__main__":
    collect()
