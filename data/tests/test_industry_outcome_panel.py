"""합성 원천으로 분기·업종 분리와 결손 보존을 검증한다."""
import json

import pytest

pd = pytest.importorskip('pandas', reason='분기 패널은 pandas 선택 의존성이 필요합니다')

from data.pipelines.build_industry_outcome_panel import build, normalize


def row(**changes):
    return dict(district_id='hub', STDR_YYQU_CD='20261', TRDAR_CD='1', SVC_INDUTY_CD='A',
                SVC_INDUTY_CD_NM='합성 업종', THSMON_SELNG_AMT='100', THSMON_SELNG_CO='2') | changes


def test_panel_keeps_quarters_industries_and_unknown_values_separate():
    frame = normalize([row(), row(), row(STDR_YYQU_CD='20262', THSMON_SELNG_AMT=None),
                       row(SVC_INDUTY_CD='B', THSMON_SELNG_AMT='0')])
    assert len(frame) == 3
    assert frame['estimated_sales_krw'].isna().sum() == 1
    assert frame['estimated_sales_krw'].eq(0).sum() == 1


@pytest.mark.parametrize('bad', [dict(THSMON_SELNG_AMT='invalid'), dict(STDR_YYQU_CD='20265'),
                               dict(TRDAR_CD=None), dict(THSMON_SELNG_CO=-1)])
def test_panel_rejects_invalid_observations(bad):
    with pytest.raises(ValueError):
        normalize([row(**bad)])


def test_panel_rejects_conflicting_duplicates():
    with pytest.raises(ValueError):
        normalize([row(), row(THSMON_SELNG_AMT=200)])


def test_panel_build_preserves_provenance_and_existing_files(tmp_path):
    source = tmp_path / 'source.json'
    source.write_text(json.dumps([row()]), encoding='utf-8')
    report = build(source, '2026-10-16', tmp_path)
    gold = pd.read_parquet(tmp_path / report['gold_path'])
    assert gold.iloc[0]['source'] == 'seoul_trdar_estimated_sales'
    assert gold.iloc[0]['observed_sales']
    with pytest.raises(FileExistsError):
        build(source, '2026-10-16', tmp_path)
