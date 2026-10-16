"""같은 입력·분할의 세부 업종 실험을 비교한다. 서빙 승격 판정은 하지 않는다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.config.industry_details import DETAILS

TARGETS = {'bar', 'beauty', 'fashion', 'education', 'fitness'}


def compare(control: dict, candidate: dict) -> dict:
    a, b = control['metrics'], candidate['metrics']
    if not control.get('inputs_sha256') or control['inputs_sha256'] != candidate.get('inputs_sha256'):
        raise ValueError('입력 데이터가 다른 실험은 비교하지 않습니다')
    if not a.get('split_sha256') or a['split_sha256'] != b.get('split_sha256'):
        raise ValueError('같은 점포·정답·분할이 확인되지 않았습니다')
    by_a = {r['key']: r for r in a['per_class']}
    by_b = {r['key']: r for r in b['per_class']}
    rows = []
    for detail in DETAILS:
        if detail['parent'] not in TARGETS:
            continue
        key = detail['key']
        x, y = by_a[key], by_b[key]
        if (x['train_n'], x['test_n']) != (y['train_n'], y['test_n']):
            raise ValueError(f'{key}: 업종별 표본 불일치')
        rows.append(dict(key=key, parent=detail['parent'], label=detail['label'], test_n=y['test_n'],
                         control_top3=x['top3'], candidate_top3=y['top3'], baseline_top3=y['baseline_top3'],
                         delta_pp=round((y['top3'] - x['top3']) * 100, 3)
                         if x['top3'] is not None and y['top3'] is not None else None,
                         candidate_recall=y['recall']))
    return {'status': 'experiment_only', 'split_sha256': a['split_sha256'], 'rows': rows,
            'overall': {k: {'control': a[k], 'candidate': b[k]}
                        for k in ('test_top1', 'test_top3', 'test_macro_f1', 'baseline_district_prior_top3')},
            'limitations': ['단일 고정 분할의 관측 차이이며 통계적 유의성·상권 순위 정확도가 아니다.',
                            '큰 업종의 추천 점수로 임의 합산하지 않는다. 서빙은 자동 활성화하지 않는다.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('control', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = compare(json.loads(args.control.read_text(encoding='utf-8')),
                     json.loads(args.candidate.read_text(encoding='utf-8')))
    report['reports'] = {'control': str(args.control), 'candidate': str(args.candidate)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['overall'], ensure_ascii=False))
