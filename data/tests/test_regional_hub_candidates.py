"""출처가 부족한 탐색 후보의 공개와 기존 거점 누락을 막는다."""
import json
from pathlib import Path

import pytest

from data.config.page_hubs import ACTIVE_HUBS
from scripts.audit_regional_hub_candidates import cluster_candidates, discovery, ready_for_serving, store_metrics


def test_regional_expansion_preserves_previous_served_hubs():
    root = Path(__file__).resolve().parents[2]
    report = json.loads((root / 'reports/regional_hub_candidates_2026-11-03.json').read_text(encoding='utf-8'))
    assert set(report['baseline_active_ids']) <= set(ACTIVE_HUBS)
    for row in report['registered_unserved']:
        if row['ready_without_policy_change']:
            assert row['slug'] in ACTIVE_HUBS, row['slug']


def test_partial_anchor_or_incomplete_ledger_never_passes():
    stages = [dict(stage=s, status='ok') for s in
              ('등록', '점포', '폴리곤', '대장', '정밀분모', 'Page마스터', '앵커', '공실유닛')]
    assert ready_for_serving(stages, '')
    for stage in ('앵커', '대장', 'Page마스터'):
        broken = [{**r, 'status': 'partial'} if r['stage'] == stage else r for r in stages]
        assert not ready_for_serving(broken, '')
    assert not ready_for_serving(stages, '단일시설')
    assert not ready_for_serving(stages[:-1], '')


def test_store_probe_rejects_missing_or_duplicate_keys():
    row = dict(bizesId='one', bldMngNo='building')
    assert store_metrics([row])['stores'] == 1
    for rows in ([], [row, row], [dict(bldMngNo='building')], [dict(bizesId='one')]):
        with pytest.raises(ValueError):
            store_metrics(rows)


def test_600m_cluster_keeps_transitive_members_and_largest_measured_center():
    rows = [dict(candidate_id=str(i), label=str(i), lon=127 + i * 0.005, lat=35,
                 store_probe=dict(metrics=dict(stores=i + 1))) for i in range(3)]
    clusters = cluster_candidates(rows)
    assert len(clusters) == 1
    assert set(clusters[0]['members']) == {'0', '1', '2'}
    assert clusters[0]['representative'] == '2'


def test_support_extension_preserves_existing_measured_values(tmp_path):
    from scripts.build_regional_hub_support import extend
    path = tmp_path / 'shared.json'
    original = dict(source='실측', hubs=dict(existing=dict(value=None, source='관측 없음')))
    path.write_text(json.dumps(original), encoding='utf-8')
    extend(path, 'hubs', dict(existing=dict(value=999), added=dict(value=1)))
    result = json.loads(path.read_text(encoding='utf-8'))
    assert result['hubs']['existing'] == original['hubs']['existing']
    assert result['source'] == original['source']
    assert result['hubs']['added']['value'] == 1


def test_discovery_excludes_closed_duplicates_and_wrong_region():
    from types import SimpleNamespace
    row = dict(MGTNO='one', SITEWHLADDR='경기도 수원시 팔달구 인계동 1',
               TRDSTATEGBN='01', DCBYMD='', X=127.03, Y=37.26, CRS='EPSG:4326')
    rows = [row, row, {**row, 'MGTNO': 'closed', 'DCBYMD': '20260101'},
            {**row, 'MGTNO': 'outside', 'SITEWHLADDR': '서울특별시 중구 인계동 1'}]
    candidates, counts = discovery(rows, '경기', {'near': SimpleNamespace(cx=127.03, cy=37.26)})
    assert len(candidates) == 1
    assert candidates[0]['open_restaurants'] == 1
    assert candidates[0]['lon'] == row['X']
    assert not candidates[0]['outside_1km']
    assert counts['not_open'] == counts['outside_region'] == counts['missing_or_duplicate_id'] == 1
