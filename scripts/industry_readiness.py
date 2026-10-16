"""추천 미지원 업종의 Gold·실험 근거를 재측정한다. 서빙 파일은 변경하지 않는다.

python -m scripts.industry_readiness --output reports/industry_readiness.json
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path

from data.config.industry_details import DETAILS, classify
from data.config.page_hubs import ACTIVE_HUBS

ROOT = Path(__file__).resolve().parents[1]


def summarize(industries: list[dict], labels: set[str], counts: Counter,
              experiment: dict) -> list[dict]:
    """없는 실험값은 null로 남긴다. 표본 수만으로 추천 가능 판정을 하지 않는다."""
    metrics = {r['key']: r for r in experiment['metrics']['per_class']}
    result = []
    for item in industries:
        if item['model_label'] in labels:
            continue
        details = []
        for detail in DETAILS:
            if detail['parent'] != item['key']:
                continue
            details.append({
                'key': detail['key'], 'label': detail['label'],
                'source_names': detail['source_names'],
                'gold_graph_nodes': counts[detail['key']] if detail['source_names'] else None,
                'experiment': metrics.get(detail['key']),
            })
        result.append({
            'key': item['key'], 'label': item['label'],
            'reason': 'no_model_mapping' if item['model_label'] is None else 'absent_from_served_vocabulary',
            'model_label': item['model_label'], 'details': details,
        })
    return result


def audit(root: Path = ROOT, experiment_path: Path | None = None) -> dict:
    import pandas as pd

    files = {
        'nodes': root / 'data/gold/platform13/platform_store_graph_nodes.parquet',
        'edges': root / 'data/gold/platform13/platform_store_graph_edges.parquet',
        'serving': root / 'data/gold/platform_industry_recommend.json',
        'experiment': experiment_path or root / 'ml/reports/industry_detail_experiment.json',
        'industry_contract': root / 'apps/backend/app/services/business_fit.py',
        'detail_contract': root / 'data/config/industry_details.py',
    }
    hashes = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in files.items()}
    # 서버 초기화·DB 접속 없이 실제 업종 계약의 리터럴만 읽는다.
    tree = ast.parse(files['industry_contract'].read_text(encoding='utf-8'))
    industries = next(ast.literal_eval(n.value) for n in tree.body
                      if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                      and n.target.id == 'INDUSTRIES')
    serving = json.loads(files['serving'].read_text(encoding='utf-8'))
    experiment = json.loads(files['experiment'].read_text(encoding='utf-8'))
    labels = {t['industry'] for rows in serving['districts'].values()
              for row in rows.values() for t in row['top']}
    nodes = pd.read_parquet(files['nodes'])
    counts = Counter(nodes['inds_scls'].fillna('').map(classify))
    return {
        'source': '기존 소상공인 상가정보 Gold 그래프 · GNN 서빙 산출물 · 저장된 학습 실험(합성값 없음)',
        'inputs': {k: {'path': str(p.relative_to(root)), 'sha256': hashes[k]} for k, p in files.items()},
        'active_hubs_n': len(ACTIVE_HUBS), 'served_labels': sorted(labels),
        'graph_nodes_n': len(nodes),
        'experiment_created_at': experiment['created_at'],
        'experiment_inputs_match': all(experiment['inputs_sha256'].get(files[k].name) == hashes[k]
                                       for k in ('nodes', 'edges')),
        'experiment_serving_status': experiment['serving_status'],
        'unsupported': summarize(industries, labels, counts, experiment),
        'limitations': [
            '그래프 노드 수는 고유 점포 전수나 학습 분할 표본 수가 아니다.',
            '전시·공연의 null은 분류 대응이 없다는 뜻이며 실제 시설 0개라는 뜻이 아니다.',
            '저장된 실험의 성능이며 이번 실행에서 재학습한 값이 아니다.',
            '현존 업종 분류 성능은 상권 순위·매출·생존의 검증을 대신하지 않는다.',
        ],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--experiment', type=Path)
    args = parser.parse_args()
    result = audit(experiment_path=args.experiment.resolve() if args.experiment else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('served_labels', 'experiment_inputs_match')}, ensure_ascii=False))
