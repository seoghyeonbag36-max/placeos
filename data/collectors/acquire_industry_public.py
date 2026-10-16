"""5개 업종 공개자료 수집·기존 원본 감사. 키·가짜 데이터·부분본 승격을 금지한다."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import requests

from data.collectors.common import BRONZE, load_env

LICENSES = {
    'general_restaurants': 'LOCALDATA_072404', 'beauty': 'LOCALDATA_051801',
    'fitness': 'LOCALDATA_104201', 'golf': 'LOCALDATA_103101',
    'billiards': 'LOCALDATA_103201', 'pc_rooms': 'LOCALDATA_030505',
    'karaoke': 'LOCALDATA_030901', 'bars_entertainment': 'LOCALDATA_072302',
    'bars_danran': 'LOCALDATA_072301', 'sports_dojang': 'LOCALDATA_104101',
}


def validate_neis(pages: list[dict], service: str, id_field: str) -> dict:
    """총량·페이지 결과·서울 범위·키 중복을 모두 확인한다."""
    rows: list[dict] = []
    totals: set[int] = set()
    for page in pages:
        blocks = page.get(service)
        if not isinstance(blocks, list):
            raise ValueError('missing_service')
        for block in blocks:
            for head in block.get('head', []):
                if 'list_total_count' in head:
                    totals.add(int(head['list_total_count']))
                if 'RESULT' in head and head['RESULT'].get('CODE') != 'INFO-000':
                    raise ValueError('unsuccessful_page')
            rows.extend(block.get('row', []))
    ids = [r.get(id_field) for r in rows]
    complete = (bool(rows) and totals == {len(rows)} and all(ids)
                and len(set(ids)) == len(ids)
                and all(r.get('ATPT_OFCDC_SC_CODE') == 'B10' for r in rows))
    return {'complete': complete, 'rows': len(rows), 'reported_totals': sorted(totals),
            'unique_ids': len(set(ids)), 'scope': '서울교육청 B10'}


def audit_license(folder: Path, service: str) -> dict:
    """기존 서울 전량 원본을 재측정한다. 새 수집으로 표시하지 않는다."""
    files = sorted(p for p in folder.glob('*.json') if p.stem.isdigit())
    totals: set[int] = set()
    ids: set[tuple[str, str]] = set()
    n = duplicates = missing_ids = 0
    hashes: dict[str, str] = {}
    for path in files:
        raw = path.read_bytes()
        body = json.loads(raw).get(service, {})
        totals.add(int(body.get('list_total_count', -1)))
        for row in body.get('row', []):
            n += 1
            key = (str(row.get('OPNSFTEAMCODE') or '').strip(), str(row.get('MGTNO') or '').strip())
            if not all(key):
                missing_ids += 1
            elif key in ids:
                duplicates += 1
            ids.add(key)
        hashes[path.name] = hashlib.sha256(raw).hexdigest()
    return {'status': 'reused_verified' if files and totals == {n} and not duplicates and not missing_ids else 'incomplete_or_invalid',
            'service': service, 'rows': n, 'pages': len(files), 'reported_totals': sorted(totals),
            'duplicate_ids': duplicates, 'missing_ids': missing_ids,
            'identity_fields': ['OPNSFTEAMCODE', 'MGTNO'],
            'original_path': str(folder), 'original_collected_on': '2026-10-09', 'sha256': hashes,
            'note': '기존 원본 재검증. 현재 시점 영업 전수 또는 오늘 재수집이라는 뜻이 아님.'}


def request_raw(url: str, params: dict, path: Path, secrets: list[str]) -> dict:
    response = requests.get(url, params=params, timeout=(12, 45))
    if any(s.encode() in response.content for s in secrets if s):
        raise ValueError('credential_echo')
    # 본문이 오류여도 무키 원본을 보존한다. URL·요청 파라미터는 저장하지 않는다.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(response.content)
    response.raise_for_status()
    return response.json()


def collect_neis(root: Path, service: str, id_field: str, secrets: list[str]) -> dict:
    if not os.getenv('NEIS_API_KEY'):
        return {'status': 'blocked', 'reason': 'NEIS_API_KEY_missing'}
    pages: list[dict] = []
    try:
        for page in range(1, 101):
            body = request_raw(f'https://open.neis.go.kr/hub/{service}', {
                'KEY': os.environ['NEIS_API_KEY'], 'Type': 'json', 'pSize': 1000,
                'pIndex': page, 'ATPT_OFCDC_SC_CODE': 'B10'}, root / service / f'{page:03}.json', secrets)
            pages.append(body)
            if service not in body:
                return {'status': 'blocked', 'api_code': (body.get('RESULT') or {}).get('CODE'), 'pages': len(pages)}
            info = validate_neis(pages, service, id_field)
            print(f'{service} page={page} rows={info["rows"]}', flush=True)
            if info['complete']:
                return {'status': 'collected_complete', **info}
            if info['reported_totals'] and info['rows'] >= max(info['reported_totals']):
                return {'status': 'invalid', **info}
            if not any(block.get('row') for block in body[service]):
                break
        return {'status': 'partial', **validate_neis(pages, service, id_field)}
    except Exception as exc:
        return {'status': 'failed_or_partial', 'error_type': type(exc).__name__, 'pages': len(pages)}


def collect_school_locations(root: Path, secrets: list[str]) -> dict:
    if not os.getenv('DATA_GO_KR_SERVICE_KEY'):
        return {'status': 'blocked', 'reason': 'DATA_GO_KR_SERVICE_KEY_missing'}
    rows: list[dict] = []
    totals: set[int] = set()
    try:
        for page in range(1, 31):
            body = request_raw('https://api.data.go.kr/openapi/tn_pubr_public_elesch_mskul_lc_api', {
                'serviceKey': os.environ['DATA_GO_KR_SERVICE_KEY'], 'type': 'json',
                'pageNo': page, 'numOfRows': 1000}, root / 'school_locations' / f'{page:03}.json', secrets)
            response = body.get('response') or {}
            auth = (body.get('OpenAPI_ServiceResponse') or {}).get('cmmMsgHeader') or {}
            if auth:
                return {'status': 'blocked', 'api_code': auth.get('returnReasonCode'),
                        'reason': auth.get('errMsg')}
            header = response.get('header') or {}
            if header.get('resultCode') != '00':
                return {'status': 'blocked', 'api_code': header.get('resultCode')}
            data = response['body']
            batch = data.get('items') or []
            if isinstance(batch, dict):
                batch = batch.get('item', [])
            rows.extend(batch)
            totals.add(int(data['totalCount']))
            if len(rows) >= int(data['totalCount']):
                break
            if not batch:
                break
        ids = [r.get('schoolId') for r in rows]
        complete = bool(rows) and totals == {len(rows)} and all(ids) and len(set(ids)) == len(ids)
        return {'status': 'collected_complete' if complete else 'partial', 'rows': len(rows),
                'reported_totals': sorted(totals), 'scope': '전국',
                'seoul_rows': sum(str(r.get('cddcNm', '')).startswith('서울') for r in rows)}
    except Exception as exc:
        return {'status': 'failed_or_partial', 'error_type': type(exc).__name__, 'rows': len(rows)}


def collect_school_file(root: Path, secrets: list[str]) -> dict:
    """공식 다운로드 버튼과 같은 공개 파일 경로. OpenAPI 권한과 별개다."""
    try:
        folder = root / 'school_locations_file'
        header = request_raw('https://www.data.go.kr/download/columList.json',
                             {'pk': '15021148', 'ext': 'JSON'}, folder / 'header.json', secrets)
        total = int(header['totalCount'])
        table = header['tableVO']
        rows: list[dict] = []
        for page in range(1, (total + 9999) // 10000 + 1):
            batch = request_raw('https://www.data.go.kr/download/standard.json', {
                'publicDataPk': '15021148', 'colNmList': table['colNmList'],
                'svcTableNm': table['svcTableNm'], 'totalCount': total,
                'perPage': 10000, 'page': page}, folder / f'{page:03}.json', secrets)
            if not isinstance(batch, list):
                raise ValueError('not_a_list')
            rows.extend(batch)
        ids = [r.get('SCHOOL_ID') for r in rows]
        complete = bool(rows) and len(rows) == total and all(ids) and len(set(ids)) == len(ids)
        return {'status': 'collected_complete' if complete else 'invalid',
                'rows': len(rows), 'reported_total': total,
                'seoul_rows': sum(str(r.get('CDDC_NM', '')).startswith('서울') for r in rows),
                'reference_dates': sorted({str(r.get('REFERENCE_DATE')) for r in rows}),
                'method': '공공데이터포털 표준데이터 공식 파일 다운로드', 'scope': '전국'}
    except Exception as exc:
        return {'status': 'failed_or_partial', 'error_type': type(exc).__name__}


def collect_school_students(root: Path, secrets: list[str]) -> dict:
    """학교알리미 공개용 데이터 화면과 같은 조회. 로그인·개인 키를 사용하지 않는다."""
    folder = root / 'school_students'
    folder.mkdir(parents=True, exist_ok=False)
    results = []
    try:
        session = requests.Session()
        form = session.get('https://www.schoolinfo.go.kr/ng/go/pnnggo_a01_l3.do',
                           params={'GO_NO': '09'}, timeout=(12, 45))
        form.raise_for_status()
        (folder / 'public_form.html').write_bytes(form.content)
        # 공개 페이지가 조회에 사용하는 공용 문자열이다. 계정 인증키가 아니다.
        match = re.search(r'APIKEY\s*:\s*"([^"]+)"', form.text)
        if not match:
            raise ValueError('public_form_changed')
        public_token = match.group(1)
        for year in ('2024', '2025', '2026'):
            for kind in ('02', '03', '04'):
                response = session.post('https://www.schoolinfo.go.kr/openData.do', data={
                    'APIKEY': public_token, 'APITYPE': '09', 'DEPTHNO': '0',
                    'SCHULKNDCODE': kind, 'PBANYR': year, 'LCTNSCCODE': '01'}, timeout=(12, 45))
                if any(s.encode() in response.content for s in secrets if s):
                    raise ValueError('credential_echo')
                (folder / f'{year}_{kind}.json').write_bytes(response.content)
                response.raise_for_status()
                body = response.json()
                rows = body.get('list')
                if not isinstance(rows, list) or not rows:
                    raise ValueError('no_data_list')
                results.append({'year': year, **validate_student_rows(rows, kind)})
        valid = all(r['region_unique_check'] for r in results)
        caveat = any(r['unexpected_kind_rows'] for r in results)
        return {'status': ('collected_with_scope_caveat' if caveat else 'collected_scope_validated') if valid else 'invalid',
                'scopes': results, 'rows': sum(r['rows'] for r in results),
                'scope': '서울 초·중·고 학년별·학급별 학생수 공개 응답, 2024~2026',
                'note': '학교연도 관측 수. 공시 제외·학교 범위 차이 때문에 위치 목록과 일치한다고 가정하지 않음.'}
    except Exception as exc:
        return {'status': 'failed_or_partial', 'error_type': type(exc).__name__, 'scopes': results}


def validate_student_rows(rows: list[dict], kind: str) -> dict:
    """요청 학제가 아닌 행을 삭제하거나 정답으로 바꾸지 않고 수를 밝힌다."""
    ids = [r.get('SCHUL_CODE') for r in rows]
    counts = {k: sum(str(r.get('SCHUL_KND_SC_CODE')) == k for r in rows)
              for k in sorted({str(r.get('SCHUL_KND_SC_CODE')) for r in rows})}
    return {'school_kind': kind, 'rows': len(rows), 'returned_kind_counts': counts,
            'unexpected_kind_rows': sum(v for k, v in counts.items() if k != kind),
            'region_unique_check': bool(rows) and all(ids) and len(set(ids)) == len(ids)
                                   and all(r.get('LCTN_SC_CODE') == '01' for r in rows)}


def run(date: str) -> Path:
    load_env()
    stamp = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%H%M%S')
    root = BRONZE / 'industry_public' / date / stamp
    root.mkdir(parents=True, exist_ok=False)
    secrets = [os.getenv(k, '') for k in ('NEIS_API_KEY', 'SEOUL_OPENAPI_KEY', 'DATA_GO_KR_SERVICE_KEY')]
    results: dict = {}
    for service, field in [('acaInsTiInfo', 'ACA_ASNUM'), ('schoolInfo', 'SD_SCHUL_CODE')]:
        results[service] = collect_neis(root, service, field, secrets)
    results['school_locations'] = collect_school_locations(root, secrets)
    if results['school_locations']['status'] != 'collected_complete':
        results['school_locations_file'] = collect_school_file(root, secrets)
    results['school_students'] = collect_school_students(root, secrets)
    previous = BRONZE / 'api_acquisition/2026-10-09/215933/seoul'
    for name, service in LICENSES.items():
        try:
            results[name] = audit_license(previous / service / 'all', service)
        except Exception as exc:
            results[name] = {'status': 'audit_failed', 'error_type': type(exc).__name__}
        print(name, results[name]['status'], results[name].get('rows'), flush=True)
    hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in root.rglob('*.json')}
    manifest = {'collected_at': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(), 'results': results,
                'new_files_sha256': hashes, 'scope': '공개 원본 수집·재검증, 서비스·모델 미배선'}
    (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('manifest', root / 'manifest.json', flush=True)
    return root


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True)
    args = parser.parse_args()
    datetime.strptime(args.date, '%Y-%m-%d')
    run(args.date)
