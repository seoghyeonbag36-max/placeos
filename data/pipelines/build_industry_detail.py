"""세부 업종 경쟁점: 기존 Bronze → 정규화 Silver → 집계 Gold.

python -m data.pipelines.build_industry_detail
기존 원천을 읽으며 외부 재수집·기존 Gold 덮어쓰기는 하지 않는다.
수집 반경의 점포 재고이며 행정상권 전수·현재 영업 확인으로 표현하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from data.config.industry_details import DETAILS, classify
from data.config.page_hubs import ACTIVE_HUBS

ROOT = Path(__file__).resolve().parents[1]


def normalize(rows: list[dict]) -> dict:
    """동일 ID 중복 제거. 같은 ID의 업종·위치 충돌과 ID/좌표 결손은 제외한다."""
    by_id: dict[str, dict] = {}
    conflicts: set[str] = set()
    invalid = duplicates = 0
    for raw in rows:
        sid = str(raw.get("bizesId") or "").strip()
        try:
            lat, lon = float(raw["lat"]), float(raw["lon"])
            valid = math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
        except (KeyError, ValueError, TypeError):
            valid = False
        if not sid or not valid:
            invalid += 1
            continue
        row = dict(store_id=sid, source_name=str(raw.get("indsSclsNm") or "").strip(),
                   lat=lat, lon=lon, floor=str(raw.get("flrNo") or ""),
                   building_id=str(raw.get("bldMngNo") or ""))
        if sid in by_id:
            duplicates += 1
            if by_id[sid] != row:
                conflicts.add(sid)
        else:
            by_id[sid] = row
    return {"rows": [r for sid, r in by_id.items() if sid not in conflicts],
            "raw_n": len(rows), "invalid_n": invalid, "duplicate_n": duplicates,
            "conflicting_ids_n": len(conflicts)}


def aggregate(silver: dict) -> dict:
    counts = Counter(classify(r["source_name"]) for r in silver["rows"])
    return {k: v for k, v in silver.items() if k != "rows"} | {
        "sample_n": len(silver["rows"]),
        "classified_n": sum(v for k, v in counts.items() if k),
        "counts": {i["key"]: counts[i["key"]] if i["source_names"] and silver["rows"] else None for i in DETAILS},
        "floor_known_n": sum(bool(r["floor"]) for r in silver["rows"]),
        "building_known_n": sum(bool(r["building_id"]) for r in silver["rows"]),
    }


def build(root: Path = ROOT) -> dict:
    dest = root / "gold" / "industry_detail" / "competition.json"
    if dest.exists():
        raise FileExistsError(f"기존 Gold 보존: {dest}")
    districts: dict[str, dict] = {}
    missing = []
    for slug, hub in ACTIVE_HUBS.items():
        files = sorted((root / "bronze" / slug).glob("*/stores_raw.json"))
        if not files:
            missing.append(slug)
            continue
        path = files[-1]
        content = path.read_bytes()
        rows = json.loads(content)
        if not isinstance(rows, list):
            raise ValueError(f"{slug}: 점포 배열이 아님")
        silver = normalize(rows) | {
            "collected_on": path.parent.name, "source_sha256": hashlib.sha256(content).hexdigest(),
            "source": "소상공인시장진흥공단 상가(상권)정보",
            "radius_m": hub.stores_radius_m, "center": [hub.cy, hub.cx],
        }
        dest = root / "silver" / slug / "industry_detail_stores.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(silver, ensure_ascii=False), encoding="utf-8")
        # 소비할 계층을 명시적으로 다시 읽어 Silver 계약을 검증한다.
        districts[slug] = aggregate(json.loads(dest.read_text(encoding="utf-8")))
    out = {"schema_version": 1, "districts": districts, "missing_districts": missing,
           "note": "거점별 수집 반경 안 원천 점포 재고. 현재 영업 전수·상권 경계 전수가 아니며 거점 간 중복을 합산하지 않는다.",
           "source_url": "https://www.data.go.kr/data/15012005/openapi.do"}
    dest = root / "gold" / "industry_detail" / "competition.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    result = build()
    print(json.dumps({"districts": len(result["districts"]), "missing": result["missing_districts"]}, ensure_ascii=False))
