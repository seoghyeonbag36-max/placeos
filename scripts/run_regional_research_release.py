"""사용자가 승인한 광주·전주권 완주분만 별도 worktree에서 검증·커밋·PR 머지한다."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import collect_regional_research_ledgers as source

CONFIG = ROOT / 'data/silver/regional_research_ledgers/release_authorization.json'
STATE = ROOT / 'reports/regional_research_release_state.json'
LOG = ROOT / 'data/logs/regional-research-release.log'
LOCK = ROOT / 'data/logs/regional-research-release.lock'


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('RELEASE_PATH_ESCAPE')
    return path


def copy_verified(root: Path, destination: Path, relative: str, expected: str) -> None:
    """허용 목록에 실린 실제 파일만 복사한다. 사용자 작업 디렉터리는 수정하지 않는다."""
    path = inside(root, relative)
    if source.fingerprint(path) != expected:
        raise ValueError('RELEASE_SOURCE_CHANGED: ' + relative)
    target = inside(destination, relative)
    if target.exists() and source.fingerprint(target) != expected:
        raise ValueError('RELEASE_DESTINATION_CHANGED: ' + relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def run(command: list[str], cwd: Path, timeout: int = 1800) -> str:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=timeout, creationflags=0x08000000 if os.name == 'nt' else 0,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'})
    with LOG.open('a', encoding='utf-8') as stream:
        stream.write(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f'{Path(command[0]).name}: exit {result.returncode}')
    return result.stdout.rstrip()


def save(state: dict) -> None:
    state['updated_at'] = source.now().isoformat()
    source.atomic_json(STATE, state)


def check_remote(config: dict) -> None:
    result = subprocess.run([config['git'],'remote','get-url','origin'],cwd=ROOT,capture_output=True,text=True,
        creationflags=0x08000000 if os.name=='nt' else 0)
    if result.returncode or result.stdout.strip()!=config['remote_url']:
        raise ValueError('REPOSITORY_REMOTE_CHANGED')


def publish(config: dict, state: dict) -> None:
    from data.pipelines import build_regional_ledger_gold as pipeline
    from scripts.run_hub_chain_batch import keep_awake
    git, gh = config['git'], config['gh']
    branch = config['branch']
    worktree = inside(ROOT, config['worktree'])
    plan = source.read(source.PLAN)
    scope = dict(plan_sha256=config['plan_sha256'], paused_pnu_prefixes=['41'])
    if source.fingerprint(source.PLAN) != config['plan_sha256']:
        state.update(status='needs_review', reason='PLAN_SCOPE_CHANGED');save(state);return
    ready, reason = source.gold_scope_ready(plan, scope)
    if not ready:
        state.update(status='waiting_for_validation', reason=reason);save(state);return
    for relative, entry in config['sources'].items():
        logical = hashlib.sha256(inside(ROOT, relative).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        if logical != entry['git_sha256']:
            state.update(status='needs_review', reason='APPROVED_SOURCE_CHANGED: '+relative);save(state);return
    if not source.ac_connected():
        state.update(status='waiting_ac');save(state);return
    check_remote(config)
    keep_awake()
    try:
        if not state.get('commit'):
            # 마무리 시에는 변경 시각 캐시를 우회하여 원본·헤더·건수·해시를 전부 다시 검증한다.
            pipeline.REPORT = ROOT/'data/silver/regional_research_ledgers/release_verified_gold.json'
            verified = pipeline.run(plan, ['41'], force_verify=True)
            if ({r['id'] for r in verified['locations']} != set(config['scope_ids']) or
                    any(r['status'] != 'ledger_gold_complete' for r in verified['locations'])):
                raise ValueError('RELEASE_SCOPE_INCOMPLETE')
            if source.fingerprint(source.PLAN) != config['plan_sha256']:
                raise ValueError('PLAN_CHANGED_DURING_RELEASE_VALIDATION')
            state.update(status='data_verified');save(state)
            run([git, 'fetch', 'origin', 'main'], ROOT)
            if not worktree.exists():
                run([git, 'worktree', 'add', '-b', branch, str(worktree), 'origin/main'], ROOT)
                state['owned_worktree'] = True;save(state)
            elif not state.get('owned_worktree'):
                raise ValueError('WORKTREE_NOT_OWNED')
            allowed = set(config['sources'])
            artifact_hashes = {}
            for relative, entry in config['sources'].items():
                current = worktree/relative
                current_sha = hashlib.sha256(current.read_bytes().replace(b'\r\n',b'\n')).hexdigest() if current.is_file() else None
                if current_sha not in (entry['base_sha256'], entry['git_sha256']):
                    raise ValueError('MAIN_FILE_CHANGED: '+relative)
                snapshot = inside(ROOT, entry['snapshot'])
                if source.fingerprint(snapshot) != entry['sha256']:
                    raise ValueError('APPROVED_SNAPSHOT_CHANGED')
                target = inside(worktree, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(snapshot, target)
            for location in verified['locations']:
                evidence = source.read(ROOT/location['artifacts'][0]['path'])
                artifacts = [*location['artifacts'], evidence['silver'], location['verification_inputs']]
                for artifact in artifacts:
                    relative = artifact['path']
                    if not (relative.startswith('data/gold/regional_research_ledgers/') or
                            relative.startswith('data/silver/regional_research_ledgers/normalized/')):
                        raise ValueError('ARTIFACT_OUTSIDE_RELEASE_SCOPE')
                    copy_verified(ROOT, worktree, relative, artifact['sha256'])
                    allowed.add(relative)
                    artifact_hashes[relative] = artifact['sha256']
            manifest = 'reports/regional_research_gwangju_jeonju_release.json'
            verified.update(status='release_verified', note='대장 관측 Gold. 서비스 상권 등록·Page Gold 승격과 별개.')
            source.atomic_json(worktree/manifest, verified)
            allowed.add(manifest)
            # 외부 작업이 이 전용 worktree에 섞이면 원상복구·제외를 추측하지 않고 중단한다.
            dirty = run([git, '-c', 'core.quotePath=false', 'status', '--porcelain', '--untracked-files=all'], worktree)
            if any(line[3:] not in allowed for line in dirty.splitlines() if line):
                raise ValueError('UNRELATED_WORKTREE_CHANGE')
            run([config['python'], '-m', 'pytest', 'data/tests/test_verified_file_cache.py',
                'data/tests/test_regional_research_ledgers.py', 'data/tests/test_regional_ledger_gold.py',
                'data/tests/test_jeonju_recommendations.py', 'data/tests/test_regional_hub_candidates.py', '-q'], worktree)
            files = sorted(allowed)
            for start in range(0, len(files), 40):
                run([git, 'add', '-f', '--', *files[start:start+40]], worktree)
            run([git, 'diff', '--cached', '--check'], worktree)
            staged = run([git, 'diff', '--cached', '--name-only'], worktree).splitlines()
            if not set(staged) <= allowed:
                raise ValueError('UNRELATED_STAGED_CHANGE')
            if not staged:
                state.update(status='already_present');save(state);return
            run([git, 'commit', '-m', '광주·전주권 대장 완주 및 검증 산출물 반영'], worktree)
            for relative, expected in artifact_hashes.items():
                blob = subprocess.run([git,'cat-file','blob','HEAD:'+relative],cwd=worktree,
                    capture_output=True,check=True,creationflags=0x08000000 if os.name=='nt' else 0).stdout
                if hashlib.sha256(blob).hexdigest()!=expected:
                    raise ValueError('GIT_ARTIFACT_HASH_MISMATCH: '+relative)
            state.update(commit=run([git, 'rev-parse', 'HEAD'], worktree), status='committed');save(state)
        check_remote(config)
        run([git, 'push', '-u', 'origin', branch], worktree)
        if not state.get('pr_url'):
            existing = json.loads(run([gh, 'pr', 'list', '--repo', config['repo'], '--head', branch, '--state', 'all', '--json', 'url'], worktree))
            if existing:
                state['pr_url'] = existing[0]['url']
            else:
                body = ROOT/'data/silver/regional_research_ledgers/release_pr_body.md'
                body.write_text('광주·전주권(혁신도시 완주측 포함)의 전유부·층별개요 완주분을 검증해 '
                    '대장 관측 Gold와 Program 업종 구성으로 반영합니다. 기존 거점은 유지합니다.\n\n'
                    '원본·Silver·Gold 해시 및 전체 건수를 확인하고 전용 worktree의 데이터 테스트를 통과했습니다. '
                    '임대료·공실률·매출·예측을 생성하지 않으며, 서비스용 Page Gold·상권 등록은 별도 검증 대상입니다.\n',encoding='utf-8')
                state['pr_url'] = run([gh, 'pr', 'create', '--repo', config['repo'], '--base', 'main', '--head', branch, '--title',
                    '광주·전주권 대장 완주 및 검증 산출물 반영', '--body-file', str(body)], worktree)
            state['status'] = 'pr_open';save(state)
        pr = json.loads(run([gh, 'pr', 'view', state['pr_url'], '--repo', config['repo'], '--json', 'state,mergeCommit'], worktree))
        if pr['state'] != 'MERGED':
            run([gh, 'pr', 'checks', state['pr_url'], '--repo', config['repo'], '--watch', '--fail-fast', '--interval', '30'], worktree, timeout=3600)
            run([gh, 'pr', 'merge', state['pr_url'], '--repo', config['repo'], '--squash', '--match-head-commit', state['commit']], worktree)
            pr = json.loads(run([gh, 'pr', 'view', state['pr_url'], '--repo', config['repo'], '--json', 'state,mergeCommit'], worktree))
        if pr['state'] != 'MERGED':
            raise ValueError('MERGE_NOT_CONFIRMED')
        state.update(status='merged', merge_commit=(pr.get('mergeCommit') or {}).get('oid'));save(state)
    finally:
        keep_awake(False)


def main() -> int:
    import msvcrt
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+b') as lock:
        if lock.tell() == 0:lock.write(b'0');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return 0
        config = source.read(CONFIG)
        state = source.read(STATE) if STATE.exists() else {}
        if state.get('status') in ('merged','already_present'):return 0
        if not config.get('authorized') or source.fingerprint(Path(__file__)) != config['runner_sha256']:
            state.update(status='needs_review',reason='RUNNER_NOT_APPROVED');save(state);return 2
        try:
            publish(config,state)
        except Exception as exc:
            state.update(status='failed',error_type=type(exc).__name__,error=str(exc));save(state)
            return 2
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
