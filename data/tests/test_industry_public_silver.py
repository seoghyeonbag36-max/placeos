"""합성 원천으로 결손 시 실패와 보수적인 연결을 검증한다."""
import json
from datetime import date
import pytest
from data.pipelines.build_industry_public_silver import normalize, match, build


@pytest.mark.parametrize('founded,planned', [('20261018', True), ('20261017', False), ('20261016', False)])
def test_school_future_foundation_is_planned(founded, planned):
    row = {'ATPT_OFCDC_SC_CODE': 'B10', 'SD_SCHUL_CODE': 'synthetic-1', 'FOND_YMD': founded}
    result = normalize([row], ('ATPT_OFCDC_SC_CODE', 'SD_SCHUL_CODE'), 'schoolInfo',
                       'fixture.json', 'abc', '2026-10-17', date(2026, 10, 17))[0]
    assert (result['foundation_status'] == 'planned') is planned
    assert result['foundation_label'] == ('(예정)' if planned else None)
    assert result['fields']['FOND_YMD'] == founded
    assert result['status_as_of'] == '2026-10-17'


def test_planned_school_keeps_missing_identity_without_inference():
    row = {'ATPT_OFCDC_SC_CODE': 'B10', 'SD_SCHUL_CODE': '   ', 'FOND_YMD': '20270301'}
    result = normalize([row], ('ATPT_OFCDC_SC_CODE', 'SD_SCHUL_CODE'), 'schoolInfo',
                       'fixture.json', 'abc', '2026-10-17', date(2026, 10, 17))[0]
    assert result['identity'] is None
    assert result['fields']['SD_SCHUL_CODE'] is None
    assert result['foundation_label'] == '(예정)'
    assert result['source_row_1based'] == 1
    row['ATPT_OFCDC_SC_CODE'] = None
    with pytest.raises(ValueError, match='missing_identity'):
        normalize([row], ('ATPT_OFCDC_SC_CODE', 'SD_SCHUL_CODE'), 'schoolInfo',
                  'fixture.json', 'abc', '2026-10-17', date(2026, 10, 17))


@pytest.mark.parametrize('founded', ['20260230', '2027', 'unknown'])
def test_invalid_foundation_date_fails(founded):
    with pytest.raises(ValueError, match='invalid_foundation_date'):
        normalize([{'id': '1', 'FOND_YMD': founded}], ('id',), 'schoolInfo',
                  'fixture.json', 'abc', '2026-10-17', date(2026, 10, 17))


def norm(rows):
    return normalize(rows, ("id",), "synthetic", "fixture.json", "abc", "2026-10-17")


def test_missing_identity_fails():
    for row in [{}, {"id": "   "}, {"id": None}]:
        with pytest.raises(ValueError, match="missing_identity"):
            norm([row])


@pytest.mark.parametrize('field', ['BPLCNM', 'RDNWHLADDR'])
def test_corrupted_license_match_text_blocks_normalization(field):
    # 합성 원천: 손상 문자열을 정상적인 미매칭으로 승격하지 않는다.
    row = {'id': 'synthetic-1', 'BPLCNM': '상호', 'RDNWHLADDR': '서울 도로 1'}
    row[field] += '\ufffd'
    with pytest.raises(ValueError, match=f'fixture.json: row=1: corrupted_match_text: {field}'):
        normalize([row], ('id',), 'beauty', 'fixture.json', 'abc', '2026-10-17')


def test_corrupted_match_text_cannot_form_a_false_exact_match():
    rows = norm([{'id': '1', 'name': '상호\ufffd', 'address': '도로 1'}])
    stores = [{'bizesId': 's1', 'bizesNm': '상호\ufffd', 'rdnmAdr': '도로 1'}]
    with pytest.raises(ValueError, match='corrupted_match_text'):
        match(rows, stores, 'name', 'address')


def test_missing_license_address_is_preserved():
    row = {'id': 'synthetic-1', 'BPLCNM': '상호', 'RDNWHLADDR': ' '}
    result = normalize([row], ('id',), 'beauty', 'fixture.json', 'abc', '2026-10-17')
    assert result[0]['fields']['RDNWHLADDR'] is None
    assert match(result, [], 'BPLCNM', 'RDNWHLADDR')[0]['reason'] == 'missing_name_or_address'


def test_conflicting_duplicates_fail():
    with pytest.raises(ValueError, match="conflicting_identity"):
        norm([{"id": "1", "value": 1}, {"id": "1", "value": 2}])
    assert len(norm([{"id": "1"}, {"id": "1"}])) == 1


def test_missing_values_stay_null():
    fields = norm([{"id": "1", "blank": "  ", "unknown": None, "zero": 0}])[0]["fields"]
    assert fields == {"id": "1", "blank": None, "unknown": None, "zero": 0}


def test_source_provenance_preserved():
    assert norm([{"id": "1"}])[0]["provenance"] == {
        "source": "synthetic", "source_path": "fixture.json",
        "source_sha256": "abc", "collected_on": "2026-10-17"}


def test_ambiguous_matches_remain_unmatched():
    rows = norm([{"id": "1", "name": "A", "address": "Road 1"}])
    stores = [{"bizesId": k, "bizesNm": "A", "rdnmAdr": "Road 1"} for k in ["s1", "s2"]]
    result = match(rows, stores, "name", "address")[0]
    assert result["status"] == "ambiguous" and result["store_id"] is None
    assert match(rows, stores[:1], "name", "address")[0]["store_id"] == "s1"
    stores[0]["rdnmAdr"] = "Road 2"
    assert match(rows, stores[:1], "name", "address")[0]["status"] == "unmatched"


def test_existing_outputs_are_not_overwritten(tmp_path):
    output = tmp_path / "silver.json"
    output.write_text("existing")
    with pytest.raises(FileExistsError):
        build(tmp_path, tmp_path, output, tmp_path / "report.json")
    assert output.read_text() == "existing"


def test_missing_inputs_do_not_create_silver(tmp_path):
    output = tmp_path / "silver.json"
    report = build(tmp_path, tmp_path, output, tmp_path / "report.json")
    assert report["status"] == "blocked" and not output.exists()


def test_blank_school_identity_blocks_promotion(tmp_path):
    # 합성 학교 원본: 공백 키를 정상으로 세지 않으며 부분 Silver도 남기지 않는다.
    for source, row in [
        ("acaInsTiInfo", {"ATPT_OFCDC_SC_CODE": "B10", "ACA_ASNUM": "synthetic-1"}),
        ("schoolInfo", {"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "   "}),
    ]:
        folder = tmp_path / source
        folder.mkdir()
        (folder / "001.json").write_text(json.dumps({source: [{"row": [row]}]}))
    output = tmp_path / "silver.json"
    result = build(tmp_path, tmp_path, output, tmp_path / "report.json")
    assert result["status"] == "blocked"
    assert "missing_identity" in result["errors"][0]
    assert result["silver_written"] is False
    assert "matching" in result["not_processed"]
    assert not output.exists()


@pytest.mark.parametrize('corrupted_license', [False, True])
def test_planned_school_build_preserves_record_and_skips_metadata(tmp_path, monkeypatch, corrupted_license):
    import data.pipelines.build_industry_public_silver as module
    monkeypatch.setattr(module, 'LICENSES', {})
    monkeypatch.setattr(module, 'ACTIVE_HUBS', {})
    for source, row in [
        ('acaInsTiInfo', {'ATPT_OFCDC_SC_CODE': 'B10', 'ACA_ASNUM': 'synthetic-1'}),
        ('schoolInfo', {'ATPT_OFCDC_SC_CODE': 'B10', 'SD_SCHUL_CODE': ' ', 'FOND_YMD': '99990301'}),
    ]:
        folder = tmp_path / source
        folder.mkdir()
        (folder / '001.json').write_text(json.dumps({source: [{'row': [row]}]}))
        (folder / '001.json.meta.json').write_text('{}')
    folder = tmp_path / 'school_locations_file'
    folder.mkdir()
    (folder / '001.json').write_text(json.dumps([{'SCHOOL_ID': 'synthetic-location'}]))
    folder = tmp_path / 'school_students'
    folder.mkdir()
    (folder / '2026_02.json').write_text(json.dumps({'list': [{'SCHUL_CODE': 'synthetic-student'}]}))
    if corrupted_license:
        monkeypatch.setattr(module, 'LICENSES', {'beauty': 'synthetic_license'})
        folder = tmp_path / 'seoul' / 'synthetic_license' / 'all'
        folder.mkdir(parents=True)
        (folder / '001.json').write_text(json.dumps({'synthetic_license': {'row': [{
            'OPNSFTEAMCODE': 'synthetic-team', 'MGTNO': 'synthetic-id',
            'BPLCNM': '손상\ufffd', 'RDNWHLADDR': '서울 도로 1',
        }]}}))
    output = tmp_path / 'silver.json'
    result = build(tmp_path, tmp_path, output, tmp_path / 'report.json')
    if corrupted_license:
        assert result['status'] == 'blocked'
        assert result['silver_written'] is False
        assert any('corrupted_match_text: BPLCNM' in error for error in result['errors'])
        assert not output.exists()
        return
    assert result['status'] == 'validated'
    assert result['planned_schools_without_identity'] == 1
    row = json.loads(output.read_text(encoding='utf-8'))['datasets']['schoolInfo'][0]
    assert row['foundation_label'] == '(예정)' and row['identity'] is None
    assert row['fields']['SD_SCHUL_CODE'] is None


@pytest.fixture
def partial_inputs(tmp_path, monkeypatch):
    """상충 키·문자 손상을 분리해서 검증하는 합성 전체 입력."""
    import data.pipelines.build_industry_public_silver as module
    monkeypatch.setattr(module, 'LICENSES', {'beauty': 'synthetic_license'})
    monkeypatch.setattr(module, 'ACTIVE_HUBS', {})
    def write(relative, payload):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path
    for source, row in [
        ('acaInsTiInfo', {'ATPT_OFCDC_SC_CODE': 'B10', 'ACA_ASNUM': 'synthetic-academy'}),
        ('schoolInfo', {'ATPT_OFCDC_SC_CODE': 'B10', 'SD_SCHUL_CODE': 'synthetic-school'}),
    ]:
        write(f'{source}/001.json', {source: [{'row': [row]}]})
    write('school_locations_file/001.json', [{'SCHOOL_ID': 'synthetic-location'}])
    write('school_students/2026_02.json', {'list': [{'SCHUL_CODE': 'synthetic-student'}]})
    clean_row = {'OPNSFTEAMCODE': 'synthetic-team', 'MGTNO': 'clean', 'BPLCNM': '정상', 'RDNWHLADDR': ''}
    damaged_row = dict(clean_row, MGTNO='damaged', BPLCNM='  손상\ufffd  ')
    write('seoul/synthetic_license/all/001.json', {'synthetic_license': {'row': [clean_row, damaged_row]}})
    return tmp_path, write, clean_row, damaged_row


def partial_build(inputs):
    root = inputs[0]
    report = build(root, root, root / 'silver.json', root / 'report.json', root / 'quarantine.json')
    return report, root


def test_partial_counts_reconcile(partial_inputs):
    root, write, clean_row, damaged = partial_inputs
    # 동일 원천의 같은 행이 반복돼도 관측 행수 항등식은 보존한다.
    write('seoul/synthetic_license/all/001.json', {'synthetic_license': {'row': [clean_row, clean_row, damaged]}})
    report, _ = partial_build(partial_inputs)
    assert report['status'] == 'partial_quarantined'
    assert report['row_accounting']['beauty'] == {'raw_rows': 3, 'accepted_rows': 2, 'quarantined_rows': 1}
    for counts in report['row_accounting'].values():
        assert counts['accepted_rows'] + counts['quarantined_rows'] == counts['raw_rows']


def test_quarantined_rows_never_enter_accepted(partial_inputs):
    report, root = partial_build(partial_inputs)
    accepted = json.loads((root / 'silver.json').read_text(encoding='utf-8'))
    quarantine = json.loads((root / 'quarantine.json').read_text(encoding='utf-8'))
    assert accepted['status'] == quarantine['status'] == 'partial_quarantined'
    assert [row['identity'][1] for row in accepted['datasets']['beauty']] == ['clean']
    assert [row['identity'][1] for row in accepted['links']['beauty']] == ['clean']
    assert quarantine['quarantined']['beauty'][0]['identity'][1] == 'damaged'
    assert report['quarantine_written'] and report['silver_written']


@pytest.mark.parametrize('across_pages', [False, True])
def test_identity_conflicts_still_block_partial(partial_inputs, across_pages):
    root, write, clean_row, damaged = partial_inputs
    conflicting = dict(damaged, MGTNO='clean')
    write('seoul/synthetic_license/all/001.json', {'synthetic_license': {'row': [clean_row] if across_pages else [clean_row, conflicting]}})
    if across_pages:
        write('seoul/synthetic_license/all/002.json', {'synthetic_license': {'row': [conflicting]}})
    report, _ = partial_build(partial_inputs)
    assert report['status'] == 'blocked'
    assert any('conflicting_identity' in error for error in report['errors'])
    assert not (root / 'silver.json').exists() and not (root / 'quarantine.json').exists()


def test_missing_identity_still_blocks_partial(partial_inputs):
    root, write, _, damaged = partial_inputs
    damaged['MGTNO'] = None
    write('seoul/synthetic_license/all/001.json', {'synthetic_license': {'row': [damaged]}})
    report, _ = partial_build(partial_inputs)
    assert report['status'] == 'blocked' and not (root / 'silver.json').exists()
    assert any('missing_identity' in error for error in report['errors'])


def test_partial_preserves_source_provenance(partial_inputs):
    import hashlib
    root, _, _, damaged = partial_inputs
    partial_build(partial_inputs)
    quarantine = json.loads((root / 'quarantine.json').read_text(encoding='utf-8'))['quarantined']['beauty'][0]
    assert quarantine['raw_fields'] == damaged
    assert quarantine['source_row_1based'] == 2
    assert quarantine['quarantine_reason'] == 'corrupted_match_text'
    path = root / 'seoul/synthetic_license/all/001.json'
    assert quarantine['provenance']['source_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert quarantine['provenance']['source'] == 'beauty'


def test_existing_quarantine_is_not_overwritten(partial_inputs):
    root = partial_inputs[0]
    path = root / 'quarantine.json'
    path.write_text('existing')
    with pytest.raises(FileExistsError):
        partial_build(partial_inputs)
    assert path.read_text() == 'existing' and not (root / 'silver.json').exists()


def test_partial_output_paths_must_be_distinct(tmp_path):
    with pytest.raises(ValueError, match='output_paths_must_be_distinct'):
        build(tmp_path, tmp_path, tmp_path / 'same.json', tmp_path / 'report.json', tmp_path / 'same.json')
