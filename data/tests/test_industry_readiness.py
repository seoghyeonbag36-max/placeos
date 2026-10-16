"""합성 입력으로 결손·미지원 사유 분리가 유지되는지 검증한다."""
from collections import Counter

from scripts.industry_readiness import summarize


def test_readiness_distinguishes_mapping_vocabulary_and_missing_evidence():
    items = [dict(key='bar', label='술집', model_label=None),
             dict(key='culture', label='전시·공연', model_label='문화시설'),
             dict(key='cafe', label='카페', model_label='카페')]
    rows = summarize(items, {'카페'}, Counter(bar_cooking=5), {'metrics': {'per_class': []}})
    assert [r['key'] for r in rows] == ['bar', 'culture']
    assert rows[0]['reason'] == 'no_model_mapping'
    assert rows[0]['details'][0]['gold_graph_nodes'] == 5
    assert rows[0]['details'][0]['experiment'] is None
    assert rows[1]['reason'] == 'absent_from_served_vocabulary'
    assert all(d['gold_graph_nodes'] is None for d in rows[1]['details'])


def test_readiness_preserves_zero_recall_without_promoting_a_model():
    metric = dict(key='beauty_nail', train_n=30, test_n=10, recall=0.0, status='evaluation_only')
    rows = summarize([dict(key='beauty', label='미용·네일', model_label=None)], set(),
                     Counter(beauty_nail=40), {'metrics': {'per_class': [metric]}})
    nail = next(d for d in rows[0]['details'] if d['key'] == 'beauty_nail')
    assert nail['experiment'] == metric
    assert rows[0]['reason'] == 'no_model_mapping'
