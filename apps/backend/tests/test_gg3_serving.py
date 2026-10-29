"""부분 서빙이 미완료 거점을 노출하지 않고 실제 Gold만 응답하는지 검사한다."""
import json
import sys
from pathlib import Path

from app.data import measured_pages
from app.services import districts
from tests.test_active_cities_match_serving import _page_hubs


def test_completed_gg3_hubs_only_reach_serving():
    ph = _page_hubs()
    rows = {r['id']: r for r in districts.list_summaries()}
    selected = ph.GYEONGGI_BATCH3_SERVED_HUBS
    assert set(ph.GYEONGGI_BATCH3_HUBS) & set(rows) == selected
    assert set(ph.GYEONGGI_BATCH3_HUBS) & set(ph.ACTIVE_HUBS) == selected
    assert set(measured_pages.MEASURED_BY_ID) >= selected
    for slug in selected:
        assert rows[slug]['vacancy_source'] == 'gold'


def test_selected_hubs_have_complete_chain_and_usable_anchor():
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    from scripts.run_hub_chain_batch import ledger_counts, stage_done

    for slug in _page_hubs().GYEONGGI_BATCH3_SERVED_HUBS:
        counts = ledger_counts(slug)
        assert counts is not None and counts[0] == counts[1] and counts[2] == 0, slug
        assert stage_done(slug) == 'anchor', slug
        gold = root / 'data' / 'gold' / slug
        coverage = json.loads((gold / 'coverage.json').read_text(encoding='utf-8'))
        calibration = json.loads((gold / 'calibration.json').read_text(encoding='utf-8'))
        assert coverage['tier'].startswith('Tier1'), slug
        assert coverage['reference_coverage_pct'] >= 90, slug
        assert abs(calibration['primary']['gap_pp']) <= 30, slug
