"""합성 응답으로 식별키·형식·문자 손실의 복구 오판을 막는다."""
import json
import pytest

from data.validation.industry_public_recovery import assess, compare, read_rows, read_upstream_rows


def row(name='손상\ufffd'):
    return {'OPNSFTEAMCODE': 'synthetic-team', 'MGTNO': 'synthetic-id',
            'BPLCNM': name, 'RDNWHLADDR': ''}


@pytest.mark.parametrize('observed,state', [
    ('손상\ufffd', 'replacement_character'), ('손상?', 'question_mark_unresolved'),
    ('', 'missing'), (None, 'missing'),
])
def test_lossy_alternate_text_is_not_recovery(observed, state):
    result = compare(row(), [row(observed)])
    assert result['status'] == 'unresolved'
    assert result['fields']['BPLCNM']['state'] == state
    assert result['replacement_applied'] is False


def test_clean_alternate_text_requires_review_and_preserves_baseline():
    baseline = row()
    result = compare(baseline, [row('정상 이름')])
    assert result['status'] == 'review_required'
    assert result['replacement_applied'] is False
    assert baseline['BPLCNM'] == '손상\ufffd'


def test_identity_shift_and_duplicates_are_not_accepted():
    assert compare(row(), [dict(row(), MGTNO='other')])['status'] == 'identity_not_found'
    assert compare(row(), [row(), row()])['status'] == 'identity_not_unique'
    with pytest.raises(ValueError, match='missing_baseline_identity'):
        compare({}, [row()])


def test_xls_text_requires_explicit_strict_encoding(tmp_path):
    path = tmp_path / 'fixture.xls'
    path.write_bytes(('OPNSFTEAMCODE\tMGTNO\tBPLCNM\nsynthetic-team\tsynthetic-id\t상호?\n').encode('cp949'))
    with pytest.raises(ValueError, match='explicit_encoding_required'):
        read_rows(path, 'synthetic')
    with pytest.raises(UnicodeDecodeError):
        read_rows(path, 'synthetic', 'utf-8')
    assert read_rows(path, 'synthetic', 'cp949')[0]['BPLCNM'] == '상호?'


def test_xml_success_and_error_response_validation(tmp_path):
    path = tmp_path / 'fixture.xml'
    path.write_text('<synthetic><RESULT><CODE>INFO-000</CODE></RESULT><row><MGTNO>synthetic-id</MGTNO></row></synthetic>')
    assert read_rows(path, 'synthetic')[0]['MGTNO'] == 'synthetic-id'
    path.write_text('<RESULT><CODE>ERROR-300</CODE></RESULT>')
    with pytest.raises(ValueError, match='unsuccessful_response'):
        read_rows(path, 'synthetic')


def test_assessment_preserves_hashes_and_never_writes_sources(tmp_path):
    baseline = tmp_path / 'baseline.json'
    observation = tmp_path / 'observation.json'
    def payload(value):
        return json.dumps({'synthetic': {'RESULT': {'CODE': 'INFO-000'}, 'row': [value]}})
    baseline.write_text(payload(row()))
    observation.write_text(payload(row('상호?')))
    before = baseline.read_bytes(), observation.read_bytes()
    result = assess(baseline, observation, 'synthetic', ('synthetic-team', 'synthetic-id'))
    assert result['status'] == 'unresolved'
    assert len(result['baseline_sha256']) == len(result['observation_sha256']) == 64
    assert before == (baseline.read_bytes(), observation.read_bytes())


def test_upstream_explicit_field_mapping_does_not_repair_loss(tmp_path):
    path = tmp_path / 'upstream.json'
    payload = {'response': {'header': {'resultCode': '0'}, 'body': {
        'totalCount': 1, 'items': {'item': [{'OPN_ATMY_GRP_CD': 'synthetic-team',
            'MNG_NO': 'synthetic-id', 'BPLC_NM': '손상\ufffd', 'ROAD_NM_ADDR': ''}]}}}}
    path.write_text(json.dumps(payload))
    assert compare(row(), read_upstream_rows(path))['status'] == 'unresolved'
    payload['response']['body']['totalCount'] = 2
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='incomplete_upstream_observations'):
        read_upstream_rows(path)
    payload['response']['header']['resultCode'] = '30'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='unsuccessful_upstream_response'):
        read_upstream_rows(path)
