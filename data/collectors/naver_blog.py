"""[B단계·Program] 네이버 검색(블로그) + 데이터랩 트렌드 수집기 (docs §5-B).

`NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`(developers.naver.com — 검색·데이터랩 사용
설정)으로 거점 키워드의 블로그 리뷰와 월별 검색 트렌드를 수집한다.
용도: Program 의 콘텐츠 컨텍스트(리뷰 키워드·감성 원문) + 상권 관심도 시계열.

실행: python -m data.collectors.naver_blog
"""
from __future__ import annotations

import datetime
import os

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import load_env, save_json
from data.config.garosugil import BLOG_KEYWORDS, SLUG, TREND_KEYWORD_GROUPS

_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"
_DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
_DISPLAY = 100          # 요청당 최대
_PAGES = 3              # 키워드당 300건 (start 상한 1000)

# 거점 도시 → 블로그 질의 접두어(「{접두어} {거점명} 맛집」). 동명이지 차단의 1차 방어다(collect_platform13_blog 독스트링).
# `build_gold._home_terms` 가 이 표를 읽어 접두어를 그 거점의 **자기 도시**로 본다 — 둘이 어긋나면 글이 통째로 버려진다(2026-10-31).
CITY_WORD: dict[str, str] = {"seoul": "서울", "goyang": "고양", "paju": "파주", "suwon": "수원", "seongnam": "성남",
                             "bucheon": "부천", "anyang": "안양", "uijeongbu": "의정부", "gwangju": "광주", "hwaseong": "화성"}


def _headers() -> dict[str, str] | None:
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not cid or not secret:
        return None
    return {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}


def collect_blog() -> list[dict]:
    """키워드별 최신 블로그 글 수집 → link 기준 중복 제거 → Bronze 저장."""
    headers = _headers()
    if headers is None or requests is None:
        print("[naver_blog] NAVER_CLIENT_ID/SECRET 미설정(또는 requests 없음) — 건너뜀")
        return []

    seen: dict[str, dict] = {}
    for kw in BLOG_KEYWORDS:
        got = 0
        for page in range(_PAGES):
            try:
                resp = requests.get(
                    _BLOG_URL, headers=headers,
                    params={"query": kw, "display": _DISPLAY,
                            "start": page * _DISPLAY + 1, "sort": "date"},
                    timeout=15,
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
            except Exception as exc:
                print(f"  '{kw}' p{page + 1}: 실패 — {exc}")
                break
            for it in items:
                it["_query"] = kw  # 어떤 키워드로 잡혔는지 보존 (원문 필드는 무가공)
                seen[it.get("link", "")] = it
            got += len(items)
            if len(items) < _DISPLAY:
                break
        print(f"  '{kw}': {got}건")

    posts = list(seen.values())
    save_json(posts, SLUG, "naver_blog.json")
    return posts


def collect_trend() -> dict:
    """데이터랩 검색어 트렌드(최근 24개월·월 단위) → Bronze 저장."""
    headers = _headers()
    if headers is None or requests is None:
        return {}

    end = datetime.date.today()
    start = end.replace(year=end.year - 2)
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "timeUnit": "month",
        "keywordGroups": [
            {"groupName": name, "keywords": kws}
            for name, kws in TREND_KEYWORD_GROUPS.items()
        ][:5],  # API 제한: 그룹 최대 5개
    }
    try:
        resp = requests.post(
            _DATALAB_URL, headers={**headers, "Content-Type": "application/json"},
            json=body, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"[naver_blog] 데이터랩 실패 — {exc}")
        return {}

    save_json(data, SLUG, "naver_datalab_trend.json")
    return data


def collect_platform13_blog(only: set[str] | None = None) -> list[dict]:
    """[Platform·GNN/Program] 거점 블로그 리뷰 수집 — Program 상권 컨텍스트 원천.

    거점당 '{도시} {명칭} 맛집'·'{도시} {명칭} 카페' 2키워드 × 2페이지(최대 400건).
    행에 district_id 부가. Bronze: data/bronze/platform13/{날짜}/naver_blog.json

    도시 접두어는 거점의 `city` 다(서울·고양·파주, 2026-10-26). `only` 를 주면 그 거점만 받아
    **최신 파일에 병합**한다 — 전 거점을 다시 받으면 서울 거점 컨텍스트까지 오늘 글로 바뀐다.

    ⚠️ **"서울" 접두어는 동명이지(同名異地) 차단용이다 — 빼지 말 것.**
    거점명만으로 질의하면 같은 이름의 타 시도 상권 글이 섞인다. 2026-08-01 전수 실측:
    수집분 17,653건 중 1,295건(7.3%)이 타 시도였고 8개 거점이 10% 이상이었다
    (jangan 43.6% ← 수원·평택 장안동, cityhall 33.5% ← 수원·대전 시청역,
     garosugil 31.8% ← 창원 가로수길, nonhyeon 23.1% ← 인천 논현동).
    A/B 실측(100건 표본)에서 "서울" 접두어가 오염을 36%→2%, 30%→3%, 47%→1% 로 낮췄다.
    Gold 단계(build_gold._is_offsite)에도 잔여분 필터가 있지만, 필터는 표본을 깎을 뿐
    좋은 글을 더 가져오지는 못한다 — 질의를 좁히는 쪽이 본 수정이고 필터는 보루다.
    """
    from data.collectors.common import load_latest
    from data.config.page_hubs import ALL_HUBS
    from data.config.platform_places import DISTRICT_PLACES

    headers = _headers()
    if headers is None or requests is None:
        print("[naver_blog] NAVER_CLIENT_ID/SECRET 미설정(또는 requests 없음) — 건너뜀")
        return []

    seen: dict[str, dict] = {}
    for did, (_lat, _lng, _radius, name) in DISTRICT_PLACES.items():
        if only and did not in only:
            continue
        prefix = CITY_WORD.get(getattr(ALL_HUBS.get(did), "city", "seoul"), "서울")
        got = 0
        for kw in (f"{prefix} {name} 맛집", f"{prefix} {name} 카페"):
            for page in range(2):
                try:
                    resp = requests.get(
                        _BLOG_URL, headers=headers,
                        params={"query": kw, "display": _DISPLAY,
                                "start": page * _DISPLAY + 1, "sort": "date"},
                        timeout=15,
                    )
                    resp.raise_for_status()
                    items = resp.json().get("items", [])
                except Exception as exc:
                    print(f"  {did} '{kw}' p{page + 1}: 실패 — {exc}")
                    break
                for it in items:
                    it["_query"] = kw
                    it["district_id"] = did
                    seen[it.get("link", "")] = it
                got += len(items)
                if len(items) < _DISPLAY:
                    break
        print(f"  {did}: {got}건")

    posts = list(seen.values())
    if only:
        prev = load_latest("platform13", "naver_blog.json") or []
        posts = [p for p in prev if p.get("district_id") not in only] + posts
    save_json(posts, "platform13", "naver_blog.json")
    return posts


if __name__ == "__main__":
    import sys

    load_env()
    if "--platform13" in sys.argv:
        only = None
        if "--hubs" in sys.argv:
            i = sys.argv.index("--hubs")
            only = {s for s in (sys.argv[i + 1] if i + 1 < len(sys.argv) else "").split(",") if s} or None
        collect_platform13_blog(only)
    else:
        collect_blog()
        collect_trend()
