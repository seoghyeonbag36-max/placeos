"""도시 레지스트리 — 거점이 어느 시(市)에 속하는지, 그 시에 어떤 소스가 서는지.

## 왜 필요한가

54거점은 전부 서울이라 지금까지 도시가 **암묵**이었다(`seoul_pages.py`라는 파일명이
곧 도시였다). 고양·파주를 붙이려면 그 암묵을 필드로 끌어내야 한다 —
`city` 가 없으면 프론트가 거점 목록에서 서울과 경기를 구분할 수 없고, 백엔드는
"이 거점에 TRDAR 이 서는가"를 물을 방법이 없다.

## 두 축을 한 곳에서 정한다

1. **소속** — `gu`(자치구·일반구) → 도시. 거점 시드가 이미 `gu` 를 갖고 있으므로
   54개 항목을 건드리지 않고 도시를 유도할 수 있다.
2. **소스 세트** — 그 도시에 서울 전용 소스(TRDAR·서울 생활인구·서울 문화행사)가
   서는가. 서지 않으면 그 자리는 **비워 두고 화면이 그 사실을 밝힌다**(경기 대체
   소스 배선은 docs/plan-gyeonggi-expansion-2026-08-29.md Phase 3).

⚠ 도시를 늘릴 때는 `data/config/page_hubs.PageHub.city` 도 같이 늘린다. 두 곳이
   어긋나면 수집은 되는데 API 가 그 거점을 다른 도시로 부르게 된다 —
   `tests/test_city_registry.py` 가 이 어긋남을 고정한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class City:
    id: str                      # 도시 슬러그 (page_hubs.PageHub.city 와 같은 값)
    name: str                    # 정식 명칭
    short: str                   # 화면 표기 (칩·필터)
    sido: str                    # 시도명
    sgg_codes: frozenset[str]    # 법정 시군구 코드 5자리 — PNU 앞 5자리와 대조한다
    gus: frozenset[str]          # 이 도시에 속한 구(자치구·일반구) 또는 시 이름
    # 서울 전용 소스가 서는가. False 면 그 축은 **비어 있는 것이 정상**이다.
    has_trdar: bool = False          # 상권분석(추정매출·유동·연령·성별)
    has_living_pop: bool = False     # 생활인구(행정동·집계구 24시간)
    has_city_events: bool = False    # 문화행사 실데이터
    note: str = ""


_SEOUL_GUS = frozenset({
    "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구",
    "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구",
    "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구",
    "강동구",
})
# 서울 25 자치구 코드 11110~11740 (10 단위). 전부 적지 않고 접두로 판정한다.
_SEOUL_SGG = frozenset({f"111{n:02d}" for n in range(10, 100)} |
                       {f"112{n:02d}" for n in range(10, 100)} |
                       {f"113{n:02d}" for n in range(10, 100)} |
                       {f"114{n:02d}" for n in range(10, 100)} |
                       {f"115{n:02d}" for n in range(10, 100)} |
                       {f"116{n:02d}" for n in range(10, 100)} |
                       {f"117{n:02d}" for n in range(10, 100)})

CITIES: dict[str, City] = {
    "seoul": City(
        id="seoul", name="서울특별시", short="서울", sido="서울특별시",
        sgg_codes=_SEOUL_SGG, gus=_SEOUL_GUS,
        has_trdar=True, has_living_pop=True, has_city_events=True,
        note="원년 도시. 서울 전용 소스 3종이 전부 선다 — 거점 수는 page_hubs.ACTIVE_HUBS 가 정한다",
    ),
    "goyang": City(
        id="goyang", name="고양특례시", short="고양", sido="경기도",
        # 41281 덕양구 · 41285 일산동구 · 41287 일산서구
        sgg_codes=frozenset({"41281", "41285", "41287"}),
        gus=frozenset({"덕양구", "일산동구", "일산서구"}),
        note="R-ONE 표본 2곳(고양시청·탄현역). 계획상가 밀집 주의 → plan §3-B",
    ),
    "paju": City(
        id="paju", name="파주시", short="파주", sido="경기도",
        sgg_codes=frozenset({"41480"}),
        gus=frozenset({"파주시"}),
        note="R-ONE 표본 1곳(파주시청). 운정은 공유 매핑 대상",
    ),
    # ── 경기 3차 확장 20개 시(2026-10-28 · 등록만 — 서빙은 Gold·앵커 대조 뒤) ─────────────────────
    # 시군구 코드는 그 거점 점포(상가정보 signguCd)에서 읽은 실측이다. 일반구가 있는 시는 구 코드를 모두 적는다 —
    # 부천은 2024 일반구 부활(원미 41192 · 소사 41194 · 오정 41196), 화성은 2026 일반구(만세 41591 · 효행 41593 ·
    # 병점 41595 · 동탄 41597)라 옛 시 코드(41190 · 41590)도 같이 둔다(PNU 가 옛 코드로 남은 필지가 있을 수 있다).
    "suwon": City(id="suwon", name="수원특례시", short="수원", sido="경기도",
                  sgg_codes=frozenset({"41111", "41113", "41115", "41117"}),
                  gus=frozenset({"장안구", "권선구", "팔달구", "영통구"}),
                  note="R-ONE 6곳(수원역·인계동·팔달문로터리·수원파장동·아주대삼거리·영통역)"),
    "seongnam": City(id="seongnam", name="성남시", short="성남", sido="경기도",
                     sgg_codes=frozenset({"41131", "41133", "41135"}),
                     gus=frozenset({"수정구", "중원구", "분당구"}),
                     note="R-ONE 4곳(모란·성남구시가지·단대오거리역·분당역세권) — 분당 서현역은 계획상가 밀집으로 제외"),
    "bucheon": City(id="bucheon", name="부천시", short="부천", sido="경기도",
                    sgg_codes=frozenset({"41190", "41192", "41194", "41196"}),
                    gus=frozenset({"원미구", "소사구", "오정구"}),
                    note="R-ONE 1곳(부천역) — 송내·역곡·신중동은 공유"),
    "anyang": City(id="anyang", name="안양시", short="안양", sido="경기도",
                   sgg_codes=frozenset({"41171", "41173"}),
                   gus=frozenset({"만안구", "동안구"}),
                   note="R-ONE 2곳(안양역·인덕원) — 범계역은 계획상가 밀집으로 제외"),
    "uijeongbu": City(id="uijeongbu", name="의정부시", short="의정부", sido="경기도",
                      sgg_codes=frozenset({"41150"}), gus=frozenset({"의정부시"}),
                      note="R-ONE 1곳(의정부역)"),
    "pyeongtaek": City(id="pyeongtaek", name="평택시", short="평택", sido="경기도",
                       sgg_codes=frozenset({"41220"}), gus=frozenset({"평택시"}),
                       note="R-ONE 3곳(평택역·평택시청·신장/지산/서정)"),
    "guri": City(id="guri", name="구리시", short="구리", sido="경기도",
                 sgg_codes=frozenset({"41310"}), gus=frozenset({"구리시"}), note="R-ONE 1곳(구리역)"),
    "yongin": City(id="yongin", name="용인특례시", short="용인", sido="경기도",
                   sgg_codes=frozenset({"41461", "41463", "41465"}),
                   gus=frozenset({"처인구", "기흥구", "수지구"}),
                   note="R-ONE 3곳(용인수지·김량장동·기흥역)"),
    "hwaseong": City(id="hwaseong", name="화성특례시", short="화성", sido="경기도",
                     sgg_codes=frozenset({"41590", "41591", "41593", "41595", "41597"}),
                     gus=frozenset({"만세구", "효행구", "병점구", "동탄구"}),
                     note="R-ONE 3곳(병점역·화성봉담읍·화성남양읍) — 동탄역은 계획상가 밀집, 남양읍은 점포가 적어 이번 배치에서 뺐다"),
    "osan": City(id="osan", name="오산시", short="오산", sido="경기도",
                 sgg_codes=frozenset({"41370"}), gus=frozenset({"오산시"}), note="R-ONE 1곳(오산시청)"),
    "icheon": City(id="icheon", name="이천시", short="이천", sido="경기도",
                   sgg_codes=frozenset({"41500"}), gus=frozenset({"이천시"}), note="R-ONE 1곳(이천종합터미널)"),
    "yeoju": City(id="yeoju", name="여주시", short="여주", sido="경기도",
                  sgg_codes=frozenset({"41670"}), gus=frozenset({"여주시"}), note="R-ONE 1곳(여주시청)"),
    "pocheon": City(id="pocheon", name="포천시", short="포천", sido="경기도",
                    sgg_codes=frozenset({"41650"}), gus=frozenset({"포천시"}),
                    note="R-ONE 2곳(포천시외버스터미널·포천소흘읍)"),
    "dongducheon": City(id="dongducheon", name="동두천시", short="동두천", sido="경기도",
                        sgg_codes=frozenset({"41250"}), gus=frozenset({"동두천시"}), note="R-ONE 1곳(동두천중앙로)"),
    "yangju": City(id="yangju", name="양주시", short="양주", sido="경기도",
                   sgg_codes=frozenset({"41630"}), gus=frozenset({"양주시"}), note="R-ONE 1곳(양주덕정역)"),
    "hanam": City(id="hanam", name="하남시", short="하남", sido="경기도",
                  sgg_codes=frozenset({"41450"}), gus=frozenset({"하남시"}),
                  note="R-ONE 1곳(하남원도심) — 미사역은 계획상가 밀집으로 제외"),
    "gwangju-gg": City(id="gwangju-gg", name="광주시", short="경기광주", sido="경기도",
                       sgg_codes=frozenset({"41610"}), gus=frozenset({"광주시"}),
                       note="R-ONE 2곳(광주시가지·광주광남동). 광주광역시와 헷갈리지 않게 short 를 「경기광주」로 둔다"),
    "gwangmyeong": City(id="gwangmyeong", name="광명시", short="광명", sido="경기도",
                        sgg_codes=frozenset({"41210"}), gus=frozenset({"광명시"}), note="R-ONE 1곳(광명철산)"),
    "siheung": City(id="siheung", name="시흥시", short="시흥", sido="경기도",
                    sgg_codes=frozenset({"41390"}), gus=frozenset({"시흥시"}), note="R-ONE 1곳(신천역)"),
    "anseong": City(id="anseong", name="안성시", short="안성", sido="경기도",
                    sgg_codes=frozenset({"41550"}), gus=frozenset({"안성시"}), note="R-ONE 1곳(안성 서인사거리)"),
}

DEFAULT_CITY = "seoul"


def by_id(city_id: str | None) -> City:
    """도시 슬러그 → City. 모르는 값은 서울로 눕히지 않고 KeyError 를 낸다 —
    조용히 서울이 되면 경기 거점이 서울 소스를 가진 것처럼 응답한다."""
    return CITIES[city_id or DEFAULT_CITY]


def of_gu(gu: str | None) -> City:
    """거점의 `gu` 로 도시를 판정. 어느 도시에도 안 걸리면 서울(원년 기본값).

    ⚠ 새 도시를 넣을 때 `gus` 를 채우지 않으면 그 거점이 **조용히 서울이 된다**.
       `tests/test_city_registry.py::test_every_hub_city_is_registered` 가 막는다.
    """
    for city in CITIES.values():
        if gu in city.gus:
            return city
    return CITIES[DEFAULT_CITY]


def of_pnu(pnu: str | None) -> City | None:
    """PNU 19자리 앞 5자리(법정 시군구 코드) → City. 미등록 지역이면 None.

    수집 산출물이 **정말 그 도시 것인지** 좌표가 아니라 코드로 검증하는 자리다
    (좌표는 경계에서 흔들리지만 PNU 는 안 흔들린다).
    """
    if not pnu or len(pnu) < 5:
        return None
    sgg = pnu[:5]
    for city in CITIES.values():
        if sgg in city.sgg_codes:
            return city
    return None
