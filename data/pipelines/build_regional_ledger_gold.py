"""완주한 탐색 위치의 대장을 Bronze→Silver→Gold 관측 산출물로 승격한다.

상권 경계·폴리곤·앵커가 확정되지 않은 탐색 위치를 Page 거점으로 등록하지 않는다.
빈 응답은 검증된 0건으로만 처리하며 임대·공실률·매출·예측은 만들지 않는다.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import shutil
from collections import Counter
from pathlib import Path

from data.collectors.building_vacancy import expos_units
from data.collectors.floor_capacity import commercial_floor_nos
from data.config.store_taxonomy import category_path, is_storefront
from scripts import collect_regional_research_ledgers as source

VERSION = 1
GOLD = source.ROOT / 'data/gold/regional_research_ledgers'
SILVER = source.ROOT / 'data/silver/regional_research_ledgers/normalized'
REPORT = source.ROOT / 'reports/regional_research_gold.json'


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()


def bronze_path(relative: str) -> Path:
    """원천 참조가 저장소 Bronze를 이탈하면 중단한다."""
    path = (source.ROOT / relative).resolve()
    if not path.is_relative_to((source.ROOT / 'data/bronze').resolve()):
        raise ValueError('BRONZE_PATH_ESCAPE')
    return path


def verified_rows(pnu: str, endpoint: str, marker: dict) -> list[dict]:
    """완료 표식만 믿지 않고 페이지 해시·헤더·전체 건수·중복을 재검증한다."""
    if (marker.get('complete') is not True or marker.get('pnu') != pnu or
            marker.get('endpoint') != endpoint or type(marker.get('total')) is not int or
            marker['total'] < 0 or type(marker.get('received')) is not int or
            marker.get('received') != marker['total'] or not marker.get('pages')):
        raise ValueError('INCOMPLETE_LEDGER_MARKER')
    rows, identities = [], set()
    for page in marker['pages']:
        path = bronze_path(page['path'])
        if source.fingerprint(path) != page['sha256']:
            raise ValueError('LEDGER_PAGE_HASH_MISMATCH')
        total, items = source.parse_page(source.read(path))
        if total != marker['total']:
            raise ValueError('LEDGER_TOTAL_MISMATCH')
        for item in items:
            key = digest(item)
            if key in identities:
                raise ValueError('DUPLICATE_LEDGER_ROW')
            identities.add(key)
        rows.extend(items)
    if len(rows) != marker['total']:
        raise ValueError('LEDGER_ROW_COUNT_MISMATCH')
    return rows


def immutable(path: Path, value: bytes) -> None:
    """같은 원천 해시의 산출물을 바꾸지 않는다. 불일치하면 덮어쓰지 않고 실패한다."""
    if path.exists():
        if path.read_bytes() != value:
            raise ValueError('EXISTING_ARTIFACT_MISMATCH')
        return
    if shutil.disk_usage(source.ROOT).free < 2 * 1024 ** 3:
        raise source.DiskWait('DISK_FREE_BELOW_2GIB')
    source.atomic_bytes(path, value)


def json_gz(value: dict) -> bytes:
    return gzip.compress(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode('utf-8'), mtime=0)


def run(plan: dict, paused_prefixes: list[str]) -> dict:
    """위치별 두 대장이 전량 완주한 경우에만 Silver와 Gold를 만든다. 네트워크 호출 없음."""
    excluded = tuple(paused_prefixes)
    locations = [loc for loc in plan['locations'] if loc['pnus'] and
                 not any(p.startswith(excluded) for p in loc['pnus'])] if excluded else plan['locations']
    # 수만 번의 없는 파일 exists() 대신 실제 완료 표식을 한 번 색인한다.
    markers = {e: {p.parent.name: p for p in (source.RAW / e).glob('*/complete.json')}
               for e in source.ENDPOINTS}
    legacy_data, normalized = {}, {}
    result = dict(schema_version=VERSION, checked_at=source.now().isoformat(),
        plan_sha256=source.fingerprint(source.PLAN), paused_pnu_prefixes=paused_prefixes,
        scope='탐색 위치의 검증된 대장 관측 Gold. 서비스용 Page Gold·거점 등록과 별개',
        locations=[], source='건축HUB 원본·소상공인 상가정보 원본', seed=False)
    for loc in locations:
        entry = dict(id=loc['id'], label=loc['label'], region=loc['region'], total_pnus=len(loc['pnus']))
        missing = {e: sum(p not in markers[e] and not (e == 'expos' and p in plan['legacy_expos'])
                         for p in loc['pnus']) for e in source.ENDPOINTS}
        if loc['unresolved'] or any(missing.values()):
            entry.update(status='waiting_raw', missing=missing, unresolved=len(loc['unresolved']))
            result['locations'].append(entry)
            continue
        source_refs, observations = {}, []
        for pnu in loc['pnus']:
            if pnu not in normalized:
                rows, refs = {}, {}
                for endpoint in source.ENDPOINTS:
                    if endpoint == 'expos' and pnu in plan['legacy_expos']:
                        old = plan['legacy_expos'][pnu]
                        path = bronze_path(old['source'])
                        expected = plan['legacy_sources'][old['source']]
                        if old['source'] not in legacy_data:
                            if source.fingerprint(path) != expected:
                                raise ValueError('LEGACY_SOURCE_HASH_MISMATCH')
                            legacy_data[old['source']] = source.read(path)
                        raw = legacy_data[old['source']][pnu]
                        items = raw.get('expos')
                        if (not isinstance(items, list) or not items or raw.get('expos_capped') or
                                raw.get('expos_total') != len(items) or old['total'] != len(items) or
                                len({digest(r) for r in items}) != len(items)):
                            raise ValueError('INCOMPLETE_LEGACY_LEDGER')
                        rows[endpoint] = items
                        refs[endpoint] = dict(source=old['source'], sha256=expected, kind='legacy_bronze')
                    else:
                        path = markers[endpoint][pnu]
                        rows[endpoint] = verified_rows(pnu, endpoint, source.read(path))
                        refs[endpoint] = dict(marker=path.relative_to(source.ROOT).as_posix(),
                                              sha256=source.fingerprint(path), kind='api_pages')
                normalized[pnu] = (dict(pnu=pnu, expos_rows=len(rows['expos']),
                    floor_rows=len(rows['floors']), commercial_expos_units=len(expos_units(rows['expos'])),
                    commercial_ground_floor_numbers=sorted(commercial_floor_nos(rows['floors']))), refs)
            observation, refs = normalized[pnu]
            observations.append(observation)
            source_refs[pnu] = refs
        stores_path = bronze_path(loc['source'])
        if source.fingerprint(stores_path) != loc['source_sha256']:
            raise ValueError('STORE_SOURCE_HASH_MISMATCH')
        stores = source.read(stores_path)
        ids = [row.get('bizesId') for row in stores]
        if not all(ids) or len(ids) != len(set(ids)):
            raise ValueError('STORE_KEYS_INVALID')
        fingerprint = digest(dict(version=VERSION, stores=loc['source_sha256'], ledgers=source_refs))
        silver_path = SILVER / loc['id'] / (fingerprint + '.json.gz')
        silver = dict(schema_version=VERSION, candidate_id=loc['id'], source_digest=fingerprint,
            stores_source=dict(path=loc['source'], sha256=loc['source_sha256']),
            ledger_sources=source_refs, observations=observations, seed=False)
        immutable(silver_path, json_gz(silver))
        # Gold는 방금 저장한 Silver를 실제로 다시 읽어서 만든다.
        silver = source.read(silver_path)
        folder = GOLD / loc['id'] / fingerprint
        gold_path = folder / 'ledger_evidence.json.gz'
        gold = dict(schema_version=VERSION, candidate_id=loc['id'], label=loc['label'], region=loc['region'],
            source='건축HUB 검증 완료 대장 관측', seed=False, serving_eligible=False,
            page_gold_status='requires_boundary_polygon_anchor_validation',
            silver=dict(path=silver_path.relative_to(source.ROOT).as_posix(), sha256=source.fingerprint(silver_path)),
            observations=silver['observations'],
            note='상가정보 점포가 확인된 지번만 포함. 전유 호 수와 상업층은 관측이며 공실률·상가 수용량·임대료가 아님.')
        immutable(gold_path, json_gz(gold))
        # 기존 Program 정제와 같은 점포 필터·소분류 집계를 재사용한다. 리뷰·트렌드는 만들지 않는다.
        cats = Counter(category_path(r).split(' > ')[-1] for r in stores if is_storefront(r))
        cats.pop('', None)
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(['kind', 'key', 'value'])
        writer.writerows(('category', key, value) for key, value in cats.most_common(30))
        context_path = folder / 'program_content_context.csv'
        immutable(context_path, stream.getvalue().encode('utf-8-sig'))
        entry.update(status='ledger_gold_complete', serving_eligible=False,
            page_gold_status=gold['page_gold_status'], source_digest=fingerprint,
            silver=silver_path.relative_to(source.ROOT).as_posix(),
            artifacts=[dict(path=p.relative_to(source.ROOT).as_posix(), sha256=source.fingerprint(p))
                       for p in (gold_path, context_path)])
        result['locations'].append(entry)
    counts = Counter(r['status'] for r in result['locations'])
    result['summary'] = dict(locations=len(locations), ledger_gold_complete=counts['ledger_gold_complete'],
        waiting_raw=counts['waiting_raw'], serving_promoted=0,
        page_gold_pending=len(locations), normalized_unique_pnus=len(normalized))
    source.atomic_json(REPORT, result)
    return result
