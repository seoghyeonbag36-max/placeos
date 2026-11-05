"""광주·전주 수집 완료분의 Silver·대장 Gold·Program 업종 산출물을 잇는 재실행 작업."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import collect_regional_research_ledgers as source
from data.pipelines import build_regional_ledger_gold as pipeline

LOCK = ROOT / 'data/logs/regional-research-gold.lock'
LOG = ROOT / 'data/logs/regional-research-gold.log'


def main() -> int:
    """수집기와 별도 잠금으로 중복 실행을 막는다. 수집 상태·일일 호출량은 수정하지 않는다."""
    import msvcrt
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return 0
        state = source.read(source.STATE)
        if state['plan_sha256'] != source.fingerprint(source.PLAN):
            raise ValueError('PLAN_HASH_MISMATCH')
        progress = dict(plan=state['plan_sha256'], paused=state.get('paused_pnu_prefixes', []),
            completed={e: state['endpoints'][e]['completed'] for e in source.ENDPOINTS}, version=pipeline.VERSION)
        prior = source.read(pipeline.REPORT) if pipeline.REPORT.exists() else {}
        if prior.get('input_progress') == progress and prior.get('status') == 'checked':
            return 0
        with LOG.open('a', encoding='utf-8') as log:
            log.write(f'[{source.now().isoformat()}] 시작 pid={os.getpid()}\n')
        try:
            result = pipeline.run(source.read(source.PLAN), state.get('paused_pnu_prefixes', []))
        except Exception as exc:
            prior.update(status='waiting_disk_space' if isinstance(exc, source.DiskWait) else 'validation_failed',
                checked_at=source.now().isoformat(), error_type=type(exc).__name__, error=str(exc))
            source.atomic_json(pipeline.REPORT, prior)
            with LOG.open('a', encoding='utf-8') as log:
                log.write(f'[{source.now().isoformat()}] 중단 {type(exc).__name__}: {exc}\n')
            return 2
        result.update(status='checked', input_progress=progress)
        source.atomic_json(pipeline.REPORT, result)
        with LOG.open('a', encoding='utf-8') as log:
            log.write(f'[{source.now().isoformat()}] {json.dumps(result["summary"], ensure_ascii=False)}\n')
        if sys.stdout is not None:
            print(json.dumps(result['summary'], ensure_ascii=False))
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
