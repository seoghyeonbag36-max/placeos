"""부분 Silver에서 원천 식별키별 관측 숫자 피처를 만든다. 점포 귀속·서빙은 하지 않는다."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import re
from pathlib import Path
import sqlite3
import tempfile
from typing import Any

from data.collectors.acquire_industry_public import LICENSES
from data.validation.industry_public_stream import silver_rows

FEATURE_FIELDS = {'acaInsTiInfo': ('TOFOR_SMTOT', 'DTM_RCPTN_ABLTY_NMPR_SMTOT'),
                  **{source: ('SITEAREA',) for source in LICENSES}}


def numeric(value: Any) -> float | None:
    """미관측은 null, 실제 0은 0이다. 단위 변환·문자열 추정은 하지 않는다."""
    if value is None or isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('invalid_numeric_observation')
    if isinstance(value, str) and ',' in value:
        if not re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?', value.strip()):
            raise ValueError('invalid_numeric_observation')
        value = value.replace(',', '')
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError('invalid_numeric_observation') from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError('invalid_numeric_observation')
    return number


def feature(source: str, row: dict) -> dict:
    """원천 필드 이름·상태·출처를 보존한다. 값의 뜻을 매출·성공 확률로 바꾸지 않는다."""
    if source not in FEATURE_FIELDS or not row.get('identity'):
        raise ValueError('unsupported_source_or_missing_identity')
    fields, provenance = row['fields'], row['provenance']
    if provenance['source'] != source or not provenance.get('source_sha256'):
        raise ValueError('invalid_provenance')
    match_fields = ('ACA_NM', 'FA_RDNMA') if source == 'acaInsTiInfo' else ('BPLCNM', 'RDNWHLADDR')
    if any('\ufffd' in str(fields.get(f) or '') for f in match_fields):
        raise ValueError('corrupted_match_text_in_accepted')
    values = {field: numeric(fields.get(field)) for field in FEATURE_FIELDS[source]}
    return {'source': source, 'identity': row['identity'], 'store_id': None,
            'values': values, 'observed': {field: value is not None for field, value in values.items()},
            'raw_values': {field: fields.get(field) for field in values},
            'source_state': {field: fields.get(field) for field in
                (('REG_STTUS_NM', 'LOAD_DTM') if source == 'acaInsTiInfo' else ('TRDSTATEGBN', 'UPDATEDT'))},
            'provenance': provenance, 'source_row_1based': row['source_row_1based']}


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build(silver: Path, verification: Path, quarantine: Path, output: Path, report_path: Path) -> dict:
    """검증된 부분 Silver만 소비한다. 실패 시 최종 피처 파일을 만들지 않는다."""
    if output.resolve() == report_path.resolve():
        raise ValueError('output_paths_must_be_distinct')
    if output.exists() or report_path.exists():
        raise FileExistsError('기존 산출물은 덮어쓰지 않습니다')
    verified = json.loads(verification.read_text(encoding='utf-8'))
    if (verified['status'] != 'verified' or not verified['quarantined_identities_absent_from_datasets_and_links']
            or not verified['quarantine_raw_fields_and_source_hashes_verified']):
        raise ValueError('unverified_partial_silver')
    silver_hash, quarantine_hash = digest(silver), digest(quarantine)
    if silver_hash != verified['datasets_sha256'] or quarantine_hash != verified['quarantine_sha256']:
        raise ValueError('input_hash_mismatch')
    quarantined = json.loads(quarantine.read_text(encoding='utf-8'))
    if quarantined['status'] != 'partial_quarantined':
        raise ValueError('invalid_quarantine_status')
    blocked = {(source, tuple(row['identity'])) for source, rows in quarantined['quarantined'].items() for row in rows}
    counts: Counter[str] = Counter()
    missing: Counter[str] = Counter()
    dataset_rows = 0
    with tempfile.TemporaryDirectory(prefix='industry-features-') as folder:
        staged = Path(folder) / 'features.jsonl'
        connection = sqlite3.connect(Path(folder) / 'seen.sqlite')
        try:
            connection.execute('CREATE TABLE seen (source TEXT, identity TEXT, digest TEXT, PRIMARY KEY(source,identity))')
            with staged.open('w', encoding='utf-8') as stream:
                for section, source, row in silver_rows(silver):
                    if (source, tuple(row.get('identity') or ())) in blocked:
                        raise ValueError('quarantined_identity_in_silver')
                    if section != 'datasets':
                        continue
                    dataset_rows += 1
                    if source not in FEATURE_FIELDS:
                        continue
                    item = feature(source, row)
                    identity = json.dumps(row['identity'])
                    fingerprint = hashlib.sha256(json.dumps(row['fields'], sort_keys=True).encode()).hexdigest()
                    previous = connection.execute('SELECT digest FROM seen WHERE source=? AND identity=?', (source, identity)).fetchone()
                    if previous:
                        if previous[0] != fingerprint:
                            raise ValueError('conflicting_feature_identity')
                        raise ValueError('duplicate_feature_identity')
                    connection.execute('INSERT INTO seen VALUES (?,?,?)', (source, identity, fingerprint))
                    counts[source] += 1
                    missing.update(f'{source}.{field}' for field, value in item['values'].items() if value is None)
                    stream.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + '\n')
            if dataset_rows != verified['accepted_rows']:
                raise ValueError('accepted_row_count_mismatch')
            result = {'status': 'partial_quarantined', 'usage': '원천 식별키별 로컬 연구 피처. 점포·모델·API 미연결.',
                'input_silver': str(silver), 'input_silver_sha256': silver_hash,
                'quarantine_path': str(quarantine), 'quarantine_sha256': quarantine_hash,
                'verification_path': str(verification), 'verification_sha256': digest(verification),
                'accepted_silver_rows': dataset_rows, 'feature_rows': sum(counts.values()),
                'rows_by_source': dict(counts), 'missing_by_field': dict(missing),
                'feature_fields': FEATURE_FIELDS, 'output': str(output), 'output_sha256': digest(staged),
                'limitations': ['정원·일시수용능력은 재원생 실측이 아니다.',
                    'SITEAREA는 원천 소재지면적 필드이며 공실 가용면적이 아니다. 단위 환산 없음.',
                    '원천 휴폐업·등록 상태를 보존한다. 현재 영업 전수 또는 예측시점 가용 피처가 아니다.',
                    '학교·학생 원천은 코드 자동 연결 없이 이번 피처 대상에서 제외했다.',
                    '상호·주소 후보로 점포를 확정하지 않는다. 라벨·매출·권리금·성공 확률 생성 없음.']}
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('xb') as destination, staged.open('rb') as source_stream:
                import shutil
                shutil.copyfileobj(source_stream, destination)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with report_path.open('x', encoding='utf-8') as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
            return result
        finally:
            connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('silver', type=Path)
    parser.add_argument('--verification', type=Path, required=True)
    parser.add_argument('--quarantine', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.silver, args.verification, args.quarantine, args.output, args.report)
    print(json.dumps({'status': result['status'], 'feature_rows': result['feature_rows']}, ensure_ascii=False))
