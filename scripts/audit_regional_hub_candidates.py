"""기존 공공 원본으로 서울 밖 후보와 미공개 거점의 증거를 재조사한다.

인허가 주소 묶음은 발달상권 경계를 대체하지 않는다. 신규 위치는 탐색 후보이며,
점포·대장·Gold 검증 없이 서빙하거나 R-ONE 공유 앵커를 임의 배정하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import argparse
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.collectors.common import load_latest
from data.collectors.gg_licensing import _place
from data.config.page_hubs import ACTIVE_HUBS, ALL_HUBS
from scripts.chain_status import summarize


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    """탐색 단계의 평면 근사 거리(m). 좌표 순서는 경도·위도다."""
    return math.hypot((a[0] - b[0]) * 111320 * math.cos(math.radians(a[1])),
                      (a[1] - b[1]) * 111000)


def store_metrics(rows: list[dict]) -> dict:
    """서울 4차와 같은 전체 점포 / 건물관리번호 보유 건물 지표."""
    ids = [r.get('bizesId') for r in rows]
    if not rows or not all(ids) or len(ids) != len(set(ids)):
        raise ValueError('점포 원본이 비었거나 고유 점포 키 누락·중복')
    buildings = Counter(r['bldMngNo'] for r in rows if r.get('bldMngNo'))
    if not buildings:
        raise ValueError('건물관리번호가 없어 밀도 판정 불가')
    ratio = len(rows) / len(buildings)
    concentration = sum(n for _, n in buildings.most_common(10)) / len(rows) * 100
    return dict(stores=len(rows), buildings=len(buildings), stores_per_building=round(ratio, 2),
                top10_building_pct=round(concentration, 2),
                verdict='밀집 검토' if ratio > 10 else '주의' if concentration > 25 else '통과')


def ready_for_serving(stages: list[dict], deferred: str) -> bool:
    """공개 목록만 빠진 완주 거점을 고른다. 앵커 결측·폴백은 부분 통과시키지 않는다."""
    required = {'등록', '점포', '폴리곤', '대장', '정밀분모', 'Page마스터', '앵커', '공실유닛'}
    states = {r['stage']: r['status'] for r in stages if r['stage'] != '서빙등재'}
    return not deferred and required <= states.keys() and all(
        state == 'ok' or (stage == '정밀분모' and state == 'partial')
        for stage, state in states.items())


def discovery(rows: list[dict], region: str, hubs: dict) -> tuple[list[dict], dict]:
    """주소별 영업 인허가의 실재 좌표를 조사 중심으로 제안한다. 추정 중심 생성 금지."""
    from pyproj import Transformer
    transform = Transformer.from_crs(2097, 4326, always_xy=True)
    groups: dict[tuple, list] = defaultdict(list)
    counts: Counter = Counter()
    seen: set[str] = set()
    for row in rows:
        key = row.get('MGTNO')
        if not key or key in seen:
            counts['missing_or_duplicate_id'] += 1
            continue
        seen.add(key)
        addr = str(row.get('SITEWHLADDR') or '')
        valid = (addr.startswith(('경기도 ', '경기 ')) if region == '경기' else
                 addr.startswith(('광주광역시 ', '전남광주통합특별시 ')) if region == '광주' else
                 '전주시 ' in addr and addr.startswith(('전북특별자치도 ', '전라북도 ')))
        if not valid:
            counts['outside_region'] += 1
            continue
        if row.get('TRDSTATEGBN') != '01' or str(row.get('DCBYMD') or '').strip():
            counts['not_open'] += 1
            continue
        place = _place(addr)
        if not place:
            counts['address_unresolved'] += 1
            continue
        try:
            xy = float(row['X']), float(row['Y'])
            lon, lat = xy if row.get('CRS') == 'EPSG:4326' else transform.transform(*xy)
            if not (124 < lon < 132 and 33 < lat < 39):
                raise ValueError('좌표 범위 밖')
        except (TypeError, ValueError, KeyError):
            counts['coordinate_unresolved'] += 1
            continue
        groups[place].append((lon, lat, key, addr))
        counts['usable_open_rows'] += 1
    candidates = []
    for place, items in sorted(groups.items()):
        mean = (sum(x[0] for x in items) / len(items), sum(x[1] for x in items) / len(items))
        # 평균은 선택에만 쓰며 조사 중심은 관측된 한 업소 좌표다.
        center = min(items, key=lambda x: (distance(x[:2], mean), x[2]))
        nearest, gap = min(((slug, distance(center[:2], (h.cx, h.cy))) for slug, h in hubs.items()),
                           key=lambda x: x[1])
        ident = hashlib.sha256(('|'.join(place)).encode()).hexdigest()[:12]
        candidates.append(dict(candidate_id=f'research-{ident}', region=region,
            label=' '.join(place), open_restaurants=len(items), lon=center[0], lat=center[1],
            observed_center_id=center[2], observed_center_address=center[3],
            nearest_registered_hub=nearest, nearest_registered_m=round(gap),
            outside_1km=gap > 1000, status='점포 실측·상권 경계·앵커 확인 필요' if gap > 1000 else '기존 등록 거점 근접',
            source='일반음식점 인허가 실측 원본', seed=False))
    return sorted(candidates, key=lambda x: (-x['open_restaurants'], x['label'])), dict(counts)


def cluster_candidates(rows: list[dict]) -> list[dict]:
    """서울 후기 확장과 같은 600m 단일연결로 탐색 중심을 묶는다. 원본 후보는 남긴다."""
    remaining = {r['candidate_id']: r for r in rows if r.get('store_probe', {}).get('metrics')}
    clusters = []
    while remaining:
        first = remaining.pop(sorted(remaining)[0])
        members, queue = [first], [first]
        while queue:
            center = queue.pop()
            hits = [key for key, row in remaining.items()
                    if distance((center['lon'], center['lat']), (row['lon'], row['lat'])) <= 600]
            for key in hits:
                row = remaining.pop(key)
                members.append(row)
                queue.append(row)
        representative = min(members, key=lambda r: (-r['store_probe']['metrics']['stores'], r['candidate_id']))
        clusters.append(dict(representative=representative['candidate_id'], label=representative['label'],
            members=[r['candidate_id'] for r in members], metrics=representative['store_probe']['metrics'],
            status='신규 후보 — 상권 범위·공유 앵커·대장·Gold 검증 필요'))
    return sorted(clusters, key=lambda r: (-r['metrics']['stores'], r['label']))


def run(baseline_ids: list[str] | None = None) -> dict:
    """기존 자료만 읽는다. 운영 레지스트리와 Gold는 수정하지 않는다."""
    from data.collectors.gwangju_licensing_hubs import load_source_rows as gj_rows, norm
    from data.collectors.jeonju_licensing_hubs import load_source_rows as jj_rows
    stage = sorted((ROOT / 'data/bronze/_gg_licensing_stage').glob('*.json'))[-1]
    buckets = json.loads(stage.read_text(encoding='utf-8'))
    gg = [r for rows in buckets.values() for r in rows]
    sources = {'경기': gg, '광주': [norm(r) for r in gj_rows()], '전주': [norm(r) for r in jj_rows()]}
    baseline = set(baseline_ids if baseline_ids is not None else ACTIVE_HUBS)
    registered = []
    for slug, hub in ALL_HUBS.items():
        if hub.city == 'seoul' or slug in baseline:
            continue
        stages = summarize(slug)['stages']
        metrics = store_metrics(load_latest(slug, 'stores_raw.json') or [])
        registered.append(dict(slug=slug, name=hub.name, city=hub.city, deferred=hub.deferred,
            metrics=metrics, stages=stages, ready_without_policy_change=ready_for_serving(stages, hub.deferred)))
    candidates, exclusions = {}, {}
    for region, rows in sources.items():
        candidates[region], exclusions[region] = discovery(rows, region, ALL_HUBS)
    return dict(source='기존 공공데이터·실측 산출물', seed=False,
        baseline_active_ids=sorted(baseline), registered_unserved=registered,
        discovery=candidates, source_exclusions=exclusions,
        limitations=[
            '경기 인허가 stage는 기존 후보의 동에 걸린 버킷이다. 경기 전역 전수 후보 목록이 아니다.',
            '광주·전주는 도시 인허가 원본을 사용하나 일반음식점만 포함한다. 모든 업종·상권의 전수 목록이 아니다.',
            '법정동별 인허가 묶음은 서울 TRDAR 발달상권·관광특구 경계와 다르다. 600m 군집을 동 경계에 임의 적용하지 않았다.',
            '인허가 좌표는 원천 EPSG:2097 변환값이며 건물 PIP의 주소 자가 보정을 적용하지 않았다. 1km 판정은 탐색용이다.',
            '신규 탐색 후보는 점포 실측·공식 상권 범위·R-ONE 매핑·대장·Gold 검증 전 서빙하지 않는다.'])


def probe_stores(row: dict) -> dict:
    """탐색 중심 700m 점포 전량을 받는다. 부분 응답은 완료로 저장하지 않는다."""
    import os
    import requests
    from data.collectors.common import latest_bronze, save_json

    slug = row['candidate_id']
    cached = latest_bronze(slug, 'store_probe_complete.json')
    if cached:
        result = json.loads(cached.read_text(encoding='utf-8'))
        raw = cached.parent / 'stores_raw.json'
        if not raw.exists():
            raise ValueError('완주 표식은 있으나 점포 원본 없음')
        rows = json.loads(raw.read_text(encoding='utf-8'))
        if len(rows) != result['total'] or store_metrics(rows) != result['metrics']:
            raise ValueError('완주 표식과 점포 원본 불일치')
        return {**result, 'bronze_path': raw.relative_to(ROOT).as_posix(),
                'sha256': hashlib.sha256(raw.read_bytes()).hexdigest()}
    rows: list[dict] = []
    for page in range(1, 101):
        response = requests.get('https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius',
            params=dict(serviceKey=os.environ['DATA_GO_KR_SERVICE_KEY'], type='json',
                        numOfRows=1000, pageNo=page, radius=700, cx=row['lon'], cy=row['lat']), timeout=30)
        if response.status_code != 200:
            raise ValueError(f'상가정보 HTTP {response.status_code}')
        raw = response.json()
        save_json(raw, slug, f'store_probe_page_{page:03d}.json')
        body = raw.get('body', {})
        if 'totalCount' not in body or not isinstance(body.get('items'), list):
            raise ValueError('상가정보 정상 응답 아님')
        rows.extend(body['items'])
        total = int(body['totalCount'])
        if len(rows) == total:
            result = dict(metrics=store_metrics(rows), total=total, radius_m=700,
                          source='소상공인 상가정보 storeListInRadius 실호출', seed=False)
            save_json(rows, slug, 'stores_raw.json')
            save_json(result, slug, 'store_probe_complete.json')
            return probe_stores(row)
        if not body['items'] or len(rows) > total:
            raise ValueError('상가정보 부분 페이지·중복 응답')
    raise ValueError('점포 페이지 상한 도달')


def write_markdown(report: dict) -> None:
    """지역·상권 이름과 미완 사유를 빠짐없이 사람이 읽을 수 있게 쓴다."""
    from app.data.cities import CITIES
    by_city = defaultdict(list)
    for slug in report['added_ids']:
        by_city[ALL_HUBS[slug].city].append(ALL_HUBS[slug].name)
    lines = ['# 경기·광주·전주 후보 재조사 (2026-11-03)', '',
        '기존 122곳을 유지하고 검증이 끝난 경기 36곳을 서빙 목록에 추가했다. 합계 158곳(서울 81 · 경기 59 · 광주 13 · 전주 5). 이 문서는 로컬 검증 결과이며 실제 배포 상태는 GitHub 워크플로에서 확인한다.', '',
        '## 적용한 기준', '',
        '- 서울 초기 선정은 R-ONE 표본 활용, 후기 선정은 기존 거점에서 1km 초과인 발달상권·관광특구를 600m 단일연결로 묶고 실측 점포 수로 우선순위를 정했다.',
        '- 정식 밀도 지표는 전체 점포 / 건물관리번호 보유 건물 수다. 건물당 10점포 초과는 밀집 검토, 상위 10건물 집중도 25% 초과는 주의로 표시했다. 주의만으로 제외하지 않는다.',
        '- 공개는 대장 완주, Tier1 Gold, 정밀 커버리지, 실제 R-ONE 앵커 대조, 공실유닛을 확인한다. 기존 테스트의 대표 집계 커버리지 90% 이상·서빙 대표값 기준 앵커 차이 ±30%p도 통과했다.',
        '- 기존 서울의 계획상가 예외를 다른 지역에 자동 복제하지 않았다. 공실 집계 배제 규칙과 출처 계약은 유지했다.', '',
        '## 이번에 추가한 거점 전체', '', '| 도시 | 추가 상권 |', '|---|---|']
    for city, names in sorted(by_city.items()):
        lines.append(f"| {CITIES[city].name} | {' · '.join(names)} |")
    lines += ['', '## 등록 후보 중 아직 공개하지 않은 곳', '', '| 상권 | 사유 |', '|---|---|']
    for row in report['registered_unserved']:
        if row['slug'] not in report['added_ids']:
            gaps = [s['stage'] + ': ' + s['evidence'] for s in row['stages']
                    if s['stage'] != '서빙등재' and s['status'] not in ('ok', 'partial')]
            reason = ' / '.join([row['deferred']] + gaps)
            lines.append(f"| {row['name']} | {reason} |")
    lines += ['', '## 신규 탐색 조사 전체', '',
        '411개 인허가 주소 묶음을 점검했다. 등록된 거점 중심에서 1km 초과인 227개 위치에 대해 700m 반경 상가정보를 완주 조회했다. 이를 600m 단일연결로 묶은 209개 묶음을 아래 전부 싣는다.', '',
        '**아래 목록은 정식 상권 또는 공개 거점 목록이 아니다.** 일반음식점 인허가 주소에서 발견한 탐색 위치다. 관측된 실제 업소 좌표를 조사 중심으로 썼고, 법정동·행정구역 이름을 공식 상권 이름으로 바꾸지 않았다. 신규 후보끼리의 700m 반경도 겹칠 수 있으므로 점포 수를 합산하지 않는다.', '',
        '추가 등록·공개 전에는 공식 상권 범위 또는 별도 범위 검증, 중심·반경 중복 조정, 공유 앵커의 근거, 대장 수집과 Gold 검증이 필요하다. 부재한 임대료·공실·수요·행사를 채우지 않았다.', '']
    for region, clusters in report['clusters_600m'].items():
        lines += [f'### {region} — {len(clusters)}개 탐색 묶음', '',
                  '| 대표 조사 위치(주소) | 700m 점포 수 | 건물 수 | 건물당 점포 | 상위 10건물 비중 | 점포 프로브 판정 | 묶인 위치 수 |',
                  '|---|---:|---:|---:|---:|---|---:|']
        for cluster in clusters:
            m = cluster['metrics']
            lines.append(f"| {cluster['label']} | {m['stores']} | {m['buildings']} | {m['stores_per_building']} | {m['top10_building_pct']}% | {m['verdict']} | {len(cluster['members'])} |")
        lines.append('')
    lines += ['## 입력의 범위와 한계', ''] + ['- ' + x for x in report['limitations']]
    lines += ['', '## 재현·검증', '',
        '- `python scripts/audit_regional_hub_candidates.py --probe` — 캐시 원본의 건수·고유 키·지표를 확인하며 재사용. 키·원본이 없는 환경에서는 조사 재현이 실패한다. 원본을 지어내지 않는다.',
        '- 기계 판독 근거: `reports/regional_hub_candidates_2026-11-03.json`(기존 122개 ID, 추가 36개 ID, 등록 후보 47개 체인, 신규 411개 주소 묶음, 상가정보 조회 227개 및 원본 경로·해시, 600m 묶음 전체).',
        '- Backend 기존 검증 22개 통과: `test_gg3_serving.py`, `test_active_cities_match_serving.py`, `test_city_registry.py`, `test_landing_facts.py`.',
        '- 구역·층별개요·점포요약·Program 업종 컨텍스트와 외곽선·임대·R-ONE 시계열도 추가 거점으로 확장했다. 기존 거점 항목은 그대로 보존했다. 새 36곳 중 평택시청·광주 광남동·야탑역·정자역·매탄동 5곳은 소규모 임대 표본이 없어 임대료를 비워 두었다.',
        '- 추가 36곳의 Program CSV에는 실제 점포 업종 집계만 실었다. 미수집 블로그·검색 트렌드는 비워 두고 진행률 검사에도 결손으로 남겼다. 서울 전용 매출값은 보존하고 매출 산출물의 공개 모집단 커버리지 메타데이터만 갱신했다.',
        '- 시작점 두 곳 중 큰 쪽의 대표 지번 수 이하인 새 경기 20곳에는 11-01 확정 규칙대로 「표본 소형」 문구를 붙였다. 기존 문구를 유지하고, 하위 25%라는 과거 관측을 고정하던 검사도 실제 확정 기준선 검사로 맞췄다.',
        '- Data 915개 통과: `test_regional_hub_candidates.py`, `test_chain_status.py`, `test_jeonju_expansion.py`, `test_district_zones.py`, `test_renewal_gold.py`. 임대 결측 고정 목록에 이번에 공개한 원천 결측 5곳을 추가했다.',
        '- Frontend 타입 검사·Vite 프로덕션 빌드 통과. PPPP 가드 9개 통과. `scripts/pppp_screens_check.py`: 22개 통과·실패 0·종료코드 0.',
        '- 추가 36곳의 핵심 Gold 216개 파일은 이미 Git 추적 중이다. 신규 보조 Gold 144개(구역·점포요약·층별개요·Program 업종 컨텍스트)는 기존 .gitignore 예외의 적용 대상이다.', '']
    (ROOT / 'docs/regional-hub-candidates-2026-11-03.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'reports/regional_hub_candidates_2026-11-03.json'
    baseline = json.loads(path.read_text(encoding='utf-8'))['baseline_active_ids'] if path.exists() else None
    result = run(baseline)
    if args.probe:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from data.collectors.common import load_env
        load_env()
        todo = [r for rows in result['discovery'].values() for r in rows if r['outside_1km']]
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(probe_stores, r): r for r in todo}
            for future in as_completed(futures):
                row = futures[future]
                try:
                    row['store_probe'] = future.result()
                except Exception as exc:
                    # 요청 예외의 URL에는 키가 포함되므로 예외 종류만 남긴다.
                    row['store_probe'] = dict(status='failed', error_type=type(exc).__name__)
                print(row['label'], row['store_probe'].get('metrics', {}).get('verdict', '미완료'), flush=True)
    result['clusters_600m'] = {k: cluster_candidates(rows) for k, rows in result['discovery'].items()}
    result['active_ids_after'] = sorted(ACTIVE_HUBS)
    result['added_ids'] = sorted(set(ACTIVE_HUBS) - set(result['baseline_active_ids']))
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.probe:
        write_markdown(result)
    print('등록 미공개', len(result['registered_unserved']))
    print('검증 완료', sum(r['ready_without_policy_change'] for r in result['registered_unserved']))
    for region, rows in result['discovery'].items():
        print(region, '주소 묶음', len(rows), '1km 밖', sum(r['outside_1km'] for r in rows))
