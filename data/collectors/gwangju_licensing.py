"""행안부 일반음식점 API에서 광주 5개 구의 인허가 원본을 수집한다.

도로명 주소로 관측한 개방자치단체코드를 사용한다. 새 키를 만들지 않고 기존 공공데이터
키로 권한을 확인한다. 업종은 일반음식점 한 종류이며 전체 업종으로 확대 해석하지 않는다.
"""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from data.collectors.common import bronze_dir, load_env

URL = 'https://apis.data.go.kr/1741000/general_restaurants/info'
GUS = ('동구', '서구', '남구', '북구', '광산구')
ROOT = Path(__file__).resolve().parents[2]
_LOCAL = threading.local()


def fetch(params: dict) -> dict:
    session = getattr(_LOCAL, 'session', None)
    if session is None:
        session = _LOCAL.session = requests.Session()
    response = None
    for attempt in range(3):
        try:
            response = session.get(URL, params={
                'serviceKey': os.environ['DATA_GO_KR_SERVICE_KEY'], 'returnType': 'JSON',
                'pageNo': 1, 'numOfRows': 100, **params,
            }, timeout=40)
            if response.status_code < 500:
                break
        except requests.RequestException:
            if attempt == 2:
                raise RuntimeError('인허가 네트워크 재시도 실패') from None
        time.sleep(attempt + 1)
    if response is None:
        raise RuntimeError('인허가 응답 없음')
    if response.status_code != 200:
        raise RuntimeError(f'인허가 HTTP {response.status_code}')
    data = response.json()
    envelope = data.get('response', {})
    if str(envelope.get('header', {}).get('resultCode')) not in ('0', '00'):
        raise RuntimeError('인허가 권한 또는 응답 오류')
    if 'totalCount' not in envelope.get('body', {}):
        raise RuntimeError('인허가 전체 건수 없음')
    return data


def rows_of(data: dict) -> list[dict]:
    rows = data['response']['body'].get('items', {}) or {}
    rows = rows.get('item', []) if isinstance(rows, dict) else rows
    return [rows] if isinstance(rows, dict) else rows


def collect_gu(gu: str) -> dict:
    target = bronze_dir('gwangju_licensing')
    # 재개 시 완주 표식이 있는 구만 재사용한다. 원본은 덮어쓰지 않는다.
    marker = target / f'{gu}_complete.json'
    if marker.exists():
        return json.loads(marker.read_text(encoding='utf-8'))
    codes: set[str] = set()
    for index, city in enumerate(('광주광역시', '전남광주통합특별시')):
        probe_file = target / f'{gu}_probe_{index}.json'
        probe = (json.loads(probe_file.read_text(encoding='utf-8')) if probe_file.exists()
                 else fetch({'cond[ROAD_NM_ADDR::LIKE]': f'{city} {gu}', 'numOfRows': 1}))
        if not probe_file.exists():
            probe_file.write_text(json.dumps(probe, ensure_ascii=False), encoding='utf-8')
        for row in rows_of(probe):
            if f'{city} {gu}' not in str(row.get('ROAD_NM_ADDR', '')):
                raise ValueError('주소 필터 미적용 — 인허가 수집 중단')
            codes.add(str(row['OPN_ATMY_GRP_CD']))
    if not codes:
        raise ValueError(f'{gu}: 자치단체 코드 관측 실패')
    all_rows: dict[str, dict] = {}
    for code in sorted(codes):
        page = 1
        received = 0
        while True:
            path = target / f'{gu}_{code}_{page:04d}.json'
            data = (json.loads(path.read_text(encoding='utf-8')) if path.exists()
                    else fetch({'cond[OPN_ATMY_GRP_CD::EQ]': code, 'pageNo': page}))
            rows = rows_of(data)
            if any(str(row.get('OPN_ATMY_GRP_CD')) != code for row in rows):
                raise ValueError('자치단체 코드 필터 미적용')
            if not path.exists():
                path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            received += len(rows)
            for row in rows:
                all_rows[row['MNG_NO']] = row
            total = int(data['response']['body']['totalCount'])
            if received == total:
                break
            if not rows or received > total or page >= 2000:
                raise ValueError('인허가 부분 수집 — 완주 표식 미작성')
            page += 1
    report = {'gu': gu, 'codes': sorted(codes), 'rows': len(all_rows),
              'active_rows': sum(r.get('SALS_STTS_CD') == '01' for r in all_rows.values()),
              'source': URL, 'industry': '일반음식점', 'complete': True}
    marker.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(gu, 'complete', len(all_rows), flush=True)
    return report


def main() -> None:
    load_env()
    if not os.getenv('DATA_GO_KR_SERVICE_KEY'):
        raise SystemExit('DATA_GO_KR_SERVICE_KEY 미설정')
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = {gu: pool.submit(collect_gu, gu) for gu in GUS}
        reports = []
        for gu, job in jobs.items():
            try:
                reports.append(job.result())
            except Exception as exc:
                # 요청 URL의 키 노출을 막기 위해 예외 종류만 기록한다.
                reports.append({'gu': gu, 'complete': False, 'error_type': type(exc).__name__})
    target = ROOT / 'reports' / 'gwangju_licensing_collection_2026-10-28.json'
    target.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not all(r['complete'] for r in reports):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
