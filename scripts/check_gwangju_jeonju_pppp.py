"""기존 광주 13·전주 5 Gold와 PPPP 연결 증거를 읽어 보고한다. Gold는 덮어쓰지 않는다."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'apps/backend'))

from data.config.page_hubs import GWANGJU_HUBS, JEONJU_HUBS
from app.services import districts, marketing, platform_profile, posting, posting_inputs, program_site, vacant_inventory
from scripts.chain_status import summarize

ARTIFACTS = ('coverage.json', 'calibration.json', 'page_building_master.geojson',
             'vacant_units.json', 'vacant_floor_units.json', 'building_history.json',
             'building_floors.json.gz', 'stores_lite.json.gz', 'district_zones.json',
             'program_content_context.csv')


def check() -> dict:
    """출처·잔여·미지원 모델을 숨기지 않고 현재 산출물과 실제 로더를 검사한다."""
    tracked = set(subprocess.run(['git', 'ls-files', 'data/gold'], cwd=ROOT,
        capture_output=True, text=True, check=True).stdout.splitlines())
    gold = ROOT / 'data/gold'
    recommend = json.loads((gold / 'platform_industry_recommend.json').read_text(encoding='utf-8'))
    forecast = json.loads((gold / 'platform_vacancy_forecast.json').read_text(encoding='utf-8'))
    hubs = []
    for slug, hub in {**GWANGJU_HUBS, **JEONJU_HUBS}.items():
        folder = gold / slug
        artifacts = {}
        for name in ARTIFACTS:
            path = folder / name
            if not path.is_file():
                raise ValueError(f'{slug}: {name} 누락')
            relative = path.relative_to(ROOT).as_posix()
            if relative not in tracked:
                raise ValueError(f'{relative}: 배포 추적 누락')
            artifacts[name] = dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), tracked=True)
        coverage = json.loads((folder / 'coverage.json').read_text(encoding='utf-8'))
        cal = json.loads((folder / 'calibration.json').read_text(encoding='utf-8'))
        units = vacant_inventory.units(slug)
        context = marketing.context_rows(slug) or []
        # 외부 코파일럿·LLM을 호출하지 않는다. API 실행 검증은 별도 테스트가 한다.
        simulated = (posting.simulate(slug, units[0]['id']) if units and
                     not posting.settings.posting_copilot_url else None)
        chain = summarize(slug)
        row = dict(id=slug, name=hub.name, city=hub.city, artifacts=artifacts,
            chain_complete=chain['done'] == chain['total'], chain=chain,
            tier=coverage['tier'], reference_coverage_pct=coverage['reference_coverage_pct'],
            anchor_pct=cal['anchor_pct'], anchor_is_fallback=cal['anchor_is_fallback'],
            platform=dict(identity_available=platform_profile.identity(slug) is not None,
                gnn_available=bool(recommend.get('districts', {}).get(slug)),
                forecast_available=bool(forecast.get('districts', {}).get(slug))),
            page=dict(vacancy_source=districts.get_summary(slug)['vacancy_source']),
            posting=dict(gold_units=len(units), rent_available=bool(posting_inputs.for_district(slug)),
                calculation_status=simulated.get('calculation_status') if simulated else None,
                unavailable_reason=simulated.get('unavailable_reason') if simulated else None),
            program=dict(context_rows=len(context), context_kinds=sorted({r[0] for r in context}),
                site_source=program_site.provenance(slug)['site_source'],
                events_source=marketing.get_district_events(slug)['events_source'], live_llm_verified=False))
        if not coverage['tier'].startswith('Tier1') or cal['anchor_is_fallback'] is not False:
            raise ValueError(f'{slug}: Tier1·실앵커 조건 미충족')
        hubs.append(row)
    return dict(checked_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),
        scope='기존 광주 13·전주 5. 신규 조사 후보는 포함하지 않음',
        gold_action='기존 산출물 검증. 전주 서부는 신규 실응답 1동 반영 후 기존 파이프라인으로 갱신',
        repair_evidence=dict(hub='jj-west', pnu='5211112900108570003',
            endpoint='getBrFlrOulnInfo',
            raw_marker='data/bronze/regional_research_ledgers/2026-11-03/floors/5211112900108570003/complete.json',
            previous_gold_backup='data/silver/regional_pppp_backups/2026-11-04/jj-west'),
        deployment_verified=False, hubs=hubs,
        summary=dict(hubs=len(hubs), chain_complete=sum(r['chain_complete'] for r in hubs),
            tracked_runtime_artifacts=sum(len(r['artifacts']) for r in hubs),
            building_units=sum(r['posting']['gold_units'] for r in hubs),
            residual_chain=[r['id'] for r in hubs if not r['chain_complete']],
            missing_rent=[r['id'] for r in hubs if not r['posting']['rent_available']],
            missing_gnn=[r['id'] for r in hubs if not r['platform']['gnn_available']],
            missing_forecast=[r['id'] for r in hubs if not r['platform']['forecast_available']]))


if __name__ == '__main__':
    report = check()
    target = ROOT / 'reports/gwangju_jeonju_pppp_readiness_2026-11-04.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False))
