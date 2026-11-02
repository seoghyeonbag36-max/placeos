"""건물 단위 공실 GeoJSON 서비스 (Page 공실 레이어) — 서울 핵심 거점 다거점.

건물 footprint 폴리곤 + 추정 공실률을 GeoJSON FeatureCollection 으로 제공한다.
프론트(MapShell)가 naver.maps.Polygon 으로 색칠 렌더한다.

실데이터: data/gold/{slug}/page_building_master.geojson
  (V-World 폴리곤 ⊕ 상가정보 활성점포 ⊕ 건축HUB capacity — build_page_master.py 산출)
  거점 slug 는 data/config/page_hubs.py HUBS 와 동일(= seoul_pages DISTRICTS id).
  garosugil 은 gold 파일이 없을 때 아래 _GAROSU 샘플 8동으로 폴백(PoC 최소 데모 보장).

거점 id 별칭(gangnam-garosugil/sinsa → garosugil)은 page_hubs.ALIASES 와 정합.
백엔드는 data 패키지를 import 하지 않으므로(서버리스 배포 호환) 별칭 맵을 여기 복제한다.
"""
from __future__ import annotations

import json
from pathlib import Path

# repo/data/gold  (services → app → backend → apps → repo)
_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"
_cache: dict[str, dict] = {}   # slug → {"mtime", "fc"}
_enriched: dict[str, tuple[tuple, list[dict]]] = {}   # slug → (재료 mtime 들, 피처)

# 거점 id 별칭 → 정규 slug (data/config/page_hubs.py ALIASES 와 동일하게 유지)
_ALIASES = {"gangnam-garosugil": "garosugil", "sinsa": "garosugil"}

# 가로수길 코어 샘플 건물 (gold 미생성 환경 폴백). status: full/partial/high/empty
_GAROSU = [
    {"id": "b1", "name": "가로수길 A빌딩", "lat": 37.5219, "lng": 127.0222, "status": "empty", "capacity": 12, "active": 1, "industry": "의류"},
    {"id": "b2", "name": "세로수길 B타워", "lat": 37.5211, "lng": 127.0231, "status": "high", "capacity": 10, "active": 4, "industry": "카페"},
    {"id": "b3", "name": "신사 C스퀘어", "lat": 37.5203, "lng": 127.0226, "status": "partial", "capacity": 8, "active": 6, "industry": "화장품"},
    {"id": "b4", "name": "가로수 D플라자", "lat": 37.5198, "lng": 127.0236, "status": "full", "capacity": 6, "active": 6, "industry": "F&B"},
    {"id": "b5", "name": "도산 E빌딩", "lat": 37.5226, "lng": 127.0238, "status": "empty", "capacity": 9, "active": 0, "industry": "편집숍"},
    {"id": "b6", "name": "신사 F빌딩", "lat": 37.5190, "lng": 127.0221, "status": "partial", "capacity": 7, "active": 5, "industry": "뷰티"},
    {"id": "b7", "name": "가로수 G동", "lat": 37.5215, "lng": 127.0245, "status": "high", "capacity": 11, "active": 3, "industry": "패션"},
    {"id": "b8", "name": "신사 H타워", "lat": 37.5207, "lng": 127.0213, "status": "full", "capacity": 5, "active": 5, "industry": "오피스"},
]

# footprint 근사 사각형 반경(도 단위) ≈ 위도 15m / 경도 15m
_D_LAT = 0.00013
_D_LNG = 0.00017


def _resolve(district: str) -> str:
    """거점 id/별칭 → 정규 slug."""
    return _ALIASES.get(district, district)


def _ring(lat: float, lng: float) -> list[list[float]]:
    """[lng, lat] 순서(GeoJSON)의 닫힌 사각 링."""
    return [
        [lng - _D_LNG, lat - _D_LAT],
        [lng + _D_LNG, lat - _D_LAT],
        [lng + _D_LNG, lat + _D_LAT],
        [lng - _D_LNG, lat + _D_LAT],
        [lng - _D_LNG, lat - _D_LAT],
    ]


def _load_gold(slug: str) -> dict | None:
    """거점 gold GeoJSON 로드 — slug별 mtime 캐시 (파이프라인 재실행 시 자동 반영)."""
    path = _GOLD_DIR / slug / "page_building_master.geojson"
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    hit = _cache.get(slug)
    if not hit or hit["mtime"] != mtime:
        hit = {"mtime": mtime, "fc": json.loads(path.read_text(encoding="utf-8"))}
        _cache[slug] = hit
    return hit["fc"]


def load_master(district: str) -> dict | None:
    """거점 gold 마스터 GeoJSON 원본 (별칭 해석 포함, 없으면 None).

    같은 파일을 읽는 다른 서비스(gold_vacancy 의 그리드 집계)가 mtime 캐시를
    공유하도록 공개한다 — 거점당 수백~2천 피처라 중복 로드는 피한다.
    """
    return _load_gold(_resolve(district))


def _garosu_sample(district: str) -> dict:
    """gold 미생성 환경용 가로수길 샘플 8동 FeatureCollection."""
    features = []
    for b in _GAROSU:
        vac = round((1 - b["active"] / b["capacity"]) * 100, 1)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(b["lat"], b["lng"])]},
            "properties": {
                "id": b["id"], "name": b["name"], "status": b["status"],
                "capacity": b["capacity"], "active": b["active"],
                "industry": b["industry"], "vacancy_rate": vac,
            },
        })
    return {"type": "FeatureCollection", "district": district, "features": features}


def _enriched_features(slug: str, gold: dict) -> list[dict]:
    """피처에 `vac_class`(3분류) · `road_addr`(대장 도로명)를 더한다. 화면이 추가 호출 없이 3분류를 쓰려는 값이다.

    마스터 원본을 건드리지 않는다 — `load_master` 를 함께 쓰는 집계가 그 값에 기대지 않게.
    재료 파일이 바뀌면 다시 만든다(mtime). 거점당 수천 피처라 요청마다 만들지 않는다.
    """
    from app.services import building_floors, floor_vacancy, vacancy_class

    path = floor_vacancy.path(slug)
    key = (_cache[slug]["mtime"], path.stat().st_mtime if path.exists() else 0.0, building_floors.mtime(slug))
    hit = _enriched.get(slug)
    if hit and hit[0] == key:
        return hit[1]
    listed = vacancy_class.floors_by_pnu(slug)
    lots = (building_floors.load(slug) or {}).get("lots") or {}
    features = []
    for f in gold.get("features") or []:
        p = f.get("properties") or {}
        pnu = str(p.get("pnu") or building_floors.pnu_of(str(p.get("id") or "")))
        features.append({**f, "properties": {
            **p, "vac_class": vacancy_class.classify(p, listed.get(pnu)),
            "road_addr": (lots.get(pnu) or {}).get("road"),
        }})
    _enriched[slug] = (key, features)
    return features


def building_vacancy_geojson(district: str) -> dict | None:
    """건물 공실 GeoJSON FeatureCollection. 미지원 거점이면 None.

    gold 산출물이 있으면 실데이터, 없고 garosugil 계열이면 샘플 8동으로 폴백.
    """
    slug = _resolve(district)
    gold = _load_gold(slug)
    if gold is not None:
        return {**gold, "features": _enriched_features(slug, gold), "district": district}
    if slug == "garosugil":
        return _garosu_sample(district)
    return None
