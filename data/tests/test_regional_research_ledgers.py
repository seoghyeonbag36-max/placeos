"""신규 탐색 위치 수집의 AC·원본 검증·중복 지번·부분 페이지·쿼터 회귀를 막는다."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import collect_regional_research_ledgers as runner


def page(total, rows):
    return {'response': {'header': {'resultCode': '00'},
                         'body': {'totalCount': total, 'items': {'item': rows}}}}


def test_paused_gyeonggi_has_no_calls_and_preserves_completed(isolated, monkeypatch):
    monkeypatch.setattr(runner, 'ac_connected', lambda: True)
    called = []
    monkeypatch.setattr(runner, 'collect_target', lambda key, pnu, endpoint, state: called.append((pnu, endpoint)))
    gg, gj, jj = '4111111111111111111', '2911111111111111111', '5211111111111111111'
    plan = {'targets': [{'pnu': p} for p in (gg, gj, jj)]}
    state = dict(paused_pnu_prefixes=['41'], unique_pnus=3,
        done={'expos': {gg: {'source_kind': 'api_pages'}}, 'floors': {}}, failures={},
        endpoints={e: dict(day=runner.now().date().isoformat(), calls_today=0, completed=0)
                   for e in runner.ENDPOINTS})
    runner.collect_pass(plan, state, 'test')
    assert called == [(gj, 'expos'), (gj, 'floors'), (jj, 'expos'), (jj, 'floors')]
    assert state['done']['expos'][gg] == {'source_kind': 'api_pages'}
    assert len(plan['targets']) == 3


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'RAW', tmp_path / 'data/bronze/research/day')
    monkeypatch.setattr(runner, 'STATE', tmp_path / 'reports/state.json')
    monkeypatch.setattr(runner, 'FAILURES', tmp_path / 'data/silver/failures.json')
    monkeypatch.setattr(runner, 'LOG', tmp_path / 'logs/worker.log')
    monkeypatch.setattr(runner.time, 'sleep', lambda _: None)
    return tmp_path


def test_empty_success_is_distinct_from_api_error():
    assert runner.parse_page(page(0, [])) == (0, [])
    with pytest.raises(runner.QuotaError):
        runner.parse_page({'response': {'header': {'resultCode': '22'}}})
    with pytest.raises(runner.AuthError):
        runner.parse_page({'response': {'header': {'resultCode': '30'}}})
    for payload in ({}, page(2, []), page(0, [{'rnum': 1}]),
                    {'response': {'header': {'resultCode': '00'}, 'body': {}}}):
        with pytest.raises(runner.CollectionError):
            runner.parse_page(payload)


def test_full_paging_and_cached_resume_do_not_repeat_calls(isolated, monkeypatch):
    calls = []
    def fetch(_key, _pnu, _endpoint, number, _state):
        calls.append(number)
        return page(102, [{'rnum': i} for i in (range(1, 101) if number == 1 else range(101, 103))])
    monkeypatch.setattr(runner, 'request_page', fetch)
    result = runner.collect_target('test', '1234567890123456789', 'expos', {})
    assert result['complete'] and result['received'] == result['total'] == 102
    assert calls == [1, 2]
    runner.collect_target('test', '1234567890123456789', 'expos', {})
    assert calls == [1, 2]
    assert not (isolated / 'data/gold').exists()


def test_partial_failure_has_no_complete_marker_and_resumes_from_next_page(isolated, monkeypatch):
    pnu = '1234567890123456789'
    def fetch(_key, _pnu, _endpoint, number, _state):
        if number == 2:
            raise runner.QuotaError('HTTP_429')
        return page(101, [{'rnum': i} for i in range(100)])
    monkeypatch.setattr(runner, 'request_page', fetch)
    with pytest.raises(runner.QuotaError):
        runner.collect_target('test', pnu, 'floors', {})
    assert not runner.completion(pnu, 'floors').exists()
    calls = []
    def resumed(_key, _pnu, _endpoint, number, _state):
        calls.append(number)
        return page(101, [{'rnum': 100}])
    monkeypatch.setattr(runner, 'request_page', resumed)
    assert runner.collect_target('test', pnu, 'floors', {})['received'] == 101
    assert calls == [2]


def test_duplicate_page_never_counts_as_complete(isolated, monkeypatch):
    monkeypatch.setattr(runner, 'request_page', lambda *a: page(2, [{'rnum': 1}]))
    with pytest.raises(runner.CollectionError, match='DUPLICATE'):
        runner.collect_target('test', '1234567890123456789', 'expos', {})
    assert not runner.completion('1234567890123456789', 'expos').exists()


def test_no_http_call_without_ac(isolated, monkeypatch):
    monkeypatch.setattr(runner, 'ac_connected', lambda: False)
    import requests
    monkeypatch.setattr(requests, 'get', lambda *a, **k: pytest.fail('AC 미연결 상태에서 API 호출'))
    state = {'endpoints': {'expos': {'day': runner.now().date().isoformat(), 'calls_today': 0}}}
    with pytest.raises(runner.PowerWait):
        runner.request_page('test', '1234567890123456789', 'expos', 1, state)
    assert state['endpoints']['expos']['calls_today'] == 0


def test_quota_only_pauses_the_exhausted_operation(isolated, monkeypatch):
    monkeypatch.setattr(runner, 'ac_connected', lambda: True)
    called = []
    def fetch(_key, _pnu, endpoint, _state):
        called.append(endpoint)
        if endpoint == 'expos':
            raise runner.QuotaError('HTTP_429')
        return {}
    monkeypatch.setattr(runner, 'collect_target', fetch)
    state = dict(unique_pnus=1, done={e: {} for e in runner.ENDPOINTS}, failures={}, endpoints={
        e: dict(day=runner.now().date().isoformat(), calls_today=0, completed=0) for e in runner.ENDPOINTS})
    runner.collect_pass(dict(targets=[dict(pnu='1234567890123456789')]), state, 'test')
    assert called == ['expos', 'floors']
    assert state['done']['expos'] == {}
    assert state['endpoints']['expos']['reason'] == 'HTTP_429'
    assert state['endpoints']['floors']['completed'] == 1


def test_korean_midnight_rollover_during_a_long_pass(monkeypatch):
    moment = datetime(2026, 11, 3, 15, 6, tzinfo=timezone.utc).astimezone(runner.KST)
    monkeypatch.setattr(runner, 'now', lambda: moment)
    record = dict(day='2026-11-03', calls_today=9999, retry_after='2026-11-04T00:05:00+09:00')
    runner.rollover(record)
    assert record['calls_today'] == 0 and record['day'] == '2026-11-04'
    assert 'retry_after' not in record
    assert runner.retry_after(datetime(2026, 11, 3, 14, 59, tzinfo=timezone.utc)).isoformat() == '2026-11-04T00:05:00+09:00'


def test_unknown_power_is_not_ac(monkeypatch):
    monkeypatch.setattr(runner, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(runner.ctypes, 'windll', SimpleNamespace(kernel32=SimpleNamespace(
        GetSystemPowerStatus=lambda _: 0)), raising=False)
    assert runner.ac_connected() is False


def test_plan_deduplicates_overlapping_locations_and_preserves_unresolved(isolated, monkeypatch):
    source = isolated / 'data/bronze/stores/day/stores_raw.json'
    runner.atomic_json(source, [dict(bizesId='one')])
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    report = isolated / 'report.json'
    runner.atomic_json(report, dict(discovery={'경기': [dict(candidate_id=str(i), label=str(i), region='경기', outside_1km=True,
        store_probe=dict(bronze_path=source.relative_to(isolated).as_posix(), sha256=sha, total=1)) for i in range(227)]}))
    monkeypatch.setattr(runner, 'REPORT', report)
    monkeypatch.setattr(runner, 'PLAN', isolated / 'data/silver/plan.json')
    monkeypatch.setattr(runner, 'group_by_building', lambda _: {
        'valid': dict(lnoCd='1234567890123456789'), 'missing': dict(lnoCd='')})
    plan = runner.prepare()
    assert len(plan['targets']) == 1 and len(plan['targets'][0]['locations']) == 227
    assert len(plan['unresolved']) == 227
    assert all(r['unresolved'] == ['missing'] for r in plan['locations'])
    assert plan['seed'] is False


def test_atomic_status_write_retries_windows_reader_lock(isolated, monkeypatch):
    original = Path.replace
    attempts = []
    def replace(path, target):
        attempts.append(path)
        if len(attempts) == 1:
            raise PermissionError('temporary file sharing conflict')
        return original(path, target)
    monkeypatch.setattr(Path, 'replace', replace)
    runner.atomic_json(runner.STATE, dict(status='collecting'))
    assert runner.read(runner.STATE) == dict(status='collecting')
    assert len(attempts) == 2


def test_new_api_pages_are_losslessly_compressed(isolated, monkeypatch):
    payload = page(1, [dict(rnum=1, mainPurpsCdNm='소매점')])
    monkeypatch.setattr(runner, 'request_page', lambda *a: payload)
    result = runner.collect_target('test', '1234567890123456789', 'floors', {})
    path = isolated / result['pages'][0]['path']
    assert path.name.endswith('.json.gz')
    assert runner.read(path) == payload


def test_sequence_waits_for_gold_without_unpausing_gyeonggi(isolated, monkeypatch):
    monkeypatch.setattr(runner, 'gold_scope_ready', lambda *_: (False, 'GOLD_LOCATION_INCOMPLETE'))
    state = dict(sequence=dict(enabled=True, phase='gwangju_jeonju'), paused_pnu_prefixes=['41'])
    assert runner.advance_sequence({}, state) == 'waiting'
    assert state['paused_pnu_prefixes'] == ['41']
    assert state['sequence']['phase'] == 'gwangju_jeonju'
    assert state['sequence']['wait_reason'] == 'GOLD_LOCATION_INCOMPLETE'


def test_sequence_resumes_only_missing_gyeonggi_without_resetting_quota(isolated, monkeypatch):
    monkeypatch.setattr(runner, 'gold_scope_ready', lambda *_: (True, ''))
    runner.atomic_json(isolated / 'reports/regional_research_gold.json', {'status': 'checked'})
    gj, gg = '2911111111111111111', '4111111111111111111'
    plan = dict(targets=[dict(pnu=gj), dict(pnu=gg)])
    state = dict(sequence=dict(enabled=True, phase='gwangju_jeonju'), paused_pnu_prefixes=['41'],
        paused_regions=['경기'], unique_pnus=2, failures={},
        done={'expos': {gj: {}, gg: {}}, 'floors': {gj: {}}},
        endpoints={e: dict(day=runner.now().date().isoformat(), calls_today=9999,
                          completed=2 if e == 'expos' else 1) for e in runner.ENDPOINTS})
    assert runner.advance_sequence(plan, state) == 'advanced'
    assert state['sequence']['phase'] == 'gyeonggi'
    assert not state['paused_pnu_prefixes']
    assert all(r['calls_today'] == 9999 for r in state['endpoints'].values())
    called = []
    monkeypatch.setattr(runner, 'ac_connected', lambda: True)
    monkeypatch.setattr(runner, 'collect_target', lambda key, pnu, ep, state: called.append((pnu, ep)))
    runner.collect_pass(plan, state, 'test')
    assert called == [(gg, 'floors')]
    assert gj in state['done']['expos'] and gj in state['done']['floors']
    assert runner.advance_sequence(plan, state) == 'complete'
    assert state['status'] == 'sequence_complete'


def test_gold_handoff_verifies_gold_and_silver_hashes(isolated):
    root = isolated
    plan = {'locations': [dict(id='research-one', pnus=['2911111111111111111'], unresolved=[])]}
    state = dict(plan_sha256='plan-hash', paused_pnu_prefixes=['41'])
    silver = root / 'data/silver/evidence.json'
    runner.atomic_json(silver, {'observation': 1})
    folder = root / 'data/gold/regional_research_ledgers/research-one/hash'
    evidence, context = folder / 'ledger_evidence.json.gz', folder / 'program_content_context.csv'
    import gzip
    runner.atomic_bytes(evidence, gzip.compress(json.dumps(dict(candidate_id='research-one', silver=dict(
        path=silver.relative_to(root).as_posix(), sha256=runner.fingerprint(silver)))).encode()))
    runner.atomic_bytes(context, b'kind,key,value\r\n')
    report = root / 'reports/regional_research_gold.json'
    runner.atomic_json(report, dict(status='checked', plan_sha256='plan-hash', locations=[dict(
        id='research-one', status='ledger_gold_complete', artifacts=[dict(
            path=p.relative_to(root).as_posix(), sha256=runner.fingerprint(p)) for p in (evidence, context)])]))
    assert runner.gold_scope_ready(plan, state) == (True, '')
    context.write_bytes(b'tampered')
    assert runner.gold_scope_ready(plan, state) == (False, 'GOLD_ARTIFACT_HASH_MISMATCH')


def test_unresolved_pnu_is_not_sequence_success(isolated):
    runner.atomic_json(isolated / 'reports/regional_research_gold.json', dict(status='checked'))
    plan = {'locations': [dict(id='research-one', pnus=['4111111111111111111'], unresolved=['missing'])]}
    assert runner.gold_scope_ready(plan, dict(paused_pnu_prefixes=[])) == (False, 'UNRESOLVED_PNU')


@pytest.mark.parametrize('damage', [None, 'page_hash', 'partial', 'wrong_pnu', 'empty_pages'])
def test_indexed_startup_revalidates_every_completed_page(isolated, damage):
    pnu = '2911111111111111111'
    path = runner.RAW / 'expos' / pnu / 'page_00001.json'
    runner.atomic_json(path, page(1, [dict(rnum=1)]))
    marker = dict(pnu=pnu, endpoint='expos', complete=True, total=1, received=1,
        pages=[dict(path=path.relative_to(isolated).as_posix(), sha256=runner.fingerprint(path))])
    if damage == 'page_hash':
        path.write_text('{}', encoding='utf-8')
    elif damage == 'partial':
        marker['received'] = 0
    elif damage == 'wrong_pnu':
        marker['pnu'] = 'wrong'
    elif damage == 'empty_pages':
        marker['pages'] = []
    runner.atomic_json(runner.completion(pnu, 'expos'), marker)
    plan = dict(targets=[dict(pnu=pnu), dict(pnu='4111111111111111111')], legacy_expos={}, legacy_sources={})
    state = dict(done={}, endpoints={e: dict(day=runner.now().date().isoformat(),calls_today=123,completed=0)
                                   for e in runner.ENDPOINTS})
    runner.sync_existing(plan, state)
    assert (pnu in state['done']['expos']) == (damage is None)
    assert state['endpoints']['expos']['completed'] == int(damage is None)
    assert state['endpoints']['floors']['completed'] == 0
    assert all(record['calls_today'] == 123 for record in state['endpoints'].values())
    assert 'verification' not in state


def test_non_json_is_saved_and_retried_without_fake_empty_response(isolated,monkeypatch):
    import requests
    monkeypatch.setattr(runner,'ac_connected',lambda:True)
    monkeypatch.setattr(runner.shutil,'disk_usage',lambda _:SimpleNamespace(free=10*1024**3))
    class Response:
        status_code=200
        headers={'Content-Type':'text/html'}
        content=b'<html>temporary upstream response</html>'
        text=content.decode()
        def json(self):raise ValueError('not JSON')
    valid=SimpleNamespace(status_code=200,json=lambda:page(0,[]))
    responses=iter([Response(),valid])
    monkeypatch.setattr(requests,'get',lambda *args,**kwargs:next(responses))
    state={'endpoints':{'expos':dict(day=runner.now().date().isoformat(),calls_today=0)}}
    assert runner.parse_page(runner.request_page('test','2911111111111111111','expos',1,state))==(0,[])
    assert state['endpoints']['expos']['calls_today']==2
    assert list((isolated/'data/bronze/regional_research_diagnostics').rglob('*.bin'))[0].read_bytes()==Response.content
