"""수집 원본에서 최종 인수 명세를 재계산한다. 문서의 행 수를 복사하지 않는다."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from data.collectors.acquire_industry_public import LICENSES, audit_license, validate_neis, validate_student_rows
from data.collectors.common import BRONZE, load_env
from data.config.page_hubs import ACTIVE_HUBS


def audit_stores(previous: Path) -> dict:
    results = {}
    unique_ids: set[str] = set()
    for slug in ACTIVE_HUBS:
        folder = previous / 'stores' / slug
        if slug == 'suyu':
            folder = previous / 'recovery/stores/suyu'
        rows = []
        totals = set()
        for path in sorted(p for p in folder.glob('*.json') if p.stem.isdigit()):
            data = json.loads(path.read_bytes())['body']
            rows.extend(data.get('items') or [])
            totals.add(int(data['totalCount']))
        ids = [r.get('bizesId') for r in rows]
        complete = bool(rows) and totals == {len(rows)} and all(ids) and len(set(ids)) == len(ids)
        results[slug] = {'complete': complete, 'rows': len(rows), 'reported_totals': sorted(totals)}
        unique_ids.update(i for i in ids if i)
    return {'status': 'reused_verified' if all(r['complete'] for r in results.values()) else 'incomplete_or_invalid',
            'original_path': str(previous / 'stores'), 'original_collected_on': '2026-10-09',
            'active_hubs_n': len(ACTIVE_HUBS), 'hub_rows_sum': sum(r['rows'] for r in results.values()),
            'unique_store_ids': len(unique_ids), 'hubs': results,
            'note': '거점 반경 중복은 점포 ID로 구분. 재검증이지 재수집은 아니다.'}


def report(run: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    results = {}
    for service, field in [('acaInsTiInfo', 'ACA_ASNUM'), ('schoolInfo', 'SD_SCHUL_CODE')]:
        pages = [json.loads(p.read_bytes()) for p in sorted((run / service).glob('*.json'))]
        info = validate_neis(pages, service, field)
        results[service] = {'status': 'collected_complete' if info['complete'] else 'invalid', **info}
    school_folder = run / 'school_locations_file'
    header = json.loads((school_folder / 'header.json').read_bytes())
    schools = [r for p in sorted(school_folder.glob('*.json')) if p.stem.isdigit()
               for r in json.loads(p.read_bytes())]
    ids = [r.get('SCHOOL_ID') for r in schools]
    results['school_locations'] = {
        'status': 'collected_complete' if len(schools) == int(header['totalCount']) and all(ids) and len(set(ids)) == len(ids) else 'invalid',
        'rows': len(schools), 'reported_total': header['totalCount'],
        'seoul_rows': sum(str(r.get('CDDC_NM', '')).startswith('서울') for r in schools),
        'reference_dates': sorted({str(r.get('REFERENCE_DATE')) for r in schools}),
        'method': '공식 파일 다운로드. API 코드30을 받은 뒤 공개 파일로 확보'}
    scopes = []
    for path in sorted((run / 'school_students').glob('????_??.json')):
        year, kind = path.stem.split('_')
        scopes.append({'year': year, **validate_student_rows(json.loads(path.read_bytes())['list'], kind)})
    ok = len(scopes) == 9 and all(s['region_unique_check'] for s in scopes)
    results['school_students'] = {
        'status': 'collected_with_scope_caveat' if ok and any(s['unexpected_kind_rows'] for s in scopes)
                  else 'collected_scope_validated' if ok else 'partial_or_invalid',
        'rows': sum(s['rows'] for s in scopes), 'scopes': scopes,
        'unexpected_kind_rows': sum(s['unexpected_kind_rows'] for s in scopes),
        'note': '중학교 요청에 학제코드25가 매년1행 포함됨. 원본보존. 학교연도 관측 수로서 고유 학교 수 아님.'}
    previous = BRONZE / 'api_acquisition/2026-10-09/215933'
    results['licenses'] = {n: audit_license(previous / 'seoul' / s / 'all', s) for n, s in LICENSES.items()}
    results['stores'] = audit_stores(previous)
    secrets = [os.getenv(k, '').encode() for k in ('NEIS_API_KEY', 'SEOUL_OPENAPI_KEY', 'DATA_GO_KR_SERVICE_KEY') if os.getenv(k)]
    raw_files = [p for p in run.rglob('*') if p.is_file()]
    credential_hits = [str(p.relative_to(run)) for p in raw_files if any(k in p.read_bytes() for k in secrets)]
    if credential_hits:
        raise ValueError('credential_echo_in_saved_files')
    result = {'generated_at': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(), 'run': str(run),
              'results': results, 'credential_absence_check': True,
              'new_files_sha256': {str(p.relative_to(run)): hashlib.sha256(p.read_bytes()).hexdigest() for p in raw_files},
              'uncollected': {
                  'private_operations': '제공받은 사업자 POS·예약·회원관리 원본과 계정 접근권한 없음. 요청 안내 문서 참조.',
                  'physical_fit': '전력·환기·방음·하중·실제 가용면적은 매물별 관리주체 확인 필요.'},
              'note': '새 수집·기존 재검증 구분. 기존 Gold·서빙·추천 모델에는 미반영.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    load_env()
    result = report(args.run, args.output)
    print(json.dumps({k: {'status': v.get('status'), 'rows': v.get('rows')}
                      for k, v in result['results'].items() if k != 'licenses'}, ensure_ascii=False))
