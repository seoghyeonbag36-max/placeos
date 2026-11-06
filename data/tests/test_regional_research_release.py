"""검증 미완료·승인 밖 파일·변경된 목적지가 자동 공개되지 않게 한다."""
import hashlib

import pytest

from scripts import run_regional_research_release as release
from scripts import collect_regional_research_ledgers as source


def test_unfinished_gold_has_no_git_side_effect(tmp_path,monkeypatch):
    monkeypatch.setattr(release,'ROOT',tmp_path)
    monkeypatch.setattr(release,'STATE',tmp_path/'reports/release.json')
    monkeypatch.setattr(source,'ROOT',tmp_path)
    monkeypatch.setattr(source,'PLAN',tmp_path/'data/silver/plan.json')
    source.atomic_json(source.PLAN,dict(locations=[]))
    monkeypatch.setattr(release,'run',lambda *_args,**_kwargs:pytest.fail('미완료 상태에서 Git 실행'))
    config=dict(git='git',gh='gh',branch='chore/test',worktree='.codex-worktrees/test',
                plan_sha256=source.fingerprint(source.PLAN))
    state={}
    release.publish(config,state)
    assert state['status']=='waiting_for_validation'
    assert state['reason']=='GOLD_REPORT_MISSING'


def test_copy_only_matching_file_and_preserve_changed_destination(tmp_path):
    origin=tmp_path/'origin';target=tmp_path/'worktree'
    origin.mkdir();(origin/'owned.txt').write_bytes(b'approved')
    sha=hashlib.sha256(b'approved').hexdigest()
    release.copy_verified(origin,target,'owned.txt',sha)
    (target/'owned.txt').write_bytes(b'user-change')
    with pytest.raises(ValueError,match='DESTINATION_CHANGED'):
        release.copy_verified(origin,target,'owned.txt',sha)
    assert (target/'owned.txt').read_bytes()==b'user-change'
    with pytest.raises(ValueError,match='SOURCE_CHANGED'):
        release.copy_verified(origin,target,'owned.txt','not-the-hash')
    with pytest.raises(ValueError,match='PATH_ESCAPE'):
        release.inside(origin,'../outside')
