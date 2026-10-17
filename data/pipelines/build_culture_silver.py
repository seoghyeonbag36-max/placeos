"""전시·공연 시설 Bronze → Silver → Gold(거점 집계).

입력  data/bronze/culture/{수집일}/culturalSpaceInfo.json (+ .manifest.json)
Silver data/silver/culture/facilities.json   시설 단위(유형 분류·좌표 검증·중복 제거·거점 귀속)
Gold   data/gold/culture/hub_facilities.json 거점별 전시·공연 시설 수(존재·밀도 사실, 모델 라벨 아님)

규칙(docs/finding-exhibit-performance-sources-2026-10-16.md §4·§5):
- 업종 분류는 `data.config.culture_facilities.classify` 의 **원문 완전 일치**만 쓴다. 이름으로 추측하지 않는다.
- ⚠ 원천의 `X_COORD` 가 위도, `Y_COORD` 가 경도다. 서울 범위 밖·파싱 불가 좌표는 null 로 두고 사유를 남긴다
  (버리지 않는다 — 시설 자체는 존재한다).
- 시설 고유 ID 가 없어 `facility_key = sha1(norm(이름)|norm(주소))`. 같은 키이면서 좌표가 30m 안(또는 좌표 결측)이면
  같은 시설로 합친다. 같은 주소의 다른 시설(세종문화회관 / 세종문화회관 미술관)은 합치지 않는다.
- 거점 귀속은 stores_radius_m 안 후보 중 **가장 가까운 거점 중심 1곳**. 반경 밖은 hub_slug=null 로 남긴다.
- 연락처·홈페이지는 Silver 에 가져가지 않는다(업소 정보에 개인 번호가 섞일 수 있다).

실행: python -m data.pipelines.build_culture_silver
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

from data.collectors.common import BRONZE, GOLD, SILVER
from data.config.culture_facilities import (
    INDUSTRY_KEY, INDUSTRY_LABEL, SOURCE_SEOUL_CULTURE_SPACE, classify,
)
from data.config.page_hubs import ACTIVE_HUBS

ATTRIBUTION = "서울 열린데이터광장 · 서울시 문화공간 정보 (공공누리 1유형)"
DEDUP_M = 30.0
_LAT, _LON = (37.0, 38.0), (126.0, 128.0)
_NOISE = re.compile(r"[\s\-_·.,()\[\]~/]+")


def norm(text: object) -> str:
    return _NOISE.sub("", str(text or "")).lower()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def parse_coords(row: dict) -> tuple[float, float] | tuple[None, str]:
    """(위도, 경도) 또는 (None, 사유). X_COORD=위도, Y_COORD=경도."""
    try:
        lat, lon = float(row.get("X_COORD")), float(row.get("Y_COORD"))
    except (TypeError, ValueError):
        return None, "coord_unparseable"
    if not (_LAT[0] <= lat <= _LAT[1] and _LON[0] <= lon <= _LON[1]):
        return None, "coord_out_of_range"
    return lat, lon


def facility_key(name: object, address: object) -> str:
    return hashlib.sha1(f"{norm(name)}|{norm(address)}".encode("utf-8")).hexdigest()[:16]


def assign_hub(lat: float, lon: float, hubs=None) -> tuple[str | None, int | None]:
    best: tuple[str, float] | None = None
    for slug, hub in (hubs or ACTIVE_HUBS).items():
        d = haversine_m(lat, lon, hub.cy, hub.cx)
        if d <= hub.stores_radius_m and (best is None or d < best[1]):
            best = (slug, d)
    return (best[0], round(best[1])) if best else (None, None)


def normalize(rows: list[dict], collected_at: str, hubs=None) -> tuple[list[dict], dict]:
    kept: list[dict] = []
    stats: Counter = Counter()
    for index, row in enumerate(rows):
        name = str(row.get("FAC_NAME") or "").strip()
        address = str(row.get("ADDR") or "").strip()
        if not name or not address:
            raise ValueError(f"row={index + 1}: FAC_NAME/ADDR 결손 — 키를 만들 수 없어 승격을 중단한다")
        raw_type = str(row.get("SUBJCODE") or "").strip()
        coords = parse_coords(row)
        lat, lon = (coords if coords[0] is not None else (None, None))
        reason = None if lat is not None else coords[1]
        key = facility_key(name, address)

        dup = next((k for k in kept if k["facility_key"] == key
                    and (lat is None or k["lat"] is None
                         or haversine_m(lat, lon, k["lat"], k["lon"]) <= DEDUP_M)), None)
        if dup is not None:
            dup["dup_count"] += 1
            stats["duplicates_merged"] += 1
            continue

        hub_slug, hub_dist = assign_hub(lat, lon, hubs) if lat is not None else (None, None)
        kept.append({
            "facility_key": key,
            "name": name,
            "address_raw": address,
            "address_norm": norm(address),
            "lat": lat,
            "lon": lon,
            "coord_issue": reason,
            "source": SOURCE_SEOUL_CULTURE_SPACE,
            "source_type_raw": raw_type,
            "industry": classify(SOURCE_SEOUL_CULTURE_SPACE, raw_type),
            "gu": str(row.get("GNGU") or "").strip(),
            "hub_slug": hub_slug,
            "hub_distance_m": hub_dist,
            "dup_count": 1,
            "collected_at": collected_at,
            "source_ref_date": None,
        })
    stats["rows_in"] = len(rows)
    stats["facilities"] = len(kept)
    stats["coord_issue"] = sum(1 for k in kept if k["coord_issue"])
    return kept, dict(stats)


def aggregate_hubs(facilities: list[dict], hubs=None) -> dict:
    counts = Counter(f["hub_slug"] for f in facilities
                     if f["industry"] == INDUSTRY_KEY and f["hub_slug"])
    return {slug: counts.get(slug, 0) for slug in (hubs or ACTIVE_HUBS)}


def latest_run(bronze_root: Path) -> Path:
    days = sorted(p for p in bronze_root.iterdir() if (p / "culturalSpaceInfo.json").exists())
    if not days:
        raise FileNotFoundError(f"{bronze_root} 에 culturalSpaceInfo.json 이 없다")
    return days[-1]


def build(bronze_root: Path = BRONZE / "culture", silver_root: Path = SILVER / "culture",
          gold_root: Path = GOLD / "culture") -> dict:
    run = latest_run(bronze_root)
    rows = json.loads((run / "culturalSpaceInfo.json").read_text(encoding="utf-8"))
    manifest = json.loads((run / "culturalSpaceInfo.manifest.json").read_text(encoding="utf-8"))
    if manifest["rows"] != len(rows) or manifest["list_total_count"] != len(rows):
        raise ValueError("매니페스트 건수와 Bronze 행 수가 다르다 — 승격을 중단한다")

    facilities, stats = normalize(rows, manifest["collected_at"])
    in_industry = [f for f in facilities if f["industry"] == INDUSTRY_KEY]
    per_hub = aggregate_hubs(facilities)

    meta = {
        "source": manifest["service"], "dataset_id": manifest["dataset_id"],
        "attribution": ATTRIBUTION, "collected_at": manifest["collected_at"],
        "bronze_run": run.name, "rows_sha256": manifest["rows_sha256"],
        "industry": INDUSTRY_KEY, "industry_label": INDUSTRY_LABEL,
    }
    silver_root.mkdir(parents=True, exist_ok=True)
    gold_root.mkdir(parents=True, exist_ok=True)
    (silver_root / "facilities.json").write_text(
        json.dumps({"meta": meta, "stats": stats, "facilities": facilities}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    hubs_with = sum(1 for n in per_hub.values() if n)
    report = {
        **stats, "in_industry": len(in_industry),
        "in_industry_with_hub": sum(1 for f in in_industry if f["hub_slug"]),
        "in_industry_no_coord": sum(1 for f in in_industry if f["coord_issue"]),
        "by_source_type_in_industry": dict(Counter(f["source_type_raw"] for f in in_industry)),
        "hubs_total": len(per_hub), "hubs_with_facility": hubs_with,
    }
    (gold_root / "hub_facilities.json").write_text(
        json.dumps({"meta": meta, "report": report, "hubs": per_hub}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return report


def main() -> None:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    print(json.dumps(build(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
