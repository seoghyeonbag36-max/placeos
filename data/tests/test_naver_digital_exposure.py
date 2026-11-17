import datetime as dt

from data.collectors.naver_digital_exposure import complete_from, month_histogram, token_hit, window_stats


def test_token_hit_needs_every_word_and_strips_html():
    item = {"title": "<b>신사동</b> 핫플", "description": "가로수길 카페 후기"}
    assert token_hit(item, "신사동 가로수길")
    assert not token_hit(item, "신사동 압구정")
    assert not token_hit({"title": "서울 맛집 추천", "description": ""}, "숙대입구")


def test_window_stats_rate_is_posts_per_window_day():
    # 가로수길 11-17 실측 모양: 1,000건이 11-09~11-17 = 9일(양끝 포함)
    assert window_stats("20261109", 1000, dt.date(2026, 11, 17)) == (9, 111.1111)


def test_window_stats_none_when_no_posts_or_bad_date():
    assert window_stats(None, 0, dt.date(2026, 11, 17)) == (None, None)
    assert window_stats("20261301", 5, dt.date(2026, 11, 17)) == (None, None)


def test_month_histogram_buckets_by_month_and_skips_bad_dates():
    got = month_histogram(["20261105", "20261101", "20261031", "", "2026-11", "abc"])
    assert got == {"2026-10": 1, "2026-11": 2}


def test_complete_from_capped_window_drops_the_partial_oldest_month():
    # 1,000건에서 잘렸다면 가장 오래된 글의 달(2026-03)은 일부만 담겼다 → 다음 달부터 온전
    assert complete_from("20260311", capped=True) == "2026-04"
    assert complete_from("20261215", capped=True) == "2027-01"


def test_complete_from_uncapped_window_keeps_the_oldest_month():
    assert complete_from("20260311", capped=False) == "2026-03"


def test_complete_from_empty_is_none():
    assert complete_from(None, capped=False) is None
    assert complete_from("", capped=True) is None
