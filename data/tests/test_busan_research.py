"""부산 인계는 Gold 검증 뒤에만 열고, 부분·지역 밖 점포를 거부한다."""
import pytest

from scripts import collect_regional_research_ledgers as runner
from scripts import run_busan_research as busan


def test_busan_handoff_preserves_gyeonggi_and_daily_quota(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'AUTOMATION', tmp_path / 'automation.json')
    monkeypatch.setattr(runner, 'LOG', tmp_path / 'worker.log')
    monkeypatch.setattr(runner, 'gold_scope_ready', lambda *_: (True, ''))
    runner.atomic_json(runner.AUTOMATION, {'next_region': 'busan'})
    runner.atomic_json(tmp_path / 'reports/regional_research_gold.json', {'status': 'checked'})
    state = dict(sequence=dict(enabled=True, phase='gwangju_jeonju'), paused_pnu_prefixes=['41'],
                 endpoints={'expos': {'calls_today': 9999}}, active_regions=['광주', '전주'])
    assert runner.advance_sequence({}, state) == 'complete'
    assert state['sequence']['phase'] == 'busan'
    assert state['status'] == 'busan_queued'
    assert state['paused_pnu_prefixes'] == ['41']
    assert state['endpoints']['expos']['calls_today'] == 9999


def test_busan_handoff_waits_for_verified_gold(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'gold_scope_ready', lambda *_: (False, 'GOLD_LOCATION_INCOMPLETE'))
    state = dict(sequence=dict(enabled=True, phase='gwangju_jeonju'), paused_pnu_prefixes=['41'])
    assert runner.advance_sequence({}, state) == 'waiting'
    assert state['sequence']['phase'] == 'gwangju_jeonju'


def test_busan_store_response_rejects_partial_and_outside_scope():
    valid = {'header': {'resultCode': '00'}, 'body': {'totalCount': 1,
             'items': [{'ctprvnCd': '26', 'bizesId': 'fixture-one'}]}}
    assert busan.parse_stores(valid)[0] == 1
    with pytest.raises(ValueError):
        busan.parse_stores(valid, 2)
    valid['body']['items'][0]['ctprvnCd'] = '41'
    with pytest.raises(ValueError):
        busan.parse_stores(valid)
    with pytest.raises(ValueError):
        busan.parse_stores({'body': {'totalCount': 1, 'items': []}})


def test_busan_task_does_not_collect_before_handoff(tmp_path, monkeypatch):
    monkeypatch.setattr(busan, 'ROOT', tmp_path)
    runner.atomic_json(tmp_path / 'reports/regional_research_ledger_collection.json',
                       {'status': 'collecting', 'sequence': {'phase': 'gwangju_jeonju'}})
    monkeypatch.setattr(busan, 'fetch_stores', lambda: pytest.fail('부산 조기 수집'))
    assert busan.main() == 0


def test_busan_handoff_rejects_changed_gold(tmp_path, monkeypatch):
    monkeypatch.setattr(busan, 'ROOT', tmp_path)
    gold = tmp_path / 'reports/regional_research_gold.json'
    runner.atomic_json(gold, {'status': 'checked'})
    runner.atomic_json(tmp_path / 'reports/regional_research_ledger_collection.json',
        dict(status='busan_queued', sequence=dict(phase='busan',
             handoff_gold_sha256=runner.fingerprint(gold))))
    assert busan.handoff_ready()
    runner.atomic_json(gold, {'status': 'changed'})
    assert not busan.handoff_ready()


def test_busan_plan_deduplicates_parcels_and_records_missing_pnu(tmp_path, monkeypatch):
    monkeypatch.setattr(busan, 'ROOT', tmp_path)
    monkeypatch.setattr(busan, 'STORES', tmp_path / 'data/bronze/busan')
    def row(key, pnu):
        return dict(bizesId=key, bldMngNo=key, adongCd='26110510', adongNm='시험동',
                    signguNm='시험구', lnoCd=pnu, lat='35', lon='129')
    pnu = '2611010100100010000'
    plan = busan.build_plan([row('fixture-one', pnu), row('fixture-two', pnu), row('fixture-three', '')])
    assert len(plan['targets']) == 1
    assert plan['locations'][0]['pnus'] == [pnu]
    assert len(plan['unresolved']) == 1
    assert plan['locations'][0]['unresolved'] == ['fixture-three']
    assert plan['seed'] is False
