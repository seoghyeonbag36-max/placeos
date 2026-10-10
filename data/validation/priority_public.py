"""우선 수집 원본의 건수·키·날짜·시간대·비밀 비노출 검증."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
from data.collectors.common import BRONZE, load_env
from data.collectors.living_population_hourly import hub_adong_codes


def main() -> None:
    load_env()
    root = Path(sys.argv[1]).resolve()
    if not root.is_relative_to((BRONZE / 'priority_acquisition').resolve()):
        raise ValueError('수집 경로 밖은 검증하지 않음')
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    rows: list[dict] = []
    totals: set[int] = set()
    secret_check = True
    hashes_check = True
    for path in sorted(root.glob('neis_*.json')):
        raw = path.read_bytes()
        hashes_check &= hashlib.sha256(raw).hexdigest() == manifest['sha256'][path.name]
        secret_check &= os.environ['NEIS_API_KEY'].encode() not in raw
        body = json.loads(raw)['acaInsTiInfo']
        totals.add(next(x['list_total_count'] for x in body[0]['head'] if 'list_total_count' in x))
        rows.extend(body[1]['row'])
    ids = {(r['ATPT_OFCDC_SC_CODE'], r['ACA_ASNUM']) for r in rows}
    neis_check = bool(rows) and totals == {len(rows)} and len(ids) == len(rows)
    neis_check &= all(r['ATPT_OFCDC_SC_CODE'] == 'B10' for r in rows)
    days = []
    missing_files = []
    expected_codes = hub_adong_codes()
    for offset in range(61):
        date = (dt.date(2026, 7, 31) - dt.timedelta(days=offset)).isoformat()
        path = BRONZE / 'seoul' / date / 'living_population_hourly.json'
        if not path.exists():
            missing_files.append(date)
            continue
        raw = path.read_bytes()
        batch = json.loads(raw)
        codes = {str(r['ADSTRD_CODE_SE']) for r in batch}
        keys = {(str(r['STDR_DE_ID']), str(r['ADSTRD_CODE_SE']), str(r['TMZON_PD_SE'])) for r in batch}
        passed = bool(batch) and len(keys) == len(batch)
        passed &= all(str(r['STDR_DE_ID']) == date.replace('-', '') for r in batch)
        passed &= codes <= expected_codes
        passed &= all(len({str(r['TMZON_PD_SE']) for r in batch
            if str(r['ADSTRD_CODE_SE']) == code}) == 24 for code in codes)
        secret_check &= os.environ['SEOUL_OPENAPI_KEY'].encode() not in raw
        days.append({'date': date, 'rows': len(batch), 'observed_codes': len(codes),
            'missing_mapped_codes': sorted(expected_codes - codes), 'passed': passed,
            'sha256': hashlib.sha256(raw).hexdigest()})
    checks = {'neis_count_scope_unique_check': neis_check, 'raw_hash_check': hashes_check,
        'living_date_unique_hours_check': not missing_files and all(x['passed'] for x in days),
        'credential_absence_check': secret_check}
    result = {'checks': checks, 'neis_rows': len(rows), 'living_dates': len(days),
        'living_rows': sum(x['rows'] for x in days), 'mapped_codes': len(expected_codes),
        'missing_files': missing_files, 'days': days,
        'note': '행정동 미매칭은 별도 결손. 관측된 행의 무결성 통과가 거점 전체 커버리지를 뜻하지 않음'}
    (root / 'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print({k: v for k, v in result.items() if k not in ['days', 'note']})
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
