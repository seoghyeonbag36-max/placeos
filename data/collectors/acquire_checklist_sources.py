"""체크리스트 원천 확보: 응답 원본·범위·해시를 보존하고 Gold를 변경하지 않는다.

실행: python -m data.collectors.acquire_checklist_sources
인증키·인증 URL·예외 본문은 기록하지 않는다. 새 실행 디렉터리만 생성한다.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import zipfile

import requests

from data.collectors.common import BRONZE, load_env
from data.config.page_hubs import ACTIVE_HUBS
from data.config.rone_districts import SERIES_TABLES

LOCK = threading.Lock()


def main() -> None:
    load_env()
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    root = BRONZE / 'api_acquisition' / now.strftime('%Y-%m-%d') / now.strftime('%H%M%S')
    root.mkdir(parents=True, exist_ok=False)
    entries: list[dict] = []
    secrets = [os.environ.get(k, '') for k in (
        'DATA_GO_KR_SERVICE_KEY', 'SEOUL_OPENAPI_KEY', 'REB_RONE_API_KEY', 'EUM_API_KEY')]

    def record(item: dict) -> None:
        with LOCK:
            entries.append(item)
            (root / 'manifest.json').write_text(json.dumps({
                'started_at': now.isoformat(), 'entries': entries,
                'scope': '공공 원천 확보. 원본 페이지 보존; 부분 수집과 전량 수집 구분. Gold 미변경.',
            }, ensure_ascii=False, indent=2), encoding='utf-8')
            print(item['source'], item['status'], item.get('rows', ''), flush=True)

    def fetch(name: str, url: str, params: dict | None = None, suffix: str = 'json') -> tuple[bytes, str]:
        r = requests.get(url, params=params, timeout=(12, 60))
        content = r.content
        # 서비스가 요청 URL·키를 오류 본문에 반사하면 원문을 저장하지 않는다.
        if any(s and s.encode() in content for s in secrets):
            raise ValueError('credential_echo')
        path = root / f'{name}.{suffix}'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as f:
            f.write(content)
        (path.with_suffix(path.suffix + '.meta.json')).write_text(json.dumps({
            'endpoint': re.sub(r'/[^/]+/json/', '/REDACTED/json/', url),
            'requested_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'http_status': r.status_code, 'content_type': r.headers.get('content-type'),
            'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        r.raise_for_status()
        return content, str(path.relative_to(root))

    def stores() -> None:
        key = os.environ.get('DATA_GO_KR_SERVICE_KEY', '')
        for slug, hub in ACTIVE_HUBS.items():
            n = 0
            try:
                for page in range(1, 101):
                    raw, _ = fetch(f'stores/{slug}/{page:03}',
                        'https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius', {
                            'serviceKey': key, 'type': 'json', 'numOfRows': 1000,
                            'pageNo': page, 'radius': hub.stores_radius_m, 'cx': hub.cx, 'cy': hub.cy})
                    body = json.loads(raw)['body']
                    rows = body.get('items') or []
                    total = int(body['totalCount'])
                    n += len(rows)
                    if n >= total:
                        record({'source': f'stores/{slug}', 'status': 'complete', 'rows': n,
                                'total': total, 'radius_m': hub.stores_radius_m})
                        break
                    if not rows:
                        raise ValueError('empty_page_before_total')
                    time.sleep(.15)
                else:
                    raise ValueError('page_limit')
            except Exception as e:
                record({'source': f'stores/{slug}', 'status': 'failed_or_partial', 'rows': n,
                        'error_type': type(e).__name__})

    def rone() -> None:
        for series, tables in SERIES_TABLES.items():
            for table in tables:
                n = 0
                try:
                    for page in range(1, 101):
                        raw, _ = fetch(f'rone/{table}/{page:03}',
                            'https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do', {
                                'KEY': os.environ.get('REB_RONE_API_KEY', ''), 'Type': 'json',
                                'pIndex': page, 'pSize': 1000, 'STATBL_ID': table, 'DTACYCLE_CD': 'QY'})
                        block = json.loads(raw)['SttsApiTblData']
                        total = int(block[0]['head'][0]['list_total_count'])
                        rows = block[1]['row']
                        n += len(rows)
                        if n >= total:
                            record({'source': f'rone/{table}', 'series': series, 'status': 'complete',
                                    'rows': n, 'total': total})
                            break
                        if not rows:
                            raise ValueError('empty_page_before_total')
                        time.sleep(.2)
                    else:
                        raise ValueError('page_limit')
                except Exception as e:
                    record({'source': f'rone/{table}', 'status': 'failed_or_partial', 'rows': n,
                            'error_type': type(e).__name__})

    def seoul() -> None:
        from data.collectors.seoul_trdar import SERVICES
        # 최근 완료 분기는 공표 전일 수 있으므로 최신 두 분기를 독립적으로 기록한다.
        jobs = [(s, q, True) for s in SERVICES.values() for q in
                ([''] if s == 'TbgisTrdarRelm' else ['20262', '20263'])]
        from data.collectors.seoul_licensing import SERVICES as LICENSES
        jobs += [(s, '', False) for s in LICENSES.values()]
        for service, quarter, full in jobs:
            n = 0
            name = f'seoul/{service}/{quarter or "all"}'
            try:
                for page in range(1, 101 if full else 2):
                    start = (page - 1) * 1000 + 1
                    url = (f'http://openapi.seoul.go.kr:8088/{os.environ.get("SEOUL_OPENAPI_KEY", "")}'
                           f'/json/{service}/{start}/{start+999}' + (f'/{quarter}' if quarter else ''))
                    raw, _ = fetch(f'{name}/{page:03}', url)
                    j = json.loads(raw)
                    if service not in j:
                        result = j.get('RESULT', {})
                        record({'source': name, 'status': 'no_data' if result.get('CODE') == 'INFO-200'
                                else 'api_error', 'code': result.get('CODE'), 'rows': n})
                        break
                    block = j[service]
                    total = int(block['list_total_count'])
                    rows = block.get('row') or []
                    n += len(rows)
                    if n >= total or not full:
                        record({'source': name, 'status': 'complete' if n >= total else 'sample_only',
                                'rows': n, 'total': total})
                        break
                    if not rows:
                        raise ValueError('empty_page_before_total')
                    time.sleep(.15)
                else:
                    raise ValueError('page_limit')
            except Exception as e:
                record({'source': name, 'status': 'failed_or_partial', 'rows': n,
                        'error_type': type(e).__name__})

    def eum() -> None:
        for filename in ['llmt', 'arhist', 'lrgt']:
            try:
                _, path = fetch(f'eum/{filename}',
                    f'https://www.eum.go.kr/web/lc/bi/data/{filename}.zip', suffix='zip')
                with zipfile.ZipFile(root / path) as archive:
                    bad = archive.testzip()
                    if bad:
                        raise ValueError('zip_crc')
                    members = [{'name': x.filename, 'bytes': x.file_size} for x in archive.infolist()]
                record({'source': f'eum/{filename}', 'status': 'downloaded_valid_zip',
                        'path': path, 'members': members,
                        'note': '다운로드 시점과 자료 기준일은 다름. 필지별 입점 판정 자료 아님.'})
            except Exception as e:
                record({'source': f'eum/{filename}', 'status': 'failed', 'error_type': type(e).__name__})
        raw, path = fetch('eum/api_catalog', 'https://www.data.go.kr/data/15058410/openapi.do', suffix='html')
        m = re.search(r'const swaggerJson = `(.*?)`;', raw.decode('utf-8'), re.S)
        if m:
            spec = json.loads(m.group(1))
            (root/'eum/swagger.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
            record({'source': 'eum/api_spec', 'status': 'downloaded', 'path': 'eum/swagger.json'})

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): fn.__name__ for fn in [stores, rone, seoul, eum]}
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception as e:
                record({'source': futures[f], 'status': 'failed', 'error_type': type(e).__name__})
    for source, reason in [
        ('neis', 'NEIS_API_KEY 미설정. 브라우저 미연결로 신규 신청 불가; 공개 파일 경로 추가 확인 필요'),
        ('kopis', 'KOPIS_API_KEY 미설정. 브라우저 미연결로 신규 신청 불가'),
        ('business_performance', '사업자 제공·동의 자료 및 POS/PMS/회계 연동 없음'),
        ('nts_status', '조회 대상 사업자등록번호 연결자료 없음; 무작위 번호 조회하지 않음'),
    ]:
        record({'source': source, 'status': 'needs_input', 'reason': reason})
    print('OUTPUT', root.as_posix(), flush=True)


if __name__ == '__main__':
    main()
