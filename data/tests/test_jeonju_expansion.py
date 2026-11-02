"""전주 지역 혼입·자정 재시도·미완 대장 승격 회귀를 막는다."""
from datetime import datetime, timezone

import pytest

from data.collectors.jeonju_candidates import select_place, validate_stores
from data.config.page_hubs import JEONJU_HUBS, ACTIVE_HUBS
from data.config.rone_districts import DISTRICT_RONE
from scripts import run_jeonju_expansion as runner


def test_location_rejects_same_name_outside_jeonju():
    wrong = {'title': '전주시청', 'address': {'parcel': '서울특별시 중구'}}
    correct = {'title': '전주시청', 'address': {'parcel': '전북특별자치도 전주시 완산구'}}
    assert select_place([wrong, correct], '전주시청') == correct
    with pytest.raises(ValueError):
        select_place([wrong], '전주시청')


def test_cached_store_city_and_unique_ids_are_checked():
    good = {'bizesId': 'one', 'lnoAdr': '전북특별자치도 전주시 완산구'}
    validate_stores([good])
    with pytest.raises(ValueError, match='중복'):
        validate_stores([good, good])
    with pytest.raises(ValueError, match='타 도시'):
        validate_stores([{**good, 'lnoAdr': '전북특별자치도 익산시'}])


def test_all_five_verified_rone_hubs_are_public():
    assert {DISTRICT_RONE[s] for s in JEONJU_HUBS} == {
        '전북>전주동부', '전북>전주서부', '전북>전주서부신시가지',
        '전북>전주한옥마을', '전북>송천동'}
    assert set(JEONJU_HUBS) <= set(ACTIVE_HUBS)
    assert all(h.city == 'jeonju' for h in JEONJU_HUBS.values())


def test_retry_uses_korean_midnight_even_on_utc_host():
    quota = datetime(2026, 11, 1, 14, 59, tzinfo=timezone.utc)
    assert runner.retry_after(quota).isoformat() == '2026-11-02T00:05:00+09:00'


def test_network_failure_is_not_daily_quota():
    assert runner.has_quota('[HTTP 실패 1연속 | 429 x3 · pace 0.5s]')
    assert runner.has_quota('429 로 3회 연속 소진')
    assert not runner.has_quota('연결/기타 — timeout')
    assert not runner.has_quota('서버 5xx/비JSON x3')


def test_incomplete_ledger_never_reaches_gold(monkeypatch):
    calls = []
    monkeypatch.setattr(runner.chain, 'power', lambda: (True, 100))
    monkeypatch.setattr(runner.chain, 'ledger_gap', lambda slug: 7)
    monkeypatch.setattr(runner, 'run', lambda module, *args: (calls.append(module) or True, False))
    with pytest.raises(ValueError, match='전유부 수집 미완료'):
        runner.attempt({})
    assert calls == ['data.collectors.building_vacancy'] * 3


def test_quota_stops_before_floor_calls_or_gold(monkeypatch):
    calls = []
    monkeypatch.setattr(runner.chain, 'power', lambda: (True, 100))
    monkeypatch.setattr(runner.chain, 'ledger_gap', lambda slug: 7)
    monkeypatch.setattr(runner, 'run', lambda module, *args: (calls.append(module) or True, True))
    monkeypatch.setattr(runner, 'save', lambda state: None)
    state = {}
    assert runner.attempt(state)
    assert state['status'] == 'quota'
    assert calls == ['data.collectors.building_vacancy']


def test_city_license_code_is_collected_once_for_two_gus(tmp_path, monkeypatch):
    from data.collectors import jeonju_licensing as licensing
    calls = []
    monkeypatch.setattr(licensing, 'load_env', lambda: None)
    monkeypatch.setattr(licensing, 'bronze_dir', lambda _: tmp_path)
    monkeypatch.setattr(licensing, 'ROOT', tmp_path)
    (tmp_path / 'reports').mkdir()
    def fetch(params):
        calls.append(params)
        address = params.get('cond[ROAD_NM_ADDR::LIKE]', '전북특별자치도 전주시 완산구')
        return {'response': {'body': {'totalCount': 1, 'items': {'item': [
            {'MNG_NO': 'one', 'OPN_ATMY_GRP_CD': '4641000', 'ROAD_NM_ADDR': address}
        ]}}}}
    monkeypatch.setattr(licensing, 'fetch', fetch)
    assert licensing.collect()['rows'] == 1
    assert len([c for c in calls if 'pageNo' in c]) == 1
    assert licensing.collect()['rows'] == 1
    assert len(calls) == 5  # 주소 probe 4번 + 같은 시 코드 전량 1번


def test_license_duplicate_pages_are_not_complete(tmp_path, monkeypatch):
    from data.collectors import jeonju_licensing as licensing
    monkeypatch.setattr(licensing, 'load_env', lambda: None)
    monkeypatch.setattr(licensing, 'bronze_dir', lambda _: tmp_path)
    def fetch(params):
        address = params.get('cond[ROAD_NM_ADDR::LIKE]', '전북특별자치도 전주시 완산구')
        return {'response': {'body': {'totalCount': 2, 'items': {'item': [
            {'MNG_NO': 'duplicate', 'OPN_ATMY_GRP_CD': '4641000', 'ROAD_NM_ADDR': address}
        ]}}}}
    monkeypatch.setattr(licensing, 'fetch', fetch)
    with pytest.raises(ValueError, match='페이지 중복'):
        licensing.collect()
    assert not (tmp_path / 'city_complete.json').exists()


def test_license_bucket_keeps_same_dong_in_different_gus_separate():
    from data.collectors.jeonju_licensing_hubs import bucket
    rows = [{'LOTNO_ADDR': '전북특별자치도 전주시 완산구 중앙동1가 1', 'MNG_NO': 'one'}]
    result = bucket(rows, {'east': {('완산구', '중앙동1가')}, 'other': {('덕진구', '중앙동1가')}})
    assert len(result['east']) == 1
    assert not result['other']
