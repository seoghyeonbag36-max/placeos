"""광주 앵커 산정은 시 집계·결측·과거 분기를 세지 않는다."""
import pytest

from scripts.audit_gwangju_capacity import summarize


def test_anchor_count_excludes_aggregate_missing_and_old_quarter():
    def row(name, value=1, quarter='202602'):
        return {'CLS_FULLNM': name, 'DTA_VAL': value, 'WRTTIME_IDTFR_ID': quarter}

    rows = [row('광주'), row('광주>상무지구'), row('광주>상무지구'),
            row('광주>결측', None), row('광주>과거', quarter='202601'),
            row('경기>광주시가지'), row('서울>도심'), row('서울>도심>종로')]
    report = summarize({'vac_mid': rows, 'rent_small': rows})
    assert report['anchors'] == ['광주>상무지구']
    assert report['seoul_anchor_count'] == 1


def test_empty_source_fails_instead_of_inventing_capacity():
    with pytest.raises(ValueError):
        summarize({'vac_mid': []})
