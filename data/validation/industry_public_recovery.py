"""공식 재조회 응답을 식별키로 대조한다. 형식 변환을 원문 복구로 오인하지 않는다."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

FIELDS = ('BPLCNM', 'RDNWHLADDR')
IDENTITY = ('OPNSFTEAMCODE', 'MGTNO')
UPSTREAM_FIELDS = {'OPNSFTEAMCODE': 'OPN_ATMY_GRP_CD', 'MGTNO': 'MNG_NO',
                   'BPLCNM': 'BPLC_NM', 'RDNWHLADDR': 'ROAD_NM_ADDR'}


def read_upstream_rows(path: Path) -> list[dict]:
    """행안부 공식 응답의 명시 필드만 비교용으로 대응한다. 원본은 바꾸지 않는다."""
    response = json.loads(path.read_bytes())['response']
    if str(response['header']['resultCode']) not in {'0', '00'}:
        raise ValueError('unsuccessful_upstream_response')
    body = response['body']
    rows = body['items']['item']
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or len(rows) != int(body['totalCount']):
        raise ValueError('incomplete_upstream_observations')
    if any(any(field not in row for field in UPSTREAM_FIELDS.values()) for row in rows):
        raise ValueError('missing_upstream_comparison_fields')
    return [{target: row[source] for target, source in UPSTREAM_FIELDS.items()} for row in rows]


def read_rows(path: Path, service: str, encoding: str | None = None) -> list[dict]:
    """바이트를 엄격히 읽는다. xls 탭 구분 응답은 인코딩을 명시해야 한다."""
    raw = path.read_bytes()
    if path.suffix == '.json':
        body = json.loads(raw)[service]
        if body.get('RESULT', {}).get('CODE') != 'INFO-000':
            raise ValueError('unsuccessful_response')
        return body['row']
    if path.suffix == '.xml':
        root = ET.fromstring(raw)
        if root.tag != service or root.findtext('RESULT/CODE') != 'INFO-000':
            raise ValueError('unsuccessful_response')
        return [{child.tag: child.text for child in row} for row in root.findall('row')]
    if path.suffix == '.xls':
        if encoding is None:
            raise ValueError('explicit_encoding_required')
        text = raw.decode(encoding, errors='strict')
        if not text.startswith('OPNSFTEAMCODE\tMGTNO\t'):
            raise ValueError('unsupported_excel_payload')
        reader = csv.DictReader(io.StringIO(text), delimiter='\t')
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError('malformed_tabular_row')
        return rows
    raise ValueError('unsupported_format')


def compare(baseline: dict, observations: list[dict]) -> dict:
    """동일 키가 한 행일 때만 비교하고 복구 후보도 자동 반영하지 않는다."""
    identity = tuple(str(baseline.get(field) or '').strip() for field in IDENTITY)
    if not all(identity):
        raise ValueError('missing_baseline_identity')
    same = [row for row in observations if tuple(str(row.get(f) or '').strip() for f in IDENTITY) == identity]
    result: dict[str, Any] = {'identity': list(identity), 'same_identity_count': len(same),
                              'replacement_applied': False, 'fields': {}}
    if len(same) != 1:
        result['status'] = 'identity_not_unique' if same else 'identity_not_found'
        return result
    baseline_damage = [field for field in FIELDS if '\ufffd' in str(baseline.get(field) or '')]
    if not baseline_damage:
        result['status'] = 'baseline_has_no_replacement_character'
        return result
    states = []
    for field in baseline_damage:
        value = same[0].get(field)
        state = ('missing' if value is None or not str(value).strip() else
                 'replacement_character' if '\ufffd' in str(value) else
                 'question_mark_unresolved' if '?' in str(value) else
                 'review_required')
        states.append(state)
        result['fields'][field] = {'baseline': baseline[field], 'observed': value, 'state': state}
    result['status'] = ('unresolved' if any(state != 'review_required' for state in states)
                        else 'review_required')
    return result


def assess(baseline_path: Path, observation_path: Path, service: str,
           identity: tuple[str, str], encoding: str | None = None) -> dict:
    """원본 해시와 명시적 디코딩 조건을 붙여 읽기 전용으로 비교한다."""
    baselines = read_rows(baseline_path, service)
    same = [row for row in baselines if tuple(str(row.get(f) or '').strip() for f in IDENTITY) == identity]
    if len(same) != 1:
        raise ValueError('baseline_identity_not_unique')
    result = compare(same[0], read_rows(observation_path, service, encoding))
    result.update(service=service, encoding=encoding,
                  baseline_path=str(baseline_path), observation_path=str(observation_path),
                  baseline_sha256=hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
                  observation_sha256=hashlib.sha256(observation_path.read_bytes()).hexdigest())
    return result
