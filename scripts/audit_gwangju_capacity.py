"""광주광역시 R-ONE 앵커 수를 원본에서 확인한다(건축HUB 호출 없음)."""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.collectors.rone_rent import _fetch_all, _key
from data.config.rone_districts import SERIES_TABLES


def summarize(tables: dict[str, list[dict]]) -> dict:
    """최신 공통 분기의 유효한 개별 상권만 센다. 도시 집계는 제외한다."""
    quarters = [{r['WRTTIME_IDTFR_ID'] for r in rows} for rows in tables.values()]
    quarter = max(set.intersection(*quarters))
    by_series = {
        series: sorted({r['CLS_FULLNM'] for r in rows
                        if r['WRTTIME_IDTFR_ID'] == quarter
                        and str(r.get('CLS_FULLNM', '')).startswith('광주>')
                        and r.get('DTA_VAL') is not None})
        for series, rows in tables.items()
    }
    anchors = sorted(set().union(*map(set, by_series.values())))
    seoul = set().union(*[
        {r['CLS_FULLNM'] for r in rows if r['WRTTIME_IDTFR_ID'] == quarter
         and str(r.get('CLS_FULLNM', '')).startswith('서울>')
         and str(r['CLS_FULLNM']).count('>') == 2 and r.get('DTA_VAL') is not None}
        for rows in tables.values()
    ])
    from data.config.page_hubs import ACTIVE_HUBS
    seoul_hubs = sum(h.city == 'seoul' for h in ACTIVE_HUBS.values())
    ratio = seoul_hubs / len(seoul)
    return {'quarter': quarter, 'by_series': by_series, 'anchors': anchors,
            'anchor_count': len(anchors), 'seoul_anchor_count': len(seoul),
            'seoul_served_hubs': seoul_hubs, 'reference_ratio': ratio,
            'planning_reference_hubs': round(len(anchors) * ratio),
            'gyeonggi_convention_ratio': 1.47,
            'gyeonggi_convention_reference_hubs': round(len(anchors) * 1.47),
            'note': '서울 앵커 공유 비율을 적용한 계획 참고치이며 물리적 최대나 서빙 확정 수가 아니다.'}


def main() -> None:
    key = _key()
    ids = {s: tables[-1] for s, tables in SERIES_TABLES.items()}
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {s: pool.submit(_fetch_all, key, table) for s, table in ids.items()}
        tables = {s: job.result() for s, job in jobs.items()}
    if any(not rows for rows in tables.values()):
        raise RuntimeError('R-ONE 원본 누락 — 거점 수 산정 중단')
    raw = ROOT / 'data' / 'bronze' / 'gwangju_capacity' / date.today().isoformat()
    raw.mkdir(parents=True, exist_ok=True)
    for series, rows in tables.items():
        target = raw / f'{series}.json'
        if not target.exists():
            target.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
    report = summarize(tables)
    report['source'] = '한국부동산원 R-ONE SttsApiTblData.do'
    report['table_ids'] = ids
    report['bronze'] = str(raw.relative_to(ROOT))
    target = ROOT / 'reports' / 'gwangju_capacity_2026-10-28.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
