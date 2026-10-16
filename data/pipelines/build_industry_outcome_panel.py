"""분기별 업종 추정매출을 검증용 패널로 보존한다. GNN 피처에는 연결하지 않는다."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
KEYS = ['district_id', 'quarter', 'trdar_cd', 'industry_code']


def normalize(rows: list[dict]) -> pd.DataFrame:
    """원천 코드 유지·동일 행 중복 제거. 충돌·결손 키·잘못된 숫자는 실패한다."""
    if not rows:
        raise ValueError('원천 행이 없습니다')
    mapping = {'district_id': 'district_id', 'STDR_YYQU_CD': 'quarter',
               'TRDAR_CD': 'trdar_cd', 'SVC_INDUTY_CD': 'industry_code',
               'SVC_INDUTY_CD_NM': 'industry_name', 'THSMON_SELNG_AMT': 'estimated_sales_krw',
               'THSMON_SELNG_CO': 'estimated_transactions'}
    frame = pd.DataFrame(rows)
    if set(mapping) - set(frame.columns):
        raise ValueError('필수 원천 컬럼이 없습니다')
    frame = frame[list(mapping)].rename(columns=mapping)
    for key in KEYS + ['industry_name']:
        if frame[key].isna().any() or frame[key].astype(str).str.strip().eq('').any():
            raise ValueError(f'결손 키: {key}')
        frame[key] = frame[key].astype(str).str.strip()
    if not frame['quarter'].str.fullmatch(r'\d{4}[1-4]').all():
        raise ValueError('분기 형식은 YYYYQ여야 합니다')
    for key in ['estimated_sales_krw', 'estimated_transactions']:
        original = frame[key].replace('', None)
        converted = pd.to_numeric(original, errors='coerce')
        if (original.notna() & converted.isna()).any() or converted.dropna().isin([float('inf'), float('-inf')]).any() or converted.dropna().lt(0).any():
            raise ValueError(f'유효하지 않은 숫자: {key}')
        if (converted.dropna() % 1 != 0).any():
            raise ValueError(f'정수 단위가 필요합니다: {key}')
        frame[key] = converted.astype('Int64')
    frame = frame.drop_duplicates()
    if frame.duplicated(KEYS).any():
        raise ValueError('동일 상권·업종·분기에 충돌하는 관측값이 있습니다')
    return frame.sort_values(KEYS).reset_index(drop=True)


def build(source: Path, tag: str, root: Path = ROOT) -> dict:
    if not tag or any(c not in '0123456789-' for c in tag):
        raise ValueError('출력 태그는 숫자와 하이픈만 허용합니다')
    silver = root / 'data/silver/platform13' / f'industry_outcome_panel_{tag}.parquet'
    gold = root / 'data/gold/features' / f'industry_outcome_panel_{tag}.parquet'
    report_path = root / 'reports' / f'industry_outcome_panel_{tag}.json'
    if any(p.exists() for p in (silver, gold, report_path)):
        raise FileExistsError('기존 산출물은 덮어쓰지 않습니다')
    content = source.read_bytes()
    rows = json.loads(content)
    frame = normalize(rows)
    silver.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(silver, index=False)
    normalized = pd.read_parquet(silver)
    normalized['source'] = 'seoul_trdar_estimated_sales'
    normalized['observed_sales'] = normalized['estimated_sales_krw'].notna()
    normalized['observed_transactions'] = normalized['estimated_transactions'].notna()
    gold.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_parquet(gold, index=False)
    report = {'source_path': str(source), 'source_sha256': hashlib.sha256(content).hexdigest(),
              'gold_path': str(gold.relative_to(root)), 'gold_sha256': hashlib.sha256(gold.read_bytes()).hexdigest(),
              'raw_rows': len(rows), 'rows': len(normalized), 'districts': normalized['district_id'].nunique(),
              'quarters': sorted(normalized['quarter'].unique().tolist()),
              'missing_sales': int(normalized['estimated_sales_krw'].isna().sum()),
              'missing_transactions': int(normalized['estimated_transactions'].isna().sum()),
              'industries': normalized[['industry_code', 'industry_name']].drop_duplicates().to_dict('records'),
              'usage': '검증용 로컬 패널. 모델 입력·서빙 미연결. 추정매출이며 POS 실측값이 아님.',
              'limitations': ['여러 거점에 겹친 TRDAR를 거점 간 합산하지 않는다.',
                              '큰 업종·세부 업종 대응은 자동 추정하지 않는다.',
                              '누락된 상권·업종·분기는 0으로 보간하지 않는다.',
                              '정정된 과거 값일 수 있어 당시 이용 가능했던 데이터라는 보장은 없다.']}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    result = build(args.source, args.tag)
    print(json.dumps({k: result[k] for k in ('rows', 'districts', 'quarters')}, ensure_ascii=False))
