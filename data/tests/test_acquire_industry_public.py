"""합성 API 응답으로 부분 수집·서울 범위·인허가 식별 키를 검증한다."""
import json

import pytest

from data.collectors.acquire_industry_public import audit_license, validate_neis, validate_student_rows


def page(rows, total=2):
    return {'schoolInfo': [{'head': [{'list_total_count': total}, {'RESULT': {'CODE': 'INFO-000'}}]},
                           {'row': rows}]}


def test_neis_requires_complete_unique_seoul_rows():
    a = {'ATPT_OFCDC_SC_CODE': 'B10', 'SD_SCHUL_CODE': 'a'}
    b = {**a, 'SD_SCHUL_CODE': 'b'}
    assert not validate_neis([page([a])], 'schoolInfo', 'SD_SCHUL_CODE')['complete']
    assert validate_neis([page([a]), page([b])], 'schoolInfo', 'SD_SCHUL_CODE')['complete']
    assert not validate_neis([page([a, a])], 'schoolInfo', 'SD_SCHUL_CODE')['complete']
    assert not validate_neis([page([a, {**b, 'ATPT_OFCDC_SC_CODE': 'C10'}])], 'schoolInfo', 'SD_SCHUL_CODE')['complete']


def test_neis_rejects_api_error():
    with pytest.raises(ValueError):
        validate_neis([{'RESULT': {'CODE': 'INFO-200'}}], 'schoolInfo', 'SD_SCHUL_CODE')


def test_license_identity_includes_municipality(tmp_path):
    rows = [{'OPNSFTEAMCODE': '1', 'MGTNO': '001'}, {'OPNSFTEAMCODE': '2', 'MGTNO': '001'}]
    target = tmp_path / '001.json'
    target.write_text(json.dumps({'service': {'list_total_count': 2, 'row': rows}}), encoding='utf-8')
    result = audit_license(tmp_path, 'service')
    assert result['status'] == 'reused_verified'
    assert result['duplicate_ids'] == 0
    rows[1]['OPNSFTEAMCODE'] = '1'
    target.write_text(json.dumps({'service': {'list_total_count': 2, 'row': rows}}), encoding='utf-8')
    assert audit_license(tmp_path, 'service')['status'] == 'incomplete_or_invalid'


def test_license_partial_page_is_not_marked_complete(tmp_path):
    (tmp_path / '001.json').write_text(json.dumps({'service': {'list_total_count': 3, 'row': [
        {'OPNSFTEAMCODE': '1', 'MGTNO': '001'}]}}), encoding='utf-8')
    assert audit_license(tmp_path, 'service')['status'] == 'incomplete_or_invalid'


def test_student_response_scope_difference_is_preserved():
    rows = [{'SCHUL_CODE': 'a', 'LCTN_SC_CODE': '01', 'SCHUL_KND_SC_CODE': '03'},
            {'SCHUL_CODE': 'b', 'LCTN_SC_CODE': '01', 'SCHUL_KND_SC_CODE': '25'}]
    result = validate_student_rows(rows, '03')
    assert result['region_unique_check']
    assert result['rows'] == 2 and result['unexpected_kind_rows'] == 1
    assert result['returned_kind_counts'] == {'03': 1, '25': 1}
