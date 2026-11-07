"""추천 권역의 누락 관측점·완주 원본·기존 작업표 보존을 검증한다."""
import copy

import pytest

from scripts import include_jeonju_recommendations as inclusion
from scripts import collect_regional_research_ledgers as source


def test_gap_centers_are_observed_points_and_cover_every_gap():
    points = [dict(MGTNO=str(i), lon=127.0+i*0.01, lat=35.8) for i in range(4)]
    selected = inclusion.gap_centers(points, [(127.0,35.8,700)])
    covered = {i for row in selected for i in row['covered_license_ids']}
    assert covered == {'1','2','3'}
    assert all(any(row['MGTNO']==p['MGTNO'] and (row['lon'],row['lat'])==(p['lon'],p['lat'])
                   for p in points) for row in selected)
    assert inclusion.gap_centers(points, [(p['lon'],p['lat'],700) for p in points]) == []


def test_eco_name_in_other_dong_does_not_expand_eco_scope():
    row=dict(SITEWHLADDR='전주시 완산구 효자동1가',BPLCNM='에코 식당',RDNWHLADDR='')
    assert not inclusion.GROUPS['에코시티'](row)
    row['SITEWHLADDR']='전주시 덕진구 송천동2가'
    assert inclusion.GROUPS['에코시티'](row)


def test_plan_extension_deduplicates_pnus_preserves_previous_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(inclusion,'ROOT',tmp_path)
    monkeypatch.setattr(inclusion,'REPORT',tmp_path/'reports/scope.json')
    pnu='5211111111111111111'
    original=dict(locations=[dict(id='old',pnus=[pnu],unresolved=[])],targets=[dict(pnu=pnu,locations=['old'])],
                  unresolved=[],legacy_expos={},legacy_sources={})
    baseline=copy.deepcopy(original)
    stores=tmp_path/'data/bronze/new/day/stores_raw.json'
    source.atomic_json(stores,[dict(bizesId='one',bldMngNo='building')])
    report=dict(added_centers=[dict(id='new',label='추천 보완',region='전주',store_probe=dict(
        path=stores.relative_to(tmp_path).as_posix(),sha256=source.fingerprint(stores)))])
    source.atomic_json(inclusion.REPORT,report)
    monkeypatch.setattr(inclusion.ledgers,'group_by_building',lambda _: {
        'valid':dict(lnoCd=pnu),'missing':dict(lnoCd='')})
    result=inclusion.extend_plan(original,report)
    assert original==baseline
    assert result['locations'][0]==baseline['locations'][0]
    assert len(result['targets'])==1 and result['targets'][0]['locations']==['old','new']
    assert result['locations'][1]['unresolved']==['missing']
    assert inclusion.extend_plan(result,report)==result
    archive=tmp_path/result['scope_additions'][0]['report']
    assert source.fingerprint(archive)==result['scope_additions'][0]['sha256']


def test_wanju_partial_page_does_not_get_completion_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(inclusion,'ROOT',tmp_path)
    monkeypatch.setattr(inclusion,'load_env',lambda:None)
    pages=iter([[dict(MNG_NO='one',ROAD_NM_ADDR='전북 완주군 이서면 기지로')],[]])
    monkeypatch.setattr(inclusion,'fetch',lambda _:dict(response=dict(body=dict(
        totalCount=2,items=dict(item=next(pages))))))
    with pytest.raises(ValueError,match='부분 수집'):
        inclusion.wanju_source()
    assert not list(tmp_path.glob('data/bronze/wanju_innovation_licensing/*/complete.json'))
