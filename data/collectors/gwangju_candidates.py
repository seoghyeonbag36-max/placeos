"""광주광역시 13개 R-ONE 상권의 후보 위치·점포·폴리곤 원본 수집.

후보 중심은 V-World 공공시설 검색으로 정하며 R-ONE 경계의 실측 중심이라고 주장하지 않는다.
서빙 등록·Gold 빌드·대장 호출은 하지 않는다. 기존 원본은 재사용한다.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import Counter
from pathlib import Path

import requests

from data.collectors.common import load_env, load_latest, save_json
from data.config.page_hubs import PageHub

ROOT = Path(__file__).resolve().parents[2]
# 상권별 공공시설을 후보 조사 중심으로 삼는다. 동일 지명은 구까지 지정한다.
CANDIDATES = [
    ('gj-chungjang', '금남로/충장로', '충장로우체국', '동구'),
    ('gj-geumho', '금호지구', '금호1동행정복지센터', '서구'),
    ('gj-bongseon', '봉선동', '봉선2동행정복지센터', '남구'),
    ('gj-sangmu', '상무지구', '상무역', '서구'),
    ('gj-songjeong', '송정동지구', '광주송정역', '광산구'),
    ('gj-yangsan', '양산지구', '양산동행정복지센터', '북구'),
    ('gj-eoryong', '어룡동', '어룡동행정복지센터', '광산구'),
    ('gj-yongbong', '용봉동', '용봉동행정복지센터', '북구'),
    ('gj-usan', '우산동', '우산동행정복지센터', '광산구'),
    ('gj-wolsan', '월산동지구', '월산동행정복지센터', '남구'),
    ('gj-ilgok', '일곡동', '일곡동행정복지센터', '북구'),
    ('gj-chonnam', '전남대', '전남대학교', '북구'),
    ('gj-cheomdan1', '첨단1지구', '첨단1동행정복지센터', '광산구'),
]


def select_place(items: list[dict], gu: str, landmark: str) -> dict:
    """구·시설명이 일치하는 검색 순위 첫 시설을 조사 중심 후보로 삼는다.

    같은 시설의 복수 POI가 있어도 원본 순서를 유지하며, 중심은 상권 경계가 아니다.
    """
    def normalized(value: str) -> str:
        return value.replace(' ', '').replace('주민센터', '행정복지센터')

    matches = [r for r in items
               if any(city in str(r.get('address', {})) for city in ('광주광역시', '전남광주통합특별시'))
               and gu in str(r.get('address', {}))
               and normalized(r.get('title', '')) in
               (normalized(landmark), '광주' + normalized(landmark), normalized(landmark) + '광주캠퍼스')]
    if not matches:
        raise ValueError(f'후보 위치 불확정: {landmark} ({len(matches)}개 일치)')
    return matches[0]


def locate(slug: str, landmark: str, gu: str) -> dict:
    cached = load_latest(slug, 'vworld_candidate_search.json')
    if cached is not None and cached.get('response', {}).get('status') == 'NOT_FOUND':
        filename = 'vworld_candidate_search_university.json' if slug == 'gj-chonnam' else 'vworld_candidate_search_short.json'
        cached = load_latest(slug, filename)
        query = landmark
    else:
        filename = 'vworld_candidate_search.json'
        query = f'광주광역시 {gu} {landmark}'
    if cached is None:
        response = requests.get('https://api.vworld.kr/req/search', params={
            'service': 'search', 'request': 'search', 'version': '2.0',
            'type': 'PLACE', 'query': query, 'bbox': '126.5,35.0,127.0,35.3',
            'format': 'json', 'crs': 'EPSG:4326', 'size': 50,
            'key': os.environ['VWORLD_API_KEY'],
        }, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f'V-World HTTP {response.status_code}')
        cached = response.json()
        save_json(cached, slug, filename)
    body = cached.get('response', {})
    if body.get('status') != 'OK':
        raise ValueError(f"V-World 상태 {body.get('status')}")
    return select_place(body.get('result', {}).get('items', []), gu, landmark)


def distance_m(a: PageHub, b: PageHub) -> float:
    return math.hypot((a.cx-b.cx)*111320*math.cos(math.radians(a.cy)),
                      (a.cy-b.cy)*111000)


def fetch_complete_stores(key: str, hub: PageHub) -> list[dict]:
    """부분 응답을 완주로 저장하지 않는다. 건축HUB는 호출하지 않는다."""
    from data.collectors.building_vacancy import BASE_SDSC, _get_json

    rows: list[dict] = []
    for page in range(1, 101):
        data = _get_json(f'{BASE_SDSC}/storeListInRadius', {
            'serviceKey': key, 'type': 'json', 'numOfRows': 1000, 'pageNo': page,
            'radius': hub.stores_radius_m, 'cx': hub.cx, 'cy': hub.cy,
        })
        body = (data or {}).get('body', {})
        if 'totalCount' not in body or 'items' not in body:
            raise ValueError('점포 API 정상 응답 아님')
        total = int(body['totalCount'])
        items = body['items'] or []
        rows.extend(items)
        if len(rows) == total:
            return rows
        if not items or len(rows) > total:
            raise ValueError('점포 API 부분 수집')
        time.sleep(0.2)
    raise ValueError('점포 페이지 상한 도달')


def collect_blog(slug: str, anchor: str) -> int | None:
    """검색 원본만 보존한다. 감성·점포 귀속·방문 수요로 해석하지 않는다."""
    cached = load_latest(slug, 'naver_blog_search_raw.json')
    if cached is not None:
        return len(cached.get('items', []))
    if not os.getenv('NAVER_CLIENT_ID') or not os.getenv('NAVER_CLIENT_SECRET'):
        return None
    response = requests.get('https://openapi.naver.com/v1/search/blog.json', params={
        'query': '광주 ' + anchor.replace('/', ' ') + ' 상권', 'display': 100, 'sort': 'date',
    }, headers={'X-Naver-Client-Id': os.environ['NAVER_CLIENT_ID'],
                'X-Naver-Client-Secret': os.environ['NAVER_CLIENT_SECRET']}, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f'네이버 HTTP {response.status_code}')
    data = response.json()
    if 'items' not in data or 'total' not in data:
        raise ValueError('네이버 검색 정상 응답 아님')
    save_json(data, slug, 'naver_blog_search_raw.json')
    return len(data['items'])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--locate-only', action='store_true')
    parser.add_argument('--blogs', action='store_true')
    args = parser.parse_args()
    load_env()
    required = ['VWORLD_API_KEY'] + ([] if args.locate_only else ['DATA_GO_KR_SERVICE_KEY'])
    if any(not os.getenv(k) for k in required):
        raise SystemExit('필수 키 미설정: ' + ', '.join(k for k in required if not os.getenv(k)))
    report: list[dict] = []
    hubs: dict[str, PageHub] = {}
    for slug, anchor, landmark, gu in CANDIDATES:
        row = {'slug': slug, 'anchor': '광주>' + anchor, 'landmark': landmark,
               'gu': gu, 'status': 'location_pending', 'source': 'V-World 검색·상가정보'}
        report.append(row)
        try:
            place = locate(slug, landmark, gu)
            cx, cy = float(place['point']['x']), float(place['point']['y'])
            if not (126 < cx < 128 and 34 < cy < 36):
                raise ValueError('광주 좌표 범위 밖')
            hubs[slug] = PageHub(slug, anchor, cx, cy, 500, 700, city='gwangju')
            row.update(cx=cx, cy=cy, selected=place, status='located')
        except (ValueError, KeyError, requests.RequestException, RuntimeError) as exc:
            # 요청 URL에는 키가 있으므로 네트워크 예외 문자열을 기록하지 않는다.
            row['error_type'] = type(exc).__name__
        print(slug, row['status'], flush=True)
    for row in report:
        slug = row['slug']
        if slug not in hubs:
            continue
        hub = hubs[slug]
        nearest = min((distance_m(hub, other) for s, other in hubs.items() if s != slug), default=1400)
        radius = min(700, int(nearest / 2))
        hub = PageHub(slug, hub.name, hub.cx, hub.cy, min(500, radius), radius, city='gwangju')
        row.update(radius_m=hub.radius_m, stores_radius_m=radius, nearest_candidate_m=round(nearest))
        if args.locate_only:
            continue
        try:
            from data.collectors.building_vacancy import group_by_building
            stores = load_latest(slug, 'stores_raw.json')
            if stores is None:
                stores = fetch_complete_stores(os.environ['DATA_GO_KR_SERVICE_KEY'], hub)
                if not stores:
                    raise ValueError('점포 수집 결과 없음')
                # 현행 원본은 시도 12·시군구 122xx와 과거 건물관리번호 29xxx가 혼재한다.
                # 시도 코드만으로 경기광주/전남 지역을 혼입하지 않고 구·좌표도 대조한다.
                save_json(stores, slug, 'stores_raw.json')
            # 반경이 시 경계를 넘더라도 원본은 보존하고 혼입 건수를 별도로 밝힌다.
            row['outside_city_rows'] = sum(
                str(s.get('signguNm', '')) not in {'동구', '서구', '남구', '북구', '광산구'}
                or not str(s.get('signguCd', '')).startswith(('29', '122', '123'))
                for s in stores)
            row['administrative_codes'] = sorted({str(s.get('signguCd')) for s in stores})
            row['building_code_prefixes'] = sorted({str(s.get('bldMngNo', ''))[:5] for s in stores})
            buildings = group_by_building(stores)
            concentration = Counter(s.get('lnoCd') for s in stores)
            per = len(stores) / max(1, len(buildings))
            top10 = sum(n for _, n in concentration.most_common(10)) / len(stores) * 100
            row.update(stores=len(stores), buildings=len(buildings), stores_per_building=round(per, 2),
                       top10_parcel_pct=round(top10, 2),
                       verdict='계획상가 밀집' if per > 10 else '주의(대장 확인)' if top10 > 25 else '1차 통과')
            from data.collectors.vworld_bldg import collect_hub
            polygons = load_latest(slug, 'bldg_polygons.geojson')
            count = len(polygons['features']) if polygons else collect_hub(os.environ['VWORLD_API_KEY'], hub)
            row.update(polygons=count, status='stores_and_polygons' if count else 'stores_only')
            if args.blogs:
                row['blog_search_items'] = collect_blog(slug, hub.name)
        except Exception as exc:
            row.update(status='collection_failed', error_type=type(exc).__name__)
        print(slug, row['status'], row.get('stores'), flush=True)
    target = ROOT / 'reports' / 'gwangju_candidates_collection_2026-10-28.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('report:', target.relative_to(ROOT))
    if any(row['status'] not in ({'located'} if args.locate_only else {'stores_and_polygons'}) for row in report):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
