"""건물 주소 후보를 진단한다. 점포 확정·Silver 승격을 하지 않는다."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from data.collectors.acquire_industry_public import LICENSES
from data.config.page_hubs import ACTIVE_HUBS


def token(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip())


def building_address(value: Any) -> str:
    """후보 검색 전용. 원문은 보존하고 쉼표·괄호 이후 상세주소만 분리한다."""
    return re.split(r'[,()]', token(value), maxsplit=1)[0].strip()


def floor(value: Any, *, address: bool = False) -> int | None:
    """명시적인 단일 층만 읽는다. 호실에서 층을 추정하지 않는다."""
    text = token(value)
    if address:
        # 건물명·법정동 괄호 안 숫자와 범위/복수 층은 해석하지 않는다.
        text = text.split('(', 1)[0]
        parts = text.split(',', 1)
        if len(parts) != 2:
            return None
        detail = parts[1].strip()
        found = re.findall(r'(?<![\d-])(지하\s*|B\s*)?(\d+)\s*층', detail, re.I)
        if len(found) != 1 or re.search(r'[~∼\-]|\d\s*[,·/]\s*\d', detail):
            return None
        underground, number = found[0]
        return -int(number) if underground else int(number)
    found = re.fullmatch(r'(지하\s*|B\s*|-)?(\d+)(?:\s*층)?', text, re.I)
    if not found:
        return None
    return -int(found[2]) if found[1] else int(found[2])


def candidate(row: dict, stores: list[dict]) -> dict:
    """후보 수와 층 근거를 남기되 store_id를 확정하지 않는다."""
    name, address = token(row.get('BPLCNM')), token(row.get('RDNWHLADDR'))
    result: dict = {'status': 'candidate_only', 'store_id': None, 'candidates': []}
    if '\ufffd' in name + address:
        result['status'] = 'blocked_corrupted_text'
        return result
    if not name or not address:
        result['status'] = 'missing_name_or_address'
        return result
    by_id: dict[str, dict] = {}
    for store in stores:
        if (token(store.get('bizesNm')) == name and
                token(store.get('rdnmAdr')) == building_address(address)):
            by_id[str(store['bizesId'])] = store
    license_floor = floor(address, address=True)
    for store_id, store in sorted(by_id.items()):
        store_floor = floor(store.get('flrNo'))
        state = ('unknown' if license_floor is None or store_floor is None else
                 'equal' if license_floor == store_floor else 'conflict')
        result['candidates'].append({'store_id': store_id, 'floor_evidence': state,
                                     'license_floor': license_floor, 'store_floor': store_floor})
    result['status'] = ('no_candidate' if not by_id else 'multiple_store_candidates'
                        if len(by_id) > 1 else 'candidate_only')
    return result


def audit(previous: Path, output: Path) -> dict:
    """원본 해시와 중복·충돌 수를 새 진단 보고서에 기록한다."""
    if output.exists():
        raise FileExistsError('기존 진단 보고서는 덮어쓰지 않습니다')
    index: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    provenance = []

    def read(path: Path) -> Any:
        raw = path.read_bytes()
        provenance.append({'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()})
        return json.loads(raw)

    for slug in ACTIVE_HUBS:
        folder = previous / ('recovery/stores/suyu' if slug == 'suyu' else f'stores/{slug}')
        paths = sorted(p for p in folder.glob('*.json') if p.stem.isdigit())
        if not paths:
            raise ValueError(f'missing_source: stores/{slug}')
        for path in paths:
            for row in read(path)['body']['items']:
                key = token(row.get('bizesNm')), token(row.get('rdnmAdr'))
                store_id = str(row['bizesId'])
                old = index[key].get(store_id)
                if old is not None and old != row:
                    raise ValueError(f'conflicting_store_observation: {store_id}')
                index[key][store_id] = row
    summaries = {}
    claims: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for source, service in LICENSES.items():
        counts: Counter = Counter()
        samples: dict[str, list] = defaultdict(list)
        paths = sorted(p for p in (previous / 'seoul' / service / 'all').glob('*.json') if p.stem.isdigit())
        if not paths:
            raise ValueError(f'missing_source: {service}')
        for path in paths:
            for position, row in enumerate(read(path)[service]['row'], 1):
                key = token(row.get('BPLCNM')), building_address(row.get('RDNWHLADDR'))
                result = candidate(row, list(index.get(key, {}).values()))
                counts['rows'] += 1
                counts[result['status']] += 1
                identity = (source, token(row.get('OPNSFTEAMCODE')), token(row.get('MGTNO')))
                if not all(identity):
                    raise ValueError(f'missing_identity: {path}: row={position}')
                for item in result['candidates']:
                    counts['candidate_pairs'] += 1
                    counts['floor_' + item['floor_evidence']] += 1
                    claims[item['store_id']].add(identity)
                # 원문·키·파일 위치가 붙은 진단 예시. 단일 후보도 확정하지 않는다.
                categories = {result['status'], *(x['floor_evidence'] for x in result['candidates'])}
                for category in categories:
                    if len(samples[category]) < 3:
                        samples[category].append({'source_path': str(path), 'row_1based': position,
                            'identity': list(identity), 'name': row.get('BPLCNM'),
                            'address': row.get('RDNWHLADDR'), 'business_state': row.get('TRDSTATEGBN'), **result})
        summaries[source] = {'counts': dict(counts), 'samples': dict(samples)}
    result = {'status': 'diagnostic_only', 'sources': provenance, 'by_source': summaries,
              'stores_claimed_by_multiple_licenses': sum(len(v) > 1 for v in claims.values()),
              'limitations': ['층 일치·단일 후보도 점포 확정이 아니다. 호실은 비교하지 않았다.',
                              '휴폐업 포함 과거 인허가다. 복수 청구는 동시 영업이나 오류의 증명이 아니다.',
                              '건물 주소 후보만 집계한다. Silver·Gold·모델·API 미변경.']}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.previous, args.output)
    print(json.dumps({'status': report['status'], 'stores_claimed_by_multiple_licenses':
                      report['stores_claimed_by_multiple_licenses']}, ensure_ascii=False))
