"""다른 트리의 `data/.env` 를 환경변수로 올린 뒤 명령을 실행한다 — `.env`·bronze·silver 가 없는 worktree 에서 수집을 돌릴 때.

worktree 는 git 이 만든 체크아웃이라 `data/.env`(gitignore)·`bronze`·`silver` 가 없다. 그렇다고 키 파일을 복사하지 않는다 —
키를 가진 트리(`--env-root`, 보통 메인 트리)의 로더(`data.run_collection._load_env`)로 **이 프로세스의 환경변수**에만 올리고,
자식 프로세스가 그것을 물려받는다. 자식 수집기도 자기 트리에서 `.env` 를 못 찾지만 이미 올라온 환경을 지우지 않는다.
키 값은 출력하지 않는다(로더가 개수만 찍는다).

원천 루트도 같이 돌린다 — `PLACEOS_BRONZE_ROOT` · `PLACEOS_SILVER_ROOT` 를 `--env-root` 의 `data/bronze` · `data/silver` 로
(이미 지정돼 있으면 그대로). Gold 는 이 트리의 `data/gold` 로 나간다(커밋 대상).

    python scripts/run_with_env_root.py --env-root C:\\...\\spaceos -- python -u scripts/run_hub_chain_batch.py --batch gpcity

종료코드는 명령의 종료코드다.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if "--" not in argv:
        raise SystemExit("사용법: run_with_env_root.py --env-root <트리> -- <명령...>")
    cut = argv.index("--")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-root", required=True, help="data/.env · data/bronze · data/silver 가 있는 트리")
    a = ap.parse_args(argv[:cut])
    cmd = argv[cut + 1:]
    if not cmd:
        raise SystemExit("실행할 명령이 없다")
    root = Path(a.env_root).resolve()
    env_file = root / "data" / ".env"
    if not env_file.exists():
        raise SystemExit(f"{env_file} 없음 — 키가 있는 트리를 --env-root 로 지정")
    sys.path.insert(0, str(root))
    from data.run_collection import _load_env
    _load_env(env_file)                     # 개수만 출력한다 — 값은 찍지 않는다
    for name, sub in (("PLACEOS_BRONZE_ROOT", "bronze"), ("PLACEOS_SILVER_ROOT", "silver")):
        os.environ.setdefault(name, str(root / "data" / sub))
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(cmd, env=os.environ).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
