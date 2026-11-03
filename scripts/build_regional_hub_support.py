"""추가 36곳의 기존 원본에서 화면 보조 산출물만 만든다. 기존 거점 값은 보존한다."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.collectors.common import GOLD, load_latest


def extend(path: Path, key: str, entries: dict) -> None:
    """공유 파일에 없는 거점만 추가한다. 기존 항목의 값은 변경하지 않는다."""
    doc = json.loads(path.read_text(encoding='utf-8'))
    previous = dict(doc[key])
    for slug, value in entries.items():
        if slug not in doc[key]:
            doc[key][slug] = value
    assert all(doc[key][slug] == value for slug, value in previous.items())
    text = (json.dumps(doc, ensure_ascii=False, indent=2) if path.name == 'platform_posting_inputs.json'
            else json.dumps(doc, ensure_ascii=False, separators=(',', ':')))
    path.write_text(text, encoding='utf-8')


def run() -> None:
    # pandas·scipy는 재빌드 전용 선택 의존성이다. 보존 규칙 검사·CI 임포트로 역류시키지 않는다.
    from data.pipelines import build_building_floors as floors
    from data.pipelines import build_district_zones as zones
    from data.pipelines import build_hub_outlines as outlines
    from data.pipelines import build_posting_inputs as posting
    from data.pipelines import build_rone_history as history
    from data.pipelines import build_stores_lite as stores

    report = json.loads((ROOT / 'reports/regional_hub_candidates_2026-11-03.json').read_text(encoding='utf-8'))
    added = report['added_ids']
    for slug in added:
        target = GOLD / slug / 'district_zones.json'
        if not target.exists():
            doc = zones.build(slug)
            if not doc or not doc['zones']:
                raise ValueError(f'{slug}: 구역 원본 부족')
            target.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
        if not (GOLD / slug / floors.NAME).exists():
            floors.run([slug])
    # 이미 공개 중인 점포 요약·브랜드·동시 입지 파일은 재생성하지 않는다.
    rows_by_hub, dates, unique = {}, {}, {}
    for slug in stores.ACTIVE_HUBS:
        rows_by_hub[slug], dates[slug] = stores.load_hub_rows(slug)
        unique.update({r['bizesId']: r for r in rows_by_hub[slug] if r.get('bizesId')})
    matcher = stores.BrandMatcher(stores.load_ftc())
    matcher.fit(unique.values())
    for slug in added:
        path = GOLD / slug / stores.LITE_NAME
        if not path.exists():
            stores.write_gz(stores.lite_doc(slug, rows_by_hub[slug], dates[slug], matcher), path)

    svc = outlines._heatmap_service()
    extra = {}
    for slug in added:
        hm = svc.get_vacancy_heatmap(slug)
        doc = outlines.outline(hm['cells']) if hm and hm.get('vacancy_source') == 'gold' else None
        if doc is None:
            raise ValueError(f'{slug}: 실측 격자 없음')
        extra[slug] = doc
    extend(GOLD / outlines.OUT, 'hubs', extra)

    inputs = json.loads((GOLD / 'platform_posting_inputs.json').read_text(encoding='utf-8'))
    rent = posting._rent_only(set(inputs['districts']), str(inputs['quarter']))
    extend(GOLD / 'platform_posting_inputs.json', 'districts', {s: v for s, v in rent.items() if s in added})
    raw = {key: load_latest(history.SLUG13, name) or [] for key, name in history.SERIES.items()}
    doc = history.build_doc(raw, inputs['floor_factor'])
    original = json.loads((GOLD / history.OUT).read_text(encoding='utf-8'))
    if doc['quarters'] != original['quarters']:
        raise ValueError('분기 축이 달라 기존 시계열을 보존한 추가 불가')
    extend(GOLD / history.OUT, 'hubs', {s: doc['hubs'][s] for s in added})
    print(f'추가 {len(added)}곳: 구역·층별개요·점포요약·외곽선·R-ONE·임대 입력 완료')


if __name__ == '__main__':
    run()
