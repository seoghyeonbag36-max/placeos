"""[Platform] 상권 흐름(축) 정의 — 여러 도시를 **고객이 오가는 하나의 흐름**으로 읽는 단위.

## 왜 필요한가 (2026-10-26 사용자 결정)

거점은 지금까지 한 점이었다. 「파주-고양-서울을 하나의 흐름으로」는 거점을 서로 이어
**고객이 어디서 와서 어디로 가는가 · 지역끼리 어떻게 이어지는가 · 지역마다 어떤 시너지를
낼 수 있는가**를 보자는 것이다. 이 파일은 그 흐름이 **어느 지역을 어떤 순서로** 잇는지만
정한다. 숫자는 전부 산출물(gold/platform_corridor.json)에서 나온다.

## 이것은 '동선'이 아니다

원천(서울시×KT 수도권 생활이동, OA-22300)은 **출발 행정동 → 도착 행정동 집계**다. 한 사람의
궤적이 아니다(docs/finding-movement-viz-2026-09-17.md). 그래서 화면·문서는 「유입 흐름」·
「이동 흐름(집계)」이라고 쓰고 「동선」이라고 쓰지 않는다.

## 구간(segment) 순서

북쪽에서 남쪽으로 — 파주 → 고양 → 서울. 순서는 화면이 위에서 아래로 그리는 순서다.
구간의 경계는 행정구역(시군구 코드 5자리)이다. 거점이 어느 구간인지는 거점의 `city` 로 정한다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    key: str                      # 구간 id — page_hubs.PageHub.city 와 같은 값
    name: str                     # 화면 표기
    sgg_prefixes: tuple[str, ...]  # 행정동 코드 앞자리(시군구 5자리 또는 시도 2자리)

    def contains(self, adong_cd: str) -> bool:
        return any(str(adong_cd).startswith(p) for p in self.sgg_prefixes)


@dataclass(frozen=True)
class Corridor:
    id: str
    name: str
    segments: tuple[Segment, ...]   # 화면 순서(북 → 남)
    note: str = ""

    def segment_of(self, adong_cd: str) -> str | None:
        for s in self.segments:
            if s.contains(adong_cd):
                return s.key
        return None


# 서울시×KT 생활이동의 행정동 코드는 8자리(시도 2 · 시군구 3 · 읍면동 3)다 —
# 상가정보 `adongCd` 와 같은 체계라 거점을 그대로 잇는다(2026-10-26 실측: 금촌1동 41480510).
PAJU_GOYANG_SEOUL = Corridor(
    id="paju-goyang-seoul",
    name="파주 · 고양 · 서울",
    segments=(
        Segment("paju", "파주", ("41480",)),
        # 고양 3구 — 41281 덕양구 · 41285 일산동구 · 41287 일산서구
        Segment("goyang", "고양", ("41281", "41285", "41287")),
        Segment("seoul", "서울", ("11",)),
    ),
    note="경의중앙선·3호선·GTX-A 가 지나는 서북부 생활권. 구간 경계는 행정구역이다.",
)

CORRIDORS: dict[str, Corridor] = {c.id: c for c in (PAJU_GOYANG_SEOUL,)}

# 시군구 마디 이름 — 수도권 생활이동이 서울 밖을 **시군구로만** 싣기 때문에(2026-10-26 실측:
# 경기 47 · 인천 11 코드가 전부 `XXXXX000`) 경기 쪽 흐름의 마디는 거점이 아니라 시군구다.
SGG_NAMES: dict[str, str] = {
    "41480": "파주시",
    "41281": "고양 덕양구",
    "41285": "고양 일산동구",
    "41287": "고양 일산서구",
}


# 구간 밖 출발·도착을 접는 묶음. 흐름 화면이 「그 밖」을 한 칸으로 보여 줄 때 쓴다.
def outer_group(adong_cd: str) -> str:
    """구간 밖 행정동 → 묶음 이름. 경기 기타 · 인천 · 그 밖."""
    s = str(adong_cd)
    if s.startswith("41"):
        return "gyeonggi_other"
    if s.startswith("28"):
        return "incheon"
    return "other"


OUTER_LABEL: dict[str, str] = {
    "gyeonggi_other": "경기 다른 시군",
    "incheon": "인천",
    "other": "그 밖",
}
