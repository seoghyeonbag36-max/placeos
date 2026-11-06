"""광주·전주 Gold 검증 인계 후 부산 점포 전수→지번 대장→관측 Gold를 수집한다.

소상공인 상가정보에 등재된 부산 점포가 범위다. 도시 전체 건물·공식 상권 경계가 아니다.
기존 지역 원장·쿼터·Gold는 보존하고 부산 작업표·상태를 분리한다.
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import collect_regional_research_ledgers as source

BUSAN_PLAN = ROOT / 'data/silver/busan_research_ledgers/targets.json'
BUSAN_STATE = ROOT / 'reports/busan_research_ledger_collection.json'
BUSAN_GOLD = ROOT / 'reports/busan_research_gold.json'
STORES = ROOT / 'data/bronze/busan_research_stores'


def handoff_ready() -> bool:
    """수집기에서 원본·Gold 검증을 통과한 인계만 받는다."""
    state = source.read(ROOT / 'reports/regional_research_ledger_collection.json')
    seq = state.get('sequence', {})
    return (state.get('status') == 'busan_queued' and seq.get('phase') == 'busan'
            and seq.get('handoff_gold_sha256') == source.fingerprint(
                ROOT / 'reports/regional_research_gold.json'))


def parse_stores(payload: dict, total: int | None = None) -> tuple[int, list[dict]]:
    """부분·중복·지역 밖 응답을 정상 원본으로 저장하지 않는다."""
    body = payload.get('body', {})
    count, rows = body.get('totalCount'), body.get('items')
    if (payload.get('header', {}).get('resultCode') != '00'
            or not isinstance(count, int) or count <= 0 or not isinstance(rows, list) or not rows
            or len(rows) > count or (total is not None and total != count)):
        raise ValueError('BUSAN_STORE_RESPONSE_INVALID')
    if any(not isinstance(r, dict) or str(r.get('ctprvnCd')) != '26'
           or not r.get('bizesId') for r in rows):
        raise ValueError('BUSAN_STORE_SCOPE_INVALID')
    return count, rows


def fetch_stores() -> list[dict]:
    import requests
    from data.collectors.common import load_env
    from data.collectors.building_vacancy import BASE_SDSC
    load_env()
    rows, seen, total, page = [], set(), None, 1
    # 재개 때 같은 조사 스냅샷의 저장 페이지를 재사용한다. totalCount 변경은 실패한다.
    while total is None or len(rows) < total:
        if not source.ac_connected():
            raise source.PowerWait('AC_REQUIRED')
        path = STORES / f'page_{page:05d}.json'
        if path.exists():
            payload = source.read(path)
        else:
            try:
                response = requests.get(BASE_SDSC + '/storeListInDong', params=dict(
                    serviceKey=os.environ['DATA_GO_KR_SERVICE_KEY'], divId='ctprvnCd', key='26',
                    type='json', numOfRows=1000, pageNo=page), timeout=30)
                if response.status_code != 200:
                    raise ValueError('BUSAN_STORE_HTTP_ERROR')
                payload = response.json()
            except requests.RequestException:
                raise ValueError('BUSAN_STORE_NETWORK_ERROR') from None
        total, batch = parse_stores(payload, total)
        ids = [r['bizesId'] for r in batch]
        if len(set(ids)) != len(ids) or seen.intersection(ids) or len(rows) + len(batch) > total:
            raise ValueError('BUSAN_STORE_DUPLICATE_OR_OVERFLOW')
        if not path.exists():
            source.atomic_json(path, payload)
        seen.update(ids)
        rows.extend(batch)
        page += 1
        source.time.sleep(0.2)
    return rows


def build_plan(rows: list[dict]) -> dict:
    """행정동별 원본과 중복 제거한 건물 지번 작업표를 만든다."""
    groups = defaultdict(list)
    for row in rows:
        code = str(row.get('adongCd') or '')
        if not code.startswith('26') or not row.get('adongNm'):
            raise ValueError('BUSAN_ADMINISTRATIVE_CODE_MISSING')
        groups[code].append(row)
    locations, targets, unresolved = [], {}, []
    for code, stores in sorted(groups.items()):
        ident = 'research-busan-' + code
        path = STORES / 'normalized' / code / 'stores_raw.json'
        source.atomic_json(path, stores)
        with contextlib.redirect_stdout(io.StringIO()):
            buildings = source.group_by_building(stores)
        pnus, invalid = set(), []
        for key, building in buildings.items():
            pnu = str(building.get('lnoCd') or '')
            if not re.fullmatch(r'26\d{17}', pnu):
                invalid.append(key)
                unresolved.append(dict(location=ident, building_id=key, reason='PNU 누락·지역·형식 오류'))
                continue
            pnus.add(pnu)
            targets.setdefault(pnu, dict(pnu=pnu, locations=[]))['locations'].append(ident)
        locations.append(dict(id=ident, label=stores[0]['signguNm'] + ' ' + stores[0]['adongNm'],
            region='부산', source=path.relative_to(ROOT).as_posix(), source_sha256=source.fingerprint(path),
            pnus=sorted(pnus), unresolved=invalid))
    if not targets:
        raise ValueError('BUSAN_TARGETS_EMPTY')
    return dict(created_at=source.now().isoformat(), locations=locations, targets=list(targets.values()),
        unresolved=unresolved, legacy_sources={}, legacy_expos={}, seed=False,
        source='소상공인 상가정보 부산광역시 전체 조회 실응답',
        scope='부산 등재 점포의 기존 건물 그룹화 규칙에 잡힌 지번. 빈 건물·공식 상권 경계는 포함하지 않음')


def main() -> int:
    if not handoff_ready():
        return 0
    import msvcrt
    lock_path = ROOT / 'data/logs/busan-research-wrapper.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return 0
        if not source.ac_connected():
            return 0
        if not BUSAN_PLAN.exists():
            source.atomic_json(BUSAN_PLAN, build_plan(fetch_stores()))
        source.PLAN, source.STATE = BUSAN_PLAN, BUSAN_STATE
        source.RAW = ROOT / 'data/bronze/busan_research_ledgers/markers'
        source.LOG = ROOT / 'data/logs/busan-research-ledgers.log'
        source.LOCK = ROOT / 'data/logs/busan-research-ledgers.lock'
        source.FAILURES = ROOT / 'data/silver/busan_research_ledgers/failures.json'
        source.GOLD_REPORT = BUSAN_GOLD
        if not BUSAN_STATE.exists():
            state = source.initial_state(source.read(BUSAN_PLAN))
            prior = source.read(ROOT / 'reports/regional_research_ledger_collection.json')
            # 같은 서비스 키의 당일 호출량·쿼터 대기 시각을 새 지역에서도 보존한다.
            for endpoint, record in state['endpoints'].items():
                for key in ('day', 'calls_today', 'retry_after', 'auth_error', 'reason'):
                    if key in prior['endpoints'][endpoint]:
                        record[key] = prior['endpoints'][endpoint][key]
            source.save_state(state)
        result = source.worker(once=True)
        from data.pipelines import build_regional_ledger_gold as pipeline
        pipeline.REPORT = BUSAN_GOLD
        pipeline.run(source.read(BUSAN_PLAN), [])
        return result


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # API 요청 URL·비밀 키는 기록하지 않는다.
        (ROOT / 'data/logs').mkdir(parents=True, exist_ok=True)
        with (ROOT / 'data/logs/busan-research-wrapper.log').open('a', encoding='utf-8') as stream:
            stream.write(f'[{source.now().isoformat()}] {type(exc).__name__}\n')
        raise SystemExit(1)
