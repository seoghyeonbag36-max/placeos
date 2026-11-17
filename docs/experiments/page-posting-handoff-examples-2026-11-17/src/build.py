"""전부 다시 만든다 — 원본 7개 묶음(out/set) · 표현 유형 5종(out/types) · 검증 설정(check-config.json).

python3 src/build.py            (실험 폴더에서)
"""
import json
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
X = SRC.parent
sys.path.insert(0, str(SRC))

subprocess.run([sys.executable, str(SRC / "gen_pages.py"), str(X), str(X / "out" / "set")], check=True, cwd=SRC)
subprocess.run([sys.executable, str(SRC / "gen_menu.py"), str(X / "out" / "set")], check=True, cwd=SRC)
subprocess.run([sys.executable, str(SRC / "types_render.py"), str(X / "out" / "types")], check=True, cwd=SRC)

from content import CORE_TOKENS, FACTS  # noqa: E402
from types_render import TYPES  # noqa: E402

(X / "out" / "types" / "check-config.json").write_text(json.dumps(
    {"types": [{"file": f, "key": k, "name": n} for f, k, n in TYPES], "facts": FACTS, "core": CORE_TOKENS}, ensure_ascii=False, indent=1))
print("build ok")
