"""전주 대장 → Gold 배치. 실제 429일 때만 다음 한국시간 자정 이후 한 번 재시도한다.

기존 배치 상태·예약 작업은 건드리지 않는다. 같은 전주 작업의 중복은 OS 파일 잠금으로 막는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.config.page_hubs import JEONJU_HUBS
from data.collectors.common import load_latest
from scripts import run_hub_chain_batch as chain

KST = timezone(timedelta(hours=9))
STATE = ROOT / 'reports' / 'jeonju_expansion.json'
LOG = ROOT / 'data' / 'logs' / 'jeonju-expansion.log'


def now() -> datetime:
    return datetime.now(KST)


def retry_after(moment: datetime) -> datetime:
    """quota 관측 다음 날 00:05 KST. 날짜는 실행 호스트 설정에 의존하지 않는다."""
    return (moment.astimezone(KST) + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)


def has_quota(output: str) -> bool:
    """통신 실패를 quota로 단정하지 않고 실제 HTTP 429 출력만 본다."""
    return bool(re.search(r'429 x[1-9]|429 로 [1-9]|429 [1-9]\d*회', output))


def save(state: dict) -> None:
    state['updated_at'] = now().isoformat()
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE)


def run(module: str, *args: str) -> tuple[bool, bool]:
    chain.say('전주 실행: ' + ' '.join([module, *args]))
    # 긴 전유부 호출도 진행 로그를 바로 남긴다. 종료 후 이번 호출 구간에서만 429를 찾는다.
    with LOG.open('a', encoding='utf-8') as stream:
        offset = stream.tell()
        result = subprocess.run([sys.executable, '-u', '-m', module, *args], cwd=ROOT,
                                stdout=stream, stderr=subprocess.STDOUT, timeout=14400,
                                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                                creationflags=chain.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    with LOG.open(encoding='utf-8', errors='replace') as stream:
        stream.seek(offset)
        output = stream.read()
    return result.returncode == 0, has_quota(output)


def validate_gold(slug: str) -> dict:
    """기존 정밀 커버리지·실앵커 가드를 유지한다. 통과 여부를 보고서로 남긴다."""
    folder = ROOT / 'data' / 'gold' / slug
    required = ('page_building_master.geojson', 'coverage.json', 'calibration.json',
                'vacant_units.json', 'vacant_floor_units.json', 'building_history.json')
    if any(not (folder / f).exists() for f in required):
        raise ValueError(f'{slug}: Gold 산출물 누락')
    coverage = json.loads((folder / 'coverage.json').read_text(encoding='utf-8'))
    calibration = json.loads((folder / 'calibration.json').read_text(encoding='utf-8'))
    if chain.ledger_gap(slug) != 0 or calibration.get('anchor_is_fallback') is not False:
        raise ValueError(f'{slug}: 미완 대장 또는 폴백 앵커')
    if coverage.get('reference_coverage_pct', 0) < 80 or not coverage.get('reference_buildings'):
        raise ValueError(f'{slug}: 정밀 커버리지 부족')
    from scripts.chain_status import _served_vac, ANCHOR_GAP_MAX
    reference = _served_vac(coverage)
    if reference is None or abs(reference - calibration['anchor_pct']) > ANCHOR_GAP_MAX:
        raise ValueError(f'{slug}: 기존 앵커 가드레일 미통과')
    return {'status': 'gold', 'tier': coverage['tier'],
            'reference_coverage_pct': coverage['reference_coverage_pct'],
            'reference_vacancy_pct': coverage.get('reference_vacancy_pct'),
            'served_basis_vacancy_pct': reference,
            'served_basis_anchor_gap_pp': round(reference - calibration['anchor_pct'], 2),
            'anchor_pct': calibration['anchor_pct'], 'anchor_is_fallback': False,
            'ledger_counts': chain.ledger_counts(slug),
            'note': 'Gold 산출·검증 완료. 서빙 목록 변경·배포와 별개'}


def attempt(state: dict) -> bool:
    """quota면 즉시 배치를 멈춘다. 덜 찬 대장 위에 마스터·앵커를 세우지 않는다."""
    ac, _ = chain.power()
    if not ac:
        state['status'] = 'ac_required'
        save(state)
        return False
    for slug in JEONJU_HUBS:
        if chain.ledger_gap(slug) != 0:
            # 503으로 못 받은 행도 rate_limited로 저장된다. HTTP 429와 구분해 미수집분만 두 번 더 잇는다.
            for _ in range(3):
                ok, quota = run('data.collectors.building_vacancy', slug)
                if quota:
                    state.update(status='quota', quota_at=now().isoformat(), quota_hub=slug)
                    save(state)
                    return True
                if not ok or chain.ledger_gap(slug) == 0:
                    break
            if not ok or chain.ledger_gap(slug) != 0:
                raise ValueError(f'{slug}: 전유부 수집 미완료 — Gold 중단')
        ok, quota = run('data.collectors.floor_capacity', slug, '--only-approx')
        if quota:
            state.update(status='quota', quota_at=now().isoformat(), quota_hub=slug)
            save(state)
            return True
        if not ok:
            raise ValueError(f'{slug}: 층별개요 실패')
    # 대장 수집과 독립적으로 진행한 인허가 원본을 완주 확인 뒤 버킷으로 나눈다.
    if not run('data.collectors.jeonju_licensing_hubs')[0]:
        raise ValueError('완주 인허가 원본 누락 — Gold 중단')
    for slug in JEONJU_HUBS:
        if not load_latest(slug, 'licensing_biz.json'):
            raise ValueError(f'{slug}: 완주 인허가 버킷 누락')
        # 이제 대장이 완주했다. 기존 체인이 Silver 정제·Page Gold·앵커를 순서대로 만든다.
        if chain.do_hub(slug, False) != 'anchor':
            raise ValueError(f'{slug}: Gold 체인 실패')
        if not run('data.pipelines.build_district_zones', slug)[0]:
            raise ValueError(f'{slug}: 구역 빌드 실패')
        state.setdefault('hubs', {})[slug] = validate_gold(slug)
        save(state)
    state['status'] = 'gold_complete'
    save(state)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retry', action='store_true')
    args = parser.parse_args()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    chain.LOG = LOG
    lock = (ROOT / 'reports' / 'jeonju_expansion.lock').open('a+b')
    import msvcrt
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return 0
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    if state.get('status') == 'gold_complete':
        return 0
    if args.retry:
        if state.get('status') != 'quota' or state.get('retry_used'):
            return 0
        due = retry_after(datetime.fromisoformat(state['quota_at']))
        if now() < due:
            return 0
        state['retry_used'] = True
    elif state.get('quota_at'):
        return 0
    state.pop('error_type', None)
    state.update(status='running', pid=os.getpid())
    save(state)
    chain.keep_awake()
    try:
        quota = attempt(state)
        if quota:
            state['retry_after'] = retry_after(datetime.fromisoformat(state['quota_at'])).isoformat()
            save(state)
        return 0 if state.get('status') == 'gold_complete' else 2
    except Exception as exc:
        # 외부 API 예외에는 URL·키가 들어갈 수 있어 종류만 남긴다.
        state.update(status='failed', error_type=type(exc).__name__)
        save(state)
        chain.say('전주 실패: ' + type(exc).__name__)
        return 1
    finally:
        chain.keep_awake(False)
        lock.close()


if __name__ == '__main__':
    raise SystemExit(main())
