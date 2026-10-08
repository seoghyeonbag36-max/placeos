"""랜딩이 말하는 거점 수 = 서빙 거점 수 (2026-10-08).

랜딩(`apps/frontend/src/pages/Landing.tsx`)은 「서울 N개 상권」이라고 말한다. N 은 `lib/landingFacts.ts` 에 한 번만 적혀 있고,
이 저장소에서 거점 수는 문서마다 세 번 낡았다(CLAUDE.md 「거점」 행). 거점이 늘거나 줄었는데 랜딩이 옛 숫자를 말하면
방문자가 가장 먼저 읽는 자리가 거짓이 된다 — 그래서 어긋나면 여기서 먼저 운다.

운다면: `apps/frontend/src/lib/landingFacts.ts` 의 `LANDING_HUBS` 를 `python scripts/pppp_status.py` 첫 줄의 거점 수로 고친다.
(그 숫자를 근거로 한 문장 — 「건축물대장 기준 실측」 · 「R-ONE 대조」 — 이 새 거점에도 참인지도 같이 본다:
 pppp_status 의 Page 게이트 「Tier1 대장 실측」 · 「R-ONE 앵커 대조 보유」 가 거점 수와 같은 N/N 이어야 한다.)
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_PAGE_HUBS = _ROOT / "data" / "config" / "page_hubs.py"
_FACTS = _ROOT / "apps" / "frontend" / "src" / "lib" / "landingFacts.ts"


def _active_hubs():
    spec = importlib.util.spec_from_file_location("_test_landing_page_hubs", _PAGE_HUBS)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_test_landing_page_hubs"] = mod
    spec.loader.exec_module(mod)
    return mod.ACTIVE_HUBS


def _landing_hubs() -> int:
    m = re.search(r"export\s+const\s+LANDING_HUBS\s*=\s*(\d+)\s*;", _FACTS.read_text(encoding="utf-8"))
    assert m, f"{_FACTS} 에서 LANDING_HUBS 를 못 읽었다 — 상수 이름을 바꿨다면 이 테스트도 같이 고친다"
    return int(m.group(1))


def test_landing_hub_count_matches_served_hubs():
    served = len(_active_hubs())
    claimed = _landing_hubs()
    assert claimed == served, (
        f"랜딩이 「서울 {claimed}개 상권」이라고 말하는데 서빙 거점은 {served}개다. "
        "apps/frontend/src/lib/landingFacts.ts 의 LANDING_HUBS 를 고칠 것(docs/spec-landing-founders-2026-10-08.md)."
    )


def test_every_served_hub_has_gold_coverage():
    """랜딩의 「모두 건축물대장 기준」 은 서빙 거점마다 Gold 산출물이 있다는 뜻이다 — 없는 거점이 서빙에 끼면 그 문장이 거짓이 된다."""
    gold = _ROOT / "data" / "gold"
    missing = sorted(slug for slug in _active_hubs() if not (gold / slug / "coverage.json").is_file())
    assert not missing, f"서빙 거점인데 Gold coverage.json 이 없다: {missing}"
