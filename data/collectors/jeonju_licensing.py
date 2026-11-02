"""전주 일반음식점 인허가. 두 구가 같은 개방자치단체 코드면 전주시를 한 번만 받는다."""
from __future__ import annotations

import json
from pathlib import Path

from data.collectors.common import bronze_dir, load_env
from data.collectors.gwangju_licensing import fetch, rows_of, URL

ROOT = Path(__file__).resolve().parents[2]
GUS = ('완산구', '덕진구')


def read_or_fetch(path: Path, params: dict) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    data = fetch(params)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return data


def collect() -> dict:
    load_env()
    target = bronze_dir('jeonju_licensing')
    marker = target / 'city_complete.json'
    if marker.exists():
        return json.loads(marker.read_text(encoding='utf-8'))
    codes = set()
    for gu in GUS:
        for index, city in enumerate(('전북특별자치도 전주시', '전라북도 전주시')):
            data = read_or_fetch(target / f'{gu}_probe_{index}.json',
                                 {'cond[ROAD_NM_ADDR::LIKE]': f'{city} {gu}', 'numOfRows': 1})
            for row in rows_of(data):
                if f'{city} {gu}' not in str(row.get('ROAD_NM_ADDR', '')):
                    raise ValueError('전주 주소 필터 미적용')
                codes.add(str(row['OPN_ATMY_GRP_CD']))
    if not codes:
        raise ValueError('전주 자치단체 코드 관측 실패')
    rows_by_id = {}
    expected = 0
    for code in sorted(codes):
        received = 0
        total = None
        for page in range(1, 2001):
            # 앞서 받은 구별 파일도 같은 코드·페이지다. 원본을 다시 받지 않고 참조한다.
            cached = sorted(target.glob(f'*_{code}_{page:04d}.json'))
            path = cached[0] if cached else target / f'city_{code}_{page:04d}.json'
            data = read_or_fetch(path, {'cond[OPN_ATMY_GRP_CD::EQ]': code, 'pageNo': page})
            rows = rows_of(data)
            count = int(data['response']['body']['totalCount'])
            if total is not None and count != total:
                raise ValueError('수집 중 전체 건수 변경 — 완주 판정 중단')
            total = count
            if any(str(r.get('OPN_ATMY_GRP_CD')) != code for r in rows):
                raise ValueError('인허가 자치단체 코드 혼입')
            for r in rows:
                if r['MNG_NO'] in rows_by_id:
                    raise ValueError('인허가 페이지 중복 — 완주 판정 중단')
                rows_by_id[r['MNG_NO']] = r
            received += len(rows)
            if received == total:
                expected += total
                break
            if not rows or received > total:
                raise ValueError('인허가 부분 수집')
        else:
            raise ValueError('인허가 페이지 상한')
    if len(rows_by_id) != expected:
        raise ValueError('인허가 고유 관리번호 건수 불일치')
    # 어댑터는 완주 검증된 단일 원본만 읽는다. 구별 페이지를 합치면 도시 전체가 중복된다.
    (target / 'city_rows.json').write_text(json.dumps(list(rows_by_id.values()), ensure_ascii=False), encoding='utf-8')
    report = {'complete': True, 'codes': sorted(codes), 'rows': len(rows_by_id),
              'source': URL, 'industry': '일반음식점',
              'note': '개방자치단체 코드 합집합을 각각 한 번 수집. 전체 영업·폐업 상태 포함'}
    marker.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'reports' / 'jeonju_licensing_collection.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report


if __name__ == '__main__':
    collect()
