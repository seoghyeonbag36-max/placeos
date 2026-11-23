"""Platform 인스타그램 — 거점마다 대표 해시태그 하나 (2026-11-22 사용자 결정: 「인스타그램 데이터도 수집할 것」).

왜 하나뿐인가: 공식 Instagram Graph API 는 한 계정이 이어지는 7일 동안 **해시태그 30개**만 검색할 수 있다
(docs/finding-instagram-official-api-2026-11-22.md). 서울 81거점에 하나씩이면 한 바퀴에 3주다.

규칙: 표시명에서 「·」 앞 첫 이름 → 괄호 안 지움 → 띄어쓰기 지움(`derive`). 그 규칙이 자연스러운 태그가 아니면
`OVERRIDES` 에 적는다 — 띄어쓰기 이름(신사동 가로수길 → 가로수길)과 **다른 뜻으로 더 많이 쓰이는 이름**
(수유 → 수유역 · 불광 → 불광역 …)이 여기 온다. 태그를 바꾸면 그 거점의 수집 대상이 바뀐다(이전 값과 견주지 말 것).
같은 태그를 두 거점이 쓰면(잠실 · 잠실 관광특구) 한 번만 검색하고 두 거점에 같은 값을 싣는다 — 화면은 그 사실을 밝힌다.

대상 도시는 사이트가 보이는 도시와 같다(`apps/frontend/src/lib/siteScope.ts` SITE_CITIES — 2026-11-10 서울만).
"""
from __future__ import annotations

import re

TARGET_CITIES: frozenset[str] = frozenset({"seoul"})

OVERRIDES: dict[str, str] = {
    "garosugil": "가로수길",          # 「신사동 가로수길」 — 태그는 가로수길이 압도적이다
    "seongsu": "성수동",              # 「성수동 카페거리」
    "seoulsup": "서울숲",             # 「서울숲 아틀리에길」
    "mullae": "문래동",               # 「문래동 창작촌」
    "cheongdam": "청담동",            # 「청담동 명품거리」
    "jamsil-tour": "잠실",            # 「잠실 관광특구」 — jamsil 과 같은 태그(한 번만 검색)
    "hyehwa": "대학로",               # 「혜화·대학로」 — 상권 정체성(공연)은 대학로 쪽이다
    # 다른 뜻으로 더 많이 쓰이는 이름 → 역·동 이름으로
    "suyu": "수유역",                 # 수유(모유 수유)
    "bulgwang": "불광역",
    "hwagok": "화곡역",
    "kkachisan": "까치산역",          # 까치산(산)
    "sanggye": "상계동",
    "sangbong": "상봉역",
    "doksan": "독산동",
    "cheonho": "천호동",
    "daerim": "대림동",
}

_PAREN = re.compile(r"\([^)]*\)")
_SPACE = re.compile(r"\s+")
# 인스타 해시태그에 못 쓰는 문자 — 한글·영문·숫자·밑줄만 남긴다
_NOT_TAG = re.compile(r"[^0-9A-Za-z_가-힣]")


def derive(name: str) -> str:
    """표시명 → 기본 해시태그(# 없이). 「한남동·용리단길」 → 한남동 · 「을지로(힙지로)」 → 을지로."""
    first = name.split("·", 1)[0]
    return _NOT_TAG.sub("", _SPACE.sub("", _PAREN.sub("", first)))


def hashtag_for(slug: str, name: str) -> str:
    return OVERRIDES.get(slug) or derive(name)


def targets(hubs: dict) -> dict[str, str]:
    """ACTIVE_HUBS(slug → PageHub) → {slug: 해시태그} — 대상 도시만, 표시 순서 그대로."""
    return {slug: hashtag_for(slug, hub.name) for slug, hub in hubs.items() if hub.city in TARGET_CITIES}
