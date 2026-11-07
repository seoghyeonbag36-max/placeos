"""부분 대장·위조 해시·지역 보류가 Gold 또는 서비스 거점으로 새지 않게 한다."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from data.pipelines import build_regional_ledger_gold as gold
from scripts import collect_regional_research_ledgers as source


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(source, 'ROOT', tmp_path)
    monkeypatch.setattr(source, 'RAW', tmp_path / 'data/bronze/research/day')
    monkeypatch.setattr(source, 'PLAN', tmp_path / 'data/silver/plan.json')
    monkeypatch.setattr(gold, 'GOLD', tmp_path / 'data/gold/research')
    monkeypatch.setattr(gold, 'SILVER', tmp_path / 'data/silver/normalized')
    monkeypatch.setattr(gold, 'REPORT', tmp_path / 'reports/result.json')
    monkeypatch.setattr(gold.shutil, 'disk_usage', lambda _: SimpleNamespace(free=10 * 1024 ** 3))
    pnu = '2911111111111111111'
    stores = tmp_path / 'data/bronze/stores/day/stores_raw.json'
    source.atomic_json(stores, [{'bizesId': 'one', 'indsLclsNm': '음식', 'indsSclsNm': '카페'}])
    for endpoint in source.ENDPOINTS:
        rows = ([dict(exposPubuseGbCdNm='전유', mainPurpsCdNm='소매점', hoNm='101')] if endpoint == 'expos'
                else [dict(flrGbCdNm='지상', flrNo=1, mainPurpsCdNm='소매점')])
        path = source.RAW / endpoint / pnu / 'page_00001.json'
        source.atomic_json(path, {'response': {'header': {'resultCode': '00'},
            'body': {'totalCount': 1, 'items': {'item': rows}}}})
        source.atomic_json(source.completion(pnu, endpoint), dict(pnu=pnu, endpoint=endpoint,
            complete=True, total=1, received=1,
            pages=[dict(path=path.relative_to(tmp_path).as_posix(), sha256=source.fingerprint(path))]))
    plan = dict(locations=[dict(id='research-one', label='광주 테스트', region='광주',
        pnus=[pnu], unresolved=[], source=stores.relative_to(tmp_path).as_posix(),
        source_sha256=source.fingerprint(stores))], legacy_expos={}, legacy_sources={})
    source.atomic_json(source.PLAN, plan)
    return plan, pnu


def test_complete_ledger_passes_silver_before_gold_and_never_registers_hub(inputs):
    plan, _ = inputs
    result = gold.run(plan, ['41'])
    loc = result['locations'][0]
    assert loc['status'] == 'ledger_gold_complete'
    silver = source.read(source.ROOT / loc['silver'])
    artifact = source.read(source.ROOT / loc['artifacts'][0]['path'])
    assert artifact['observations'] == silver['observations']
    assert artifact['observations'][0]['commercial_expos_units'] == 1
    assert artifact['observations'][0]['commercial_ground_floor_numbers'] == [1]
    assert artifact['serving_eligible'] is False
    assert result['summary']['serving_promoted'] == 0
    assert 'vacancy_source' not in artifact and 'rent' not in artifact
    assert not (source.ROOT / 'data/config').exists()
    before = {p: p.read_bytes() for p in gold.GOLD.rglob('*') if p.is_file()}
    gold.run(plan, ['41'])
    assert all(p.read_bytes() == value for p, value in before.items())


def test_partial_or_unresolved_location_never_reaches_gold(inputs):
    plan, pnu = inputs
    source.completion(pnu, 'floors').unlink()
    assert gold.run(plan, [])['locations'][0]['status'] == 'waiting_raw'
    assert not gold.GOLD.exists()
    plan['locations'][0]['unresolved'] = ['missing-pnu']
    assert gold.run(plan, [])['locations'][0]['unresolved'] == 1


def test_page_hash_tampering_never_reaches_gold(inputs):
    plan, pnu = inputs
    (source.RAW / 'expos' / pnu / 'page_00001.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='HASH_MISMATCH'):
        gold.run(plan, [])
    assert not gold.GOLD.exists()


def test_partial_marker_even_when_present_never_passes(inputs):
    plan, pnu = inputs
    path = source.completion(pnu, 'floors')
    marker = source.read(path)
    marker['received'] = 0
    source.atomic_json(path, marker)
    with pytest.raises(ValueError, match='INCOMPLETE_LEDGER_MARKER'):
        gold.run(plan, [])


def test_paused_gyeonggi_is_not_processed(inputs):
    plan, _ = inputs
    plan['locations'][0]['pnus'] = ['4111111111111111111']
    result = gold.run(plan, ['41'])
    assert result['summary']['locations'] == 0
    assert not gold.GOLD.exists()


def test_existing_gold_mismatch_is_not_overwritten(inputs):
    plan, _ = inputs
    result = gold.run(plan, [])
    path = source.ROOT / result['locations'][0]['artifacts'][0]['path']
    path.write_bytes(b'damaged')
    with pytest.raises(ValueError, match='EXISTING_ARTIFACT_MISMATCH'):
        gold.run(plan, [])
    assert path.read_bytes() == b'damaged'


def test_zero_rows_requires_successful_api_response(inputs):
    plan, pnu = inputs
    for endpoint in source.ENDPOINTS:
        path = source.RAW / endpoint / pnu / 'page_00001.json'
        source.atomic_json(path, {'response': {'header': {'resultCode': '00'},
            'body': {'totalCount': 0, 'items': {}}}})
        marker = source.read(source.completion(pnu, endpoint))
        marker.update(total=0, received=0)
        marker['pages'][0]['sha256'] = source.fingerprint(path)
        source.atomic_json(source.completion(pnu, endpoint), marker)
    result = gold.run(plan, [])
    artifact = source.read(source.ROOT / result['locations'][0]['artifacts'][0]['path'])
    assert artifact['observations'][0]['expos_rows'] == 0
    assert artifact['observations'][0]['floor_rows'] == 0


def test_bronze_path_escape_fails(inputs):
    with pytest.raises(ValueError, match='BRONZE_PATH_ESCAPE'):
        gold.bronze_path('../outside.json')


def test_disk_guard_does_not_write_gold(inputs, monkeypatch):
    plan, _ = inputs
    monkeypatch.setattr(gold.shutil, 'disk_usage', lambda _: SimpleNamespace(free=1024))
    with pytest.raises(source.DiskWait):
        gold.run(plan, [])
    assert not gold.GOLD.exists()


def test_verified_output_reuse_preserves_values_and_force_rechecks_raw(inputs, monkeypatch):
    plan,_=inputs
    first=gold.run(plan,[])
    artifact=source.ROOT/first['locations'][0]['artifacts'][0]['path']
    original=artifact.read_bytes()
    second=gold.run(plan,[])
    assert second['summary']['reused_verified_locations']==1
    assert artifact.read_bytes()==original
    third=gold.run(plan,[],force_verify=True)
    assert third['summary']['reused_verified_locations']==0
    assert artifact.read_bytes()==original


def test_new_valid_completion_proof_creates_new_snapshot_without_overwriting(inputs):
    plan,pnu=inputs
    first=gold.run(plan,[])
    old_path=source.ROOT/first['locations'][0]['artifacts'][0]['path']
    original=old_path.read_bytes()
    marker_path=source.completion(pnu,'floors')
    marker=source.read(marker_path);marker['completed_at']='new verification'
    source.atomic_json(marker_path,marker)
    result=gold.run(plan,[])
    assert result['locations'][0]['source_digest']!=first['locations'][0]['source_digest']
    assert old_path.read_bytes()==original
