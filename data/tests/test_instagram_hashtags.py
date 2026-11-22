"""인스타그램 해시태그 수집·Gold (2026-11-22) — 공식 Graph API 만 · 한도 30/7일 · 계정·본문·토큰을 남기지 않는다.

가짜 Graph(아래 FakeGraph)만 부른다 — 실제 인스타그램은 부르지 않는다. 게시물·태그·토큰은 테스트 전용 합성값이다.
"""
from __future__ import annotations

import datetime as dt
import json
from types import SimpleNamespace

import pytest

from data.collectors import instagram_hashtags as ig
from data.config import instagram_hashtags as cfg
from data.config.page_hubs import ACTIVE_HUBS
from data.pipelines import build_instagram_gold as gold

TOKEN = "SYNTHETIC-TOKEN-zz9"
NOW = dt.datetime(2026, 11, 22, 12, 0, tzinfo=dt.timezone.utc)
HUBS = {
    "garosugil": SimpleNamespace(name="신사동 가로수길", city="seoul"),
    "jamsil": SimpleNamespace(name="잠실·롯데월드타워", city="seoul"),
    "jamsil-tour": SimpleNamespace(name="잠실 관광특구", city="seoul"),
    "suyu": SimpleNamespace(name="수유", city="seoul"),
    "unjeong": SimpleNamespace(name="운정", city="paju"),
}


class Resp:
    def __init__(self, status: int, body: dict):
        self.status_code, self._body = status, body

    def json(self) -> dict:
        return self._body


def media(i: int, caption: str = "", likes: int | None = 10, comments: int = 1, kind: str = "IMAGE") -> dict:
    m = {"id": f"m{i}", "caption": caption, "comments_count": comments, "media_type": kind,
         "timestamp": "2026-11-22T01:00:00+0000", "permalink": f"https://instagram.example/p/{i}", "username": f"user{i}"}
    if likes is not None:
        m["like_count"] = likes
    return m


class FakeGraph:
    """경로로 응답을 고른다. recent_media 는 쪽마다 next 를 줄 수 있다."""

    def __init__(self, *, recent_ids=(), ids=None, recent_pages=1, error_on=None):
        self.calls: list[tuple[str, dict]] = []
        self.recent_ids, self.ids = list(recent_ids), ids or {}
        self.recent_pages, self.error_on = recent_pages, error_on or {}

    def get(self, url: str, params: dict | None = None, timeout: int | None = None) -> Resp:
        params = dict(params or {})
        path = url.split("graph.facebook.com/", 1)[1].split("/", 1)[1]
        self.calls.append((path, params))
        if path in self.error_on:
            code = self.error_on[path]
            return Resp(400, {"error": {"code": code, "message": f"synthetic failure for {params.get('access_token')}"}})
        if path.endswith("recently_searched_hashtags"):
            return Resp(200, {"data": [{"id": i} for i in self.recent_ids]})
        if path == "ig_hashtag_search":
            hid = self.ids.get(params["q"])
            return Resp(200, {"data": [{"id": hid}] if hid else []})
        if path.endswith("/top_media"):
            return Resp(200, {"data": [media(i, "#가로수길 #카페투어 #데이트", likes=None if i == 0 else 100 + i, comments=i)
                                       for i in range(6)]})
        if path.endswith("/recent_media"):
            page = 1 if "after" not in params else int(params["after"])
            body = {"data": [media(100 * page + i, "#카페투어 #개인계정아주긴태그이름입니다스물한자" if i < 6 else "", kind="VIDEO" if i % 2 else "IMAGE")
                             for i in range(50)]}
            if page < self.recent_pages:
                body["paging"] = {"cursors": {"after": str(page + 1)}, "next": f"https://graph.facebook.com/next?access_token={TOKEN}"}
            return Resp(200, body)
        if path.startswith("17"):                     # GET /{ig-user}
            return Resp(200, {"id": "17000", "username": "placeos_official"})
        raise AssertionError(f"부를 일이 없는 경로: {path}")


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", TOKEN)
    monkeypatch.setenv("IG_USER_ID", "17000")


# ── 대응표 ────────────────────────────────────────────────────────────

def test_hashtag_rule_and_overrides():
    assert cfg.derive("한남동·용리단길") == "한남동"
    assert cfg.derive("을지로(힙지로)") == "을지로"
    assert cfg.derive("구로디지털단지") == "구로디지털단지"
    assert cfg.hashtag_for("garosugil", "신사동 가로수길") == "가로수길"
    assert cfg.hashtag_for("suyu", "수유") == "수유역"          # 다른 뜻(모유 수유)을 피한다


def test_targets_cover_every_seoul_hub_and_only_valid_tags():
    t = cfg.targets(ACTIVE_HUBS)
    seoul = {s for s, h in ACTIVE_HUBS.items() if h.city == "seoul"}
    assert set(t) == seoul                                      # 사이트가 보이는 도시(서울)만, 빠짐없이
    for slug, tag in t.items():
        assert tag and cfg._NOT_TAG.search(tag) is None, (slug, tag)   # 인스타 해시태그에 쓸 수 있는 글자만
    assert t["jamsil-tour"] == t["jamsil"]                      # 같은 태그를 나눠 쓰는 거점이 있다 — 한 번만 검색


# ── 집계 ─────────────────────────────────────────────────────────────

def test_caption_tags_keep_only_hashtags():
    assert ig.caption_tags("오늘 #가로수길 #카페투어! #Cafe_Life 친구랑") == {"가로수길", "카페투어", "cafe_life"}
    assert ig.caption_tags(None) == set()


def test_summary_has_no_account_caption_link_or_post_id():
    top = [media(i, "#가로수길 #카페투어", likes=None if i == 0 else 50 + i, comments=i) for i in range(6)]
    recent = [media(10 + i, "#카페투어 #홍길동개인계정", kind="VIDEO") for i in range(4)]
    s = ig.summarize("가로수길", top, recent, False, NOW.isoformat())
    text = json.dumps(s, ensure_ascii=False)
    for leak in ("caption", "permalink", "username", "instagram.example", "user1", '"m1"'):
        assert leak not in text, leak
    assert s["top_likes_hidden"] == 1 and s["top_likes_median"] == 53      # 좋아요를 숨긴 게시물은 빼고 센다
    assert s["co_tags"] == [{"tag": "카페투어", "n": 10}]                 # 검색한 태그는 빼고 · 4건뿐인 태그(홍길동개인계정)는 안 싣는다
    assert s["media_mix"] == {"VIDEO": 1.0}


# ── 수집 ─────────────────────────────────────────────────────────────

def test_no_keys_means_no_calls(monkeypatch):
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("IG_USER_ID", raising=False)
    g = FakeGraph()
    state = ig.collect(HUBS, http=g, now=NOW, state={"hubs": {}, "tag_ids": {}})
    assert g.calls == [] and state["connected"] is False
    assert ig.check(http=g)["connected"] is False


def test_collect_respects_weekly_budget_and_shares_tags(creds, monkeypatch, capsys):
    monkeypatch.setattr(ig, "WEEKLY_UNIQUE", 3)
    g = FakeGraph(recent_ids=["h-old"], ids={"가로수길": "h1", "잠실": "h2", "수유역": "h3"}, recent_pages=2)
    state = ig.collect(HUBS, http=g, now=NOW, state={"hubs": {}, "tag_ids": {}})
    searched = [p["q"] for path, p in g.calls if path == "ig_hashtag_search"]
    assert len(searched) == 2                       # 한도 3 − 지난 7일 1 = 새 태그 2개만
    assert "unjeong" not in state["hubs"]           # 서울 밖은 대상이 아니다
    got = {s: h for s, h in state["hubs"].items() if h["status"] == "collected"}
    if "잠실" in searched:                           # 잠실을 받았다면 두 거점에 같은 값
        assert got["jamsil"] == got["jamsil-tour"]
    assert all(h["recent_24h"] == 100 and h["recent_capped"] is False for h in got.values())   # 2쪽에서 끝남
    out = capsys.readouterr().out + json.dumps(state, ensure_ascii=False)
    assert TOKEN not in out                          # 토큰은 화면·Bronze 어디에도 없다


def test_recent_media_cap_is_reported(creds, monkeypatch):
    monkeypatch.setattr(ig, "WEEKLY_UNIQUE", 1)
    g = FakeGraph(ids={"가로수길": "h1"}, recent_pages=9)
    state = ig.collect({"garosugil": HUBS["garosugil"]}, http=g, now=NOW, state={"hubs": {}, "tag_ids": {}})
    h = state["hubs"]["garosugil"]
    assert h["recent_24h"] == ig.RECENT_PAGES * ig.PAGE_LIMIT and h["recent_capped"] is True


def test_token_expiry_stops_and_keeps_earlier_results(creds, monkeypatch, capsys):
    g = FakeGraph(ids={"가로수길": "h1", "잠실": "h2", "수유역": "h3"}, error_on={"h2/top_media": 190})
    prior = {"hubs": {}, "tag_ids": {}}
    state = ig.collect(HUBS, http=g, now=NOW, state=prior)
    assert "190" in state["last_error"] and TOKEN not in state["last_error"]
    assert TOKEN not in capsys.readouterr().out
    assert "suyu" not in state["hubs"]                       # 멈춘 뒤로는 부르지 않는다


def test_refresh_error_keeps_previous_values(creds, monkeypatch):
    prev = {"hashtag": "가로수길", "status": "collected", "collected_at": "2026-11-01T00:00:00+00:00", "recent_24h": 7}
    g = FakeGraph(recent_ids=["h1"], ids={"가로수길": "h1"}, error_on={"h1/top_media": 100})
    state = ig.collect({"garosugil": HUBS["garosugil"]}, http=g, now=NOW,
                       state={"hubs": {"garosugil": dict(prev)}, "tag_ids": {"가로수길": "h1"}})
    h = state["hubs"]["garosugil"]
    assert h["recent_24h"] == 7 and h["collected_at"] == prev["collected_at"] and h["refresh_error"] == 100


def test_plan_reuses_this_weeks_tags_only_after_20_hours():
    targets = {"a": "가", "b": "나"}
    fresh = {"hubs": {"a": {"hashtag": "가", "collected_at": (NOW - dt.timedelta(hours=2)).isoformat()}}}
    assert ig.plan(targets, fresh, {"가"}, 0, NOW) == []                 # 2시간 전에 받은 태그 · 한도 0 → 할 일 없음
    old = {"hubs": {"a": {"hashtag": "가", "collected_at": (NOW - dt.timedelta(hours=30)).isoformat()}}}
    assert ig.plan(targets, old, {"가"}, 1, NOW) == ["나", "가"]          # 안 받은 태그가 먼저 · 이번 주 태그는 한도 없이


def test_check_reports_budget_without_spending_it(creds):
    g = FakeGraph(recent_ids=["x", "y"])
    got = ig.check(http=g)
    assert got == {"connected": True, "account": "placeos_official", "used_7d": 2, "budget_left": 28, "version": ig.graph_version()}
    assert not any(path == "ig_hashtag_search" or path.endswith("_media") for path, _ in g.calls)


# ── Gold ─────────────────────────────────────────────────────────────

def test_gold_before_connection_lists_hashtags_as_pending():
    g = gold.build(None, HUBS, "2026-11-22T00:00:00+00:00")
    assert g["connected"] is False and g["collected_n"] == 0 and g["target_n"] == 4
    assert g["hubs"]["garosugil"] == {"hashtag": "가로수길", "status": "pending", "shared_with": []}
    assert g["hubs"]["jamsil"]["shared_with"] == ["jamsil-tour"]
    assert "unjeong" not in g["hubs"]


def test_gold_drops_values_collected_for_an_old_hashtag():
    state = {"connected": True, "version": "v27.0", "hubs": {
        "garosugil": {"hashtag": "가로수길", "status": "collected", "collected_at": "2026-11-22T00:00:00+00:00", "recent_24h": 12},
        "suyu": {"hashtag": "수유", "status": "collected", "collected_at": "2026-11-22T00:00:00+00:00", "recent_24h": 999}}}
    g = gold.build(state, HUBS, "2026-11-22T00:00:00+00:00")
    assert g["hubs"]["garosugil"]["status"] == "collected" and g["hubs"]["garosugil"]["recent_24h"] == 12
    assert g["hubs"]["suyu"] == {"hashtag": "수유역", "status": "pending", "shared_with": []}   # 태그가 바뀌었다 — 옛 값 버림
    assert g["collected_n"] == 1 and g["connected"] is True


def test_unexpected_response_shape_marks_only_that_tag_and_keeps_going(creds, capsys):
    """문서에 없는 응답 모양(목록 등)은 그 태그만 오류로 두고 다음 태그로 간다 — 앞서 모은 결과·한도를 잃지 않는다(11-22 리뷰 반영)."""
    class Weird(FakeGraph):
        def get(self, url, params=None, timeout=None):
            if url.endswith("h2/top_media"):
                self.calls.append(("h2/top_media", dict(params or {})))
                return Resp(200, ["문서에 없는 모양"])
            return super().get(url, params, timeout)

    g = Weird(ids={"가로수길": "h1", "잠실": "h2", "수유역": "h3"})
    state = ig.collect(HUBS, http=g, now=NOW, state={"hubs": {}, "tag_ids": {}})
    assert state["hubs"]["jamsil"]["status"] == "error" and state["hubs"]["jamsil-tour"]["status"] == "error"
    assert state["hubs"]["garosugil"]["status"] == "collected" and state["hubs"]["suyu"]["status"] == "collected"
    assert state["tag_ids"] == {"가로수길": "h1", "잠실": "h2", "수유역": "h3"}       # 쓴 태그 id 는 남는다(다음 실행이 한도를 다시 세지 않게)
    assert TOKEN not in capsys.readouterr().out


def test_main_saves_progress_even_when_collection_is_interrupted(creds, monkeypatch):
    saved = []
    monkeypatch.setattr(ig, "_load_env", lambda: None)
    monkeypatch.setattr(ig, "load_state", lambda: {"hubs": {}, "tag_ids": {}})
    monkeypatch.setattr(ig, "save_json", lambda obj, *a: saved.append(json.loads(json.dumps(obj, ensure_ascii=False))))

    def interrupted(state=None, **kw):
        state["connected"] = True
        state["hubs"]["garosugil"] = {"hashtag": "가로수길", "status": "collected", "collected_at": NOW.isoformat()}
        raise KeyboardInterrupt

    monkeypatch.setattr(ig, "collect", interrupted)
    monkeypatch.setattr("sys.argv", ["instagram_hashtags"])
    with pytest.raises(KeyboardInterrupt):
        ig.main()
    assert saved and saved[0]["hubs"]["garosugil"]["status"] == "collected"
