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


def test_planned_school_build_preserves_record_and_skips_metadata(tmp_path, monkeypatch):
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
    output = tmp_path / 'silver.json'
    result = build(tmp_path, tmp_path, output, tmp_path / 'report.json')
    assert result['status'] == 'validated'
    assert result['planned_schools_without_identity'] == 1
    row = json.loads(output.read_text(encoding='utf-8'))['datasets']['schoolInfo'][0]
    assert row['foundation_label'] == '(예정)' and row['identity'] is None
    assert row['fields']['SD_SCHUL_CODE'] is None
