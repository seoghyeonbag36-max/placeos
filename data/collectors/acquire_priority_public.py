"""NEIS 서울 전량과 생활인구 기간 확대. Gold는 수정하지 않는다."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import requests
from data.collectors.common import BRONZE, load_env
from data.collectors.living_population_hourly import collect, hub_adong_codes


def main() -> None:
    load_env()
    root = BRONZE / 'priority_acquisition' / dt.datetime.now().strftime('%Y-%m-%d/%H%M%S')
    root.mkdir(parents=True, exist_ok=False)
    entries: list[dict] = []
    try:
        rows: list[dict] = []
        totals: set[int] = set()
        for page in range(1, 101):
            response = requests.get('https://open.neis.go.kr/hub/acaInsTiInfo', params={
                'KEY': os.environ['NEIS_API_KEY'], 'Type': 'json', 'pIndex': page,
                'pSize': 1000, 'ATPT_OFCDC_SC_CODE': 'B10'}, timeout=(15, 60))
            response.raise_for_status()
            if os.environ['NEIS_API_KEY'].encode() in response.content:
                raise ValueError('credential_echo')
            body = response.json()['acaInsTiInfo']
            header = body[0]['head']
            total = next(x['list_total_count'] for x in header if 'list_total_count' in x)
            code = next(x['RESULT']['CODE'] for x in header if 'RESULT' in x)
            if code != 'INFO-000':
                raise ValueError('api_result')
            batch = body[1]['row']
            if not batch or any(r['ATPT_OFCDC_SC_CODE'] != 'B10' for r in batch):
                raise ValueError('scope_or_empty_page')
            target = root / f'neis_{page:03}.json'
            target.write_bytes(response.content)
            rows.extend(batch)
            totals.add(int(total))
            print(f'NEIS page={page} rows={len(rows)} total={total}', flush=True)
            if len(rows) >= total:
                break
        ids = [(r['ATPT_OFCDC_SC_CODE'], r['ACA_ASNUM']) for r in rows]
        passed = totals == {len(rows)} and len(ids) == len(set(ids))
        entries.append({'source': 'neis_seoul', 'rows': len(rows), 'totals': sorted(totals),
                        'neis_count_scope_unique_check': passed})
    except Exception as exc:
        entries.append({'source': 'neis_seoul', 'status': 'failed', 'error_type': type(exc).__name__})
    try:
        result = collect(days=61)
        checks = []
        expected_codes = hub_adong_codes()
        for date in result:
            iso = f'{date[:4]}-{date[4:6]}-{date[6:]}'
            path = BRONZE / 'seoul' / iso / 'living_population_hourly.json'
            records = json.loads(path.read_text(encoding='utf-8'))
            keys = {(str(r['STDR_DE_ID']), str(r['ADSTRD_CODE_SE']), str(r['TMZON_PD_SE'])) for r in records}
            codes = {str(r['ADSTRD_CODE_SE']) for r in records}
            checks.append({'date': date, 'rows': len(records), 'observed_codes': len(codes),
                'missing_mapped_codes': sorted(expected_codes - codes),
                'living_date_unique_hours_check': bool(records) and len(keys) == len(records)
                    and all(str(r['STDR_DE_ID']) == date for r in records)
                    and all(len({str(r['TMZON_PD_SE']) for r in records
                        if str(r['ADSTRD_CODE_SE']) == code}) == 24 for code in codes),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        entries.append({'source': 'living_population_hourly', 'collected_dates': result, 'checks': checks,
                        'note': '기존 날짜는 재사용. 실제 제공 날짜 기준이며 계절 전체를 보장하지 않음'})
    except Exception as exc:
        entries.append({'source': 'living_population_hourly', 'status': 'failed', 'error_type': type(exc).__name__})
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('neis_*.json')}
    (root / 'manifest.json').write_text(json.dumps({'entries': entries, 'sha256': hashes},
        ensure_ascii=False, indent=2), encoding='utf-8')
    print('manifest:', root / 'manifest.json', flush=True)


if __name__ == '__main__':
    main()
