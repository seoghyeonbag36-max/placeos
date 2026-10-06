"""배포는 CI 가 **전부** 통과한 커밋만 내보내고, 로컬 무인 검증은 CI 와 같은 단계를 돈다 (2026-10-06).

## 왜 필요한가

`deploy.yml` 은 `on: push` 로 CI 와 **나란히** 돌았다. 순서를 강제할 수 없어 배포 쪽에서 백엔드
pytest 만 다시 돌렸고, 그래서 프론트 lint·vitest · data pytest · 최소 의존성 임포트가 빨개도 main 푸시는
프로덕션으로 나갔다. 로컬 쪽도 같은 틈이 있었다 — `scripts/run_full_verify.py` 에 lint·vitest 가 없었고,
10-05 에는 로컬 초록 · CI 린트 실패가, 09-24 에는 로컬 초록 · CI data 47건 실패가 났다
(docs/finding-project-review-4roles-2026-10-06.md §4-2).

워크플로 파일은 실행해 보기 전에는 틀려도 아무 데서도 안 터진다. 그래서 **소스만 읽고** 판정한다
(PyYAML 에 기대지 않는다 — 백엔드 CI 환경에 직접 의존성으로 들어 있지 않다).

## 여기서 고정하는 계약

  ① Deploy 는 CI 의 `workflow_run`(completed · main)으로만 자동 실행된다 — `push` 트리거가 없다.
  ② 게이트가 세 조건을 모두 본다: CI 결론 success · CI 를 일으킨 이벤트가 push · 이 저장소의 커밋.
     뒤의 둘이 빠지면 포크 PR 이 `main` 이라는 이름의 브랜치로 돌린 CI 가 배포를 일으킬 수 있다.
  ③ 체크아웃·이미지 태그·배포가 CI 가 검사한 커밋(`DEPLOY_SHA`)을 쓴다 — `github.sha` 를 직접 쓰지 않는다.
  ④ `workflow_run.workflows` 가 가리키는 이름이 실제 CI 워크플로의 `name:` 과 같다(오타면 영영 안 돈다).
  ⑤ CI 의 프론트 npm 단계와 백엔드·data pytest 가 `run_full_verify.STEPS` 에 **같은 순서로** 있다.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

# tests/ → backend → apps → 저장소 루트
_REPO = Path(__file__).resolve().parents[3]
_DEPLOY = (_REPO / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
_CI = (_REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def _top_level_block(text: str, key: str) -> str:
    """최상위 `key:` 아래 들여쓴 줄만 모은다(다음 최상위 키 직전까지). 주석 줄은 뺀다."""
    out: list[str] = []
    inside = False
    for line in text.splitlines():
        if re.match(rf"^{key}:\s*(#.*)?$", line):
            inside = True
            continue
        if inside:
            if line and not line.startswith((" ", "#")):
                break
            if not line.lstrip().startswith("#"):
                out.append(line)
    return "\n".join(out)


def _load_run_full_verify():
    path = _REPO / "scripts" / "run_full_verify.py"
    spec = importlib.util.spec_from_file_location("run_full_verify", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # main() 은 __name__ 가드 안이라 돌지 않는다
    return mod


def _cmd_text(cmd) -> str:
    return cmd if isinstance(cmd, str) else " ".join(str(c) for c in cmd)


# ── ①~④ Deploy 트리거와 게이트 ────────────────────────────────────────────────


def test_deploy_runs_only_after_ci_on_main():
    on = _top_level_block(_DEPLOY, "on")
    assert "workflow_run:" in on, "Deploy 가 CI 결과를 기다리지 않는다"
    assert re.search(r"workflows:\s*\[\s*CI\s*\]", on)
    assert re.search(r"types:\s*\[\s*completed\s*\]", on)
    assert re.search(r"branches:\s*\[\s*main\s*\]", on)
    assert not re.search(r"^\s+push:", on, re.M), "push 트리거가 남아 CI 와 나란히 배포가 돈다"


def test_deploy_gate_checks_conclusion_event_and_repository():
    gate = " ".join(_DEPLOY.split())
    for cond in ("github.event.workflow_run.conclusion == 'success'",
                 "github.event.workflow_run.event == 'push'",
                 "github.event.workflow_run.head_repository.full_name == github.repository"):
        assert cond in gate, f"배포 게이트에 빠진 조건: {cond}"


def test_deploy_uses_the_commit_ci_checked():
    assert re.search(r"DEPLOY_SHA:\s*\$\{\{\s*github\.event\.workflow_run\.head_sha\s*\|\|\s*github\.sha\s*\}\}",
                     _DEPLOY), "배포 커밋을 CI 가 검사한 head_sha 로 고정하지 않았다"
    uses_of_github_sha = [ln.strip() for ln in _DEPLOY.splitlines()
                          if "github.sha" in ln and "DEPLOY_SHA:" not in ln
                          and not ln.lstrip().startswith("#")]
    assert uses_of_github_sha == [], f"github.sha 를 직접 쓰는 줄: {uses_of_github_sha}"
    checkouts = re.findall(r"uses:\s*actions/checkout@\S+\s*\n\s*with:\s*\n\s*ref:\s*(.+)", _DEPLOY)
    assert len(checkouts) == _DEPLOY.count("actions/checkout@"), "ref 없이 체크아웃하는 잡이 있다"
    assert all("env.DEPLOY_SHA" in ref for ref in checkouts)


def test_workflow_run_points_at_the_real_ci_name():
    m = re.search(r"^name:\s*(.+?)\s*$", _CI, re.M)
    assert m and m.group(1) == "CI", "ci.yml 의 name 이 바뀌면 Deploy 의 workflows: [CI] 도 같이 바꿀 것"


# ── ⑤ 로컬 무인 검증 ↔ CI ────────────────────────────────────────────────────


def test_run_full_verify_covers_ci_steps_in_order():
    steps = [_cmd_text(cmd) for _name, cmd, _cwd, _shell in _load_run_full_verify().STEPS]

    ci_npm = re.findall(r"run:\s*(npm run [\w:-]+)", _CI)
    assert ci_npm, "ci.yml 에서 npm 단계를 못 찾았다 — 정규식이 낡았는지 볼 것"
    local_npm = [s for s in steps if s.startswith("npm run")]
    assert local_npm == ci_npm, f"프론트 단계가 CI 와 다르다 — CI {ci_npm} / 로컬 {local_npm}"

    assert any(s.endswith("-m pytest -q") for s in steps), "백엔드 pytest 가 없다"
    assert any("pytest data/tests" in s for s in steps), "data pytest 가 없다 (09-24 의 47건)"
