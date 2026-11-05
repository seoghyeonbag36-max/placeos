"""광주 13·전주 5의 Gold가 네 트랙에 연결되고 결측은 계산 불가로 남는지 검사한다."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import floor_vacancy, marketing, vacant_inventory
from tests.test_active_cities_match_serving import _page_hubs

PH = _page_hubs()
HUBS = {**PH.GWANGJU_HUBS, **PH.JEONJU_HUBS}
ROOT = Path(__file__).resolve().parents[3]
CLIENT = TestClient(app)
V1 = '/api/v1'


@pytest.mark.parametrize('slug', HUBS)
def test_verified_regional_hub_gold_reaches_all_four_tracks(slug):
    summary = CLIENT.get(f'{V1}/commercial-districts/{slug}/summary')
    assert summary.status_code == 200, summary.text
    assert summary.json()['vacancy_source'] == 'gold'
    platform = CLIENT.get(f'{V1}/commercial-districts/{slug}/platform')
    assert platform.status_code == 200, platform.text
    assert platform.json()['identity']['categories']['total'] > 0
    assert marketing.context_rows(slug)
    for route in ('floor-vacancies', 'rent-history', 'report'):
        response = CLIENT.get(f'{V1}/commercial-districts/{slug}/{route}')
        assert response.status_code == 200, (slug, route, response.text)
    sites = CLIENT.get(f'{V1}/marketing/sites', params={'district_id': slug})
    assert sites.status_code == 200, sites.text
    assert sites.json()['site_source'] != 'unavailable'
    assert {u['id'] for u in sites.json()['sites']} == {u['id'] for u in vacant_inventory.units(slug)}
    events = CLIENT.get(f'{V1}/marketing/events', params={'district_id': slug})
    assert events.status_code == 200, events.text
    if events.json()['events_source'] == 'none':
        assert not events.json()['events']  # 확보하지 않은 행사를 만들지 않는다.
    units = vacant_inventory.units(slug)
    if units:
        result = CLIENT.post(f'{V1}/ai/simulate-revenue', json={'district_id': slug, 'unit_id': units[0]['id']})
        assert result.status_code == 200, result.text
        body = result.json()
        assert body['calculation_status'] == 'unavailable'
        assert body['source'] == 'unavailable' and body['scenarios'] == {}
        assert body['unavailable_reason']
    plan = CLIENT.post(f'{V1}/marketing/generate', json={
        'district_id': slug, 'unit_id': units[0]['id'] if units else None,
        'item': '검증용 아이템', 'category': '카페', 'mode': 'actual_open', 'stage': 'pre_founder'})
    assert plan.status_code == 200, plan.text
    assert plan.json()['source'] == 'rule-stub'  # LLM 실호출 검증으로 오인하지 않는다.


@pytest.mark.parametrize('slug', ['gj-usan', 'gj-ilgok', 'jj-newtown'])
@pytest.mark.parametrize('kind', ['building', 'floor'])
def test_missing_rent_keeps_known_gold_site_unavailable_instead_of_404(slug, kind):
    unit = (vacant_inventory.units(slug) if kind == 'building' else floor_vacancy.load(slug)['units'])[0]
    response = CLIENT.post(f'{V1}/ai/simulate-revenue', json={'district_id': slug, 'unit_id': unit['id']})
    assert response.status_code == 200, response.text
    assert '임대 표본' in response.json()['unavailable_reason']
    assert response.json()['scenarios'] == {}
    assert CLIENT.post(f'{V1}/ai/simulate-revenue', json={
        'district_id': slug, 'unit_id': 'vu-not-a-real-unit'}).status_code == 404


@pytest.mark.parametrize('slug', HUBS)
def test_regional_gold_remains_tier1_with_real_anchor(slug):
    gold = ROOT / 'data/gold' / slug
    coverage = json.loads((gold / 'coverage.json').read_text(encoding='utf-8'))
    calibration = json.loads((gold / 'calibration.json').read_text(encoding='utf-8'))
    assert coverage['tier'].startswith('Tier1')
    assert coverage['reference_coverage_pct'] >= 90
    assert calibration['anchor_is_fallback'] is False
    assert slug in PH.ACTIVE_HUBS
