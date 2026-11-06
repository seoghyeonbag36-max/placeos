"""신규 탐색 위치 227곳의 전유부·층별개요 원본 수집 — 공개 거점·Gold는 변경하지 않는다.

Bronze 점포 → Silver 지번 작업표 → Bronze 건축HUB 페이지 원본 순으로 수집한다.
중복 지번은 한 번만 받고, 전유부의 기존 완주 원본은 출처를 검증해 재사용한다.
대형 전유부도 totalCount까지 받으며, 오류·쿼터·부분 페이지를 빈 대장으로 바꾸지 않는다.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import gzip
import io
import json
import os
import re
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.collectors.common import load_env
from data.collectors.building_vacancy import BASE_BLD, _jibun, group_by_building

KST = timezone(timedelta(hours=9))
REPORT = ROOT / 'reports/regional_hub_candidates_2026-11-03.json'
PLAN = ROOT / 'data/silver/regional_research_ledgers/targets_2026-11-03.json'
RAW = ROOT / 'data/bronze/regional_research_ledgers/2026-11-03'
STATE = ROOT / 'reports/regional_research_ledger_collection.json'
LOG = ROOT / 'data/logs/regional-research-ledgers.log'
LOCK = ROOT / 'data/logs/regional-research-ledgers.lock'
FAILURES = ROOT / 'data/silver/regional_research_ledgers/failures.json'
GOLD_REPORT = ROOT / 'reports/regional_research_gold.json'
AUTOMATION = ROOT / 'reports/regional_research_automation.json'
ENDPOINTS = {'expos': 'getBrExposPubuseAreaInfo', 'floors': 'getBrFlrOulnInfo'}
DAILY_GUARD = 10000


def now() -> datetime:
    return datetime.now(KST)


def atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f'.{os.getpid()}.tmp')
    tmp.write_bytes(value)
    # Windows에서 상태 조회·백신이 잠깐 파일을 열어도 진행 원장을 잃지 않는다.
    for attempt in range(8):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(min(0.1 * 2 ** attempt, 1.0))


def atomic_json(path: Path, value: dict | list) -> None:
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def read(path: Path) -> dict:
    content = gzip.decompress(path.read_bytes()).decode('utf-8') if path.suffix == '.gz' else path.read_text(encoding='utf-8')
    return json.loads(content)


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def say(message: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as stream:
        stream.write(f'[{now().isoformat(timespec="seconds")}] {message}\n')


def ac_connected() -> bool:
    """전원 상태가 불명확하면 AC로 보지 않는다. Windows 실측만 쓴다."""
    if os.name != 'nt':
        return False
    class Power(ctypes.Structure):
        _fields_ = [('ac', ctypes.c_ubyte), ('flags', ctypes.c_ubyte),
                    ('pct', ctypes.c_ubyte), ('reserved', ctypes.c_ubyte),
                    ('remaining', ctypes.c_uint32), ('full', ctypes.c_uint32)]
    status = Power()
    return bool(ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))) and status.ac == 1


def retry_after(moment: datetime) -> datetime:
    return (moment.astimezone(KST) + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)


def rollover(record: dict) -> None:
    """장시간 수집 중에도 요청마다 한국 날짜·쿼터 재개 시점을 다시 확인한다."""
    moment = now()
    if record['day'] != moment.date().isoformat():
        record.update(day=moment.date().isoformat(), calls_today=0)
    if record.get('retry_after') and moment >= datetime.fromisoformat(record['retry_after']):
        record.pop('retry_after', None)


def prepare() -> dict:
    """네트워크 없이 실측 원본·해시를 확인해 지번 작업표를 만든다."""
    report = read(REPORT)
    locations, targets, invalid = [], {}, []
    # 지역을 번갈아 순회해 한 지역만으로 하루 쿼터를 쓰지 않게 한다.
    queues = {region: [r for r in rows if r.get('outside_1km')] for region, rows in report['discovery'].items()}
    ordered = [rows[i] for i in range(max(map(len, queues.values())))
               for rows in queues.values() if i < len(rows)]
    for row in ordered:
        probe = row.get('store_probe') or {}
        source = ROOT / probe['bronze_path']
        if not probe.get('sha256') or fingerprint(source) != probe['sha256']:
            raise ValueError('점포 원본 해시 불일치: ' + row['candidate_id'])
        stores = read(source)
        ids = [s.get('bizesId') for s in stores]
        if len(stores) != probe['total'] or not all(ids) or len(ids) != len(set(ids)):
            raise ValueError('점포 수·고유 키 불일치: ' + row['candidate_id'])
        with contextlib.redirect_stdout(io.StringIO()):
            groups = group_by_building(stores)
        pnus, unresolved = set(), []
        for building_id, building in groups.items():
            pnu = str(building.get('lnoCd') or '')
            if not re.fullmatch(r'\d{19}', pnu):
                unresolved.append(building_id)
                invalid.append(dict(location=row['candidate_id'], building_id=building_id, reason='PNU 누락·형식 오류'))
                continue
            pnus.add(pnu)
            targets.setdefault(pnu, dict(pnu=pnu, locations=[]))
            if row['candidate_id'] not in targets[pnu]['locations']:
                targets[pnu]['locations'].append(row['candidate_id'])
        locations.append(dict(id=row['candidate_id'], label=row['label'], region=row['region'],
            source=probe['bronze_path'], source_sha256=probe['sha256'], pnus=sorted(pnus), unresolved=unresolved))
    if len(locations) != 227:
        raise ValueError(f'조사 원장 227곳 불일치: {len(locations)}')
    # 기존 완주 원본만 색인한다. 0행·절단·건수 불명은 성공으로 추정하지 않고 재확인한다.
    latest = {}
    for path in sorted((ROOT / 'data/bronze').glob('*/*/bldg_ledger_raw.json')):
        latest[path.parents[1].name] = path
    legacy, sources = {}, {}
    for path in sorted(latest.values(), key=lambda p: (p.parent.name, p.stat().st_mtime)):
        raw = read(path)
        if not isinstance(raw, dict):
            continue
        relevant = {}
        for pnu in targets.keys() & raw.keys():
            record = raw[pnu]
            if not isinstance(record, dict):
                continue
            rows, total = record.get('expos'), record.get('expos_total')
            if isinstance(rows, list) and rows and total == len(rows) and not record.get('expos_capped'):
                if len({json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rows}) == len(rows):
                    relevant[pnu] = dict(source=path.relative_to(ROOT).as_posix(), total=total)
        if relevant:
            sources[path.relative_to(ROOT).as_posix()] = fingerprint(path)
            legacy.update(relevant)
    plan = dict(source_report=REPORT.relative_to(ROOT).as_posix(), source_sha256=fingerprint(REPORT),
        created_at=now().isoformat(), locations=locations, targets=list(targets.values()),
        legacy_expos=legacy, legacy_sources=sources, unresolved=invalid,
        scope='상가정보의 기존 건물 그룹화 규칙에 잡힌 점포 건물·지번. 폴리곤에만 있는 빈 건물은 포함하지 않음',
        source='소상공인 상가정보 실측 원본·기존 건축HUB 전유부 원본', seed=False)
    atomic_json(PLAN, plan)
    return plan


class CollectionError(Exception):
    pass


class QuotaError(CollectionError):
    pass


class PowerWait(CollectionError):
    pass


class DiskWait(CollectionError):
    pass


class AuthError(CollectionError):
    pass


def parse_page(payload: dict) -> tuple[int, list[dict]]:
    """정상 헤더·전체 건수·행 자료형까지 확인한다. 오류 응답은 빈 대장이 아니다."""
    if not isinstance(payload, dict) or not isinstance(payload.get('response'), dict):
        raise CollectionError('API_RESPONSE_INVALID')
    response = payload['response']
    header = response.get('header') or {}
    if not isinstance(header, dict):
        raise CollectionError('API_HEADER_INVALID')
    code = str(header.get('resultCode', ''))
    if code == '22':
        raise QuotaError('API_QUOTA_22')
    if code in {'20', '30', '31', '32'}:
        raise AuthError('API_AUTH_' + code)
    if code not in {'0', '00'}:
        raise CollectionError('API_HEADER_INVALID')
    body = response.get('body') or {}
    if not isinstance(body, dict):
        raise CollectionError('API_BODY_INVALID')
    total = body.get('totalCount')
    if total is None or isinstance(total, bool) or not str(total).isdigit():
        raise CollectionError('API_TOTAL_INVALID')
    total = int(total)
    wrapped = body.get('items')
    items = wrapped.get('item', []) if isinstance(wrapped, dict) else [] if not wrapped else None
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list) or any(not isinstance(r, dict) for r in items):
        raise CollectionError('API_ITEMS_INVALID')
    if len(items) > 100 or (not items and total > 0) or len(items) > total:
        raise CollectionError('API_PAGE_PARTIAL')
    return total, items


def request_page(key: str, pnu: str, endpoint: str, page: int, state: dict) -> dict:
    """비밀 키·요청 URL을 로그나 예외 문자열에 싣지 않는다."""
    import requests
    record = state['endpoints'][endpoint]
    for attempt in range(3):
        rollover(record)
        if not ac_connected():
            raise PowerWait('AC_REQUIRED')
        if shutil.disk_usage(ROOT).free < 2 * 1024 ** 3:
            raise DiskWait('DISK_FREE_BELOW_2GIB')
        if record['calls_today'] >= DAILY_GUARD:
            raise QuotaError('LOCAL_DAILY_GUARD')
        record['calls_today'] += 1
        save_state(state)
        try:
            response = requests.get(f'{BASE_BLD}/{ENDPOINTS[endpoint]}', params=dict(
                serviceKey=key, _type='json', numOfRows=100, pageNo=page, **_jibun(pnu)), timeout=30)
        except requests.RequestException:
            if attempt == 2:
                raise CollectionError('NETWORK_ERROR') from None
            time.sleep(2 ** attempt)
            continue
        if response.status_code == 429:
            raise QuotaError('HTTP_429')
        if response.status_code in (401, 403):
            raise AuthError(f'HTTP_{response.status_code}')
        if response.status_code >= 500:
            if attempt == 2:
                raise CollectionError('UPSTREAM_5XX')
            time.sleep(2 ** attempt)
            continue
        if response.status_code != 200:
            raise CollectionError(f'HTTP_{response.status_code}')
        try:
            payload = response.json()
        except ValueError:
            # 공공데이터 게이트웨이는 HTTP 200 XML로 쿼터 오류를 주기도 한다.
            if 'LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR' in response.text:
                raise QuotaError('GATEWAY_QUOTA') from None
            if any(code in response.text for code in ('SERVICE_KEY_IS_NOT_REGISTERED_ERROR',
                    'SERVICE_ACCESS_DENIED_ERROR', 'INVALID_SERVICE_KEY')):
                raise AuthError('GATEWAY_AUTH') from None
            raise CollectionError('NON_JSON') from None
        parse_page(payload)
        return payload
    raise CollectionError('RETRY_EXHAUSTED')


def completion(pnu: str, endpoint: str) -> Path:
    return RAW / endpoint / pnu / 'complete.json'


def collect_target(key: str, pnu: str, endpoint: str, state: dict) -> dict:
    """매 페이지를 원본 그대로 원자 저장한다. totalCount까지 검증한 뒤에만 완료 표식을 쓴다."""
    pages, seen, count, total = [], set(), 0, None
    page = 1
    while True:
        # 날짜를 넘겨 계속 돌아도 실제 응답을 받은 날의 Bronze 아래에 저장한다.
        found = sorted(RAW.parent.glob(f'*/{endpoint}/{pnu}/page_{page:05d}.json*'))
        found = [p for p in found if p.name.endswith(('.json', '.json.gz'))]
        if found:
            path = found[-1]
            payload = read(path)
        else:
            payload = request_page(key, pnu, endpoint, page, state)
            path = RAW.parent / now().date().isoformat() / endpoint / pnu / f'page_{page:05d}.json.gz'
            encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            atomic_bytes(path, gzip.compress(encoded, mtime=0))
        current_total, rows = parse_page(payload)
        if total is not None and current_total != total:
            raise CollectionError('TOTAL_CHANGED_DURING_PAGING')
        total = current_total
        for row in rows:
            identity = json.dumps(row, sort_keys=True, ensure_ascii=False)
            if identity in seen:
                raise CollectionError('DUPLICATE_PAGE_ROW')
            seen.add(identity)
        count += len(rows)
        if count > total:
            raise CollectionError('ROW_COUNT_OVERFLOW')
        pages.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=fingerprint(path)))
        if count == total:
            result = dict(pnu=pnu, endpoint=endpoint, complete=True, total=total, received=count,
                pages=pages, source='건축HUB API 정상 응답', source_kind='api_pages', seed=False,
                completed_at=now().isoformat())
            atomic_json(completion(pnu, endpoint), result)
            return result
        page += 1
        if page > 10000:
            raise CollectionError('PAGE_SAFETY_LIMIT')
        time.sleep(0.05)


def save_state(state: dict) -> None:
    state['updated_at'] = now().isoformat()
    # 수만 개 완료 지번을 매 콜마다 다시 쓰지 않는다. 완료 증거는 Bronze 표식·페이지에 있고
    # 시작 때 재검증한다. 상태 JSON은 작은 진행 요약만 남긴다.
    atomic_json(STATE, {k: v for k, v in state.items() if k not in ('done', 'failures')})


def initial_state(plan: dict) -> dict:
    return dict(status='prepared', plan=PLAN.relative_to(ROOT).as_posix(), plan_sha256=fingerprint(PLAN),
        locations=len(plan['locations']), unique_pnus=len(plan['targets']), unresolved=len(plan['unresolved']),
        endpoints={e: dict(day=now().date().isoformat(), calls_today=0, completed=0) for e in ENDPOINTS},
        done={e: {} for e in ENDPOINTS}, failures={}, source='건축HUB 실호출·기존 완주 원본', seed=False)


def sync_existing(plan: dict, state: dict) -> None:
    """이미 검증 완료한 새 페이지와 원천 해시가 일치하는 기존 전유부 원본을 재사용한다."""
    state['done'] = {e: {} for e in ENDPOINTS}
    sources = {}
    for path, sha in plan['legacy_sources'].items():
        p = ROOT / path
        if p.exists() and fingerprint(p) == sha:
            sources[path] = True
    for pnu, record in plan['legacy_expos'].items():
        if record['source'] in sources:
            state['done']['expos'].setdefault(pnu, dict(source_kind='legacy_bronze', **record))
    for endpoint in ENDPOINTS:
        for target in plan['targets']:
            pnu = target['pnu']
            path = completion(pnu, endpoint)
            if pnu not in state['done'][endpoint] and path.exists():
                done = read(path)
                if done.get('complete') is True and done.get('received') == done.get('total') and all(
                    (ROOT / p['path']).exists() and fingerprint(ROOT / p['path']) == p['sha256'] for p in done['pages']):
                    state['done'][endpoint][pnu] = dict(source_kind='api_pages', marker=path.relative_to(ROOT).as_posix())
        state['endpoints'][endpoint]['completed'] = len(state['done'][endpoint])
    state['endpoints']['expos']['legacy_reused'] = sum(
        r['source_kind'] == 'legacy_bronze' for r in state['done']['expos'].values())


def active_targets(plan: dict, state: dict) -> list[dict]:
    """사용자가 보류한 시도 PNU는 원장·기수집 원본을 유지하고 호출만 제외한다."""
    paused = tuple(state.get('paused_pnu_prefixes', []))
    return [target for target in plan['targets'] if not paused or not target['pnu'].startswith(paused)]


def collect_pass(plan: dict, state: dict, key: str) -> None:
    """쿼터는 오퍼레이션별로 멈춘다. 한쪽이 소진돼도 다른 쪽은 수집한다."""
    for endpoint, record in state['endpoints'].items():
        rollover(record)
    for target in active_targets(plan, state):
        for endpoint in ENDPOINTS:
            pnu = target['pnu']
            record = state['endpoints'][endpoint]
            rollover(record)
            if pnu in state['done'][endpoint] or record.get('retry_after') or record.get('auth_error'):
                continue
            failure_key = endpoint + '/' + pnu
            prior = state['failures'].get(failure_key, {})
            if prior.get('attempts', 0) >= 3:
                continue
            if not ac_connected():
                raise PowerWait('AC_REQUIRED')
            state.update(status='collecting', current=dict(pnu=pnu, endpoint=endpoint))
            save_state(state)
            try:
                collect_target(key, pnu, endpoint, state)
            except (PowerWait, DiskWait):
                raise
            except QuotaError as exc:
                record.update(retry_after=retry_after(now()).isoformat(), reason=str(exc))
                say(f'{endpoint}: {str(exc)} — {record["retry_after"]} 이후 재개')
            except AuthError as exc:
                record['auth_error'] = str(exc)
            except CollectionError as exc:
                state['failures'][failure_key] = dict(attempts=prior.get('attempts', 0) + 1, reason=str(exc))
                atomic_json(FAILURES, state['failures'])
                say(f'{endpoint} {pnu}: {str(exc)}')
                record['consecutive_errors'] = record.get('consecutive_errors', 0) + 1
                if record['consecutive_errors'] >= 3:
                    record.update(retry_after=(now() + timedelta(minutes=10)).isoformat(), reason='TRANSIENT_ERRORS')
            else:
                record['consecutive_errors'] = 0
                state['done'][endpoint][pnu] = dict(source_kind='api_pages', marker=completion(pnu, endpoint).relative_to(ROOT).as_posix())
                if state['failures'].pop(failure_key, None) is not None:
                    atomic_json(FAILURES, state['failures'])
                record['completed'] = len(state['done'][endpoint])
                if record['completed'] % 50 == 0:
                    say(f'{endpoint}: {record["completed"]}/{state["unique_pnus"]}지번 완료')
            save_state(state)


def acquire_lock():
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    stream = LOCK.open('a+b')
    if stream.tell() == 0:
        stream.write(b'0')
        stream.flush()
    stream.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        return None
    return stream


def gold_scope_ready(plan: dict, state: dict) -> tuple[bool, str]:
    """현재 수집 범위의 대장 Gold·Program 파일까지 검증한 뒤에만 다음 지역을 연다."""
    report_path = GOLD_REPORT if GOLD_REPORT.is_relative_to(ROOT) else ROOT / 'reports/regional_research_gold.json'
    if not report_path.exists():
        return False, 'GOLD_REPORT_MISSING'
    paused = tuple(state.get('paused_pnu_prefixes', []))
    locations = [loc for loc in plan['locations'] if not paused or
                 (loc['pnus'] and not any(p.startswith(paused) for p in loc['pnus']))]
    if any(loc['unresolved'] for loc in locations):
        return False, 'UNRESOLVED_PNU'
    try:
        report = read(report_path)
        if report.get('status') != 'checked' or report.get('plan_sha256') != state['plan_sha256']:
            return False, 'GOLD_REPORT_NOT_CURRENT'
        entries = {loc['id']: loc for loc in report['locations']}
        if len(entries) != len(report['locations']):
            return False, 'DUPLICATE_GOLD_LOCATION'
        for loc in locations:
            entry = entries.get(loc['id'], {})
            if entry.get('status') != 'ledger_gold_complete':
                return False, 'GOLD_LOCATION_INCOMPLETE'
            artifacts = entry.get('artifacts', [])
            if {Path(a['path']).name for a in artifacts} != {'ledger_evidence.json.gz', 'program_content_context.csv'}:
                return False, 'GOLD_ARTIFACT_MISSING'
            for artifact in artifacts:
                path = (ROOT / artifact['path']).resolve()
                if not path.is_relative_to((ROOT / 'data/gold/regional_research_ledgers').resolve()):
                    return False, 'GOLD_PATH_ESCAPE'
                if fingerprint(path) != artifact['sha256']:
                    return False, 'GOLD_ARTIFACT_HASH_MISMATCH'
                if path.name == 'ledger_evidence.json.gz':
                    doc = read(path)
                    silver = (ROOT / doc['silver']['path']).resolve()
                    if (doc['candidate_id'] != loc['id'] or not silver.is_relative_to((ROOT / 'data/silver').resolve())
                            or fingerprint(silver) != doc['silver']['sha256']):
                        return False, 'SILVER_ARTIFACT_MISMATCH'
        return True, ''
    except (OSError, ValueError, KeyError, TypeError):
        return False, 'GOLD_VALIDATION_FAILED'


def advance_sequence(plan: dict, state: dict) -> str:
    """원본 완주 뒤 호출한다. 경기 자동 재개 시 기존 완료분과 일일 쿼터는 보존한다."""
    sequence = state.get('sequence') or {}
    if not sequence.get('enabled'):
        return 'disabled'
    if sequence.get('phase') not in ('gwangju_jeonju', 'gyeonggi'):
        state['status'] = 'waiting_gold'
        sequence['wait_reason'] = 'INVALID_SEQUENCE_PHASE'
        return 'waiting'
    ready, reason = gold_scope_ready(plan, state)
    if not ready:
        state['status'] = 'waiting_gold'
        sequence['wait_reason'] = reason
        return 'waiting'
    sequence.pop('wait_reason', None)
    if sequence['phase'] == 'gwangju_jeonju':
        config_path = AUTOMATION if AUTOMATION.is_relative_to(ROOT) else ROOT / 'reports/regional_research_automation.json'
        config = read(config_path) if config_path.exists() else {}
        if config.get('next_region') == 'busan':
            sequence.update(phase='busan', handoff_at=now().isoformat(),
                            handoff_gold_sha256=fingerprint(ROOT / 'reports/regional_research_gold.json'))
            state['status'] = 'busan_queued'
            state.pop('current', None)
            say('광주·전주 원본·대장 Gold·산출물 검증 완료 — 부산 자동 수집 대기 작업으로 인계')
            return 'complete'
        sequence.update(phase='gyeonggi', handoff_at=now().isoformat(),
                        handoff_gold_sha256=fingerprint(ROOT / 'reports/regional_research_gold.json'))
        state['paused_pnu_prefixes'] = [p for p in state.get('paused_pnu_prefixes', []) if p != '41']
        state['paused_regions'] = [r for r in state.get('paused_regions', []) if r != '경기']
        state['active_regions'] = ['광주', '전주', '경기']
        state['status'] = 'gyeonggi_resuming'
        state.pop('current', None)
        say('광주·전주 원본·대장 Gold·산출물 검증 완료 — 경기 미수집분 자동 재개')
        return 'advanced'
    sequence.update(phase='complete', completed_at=now().isoformat())
    state['status'] = 'sequence_complete'
    return 'complete'


def worker(once: bool = False) -> int:
    lock = acquire_lock()
    if lock is None:
        return 0
    from scripts.run_hub_chain_batch import keep_awake
    try:
        plan = read(PLAN)
        state = read(STATE) if STATE.exists() else initial_state(plan)
        if state['plan_sha256'] != fingerprint(PLAN):
            raise ValueError('작업표 변경 — 기존 상태와 자동 병합하지 않음')
        if state.get('status') in ('sequence_complete', 'busan_queued') or (
                state.get('status') in ('raw_complete', 'raw_complete_with_unresolved') and
                not (state.get('sequence') or {}).get('enabled')):
            return 0
        state['pid'] = os.getpid()
        state['failures'] = read(FAILURES) if FAILURES.exists() else {}
        sync_existing(plan, state)
        save_state(state)
        load_env()
        key = os.getenv('DATA_GO_KR_SERVICE_KEY')
        if not key:
            state['status'] = 'missing_api_key'
            save_state(state)
            return 2
        while True:
            selected = active_targets(plan, state)
            state['active_unique_pnus'] = len(selected)
            state['active_completed'] = {
                e: sum(t['pnu'] in state['done'][e] for t in selected) for e in ENDPOINTS}
            complete = all(state['active_completed'][e] == len(selected) for e in ENDPOINTS)
            if complete:
                transition = advance_sequence(plan, state)
                if transition != 'disabled':
                    save_state(state)
                    if transition == 'advanced':
                        continue
                    if transition == 'complete' or once:
                        return 0
                    keep_awake(False)
                    time.sleep(30)
                    continue
                state['status'] = ('selected_scope_raw_complete' if state.get('paused_pnu_prefixes') else
                    'raw_complete_with_unresolved' if plan['unresolved'] else 'raw_complete')
                save_state(state)
                return 0
            if not ac_connected():
                keep_awake(False)
                state['status'] = 'waiting_ac'
                save_state(state)
            else:
                keep_awake()
                try:
                    collect_pass(plan, state, key)
                except PowerWait:
                    state['status'] = 'waiting_ac'
                except DiskWait:
                    state['status'] = 'waiting_disk_space'
                else:
                    state['status'] = 'waiting_quota_or_retry'
                save_state(state)
            if once:
                return 0
            keep_awake(False)
            time.sleep(30)
    finally:
        keep_awake(False)
        lock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        if STATE.exists():
            raise SystemExit('기존 수집 상태가 있어 작업표를 덮어쓰지 않음')
        plan = prepare()
        state = initial_state(plan)
        sync_existing(plan, state)
        save_state(state)
    elif args.worker or args.once:
        return worker(args.once)
    if STATE.exists():
        state = read(STATE)
        print(json.dumps({k: v for k, v in state.items() if k not in ('done', 'failures')}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
