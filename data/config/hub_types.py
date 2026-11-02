"""서울 81거점 → 유형 T1~T10 — 사람이 붙인 분류 라벨(`/commercial-districts/outlines` 의 type_*).

원본: Renewal/PlaceOS_서울81개상권_유형분류_2026-10-09.html 의 표(저장소 밖 · 2026-10-09 판).
모델 출력도 공식 상권 구분도 아니다. `HUB_TYPE_FROM_DATA` 는 원본에서 「라벨 없는 거점 — 데이터로 분류」(*) 표시가
붙은 곳이다. 서울 밖에는 유형이 없다 — 지어내지 않는다.
"""
from __future__ import annotations

TYPE_NAMES: dict[str, str] = {
    "T1": "도심 관광·쇼핑",
    "T2": "시장·도매",
    "T3": "도심 재생·한옥 골목",
    "T4": "강남 하이엔드·미용의료",
    "T5": "트렌드 골목·감성",
    "T6": "대학가·청년·수험",
    "T7": "오피스·업무 배후",
    "T8": "대형 복합시설 지배",
    "T9": "지역 중심 번화가",
    "T10": "주거 배후 생활권",
}

HUB_TYPES: dict[str, str] = {
    # T1 도심 관광·쇼핑
    "cityhall": "T1",
    "myeongdong": "T1",
    # T2 시장·도매
    "cheongnyangni": "T2",
    "dongdaemun": "T2",
    "garak": "T2",
    "gwangjang": "T2",
    "namdaemun": "T2",
    # T3 도심 재생·한옥 골목
    "chungmuro": "T3",
    "euljiro": "T3",
    "ikseon": "T3",
    "mullae": "T3",
    "samcheong": "T3",
    "seochon": "T3",
    # T4 강남 하이엔드·미용의료
    "apgujeong-rodeo": "T4",
    "cheongdam": "T4",
    "dosan": "T4",
    "garosugil": "T4",
    "hannam": "T4",
    # T5 트렌드 골목·감성
    "hapjeong": "T5",
    "itaewon": "T5",
    "mangwon": "T5",
    "seongsu": "T5",
    "seoulsup": "T5",
    "songridan": "T5",
    "yeonhui": "T5",
    "yeonnam": "T5",
    # T6 대학가·청년·수험
    "anam": "T6",
    "gunja": "T6",
    "hongdae": "T6",
    "hyehwa": "T6",
    "konkuk": "T6",
    "kyunghee": "T6",
    "nokdu": "T6",
    "noryangjin": "T6",
    "sharosugil": "T6",
    "sinchon": "T6",
    "sukmyung": "T6",
    "sungshin": "T6",
    # T7 오피스·업무 배후
    "bangbang": "T7",
    "dangsan": "T7",
    "gangnam": "T7",
    "gongdeok": "T7",
    "gurodigital": "T7",
    "nambu": "T7",
    "nonhyeon": "T7",
    "seochoyeok": "T7",
    "seolleung": "T7",
    "teheran": "T7",
    "yangjae": "T7",
    # T8 대형 복합시설 지배
    "banpo": "T8",
    "jamsil": "T8",
    "yeouido": "T8",
    "yongsan": "T8",
    # T9 지역 중심 번화가
    "bulgwang": "T9",
    "cheonho": "T9",
    "daerim": "T9",
    "hwagok": "T9",
    "jamsil-tour": "T9",
    "jamsilsaenae": "T9",
    "jangan": "T9",
    "kkachisan": "T9",
    "miasageori": "T9",
    "nowon": "T9",
    "sadang": "T9",
    "sangbong": "T9",
    "sillim": "T9",
    "suyu": "T9",
    "wangsimni": "T9",
    "yeonsinnae": "T9",
    # T10 주거 배후 생활권
    "bonseobu": "T10",
    "dogok": "T10",
    "doksan": "T10",
    "gildong": "T10",
    "gurojeonhwa": "T10",
    "guui": "T10",
    "maebong": "T10",
    "mokdong-yc": "T10",
    "oryudong": "T10",
    "poi": "T10",
    "sanggye": "T10",
    "ydp-gucheong": "T10",
}

HUB_TYPE_FROM_DATA: frozenset[str] = frozenset({
    "bangbang",
    "bonseobu",
    "bulgwang",
    "cheonho",
    "daerim",
    "dogok",
    "doksan",
    "gildong",
    "gurodigital",
    "gurojeonhwa",
    "guui",
    "hwagok",
    "jamsil-tour",
    "kkachisan",
    "maebong",
    "miasageori",
    "mokdong-yc",
    "nowon",
    "oryudong",
    "poi",
    "sangbong",
    "sanggye",
    "seochoyeok",
    "suyu",
    "yangjae",
    "ydp-gucheong",
    "yeonsinnae",
})


def type_of(slug: str) -> tuple[str, str] | None:
    """거점 → (유형 코드, 유형 이름). 서울 밖·미분류는 None."""
    code = HUB_TYPES.get(slug)
    return (code, TYPE_NAMES[code]) if code else None
