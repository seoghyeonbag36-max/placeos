"""합성 표본으로 비교 분할·정답 누출·실험 산출물 격리를 검증한다."""
from copy import deepcopy

import pytest

from data.config.industry_details import DETAILS
from ml.training.industry_detail_compare import compare


def _report() -> dict:
    rows = [dict(key=d['key'], train_n=12, test_n=4, top3=.5, baseline_top3=.25, recall=.25)
            for d in DETAILS]
    return {'inputs_sha256': {'nodes': 'same'}, 'metrics': {
        'split_sha256': 'same', 'per_class': rows, 'test_top1': .25,
        'test_top3': .5, 'test_macro_f1': .2, 'baseline_district_prior_top3': .25}}


@pytest.mark.parametrize('change', ['inputs', 'split', 'missing_split', 'counts'])
def test_comparison_rejects_unpaired_experiments(change: str):
    a = _report()
    b = deepcopy(a)
    if change == 'inputs':
        b['inputs_sha256']['nodes'] = 'different'
    elif change == 'split':
        b['metrics']['split_sha256'] = 'different'
    elif change == 'missing_split':
        del b['metrics']['split_sha256']
    else:
        b['metrics']['per_class'][0]['test_n'] += 1
    with pytest.raises(ValueError):
        compare(a, b)


def test_comparison_keeps_missing_scores_and_does_not_promote():
    a = _report()
    a['metrics']['per_class'][0]['top3'] = None
    result = compare(a, deepcopy(a))
    assert result['status'] == 'experiment_only'
    assert result['rows'][0]['delta_pp'] is None
    assert {r['parent'] for r in result['rows']} == {'bar', 'beauty', 'fashion', 'education', 'fitness'}


def test_neighbor_features_ignore_held_out_labels_and_self_loops():
    np = pytest.importorskip('numpy')
    torch = pytest.importorskip('torch')
    from ml.training.train_gnn import _neighbor_label_block
    edges = torch.tensor([[0, 1, 2, 0], [2, 2, 2, 0]])
    mask = np.array([True, False, False])
    first, _ = _neighbor_label_block(edges, np.array([0, 1, 1]), mask, 2, 3)
    changed, _ = _neighbor_label_block(edges, np.array([0, 0, 0]), mask, 2, 3)
    np.testing.assert_array_equal(first, changed)
    np.testing.assert_array_equal(first[0], [0, 0, 0])
    np.testing.assert_array_equal(first[2, :2], [1, 0])


def test_no_save_experiment_preserves_existing_resume_checkpoint(monkeypatch, tmp_path):
    np = pytest.importorskip('numpy')
    pd = pytest.importorskip('pandas')
    pytest.importorskip('torch')
    from ml.training import train_gnn as tg
    nodes = pd.DataFrame({'node_id': [f'n{i}' for i in range(24)], 'district_id': ['hub'] * 24})
    edges = pd.DataFrame({'src': ['n0'], 'dst': ['n1'], 'type': ['spatial_knn']})
    checkpoint = tmp_path / 'resume.pt'
    checkpoint.write_bytes(b'existing-checkpoint')
    monkeypatch.setattr(tg, '_RESUME', checkpoint)
    monkeypatch.setattr(tg, 'load_graph', lambda: (nodes, edges))
    monkeypatch.setattr(tg, '_label_population', lambda n, e, level: (n, e, 0))
    monkeypatch.setattr(tg, '_labels', lambda n, level: (np.array([0, 1] * 12), ['bar_beer', 'beauty_nail']))
    monkeypatch.setattr(tg, '_features', lambda *a, **kw: (np.zeros((24, 2), dtype=np.float32), ['x', 'y']))
    monkeypatch.setattr(tg, '_log_mlflow', lambda *a: None)
    def forbid_save(*args, **kwargs):
        pytest.fail('실험이 서빙 파일을 저장했습니다')
    monkeypatch.setattr(tg, '_save_artifacts', forbid_save)
    result = tg.train(epochs=1, hidden=4, label_level='business_detail', save=False,
                      resume=False, ckpt_every=0)
    assert checkpoint.read_bytes() == b'existing-checkpoint'
    assert len(result['split_sha256']) == 64
