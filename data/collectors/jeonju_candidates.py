"""전주 R-ONE 5상권 조사 원본 수집. 시설 좌표는 R-ONE 경계가 아니다."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import requests

from data.collectors.common import load_env, load_latest, save_json
from data.collectors.gwangju_candidates import distance_m, fetch_complete_stores
from data.config.page_hubs import PageHub

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = [
    ('jj-east', '전주동부', '전주시청'),
    ('jj-west', '전주서부', '서신동주민센터'),
    ('jj-newtown', '전주서부신시가지', '효자5동주민센터'),
    ('jj-hanok', '전주한옥마을', '전주한옥마을'),
    ('jj-songcheon', '송천동', '송천1동주민센터'),
]


def select_place(items: list[dict], landmark: str) -> dict:
    """시설명과 전주시 주소가 일치하는 시설만 채택한다."""
    def norm(s: str) -> str:
        return s.replace(' ', '').replace('행정복지센터', '주민센터')
    matches = [r for r in items if '전주시' in str(r.get('address', {}))
               and norm(r.get('title', '')) == norm(landmark)]
    if not matches:
        raise ValueError(f'전주 시설 위치 미확정: {landmark}')
    return matches[0]


def validate_stores(stores: list[dict]) -> None:
    """새 응답과 캐시 모두 지역·고유 점포 키를 확인한다."""
    if not stores or any('전주시' not in str(s.get('lnoAdr', '')) for s in stores):
        raise ValueError('전주 점포 누락 또는 타 도시 혼입')
    ids = [s.get('bizesId') for s in stores]
    if not all(ids) or len(set(ids)) != len(ids):
        raise ValueError('점포 키 누락 또는 중복 페이지')


def collect() -> list[dict]:
    load_env()
    report = []
    hubs = {}
    for slug, anchor, landmark in CANDIDATES:
        raw = load_latest(slug, 'vworld_candidate_search.json')
        if raw is None:
            response = requests.get('https://api.vworld.kr/req/search', params={
                'service': 'search', 'request': 'search', 'version': '2.0',
                'type': 'PLACE', 'query': landmark, 'bbox': '126.9,35.7,127.3,36.0',
                'format': 'json', 'crs': 'EPSG:4326', 'size': 50,
                'key': os.environ['VWORLD_API_KEY'],
            }, timeout=30)
            if response.status_code != 200:
                raise RuntimeError(f'V-World HTTP {response.status_code}')
            raw = response.json()
            save_json(raw, slug, 'vworld_candidate_search.json')
        place = select_place(raw.get('response', {}).get('result', {}).get('items', []), landmark)
        cx, cy = float(place['point']['x']), float(place['point']['y'])
        if not (126.9 < cx < 127.3 and 35.7 < cy < 36.0):
            raise ValueError('전주 조사 범위 밖')
        hubs[slug] = PageHub(slug, '전주 ' + anchor, cx, cy, 500, 700, city='jeonju')
        report.append(dict(slug=slug, anchor='전북>' + anchor, selected=place,
                           cx=cx, cy=cy, source='V-World 시설 검색·소상공인 상가정보',
                           note='시설 중심 조사 반경이며 R-ONE 경계가 아님'))
    for row in report:
        hub = hubs[row['slug']]
        nearest = min(distance_m(hub, other) for other in hubs.values() if other.slug != hub.slug)
        radius = min(700, math.floor(nearest / 2))
        hub = PageHub(hub.slug, hub.name, hub.cx, hub.cy, min(500, radius), radius, city='jeonju')
        stores = load_latest(hub.slug, 'stores_raw.json')
        if stores is None:
            stores = fetch_complete_stores(os.environ['DATA_GO_KR_SERVICE_KEY'], hub)
            validate_stores(stores)
            save_json(stores, hub.slug, 'stores_raw.json')
        validate_stores(stores)
        from data.collectors.building_vacancy import group_by_building
        row.update(radius_m=hub.radius_m, stores_radius_m=radius, stores=len(stores),
                   buildings=len(group_by_building(stores)),
                   codes=sorted({str(s.get('signguCd')) for s in stores}),
                   building_code_prefixes=sorted({str(s.get('bldMngNo', ''))[:5] for s in stores}))
        print(json.dumps(row, ensure_ascii=False), flush=True)
    target = ROOT / 'reports' / 'jeonju_candidates.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    collect()
