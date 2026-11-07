"""사용자가 지정한 전주 권역의 관측 누락지를 보완한다. 공식 상권 경계를 만들지 않는다."""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import collect_regional_research_ledgers as ledgers
from scripts.audit_regional_hub_candidates import distance, store_metrics
from data.collectors.common import load_env, load_latest, save_json
from data.collectors.gwangju_licensing import fetch, rows_of
from data.collectors.jeonju_licensing_hubs import SRC, load_source_rows, norm
from data.collectors.gwangju_candidates import fetch_complete_stores
from data.config.page_hubs import JEONJU_HUBS, PageHub

REPORT = ROOT / 'reports/jeonju_requested_areas_2026-11-06.json'
GROUPS = {
    '효자동1가': lambda r: '효자동1가' in r['SITEWHLADDR'],
    '효자동2가': lambda r: '효자동2가' in r['SITEWHLADDR'],
    '효자동3가': lambda r: '효자동3가' in r['SITEWHLADDR'],
    '객사': lambda r: any(d in r['SITEWHLADDR'] for d in ('고사동', '중앙동', '다가동')),
    '혁신도시 전주측': lambda r: any(d in r['SITEWHLADDR'] for d in ('중동 ', '만성동', '장동 ')),
    '에코시티': lambda r: any(d in r['SITEWHLADDR'] for d in ('송천동2가', '전미동1가')) and (
        '에코' in (r['BPLCNM'] or '') or '세병' in (r['RDNWHLADDR'] or '')),
    '혁신도시 완주측': lambda r: '완주군 이서면' in r['SITEWHLADDR'] and
        any(d in r['SITEWHLADDR'] for d in ('갈산리', '반교리')),
}


def gap_centers(points: list[dict], existing: list[tuple[float, float, int]]) -> list[dict]:
    """기존 반경 밖 관측점을 모두 덮는다. 새 중심도 반드시 실제 업소의 좌표다."""
    todo = {r['MGTNO']: r for r in points if not any(
        distance((r['lon'], r['lat']), c[:2]) <= c[2] for c in existing)}
    chosen = []
    while todo:
        hits = {key: {other for other, row in todo.items() if distance(
                    (center['lon'], center['lat']), (row['lon'], row['lat'])) <= 700}
                for key, center in todo.items()}
        key = min(hits, key=lambda k: (-len(hits[k]), k))
        chosen.append({**todo[key], 'covered_license_ids': sorted(hits[key])})
        for covered in hits[key]:
            del todo[covered]
    return chosen


def wanju_source() -> tuple[list[dict], Path]:
    """완주 이서면 도로명 주소로 조회한 전량을 검증한다. 혁신도시는 이후 지번으로 한정한다."""
    load_env()
    folder = ROOT/'data/bronze/wanju_innovation_licensing'/ledgers.now().date().isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder/'rows.json'
    marker = folder/'complete.json'
    if marker.exists():
        doc, rows = ledgers.read(marker), ledgers.read(target)
        if not doc.get('complete') or len(rows) != doc['total'] or ledgers.fingerprint(target) != doc['sha256']:
            raise ValueError('완주 인허가 캐시 검증 실패')
        return rows, target
    unique, total = {}, None
    for number in range(1, 2001):
        path = folder/f'page_{number:05d}.json'
        doc = ledgers.read(path) if path.exists() else fetch({
            'cond[ROAD_NM_ADDR::LIKE]': '완주군 이서면', 'numOfRows': 1000, 'pageNo': number})
        rows = rows_of(doc)
        count = int(doc['response']['body']['totalCount'])
        if total is not None and count != total:
            raise ValueError('완주 인허가 전체 건수 변경')
        total = count
        if any('완주군 이서면' not in str(r.get('ROAD_NM_ADDR', '')) for r in rows):
            raise ValueError('완주 인허가 주소 필터 불일치')
        for row in rows:
            if not row.get('MNG_NO') or row['MNG_NO'] in unique:
                raise ValueError('완주 인허가 고유 키 누락·중복')
            unique[row['MNG_NO']] = row
        if not path.exists():
            ledgers.atomic_json(path, doc)
        if len(unique) == total:
            result = list(unique.values())
            ledgers.atomic_json(target, result)
            ledgers.atomic_json(marker, dict(complete=True, total=total, sha256=ledgers.fingerprint(target)))
            return result, target
        if not rows or len(unique) > total:
            raise ValueError('완주 인허가 부분 수집')
    raise ValueError('완주 인허가 페이지 상한')


def audit(include_wanju: bool = False) -> dict:
    from pyproj import Transformer
    plan = ledgers.read(ledgers.PLAN)
    discovery = ledgers.read(ledgers.REPORT)
    ids = {r['id'] for r in plan['locations']}
    circles = [(r['lon'], r['lat'], 700) for rows in discovery['discovery'].values() for r in rows
               if r['candidate_id'] in ids and r['region'] == '전주']
    circles += [(h.cx, h.cy, h.stores_radius_m) for h in JEONJU_HUBS.values()]
    baseline_circles = list(circles)
    transform = Transformer.from_crs(2097, 4326, always_xy=True)
    groups = {name: [] for name in GROUPS}
    originals = load_source_rows()
    extra_source = None
    if include_wanju:
        extra, extra_source = wanju_source()
        originals += extra
    for original in originals:
        row = norm(original)
        if row['TRDSTATEGBN'] != '01' or str(row['DCBYMD'] or '').strip():
            continue
        row['SITEWHLADDR'] = row['SITEWHLADDR'] or ''
        if '전주시 ' not in row['SITEWHLADDR'] and not (
                include_wanju and '완주군 이서면' in row['SITEWHLADDR']):
            continue
        try:
            lon, lat = transform.transform(float(row['X']), float(row['Y']))
        except (TypeError, ValueError):
            continue
        if not (124 < lon < 132 and 33 < lat < 39):
            continue
        row.update(lon=lon, lat=lat)
        for name, contains in GROUPS.items():
            if contains(row):
                groups[name].append(row)
    rows, centers = [], []
    for name, points in groups.items():
        if name == '혁신도시 완주측' and not include_wanju:
            continue
        before = len(circles)
        baseline_uncovered = sum(not any(distance((p['lon'], p['lat']), c[:2]) <= c[2]
                                      for c in baseline_circles) for p in points)
        chosen = gap_centers(points, circles)
        uncovered = sum(len(r['covered_license_ids']) for r in chosen)
        for point in chosen:
            ident = hashlib.sha256(point['MGTNO'].encode()).hexdigest()[:12]
            centers.append(dict(id='research-request-' + ident, region='전주권' if name == '혁신도시 완주측' else '전주',
                label=name + ' 보완',
                group=name, lon=point['lon'], lat=point['lat'], radius_m=700,
                observed_center_id=point['MGTNO'], observed_center_name=point['BPLCNM'],
                observed_center_address=point['SITEWHLADDR'],
                covered_license_ids=point['covered_license_ids']))
            circles.append((point['lon'], point['lat'], 700))
        rows.append(dict(area=name, observed_open_licenses=len(points), uncovered_licenses=uncovered,
            baseline_uncovered_licenses=baseline_uncovered,
            already_covered_licenses=len(points)-baseline_uncovered, added_centers=len(circles)-before))
    marker = sorted(SRC.glob('*/city_complete.json'))[-1]
    return dict(created_at=ledgers.now().isoformat(), baseline_plan_sha256=ledgers.fingerprint(ledgers.PLAN),
        license_source=(marker.parent/'city_rows.json').relative_to(ROOT).as_posix(),
        license_source_sha256=ledgers.fingerprint(marker.parent/'city_rows.json'),
        wanju_source=dict(path=extra_source.relative_to(ROOT).as_posix(), sha256=ledgers.fingerprint(extra_source))
            if extra_source else None, areas=rows, added_centers=centers, seed=False,
        note='영업 인허가 관측점과 기존 점포 조사 반경의 대조. 동 전체·카페 전수·공식 상권 경계가 아님.',
        innovation_scope='전주 중동·만성동·장동 + 완주 이서면 갈산리·반교리' if include_wanju else
            '전주 중동·만성동·장동')


def collect_probes(report: dict) -> None:
    load_env()
    for center in report['added_centers']:
        rows = load_latest(center['id'], 'stores_raw.json')
        if rows is None:
            hub = PageHub(center['id'], center['label'], center['lon'], center['lat'], 500, 700, city='jeonju')
            rows = fetch_complete_stores(os.environ['DATA_GO_KR_SERVICE_KEY'], hub)
            store_metrics(rows)
            path = save_json(rows, center['id'], 'stores_raw.json')
        else:
            path = sorted((ROOT/'data/bronze'/center['id']).glob('*/stores_raw.json'))[-1]
        center['store_probe'] = dict(path=Path(path).relative_to(ROOT).as_posix(),
            sha256=ledgers.fingerprint(Path(path)), stores=len(rows), metrics=store_metrics(rows))
        ledgers.atomic_json(REPORT, report)


def extend_plan(original: dict, report: dict) -> dict:
    """기존 위치·지번·미해결 기록을 보존하고, 새 점포 원본의 지번만 합친다."""
    plan = copy.deepcopy(original)
    targets = {r['pnu']: r for r in plan['targets']}
    appended = False
    for center in report['added_centers']:
        if any(r['id'] == center['id'] for r in plan['locations']):
            continue
        probe = center['store_probe']
        path = ROOT/probe['path']
        if ledgers.fingerprint(path) != probe['sha256']:
            raise ValueError('STORE_SOURCE_HASH_MISMATCH')
        stores = ledgers.read(path)
        store_metrics(stores)
        with contextlib.redirect_stdout(io.StringIO()):
            buildings = ledgers.group_by_building(stores)
        pnus, unresolved = set(), []
        for key, building in buildings.items():
            pnu = str(building.get('lnoCd') or '')
            if not re.fullmatch(r'\d{19}', pnu):
                unresolved.append(key)
                plan['unresolved'].append(dict(location=center['id'], building_id=key, reason='PNU 누락·형식 오류'))
                continue
            pnus.add(pnu)
            target = targets.setdefault(pnu, dict(pnu=pnu, locations=[]))
            if center['id'] not in target['locations']:
                target['locations'].append(center['id'])
        plan['locations'].append(dict(id=center['id'], label=center['label'], region=center['region'],
            source=probe['path'], source_sha256=probe['sha256'], pnus=sorted(pnus), unresolved=unresolved))
        appended = True
    plan['targets'] = list(targets.values())
    if not appended:
        return plan
    # 보고서의 향후 재실행으로 과거 원천 참조 해시가 깨지지 않게 불변 사본을 둔다.
    report_hash = ledgers.fingerprint(REPORT)
    archive = ROOT/'reports'/f'jeonju_requested_scope_{report_hash[:16]}.json'
    if archive.exists() and ledgers.fingerprint(archive) != report_hash:
        raise ValueError('추가 범위 보고서 충돌')
    if not archive.exists():
        ledgers.atomic_bytes(archive, REPORT.read_bytes())
    plan.setdefault('scope_additions', []).append(dict(report=archive.relative_to(ROOT).as_posix(),
        sha256=report_hash, reason='사용자 지정 전주·완주 권역의 누락 관측점 보완'))
    # 새 지번이 기존 전주 5거점의 완주 전유부에도 있으면, 같은 완주 검증으로 재사용한다.
    wanted = set(targets)-{r['pnu'] for r in original['targets']}
    for slug in JEONJU_HUBS:
        paths = sorted((ROOT/'data/bronze'/slug).glob('*/bldg_ledger_raw.json'))
        if not paths:
            continue
        path = paths[-1]
        raw = ledgers.read(path)
        if not isinstance(raw, dict):
            continue
        added = {}
        for pnu in wanted & raw.keys():
            record = raw[pnu]
            if not isinstance(record, dict):
                continue
            rows = record.get('expos')
            if (isinstance(rows, list) and rows and record.get('expos_total') == len(rows)
                    and not record.get('expos_capped') and len({json.dumps(r,sort_keys=True) for r in rows}) == len(rows)):
                added[pnu] = dict(source=path.relative_to(ROOT).as_posix(), total=len(rows))
        if added:
            plan['legacy_sources'][path.relative_to(ROOT).as_posix()] = ledgers.fingerprint(path)
            plan['legacy_expos'].update(added)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--collect-probes', action='store_true')
    parser.add_argument('--include-wanju', action='store_true')
    args = parser.parse_args()
    report = audit(args.include_wanju)
    ledgers.atomic_json(REPORT, report)
    if args.collect_probes:
        collect_probes(report)
    print(json.dumps(dict(areas=report['areas'], added_centers=len(report['added_centers'])), ensure_ascii=False))
