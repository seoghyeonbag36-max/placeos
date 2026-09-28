"""train_gnn 을 세그폴트에서 자동 재개하며 완주시킨다.

이 노트북에서 GNN 학습이 무작위 지점에서 0xC0000005(VCRUNTIME140.dll · c10.dll)로 죽는다
(train_gnn 의 '크래시 내성' 주석 · 2026-09-27 실측: 1~11분 간격으로 연달아 죽기도 했다).
학습기가 `--ckpt-every` 에포크마다 재개 파일을 남기므로 **같은 인자**로 다시 부르면 이어받는다.

- 세그폴트 종료코드만 재시도한다. 다른 실패(예외·인자 오류)는 그대로 멈춘다 — 학습이
  끝난 뒤 단계의 결정적 오류를 처음부터 재학습으로 되풀이하지 않게.
- `--ckpt-every` 를 안 주면 5 를 붙인다. 기본 25(≈13분)는 짧은 간격 크래시에서 진전이 없다.
  이 값은 재개 sig 에 들어가지 않아 기존 재개 파일을 그대로 문다.
- ⚠ 학습 중에 `ml/artifacts/.train_gnn_resume.pt` 를 열지 말 것 — 학습기의 원자적 교체가
  Windows 파일 잠금에 걸려 PermissionError 로 죽는다(2026-09-27). 진행은 로그로 본다.
- 재부팅은 못 버틴다. 재부팅 뒤 같은 명령으로 다시 부르면 이어진다.

실행 (세션 밖·절전 억제는 autorun 스킬 · keep_awake.ps1):
  python -u scripts/run_gnn_retry.py --epochs 600 --patience 80 --label-level group_mapped
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEGV = {3221225477, -1073741819}      # 0xC0000005 — 부호 없는/있는 표기
MAX_RETRY = 200


def main(argv: list[str]) -> int:
    args = list(argv)
    if not any(a == "--ckpt-every" or a.startswith("--ckpt-every=") for a in args):
        args += ["--ckpt-every", "5"]
    cmd = [sys.executable, "-u", "-m", "ml.training.train_gnn", *args]
    env = {**os.environ, "OMP_NUM_THREADS": "1", "PYTHONIOENCODING": "utf-8"}
    rc = 1
    for attempt in range(1, MAX_RETRY + 1):
        print(f"[retry] 시도 {attempt} · {datetime.now():%H:%M:%S} · {' '.join(args)}",
              flush=True)
        rc = subprocess.call(cmd, env=env, cwd=ROOT)
        if rc == 0:
            print(f"[retry] 완주 · 시도 {attempt}", flush=True)
            return 0
        if rc not in SEGV:
            print(f"[retry] 세그폴트가 아닌 종료 {rc} — 재시도하지 않는다", flush=True)
            return rc
        print(f"[retry] 세그폴트 {rc} — 재개 파일에서 다시", flush=True)
    print(f"[retry] {MAX_RETRY}회 재시도에도 완주 못 함", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
