"""[Platform] 인스타그램 해시태그 수집기 — 공식 Instagram Graph API(해시태그 검색)만 쓴다 (2026-11-22).

왜: 사용자 결정(11-22) 「인스타그램 데이터도 수집할 것」. Platform 의 「밖에서 뭐라고 불리나」에는 네이버(블로그·카페글·뉴스·검색
트렌드)만 있었다. 근거·한계: docs/finding-instagram-official-api-2026-11-22.md

무엇을 하나 — 서울 서빙 거점마다 대표 해시태그 하나(data/config/instagram_hashtags.py):
  ① `ig_hashtag_search` 로 해시태그 id → ② `top_media`(인기 게시물 1쪽) · `recent_media`(최근 24시간 · 최대 4쪽=200건)
  → **집계만** Bronze 에 남긴다: 최근 24시간 게시물 수(상한까지 셈) · 인기 게시물 좋아요·댓글 중앙값 · 형식 비율 ·
  함께 쓰인 해시태그(서로 다른 게시물 5건 이상 · 20자 이하).
⛔ 계정·본문·링크·미디어 주소를 저장하지 않는다 — 계정 이름은 공식 응답에도 없고(요청 불가), 본문에서는 해시태그만 뽑고 버린다.
   게시물 id 는 한 번 실행 안에서 인기·최근 목록의 중복을 지우는 데만 쓰고 남기지 않는다.
⛔ 비공식 수집(스크래핑·로그인 크롤링·수집 대행)은 쓰지 않는다 — 인스타그램 이용약관이 자동 수집을 금지한다.
⛔ 인스타 집계는 **유료 상품(리포트·광고)에 싣지 않는다** — Meta 플랫폼 약관이 플랫폼 데이터(집계·가공 포함)의 판매를 금지한다.

한도: 한 프로페셔널 계정이 이어지는 7일 동안 검색할 수 있는 **고유 해시태그는 30개**(다시 검색해도 다시 세지 않는다).
  `recently_searched_hashtags`(한도를 안 쓴다)로 지난 7일 사용량을 보고, 가장 오래전에 모은 거점부터 남은 한도만큼 고른다.
  서울 81거점은 한 바퀴에 약 3주다. 이미 이번 7일 안에 검색한 태그는 한도 없이 다시 받는다(20시간이 지났으면).

키(data/.env 또는 PLACEOS_ENV_FILE 이 가리키는 파일): INSTAGRAM_ACCESS_TOKEN(페이지에 연결된 사용자의 장기 토큰) ·
  IG_USER_ID(인스타 프로페셔널 계정 id) · INSTAGRAM_GRAPH_VERSION(선택 · 기본 v27.0).
  키가 없으면 아무것도 부르지 않고 「연결 전」만 남긴다. 토큰 값은 어디에도 찍지 않는다(오류 문구에서도 지운다).

실행:
  python -m data.collectors.instagram_hashtags --check     # 키·토큰·남은 한도 확인만(해시태그 한도를 쓰지 않는다)
  python -m data.collectors.instagram_hashtags             # 이번 7일 한도만큼 수집 → data/bronze/platform13/{날짜}/instagram_hashtags.json
  python -m data.pipelines.build_instagram_gold            # Bronze → data/gold/platform_instagram.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import latest_bronze, save_json
from data.config import instagram_hashtags as ig_config

SLUG13 = "platform13"                 # Bronze 거점 묶음 폴더(naver_datalab 과 같다)
BRONZE_NAME = "instagram_hashtags.json"
DEFAULT_VERSION = "v27.0"             # 2026-11-04 최신(그래프 API 변경 기록) — 바뀌면 INSTAGRAM_GRAPH_VERSION 으로
WEEKLY_UNIQUE = 30
PAGE_LIMIT = 50                       # top_media · recent_media 한 쪽 최대
RECENT_PAGES = 4                      # 최근 24시간 게시물은 200건까지 센다(넘으면 「200건 이상」)
TOP_PAGES = 1
MIN_COTAG = 5                         # 함께 쓰인 태그 — 서로 다른 게시물 5건 이상만(한 사람의 태그가 드러나지 않게)
MAX_COTAG_LEN = 20                    # 긴 태그는 개인 계정·문장형이 많다
TOP_COTAGS = 10
REFRESH_HOURS = 20                    # 이번 7일 안에 이미 검색한 태그는 이만큼 지났으면 한도 없이 다시 받는다
# 계정·링크·미디어 주소는 **요청하지 않는다** — 받지 않으면 남을 수도 없다
MEDIA_FIELDS = "id,caption,comments_count,like_count,media_type,timestamp"
STOP_CODES = {4, 17, 32, 190, 613}    # 호출 한도 · 토큰 만료 — 더 부르지 않고 지금까지를 저장한다

_TAG = re.compile(r"#([0-9A-Za-z_가-힣]+)")


class GraphError(Exception):
    """Graph API 오류 — 코드·짧은 문구만 담는다(토큰이 섞일 수 있는 URL 은 담지 않는다)."""

    def __init__(self, status: int, code: int | None, message: str):
        super().__init__(f"HTTP {status} · code {code} · {message}")
        self.status, self.code, self.message = status, code, message


def graph_version() -> str:
    return os.environ.get("INSTAGRAM_GRAPH_VERSION") or DEFAULT_VERSION


def credentials() -> tuple[str, str] | None:
    token, user = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip(), os.environ.get("IG_USER_ID", "").strip()
    return (token, user) if token and user else None


def redact(text: str, token: str | None) -> str:
    return text.replace(token, "***") if token else text


def _get(path: str, params: dict[str, Any], token: str, http: Any = None) -> dict:
    http = http or requests
    url = f"https://graph.facebook.com/{graph_version()}/{path.lstrip('/')}"
    try:
        resp = http.get(url, params={**params, "access_token": token}, timeout=20)
    except Exception as exc:  # 연결 오류 문구에는 주소(토큰 포함)가 섞인다 — 종류만 남긴다
        raise GraphError(0, None, f"연결 실패({type(exc).__name__})") from None
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):                # 문서에 없는 모양 — 오류로 다룬다(뒤에서 .get 으로 죽지 않게)
        raise GraphError(resp.status_code, None, "응답 형식이 예상과 달라요")
    if resp.status_code != 200 or "error" in body:
        err = body.get("error") or {}
        raise GraphError(resp.status_code, err.get("code"), redact(str(err.get("message") or "")[:160], token))
    return body


def caption_tags(caption: str | None) -> set[str]:
    """본문 → 해시태그 집합(소문자 · # 없이). 본문 자체는 돌려주지 않는다."""
    return {t.lower() for t in _TAG.findall(caption or "")}


def _median(values: list[int]) -> int | None:
    return int(statistics.median(values)) if values else None


def summarize(tag: str, top: list[dict], recent: list[dict], recent_capped: bool, collected_at: str) -> dict:
    """원자료 → 화면에 실을 집계. 여기서 나간 dict 에는 본문·계정·링크·게시물 id 가 없다(테스트가 잠근다)."""
    posts: dict[str, dict] = {}
    for i, m in enumerate(top + recent):
        posts.setdefault(str(m.get("id") or f"_{i}"), m)
    counts: Counter = Counter()
    for m in posts.values():
        counts.update(caption_tags(m.get("caption")) - {tag.lower()})
    co_tags = [{"tag": t, "n": n} for t, n in counts.most_common()
               if n >= MIN_COTAG and len(t) <= MAX_COTAG_LEN][:TOP_COTAGS]
    likes = [m["like_count"] for m in top if isinstance(m.get("like_count"), int)]
    comments = [m["comments_count"] for m in top if isinstance(m.get("comments_count"), int)]
    mix = Counter(str(m.get("media_type") or "UNKNOWN") for m in recent)
    return {
        "hashtag": tag, "status": "collected", "collected_at": collected_at,
        "recent_24h": len(recent), "recent_capped": recent_capped,
        "top_n": len(top), "top_likes_median": _median(likes), "top_likes_hidden": len(top) - len(likes),
        "top_comments_median": _median(comments),
        "media_mix": {k: round(v / len(recent), 3) for k, v in sorted(mix.items())} if recent else {},
        "co_tags": co_tags, "sample_posts": len(posts),
    }


def search_id(tag: str, ig_user: str, token: str, http: Any = None) -> str | None:
    data = _get("ig_hashtag_search", {"user_id": ig_user, "q": tag}, token, http).get("data") or []
    return str(data[0]["id"]) if data and data[0].get("id") else None


def fetch_edge(hid: str, edge: str, ig_user: str, token: str, pages: int, http: Any = None) -> tuple[list[dict], bool]:
    """한 해시태그의 top_media · recent_media — (게시물들, 상한에서 끊겼나)."""
    out: list[dict] = []
    after: str | None = None
    for _ in range(pages):
        params: dict[str, Any] = {"user_id": ig_user, "fields": MEDIA_FIELDS, "limit": PAGE_LIMIT}
        if after:
            params["after"] = after
        body = _get(f"{hid}/{edge}", params, token, http)
        out.extend(body.get("data") or [])
        paging = body.get("paging") or {}
        after = (paging.get("cursors") or {}).get("after")
        if not paging.get("next") or not after:
            return out, False
    return out, True


def recently_searched(ig_user: str, token: str, http: Any = None) -> list[str]:
    """지난 7일에 이 계정이 검색한 해시태그 id(한도를 쓰지 않는 호출)."""
    data = _get(f"{ig_user}/recently_searched_hashtags", {"limit": WEEKLY_UNIQUE}, token, http).get("data") or []
    return [str(d.get("id")) for d in data if d.get("id")]


def plan(targets: dict[str, str], state: dict, recent_tags: set[str], budget_left: int, now: dt.datetime) -> list[str]:
    """이번에 받을 고유 태그 — 가장 오래전에 모은 것부터. 지난 7일에 검색한 태그는 한도를 안 쓴다(20시간 지났을 때만 다시)."""
    tag_hubs: dict[str, list[str]] = {}
    for slug, tag in targets.items():
        tag_hubs.setdefault(tag, []).append(slug)
    hubs_state = state.get("hubs") or {}
    order = list(dict.fromkeys(targets.values()))

    def last(tag: str) -> str:
        stamps = [(hubs_state.get(s) or {}).get("collected_at") or "" for s in tag_hubs[tag]
                  if (hubs_state.get(s) or {}).get("hashtag") == tag]
        return min(stamps) if len(stamps) == len(tag_hubs[tag]) else ""     # 한 곳이라도 비었으면 아직 안 모은 태그

    chosen: list[str] = []
    for tag in sorted(order, key=lambda t: (last(t), order.index(t))):
        if tag in recent_tags:
            stamp = last(tag)
            if not stamp or now - dt.datetime.fromisoformat(stamp) >= dt.timedelta(hours=REFRESH_HOURS):
                chosen.append(tag)
        elif budget_left > 0:
            chosen.append(tag)
            budget_left -= 1
    return chosen


def load_state() -> dict:
    path = latest_bronze(SLUG13, BRONZE_NAME)
    if path is None:
        return {"hubs": {}, "tag_ids": {}}
    import json

    state = json.loads(Path(path).read_text(encoding="utf-8"))
    state.setdefault("hubs", {})
    state.setdefault("tag_ids", {})
    return state


def _load_env() -> None:
    from data.run_collection import _ENV_PATH, _load_env as load

    load(Path(os.environ["PLACEOS_ENV_FILE"]) if os.environ.get("PLACEOS_ENV_FILE") else _ENV_PATH)


def check(http: Any = None) -> dict:
    """키·토큰·남은 한도 — 해시태그 한도를 쓰지 않는다. 토큰 값은 찍지 않는다."""
    creds = credentials()
    if creds is None:
        return {"connected": False, "reason": "INSTAGRAM_ACCESS_TOKEN · IG_USER_ID 없음(공식 API 연결 전)"}
    token, ig_user = creds
    try:
        me = _get(ig_user, {"fields": "id,username"}, token, http)
        used = recently_searched(ig_user, token, http)
    except GraphError as exc:
        return {"connected": False, "reason": f"토큰·계정 확인 실패 — {exc}"}
    return {"connected": True, "account": me.get("username"), "used_7d": len(used),
            "budget_left": max(0, WEEKLY_UNIQUE - len(used)), "version": graph_version()}


def collect(hubs: dict | None = None, http: Any = None, now: dt.datetime | None = None,
            state: dict | None = None) -> dict:
    """이번 7일 한도만큼 모아 Bronze 상태(dict)를 돌려준다. 키가 없으면 아무것도 부르지 않는다."""
    if hubs is None:
        from data.config.page_hubs import ACTIVE_HUBS as hubs  # noqa: N811
    now = now or dt.datetime.now(dt.timezone.utc)
    state = state if state is not None else load_state()
    state.update(version=graph_version(), run_at=now.isoformat())
    creds = credentials()
    if creds is None or (requests is None and http is None):
        print("[instagram] INSTAGRAM_ACCESS_TOKEN · IG_USER_ID 없음 — 부르지 않는다(공식 API 연결 전)")
        state["connected"] = False
        return state
    token, ig_user = creds
    targets = ig_config.targets(hubs)
    tag_ids: dict[str, str] = state["tag_ids"]
    try:
        recent_ids = set(recently_searched(ig_user, token, http))
    except GraphError as exc:
        print(f"[instagram] 계정 확인 실패 — {exc}")
        state["connected"] = False
        state["last_error"] = str(exc)
        return state
    state["connected"] = True
    recent_tags = {t for t, i in tag_ids.items() if i in recent_ids}
    budget_left = max(0, WEEKLY_UNIQUE - len(recent_ids))
    todo = plan(targets, state, recent_tags, budget_left, now)
    print(f"[instagram] 지난 7일 {len(recent_ids)}/{WEEKLY_UNIQUE} 사용 · 이번에 {len(todo)}태그")
    stamp = now.isoformat()
    for tag in todo:
        slugs = [s for s, t in targets.items() if t == tag]
        try:
            hid = tag_ids.get(tag) or search_id(tag, ig_user, token, http)
            if hid is None:
                rec: dict[str, Any] = {"hashtag": tag, "status": "no_hashtag", "collected_at": stamp}
            else:
                tag_ids[tag] = hid
                top, _ = fetch_edge(hid, "top_media", ig_user, token, TOP_PAGES, http)
                recent, capped = fetch_edge(hid, "recent_media", ig_user, token, RECENT_PAGES, http)
                rec = summarize(tag, top, recent, capped, stamp)
        except GraphError as exc:
            print(f"[instagram] #{tag} 실패 — {exc}")
            if exc.code in STOP_CODES:
                state["last_error"] = str(exc)
                break
            rec = {"hashtag": tag, "status": "error", "collected_at": stamp, "error_code": exc.code}
        except Exception as exc:  # 문서에 없는 응답 모양 등 — 이 태그만 오류로 두고 다음으로 간다(앞서 모은 것을 잃지 않게)
            print(f"[instagram] #{tag} 처리 실패 — {type(exc).__name__}")      # 문구는 남기지 않는다(토큰이 섞일 수 있다)
            rec = {"hashtag": tag, "status": "error", "collected_at": stamp, "error_code": None}
        for slug in slugs:
            prev = state["hubs"].get(slug) or {}
            if rec["status"] == "error" and prev.get("status") == "collected" and prev.get("hashtag") == tag:
                prev["refresh_error"] = rec.get("error_code")      # 다시 받기 실패 — 지난 값은 지우지 않는다(날짜가 낡음을 말한다)
                continue
            state["hubs"][slug] = dict(rec)
        print(f"[instagram] #{tag} → {', '.join(slugs)} · {rec['status']}")
    return state


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="키·토큰·남은 한도만 확인한다(해시태그 한도를 쓰지 않는다)")
    args = ap.parse_args()
    _load_env()
    if args.check:
        print(check())
        return
    # 상태를 먼저 만들어 넘긴다 — collect 가 중간에 멈춰도(Ctrl-C · 예상 못 한 오류) 그때까지 모은 태그와 태그 id 를 저장한다.
    # 저장하지 않으면 이미 쓴 7일 한도를 다음 실행이 「새 태그」로 다시 센다(2026-11-22 리뷰 반영).
    state = load_state()
    try:
        collect(state=state)
    finally:
        if state.get("connected"):
            save_json(state, SLUG13, BRONZE_NAME)


if __name__ == "__main__":
    main()
