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
        gold = root / 'data' / 'gold' / slug
        # 점포 원본(Bronze)은 gitignore 라 CI 체크아웃에는 없다 — 거기서는 후보 건물 수를 못 세므로
        # 커밋된 Gold 만으로 같은 사실(대장이 있고 429 로 못 받은 행이 없다)을 본다. 로컬에서는 종전대로 엄격하다.
        if list((root / 'data' / 'bronze').glob(f'{slug}/*/stores_raw.json')):
            counts = ledger_counts(slug)
            assert counts is not None and counts[0] == counts[1] and counts[2] == 0, slug
            assert stage_done(slug) == 'anchor', slug
        else:
            ledger = json.loads((gold / 'building_vacancy.json').read_text(encoding='utf-8'))                 if (gold / 'building_vacancy.json').exists() else None
            if ledger is not None:   # building_vacancy.json 은 추적 예외가 아니라 CI 에는 없을 수 있다
                assert not any(r.get('capacity_method') == 'rate_limited' for r in ledger), slug
        assert not (gold / 'chain_failed.json').exists(), slug
        coverage = json.loads((gold / 'coverage.json').read_text(encoding='utf-8'))
        calibration = json.loads((gold / 'calibration.json').read_text(encoding='utf-8'))
        assert coverage['tier'].startswith('Tier1'), slug
        assert coverage['reference_coverage_pct'] >= 90, slug
        assert abs(calibration['primary']['gap_pp']) <= 30, slug
