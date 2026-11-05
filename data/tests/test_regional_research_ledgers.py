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
