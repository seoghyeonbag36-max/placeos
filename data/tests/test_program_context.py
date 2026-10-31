"""[Program] 상권 컨텍스트 정제 규칙 회귀 테스트.

2026-08-01 에 고친 두 결함을 고정한다.

1. **동명이지(同名異地) 오염** — 거점명만으로 블로그를 질의해 타 시도 동명 상권 글이
   섞였다. 54거점 전수 17,653건 중 1,295건(7.3%), jangan 43.6%(수원·평택 장안동),
   garosugil 31.8%(창원 가로수길). blog_keyword 2위가 '창원'이던 거점도 있었다.
2. **검색 트렌드 미완성 달** — 데이터랩 월 버킷의 마지막 달은 수집 시점까지의 부분합인데
   그대로 실어 급락처럼 보였다(신사동 63.4→35.6 = 절단비율 18/31일과 거의 일치).
   이 값이 Program 상권 카피의 트렌드 오독을 낳았다.

실행: (레포 루트에서) python -m pytest data/tests -q
"""
from __future__ import annotations

from data.pipelines.build_gold import (
    _HOME_TERMS_DEFAULT,
    _complete_trend_points,
    _home_terms,
    _hub_terms,
    _is_offsite,
    _program_context_rows,
)


# ── 1. 동명이지 필터 ────────────────────────────────────────────────────────────
def test_offsite_place_without_seoul_is_dropped():
    """타 시도 지명만 있는 글은 버린다."""
    assert _is_offsite("창원 용호동 가로수길 파스타 맛집 루포 다녀온 솔직 후기")
    assert _is_offsite("수원 장안동 맛집 추천 베스트5")


def test_seoul_shop_name_containing_place_is_kept():
    """서울 상호에 지명이 들어간 경우는 살린다 — 시청역 '진주회관', 안암 '제주고깃집'."""
    assert not _is_offsite("[서울 시청역] 진주회관 : 50년 전통 콩국수 맛집")
    assert not _is_offsite("안암 제주고깃집 서울에서 즐기는 흑돼지")


def test_offsite_adjacent_to_hub_name_is_dropped_even_with_seoul():
    """'평택시 장안동'처럼 타지명이 거점명에 붙으면 서울을 언급해도 버린다.

    평택 분양 광고가 본문에 "서울·수도권"을 끼워 넣고 말미에 "평택시 장안동에 위치"를
    다는 형태로 서울 예외를 통과해, jangan 상위 키워드에 '브레인시티'가 올라와 있었다.
    """
    text = ("8월 입주 준비에 분주한 브레인시티 대광로제비앙 — 서울과 수도권 남부는 물론 "
            "충청권에서 찾는 이동경로가 다양해지면… 평택시 장안동에 위치하고 있으며")
    assert _is_offsite(text, frozenset({"장안동"}))
    assert not _is_offsite(text)          # 거점명을 모르면 서울 예외로 살아남는다


def test_hub_terms_from_query_drops_generic_words():
    """거점 고유 지명은 검색어에서 뽑고 광역·업종어는 뺀다."""
    posts = [{"_query": "서울 장안동 맛집"}, {"_query": "서울 장안동 카페"}]
    assert _hub_terms(posts) == frozenset({"장안동"})


# ── 2. 도배 상한 ────────────────────────────────────────────────────────────────
def test_single_blogger_flood_is_capped():
    """한 블로거의 대량 발행은 상한까지만 센다 (nambu 386건 중 154건이 한 업체였다)."""
    spam = [{"title": "수거 처분 폐기 마트배달", "description": "", "_query": "서울 남부터미널 맛집",
             "bloggerlink": "blog.naver.com/spam"} for _ in range(50)]
    real = [{"title": f"남부터미널 국밥집 {i}", "description": "", "_query": "서울 남부터미널 맛집",
             "bloggerlink": f"blog.naver.com/user{i}"} for i in range(5)]
    rows = _program_context_rows(spam + real, [], None, set())
    counts = {r["key"]: r["value"] for r in rows if r["kind"] == "blog_keyword"}
    assert counts.get("마트배달", 0) == 3, "도배가 상한을 넘겨 집계됐다"
    assert counts.get("국밥집") == 5, "정상 글까지 깎였다"


# ── 3. 미완성 달 절단 ───────────────────────────────────────────────────────────
def _group(periods: list[str]) -> dict:
    return {"title": "신사동", "data": [{"period": p, "ratio": 50.0} for p in periods]}


def test_partial_last_month_is_dropped():
    """월 중에 수집했으면 마지막 달 버킷은 부분합이라 버린다."""
    g = _group(["2026-05-01", "2026-06-01", "2026-07-01"])
    kept = [p["period"] for p in _complete_trend_points(g, "2026-07-18")]
    assert kept == ["2026-05-01", "2026-06-01"]


def test_complete_last_month_is_kept():
    """말일에 수집했으면 그 달은 완성이므로 남긴다."""
    g = _group(["2026-05-01", "2026-06-01", "2026-07-01"])
    kept = [p["period"] for p in _complete_trend_points(g, "2026-07-31")]
    assert kept == ["2026-05-01", "2026-06-01", "2026-07-01"]


def test_missing_end_date_keeps_all():
    """endDate 를 모르면 자르지 않는다 — 근거 없이 데이터를 버리지 않는다."""
    g = _group(["2026-06-01", "2026-07-01"])
    assert len(_complete_trend_points(g, "")) == 2


# ── 거점 도시 이름 (2026-10-31) ─────────────────────────────────────────────
# 서울 밖 거점은 질의가 「{도시} {거점명} 맛집」이다. 그 도시 이름을 타지명으로 세면 「수원 인계동」처럼
# 자기 도시 + 거점명 인접이 동명이지 1번 규칙에 걸려 글이 거의 다 버려진다(서빙 22거점 85% 폐기 실측).

def _posts(query: str, *texts: str) -> list[dict]:
    return [{"_query": query, "title": t, "description": "", "bloggerlink": f"b{i}"} for i, t in enumerate(texts)]


def test_home_terms_come_from_the_query_prefix():
    assert _home_terms(_posts("수원 인계동 맛집", "x")) == frozenset({"수원"})
    assert _home_terms(_posts("광주 충장로 카페", "x")) == frozenset({"광주"})
    # 「부천」은 타지명 목록에 없다 — 수집기 접두어 표(CITY_WORD)로 도시를 인정한다
    assert _home_terms(_posts("부천 부천역 맛집", "x")) == frozenset({"부천"})
    # 서울 거점·도시 접두어가 없는 질의는 종전 기본값 그대로다(서울 판정 회귀 없음)
    assert _home_terms(_posts("서울 장안동 맛집", "x")) == _HOME_TERMS_DEFAULT
    assert _home_terms(_posts("신사동 가로수길", "x")) == _HOME_TERMS_DEFAULT
    assert _home_terms([]) == _HOME_TERMS_DEFAULT


def test_own_city_next_to_hub_name_is_not_offsite():
    text = "수원 인계동 맛집 추천 — 인계동 술집 거리"
    assert _is_offsite(text, frozenset({"인계동"}))                              # 종전 호출(기본값 서울) — 버렸다
    assert not _is_offsite(text, frozenset({"인계동"}), frozenset({"수원"}))      # 도시 이름을 넘기면 산다
    # 다른 도시의 같은 동네는 여전히 버린다
    assert _is_offsite("평택시 장안동 분양", frozenset({"장안동"}), frozenset({"수원"}))


def test_context_rows_keep_posts_that_name_their_own_city():
    posts = _posts("수원 인계동 맛집", *[f"수원 인계동 맛집 {i} 곱창 후기" for i in range(6)])
    rows = _program_context_rows(posts, [], None, set())
    assert any(r["kind"] == "blog_keyword" and r["key"] == "곱창" for r in rows), rows
