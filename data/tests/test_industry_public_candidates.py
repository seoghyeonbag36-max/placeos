"""합성 자료로 후보를 확정하지 않고 충돌·결손을 보존하는지 검증한다."""
import json
import pytest

from data.validation.industry_public_candidates import candidate, floor, audit


def fixtures():
    return ({'BPLCNM': '합성 상호', 'RDNWHLADDR': '서울 도로 1, 2층 (동)'},
            {'bizesId': 'synthetic-1', 'bizesNm': '합성 상호', 'rdnmAdr': '서울 도로 1', 'flrNo': '2'})


def test_single_building_candidate_never_confirms_store():
    row, store = fixtures()
    result = candidate(row, [store, store])
    assert result['status'] == 'candidate_only' and result['store_id'] is None
    assert len(result['candidates']) == 1
    assert result['candidates'][0]['floor_evidence'] == 'equal'


def test_floor_conflicts_and_missing_floors_are_preserved():
    row, store = fixtures()
    store['flrNo'] = '3'
    assert candidate(row, [store])['candidates'][0]['floor_evidence'] == 'conflict'
    store['flrNo'] = ''
    assert candidate(row, [store])['candidates'][0]['floor_evidence'] == 'unknown'


def test_multiple_store_candidates_are_not_selected_by_floor():
    row, store = fixtures()
    other = dict(store, bizesId='synthetic-2', flrNo='3')
    result = candidate(row, [store, other])
    assert result['status'] == 'multiple_store_candidates'
    assert len(result['candidates']) == 2 and result['store_id'] is None


@pytest.mark.parametrize('detail', ['201호', '1~2층', '1-2층', '1,2층', '1층 2층', '지층'])
def test_uncertain_floor_is_not_inferred(detail):
    assert floor('서울 도로 1, ' + detail, address=True) is None


def test_basement_floor_and_missing_name():
    assert floor('서울 도로 1, 지하 1층', address=True) == -1
    assert floor('B1') == -1
    row, store = fixtures()
    row['BPLCNM'] = ''
    assert candidate(row, [store])['status'] == 'missing_name_or_address'
    row['BPLCNM'] = '손상\ufffd'
    assert candidate(row, [store])['status'] == 'blocked_corrupted_text'


def test_missing_inputs_fail_without_report(tmp_path):
    output = tmp_path / 'report.json'
    with pytest.raises(ValueError, match='missing_source'):
        audit(tmp_path, output)
    assert not output.exists()


def test_audit_counts_multiple_license_claims_and_preserves_sources(tmp_path, monkeypatch):
    import data.validation.industry_public_candidates as module
    monkeypatch.setattr(module, 'ACTIVE_HUBS', {'synthetic-hub': None})
    monkeypatch.setattr(module, 'LICENSES', {'synthetic-source': 'synthetic-service'})
    row, store = fixtures()
    stores = tmp_path / 'stores' / 'synthetic-hub'
    stores.mkdir(parents=True)
    store_path = stores / '001.json'
    store_path.write_text(json.dumps({'body': {'items': [store]}}), encoding='utf-8')
    licenses = tmp_path / 'seoul' / 'synthetic-service' / 'all'
    licenses.mkdir(parents=True)
    rows = [dict(row, OPNSFTEAMCODE='synthetic-team', MGTNO=str(i)) for i in (1, 2)]
    (licenses / '001.json').write_text(json.dumps({'synthetic-service': {'row': rows}}), encoding='utf-8')
    output = tmp_path / 'report.json'
    result = audit(tmp_path, output)
    assert result['status'] == 'diagnostic_only'
    assert result['stores_claimed_by_multiple_licenses'] == 1
    assert result['by_source']['synthetic-source']['counts']['floor_equal'] == 2
    assert all(len(source['sha256']) == 64 for source in result['sources'])
    sample = result['by_source']['synthetic-source']['samples']['candidate_only'][0]
    assert sample['store_id'] is None and sample['identity'][0] == 'synthetic-source'
    with pytest.raises(FileExistsError):
        audit(tmp_path, output)
