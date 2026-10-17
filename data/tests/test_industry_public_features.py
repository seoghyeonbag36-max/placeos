"""합성 부분 Silver로 피처 결측·격리·출처·해시 계약을 검증한다."""
import io
import json
import pytest

from data.pipelines.build_industry_public_features import build, digest, feature, numeric
from data.validation.industry_public_stream import silver_rows


def record():
    return {'identity': ['synthetic-team', 'synthetic-id'], 'fields': {
        'ACA_NM': '합성학원', 'FA_RDNMA': '합성 도로 1', 'TOFOR_SMTOT': 0,
        'DTM_RCPTN_ABLTY_NMPR_SMTOT': None}, 'source_row_1based': 1,
        'provenance': {'source': 'acaInsTiInfo', 'source_path': 'synthetic.json',
                       'source_sha256': 'a' * 64, 'collected_on': '2026-10-17'}}


def test_feature_missing_stays_null_and_zero_is_observed():
    result = feature('acaInsTiInfo', record())
    assert result['values']['TOFOR_SMTOT'] == 0
    assert result['observed']['TOFOR_SMTOT'] is True
    assert result['values']['DTM_RCPTN_ABLTY_NMPR_SMTOT'] is None
    assert result['store_id'] is None
    assert result['provenance'] == record()['provenance']


@pytest.mark.parametrize('value', ['unknown', '1,00', 'nan', 'inf', -1, True, {}])
def test_invalid_feature_value_fails(value):
    with pytest.raises(ValueError, match='invalid_numeric'):
        numeric(value)


def test_thousands_separator_is_normalized_without_changing_raw_value():
    row = record()
    row['fields']['TOFOR_SMTOT'] = '1,926.52'
    result = feature('acaInsTiInfo', row)
    assert result['values']['TOFOR_SMTOT'] == 1926.52
    assert result['raw_values']['TOFOR_SMTOT'] == '1,926.52'


def inputs(tmp_path):
    silver, quarantine, verified = [tmp_path / name for name in ('silver.json', 'quarantine.json', 'verified.json')]
    silver.write_text(json.dumps({'status': 'partial_quarantined', 'datasets': {'acaInsTiInfo': [record()]},
                                 'links': {}}), encoding='utf-8')
    quarantine.write_text(json.dumps({'status': 'partial_quarantined', 'quarantined': {}}))
    verification = {'status': 'verified', 'accepted_rows': 1,
        'quarantined_identities_absent_from_datasets_and_links': True,
        'quarantine_raw_fields_and_source_hashes_verified': True,
        'datasets_sha256': digest(silver), 'quarantine_sha256': digest(quarantine)}
    verified.write_text(json.dumps(verification))
    return silver, verified, quarantine


def test_feature_build_preserves_provenance_and_only_uses_silver(tmp_path):
    paths = inputs(tmp_path)
    output, report = tmp_path / 'features.jsonl', tmp_path / 'report.json'
    result = build(*paths, output, report)
    assert result['feature_rows'] == 1
    assert json.loads(output.read_text(encoding='utf-8'))['provenance'] == record()['provenance']
    with pytest.raises(FileExistsError):
        build(*paths, output, report)


def test_changed_silver_hash_blocks_features(tmp_path):
    paths = inputs(tmp_path)
    paths[0].write_text('{}')
    with pytest.raises(ValueError, match='input_hash_mismatch'):
        build(*paths, tmp_path / 'features.jsonl', tmp_path / 'report.json')
    assert not (tmp_path / 'features.jsonl').exists()


def test_quarantined_identity_blocks_features(tmp_path):
    silver, verified, quarantine = inputs(tmp_path)
    quarantine.write_text(json.dumps({'status': 'partial_quarantined',
        'quarantined': {'acaInsTiInfo': [{'identity': record()['identity']}]}}))
    verification = json.loads(verified.read_text())
    verification['quarantine_sha256'] = digest(quarantine)
    verified.write_text(json.dumps(verification))
    with pytest.raises(ValueError, match='quarantined_identity'):
        build(silver, verified, quarantine, tmp_path / 'features.jsonl', tmp_path / 'report.json')
    assert not (tmp_path / 'features.jsonl').exists()


def test_chunk_boundaries_and_truncated_silver(tmp_path):
    silver = inputs(tmp_path)[0]
    assert list(silver_rows(silver, chunk_size=7))[0][2] == record()
    silver.write_text(silver.read_text(encoding='utf-8')[:-1], encoding='utf-8')
    with pytest.raises(ValueError):
        list(silver_rows(silver, chunk_size=7))
