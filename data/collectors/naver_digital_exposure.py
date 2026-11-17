"""[Platform 입증 패널] 디지털 노출 시계열 수집기 — 블로그 게시량 월 스냅샷 + 데이터랩 장기 시계열.

연구 질문: 서울 상권에서 「대로변·입지 프리미엄」보다 「디지털 노출(검색·게시)」이 생존·임대료·입지 선택을
더 설명하는가(docs/finding-digital-premium-inputs-2026-11-17.md). 그 패널의 독립변수를 쌓는다.

  --blog           거점 × (맛집·카페) 질의별 블로그 **게시량**. 본문·스니펫은 저장하지 않는다.
                   `total`(질의 일치 문서 수) + 최신 1,000건의 월별 게시 건수 + 그 창이 어디까지 닿는지.
                   `rate_per_day` = 최신 1,000건 ÷ 그 창의 일수 — 인기 거점은 1,000건이 며칠치뿐이라
                   월별 건수가 아니라 이 율이 비교 가능한 노출 강도다.
                   과거로 못 돌아가는 유일한 변수라 **매주 1회** 쌓는다(API 가 최신 1,000건까지만 준다).
  --datalab-long   데이터랩 월별 검색 관심도 2016-01~지난달. **기준어(맛집) 시계열을 버리지 않는다.**
                   (기존 fetch_hub_trends 는 기준어를 버려 배치 간 눈금을 복원할 수 없다 — 11-17 실측:
                    거점이 기준어보다 높이 솟는 배치는 그 배치 전체의 눈금이 0.63·0.11 배로 바뀐다.)

    python -m data.collectors.naver_digital_exposure --blog
    python -m data.collectors.naver_digital_exposure --blog --hubs garosugil,hongdae
    python -m data.collectors.naver_digital_exposure --datalab-long
    python -m data.collectors.naver_digital_exposure --panel-rebuild   # Bronze 스냅샷 → data/panel CSV 재구성

⚠ 감성 점수는 만들지 않는다 — 블로그 감성은 분산이 없다(docs/feature-platform.md §0-K).
⚠ 공간 단위는 거점이다. 점포·필지로 내려가지 않는다(블로그에는 좌표가 없다).
⚠ Bronze 는 .gitignore 대상(data/bronze/*)이라 이 파일은 **이 기계에만** 남는다.
"""
from __future__ import annotations

import datetime as dt
import os
import time
from collections import Counter

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors import naver_api
from data.collectors.common import load_env, save_json

SLUG = "platform13"
_DISPLAY = 100
_MAX_START = 1000          # 네이버 검색 start 상한
_SLEEP = 0.12
_QUERY_SUFFIX = ("맛집", "카페")  # naver_blog.collect_platform13_blog 와 같은 접미어 (접두어 「서울」 은 뺐다 — 위 독스트링)
_LONG_START = "2016-01-01"  # 데이터랩 월 단위 하한


def month_histogram(postdates: list[str]) -> dict[str, int]:
    """네이버 postdate(YYYYMMDD) → {YYYY-MM: 건수}. 형식이 아닌 값은 세지 않고 건너뛴다."""
    c: Counter[str] = Counter()
    for d in postdates:
        d = (d or "").strip()
        if len(d) == 8 and d.isdigit():
            c[f"{d[:4]}-{d[4:6]}"] += 1
    return dict(sorted(c.items()))


def complete_from(oldest_postdate: str | None, capped: bool) -> str | None:
    """월별 건수가 **온전한** 첫 달. 창이 1,000건에서 잘렸다면 가장 오래된 글의 달은 일부만 담겼다.

    잘리지 않았다면(결과 끝까지 읽음) 가장 오래된 글의 달부터 온전하고, 글이 0건이면 None.
    """
    if not oldest_postdate or len(oldest_postdate) != 8:
        return None
    y, m = int(oldest_postdate[:4]), int(oldest_postdate[4:6])
    if capped:
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}"


def window_stats(oldest_postdate: str | None, n: int, today: dt.date) -> tuple[int | None, float | None]:
    """최신 n건이 덮는 기간(일)과 일평균 게시율. 인기 거점은 1,000건이 며칠치뿐이라(가로수길 11-17 실측 8일)
    월별 건수 대신 **창 길이로 나눈 율**이 비교 가능한 노출 강도다. 글이 없거나 날짜가 깨졌으면 (None, None)."""
    if not oldest_postdate or len(oldest_postdate) != 8 or n <= 0:
        return None, None
    try:
        first = dt.date(int(oldest_postdate[:4]), int(oldest_postdate[4:6]), int(oldest_postdate[6:]))
    except ValueError:
        return None, None
    days = max(1, (today - first).days + 1)
    return days, round(n / days, 4)


def token_hit(item: dict, token: str) -> bool:
    """제목+스니펫에 거점 토큰(공백으로 쪼갠 낱말 전부)이 들어 있나. 본문은 API 가 주지 않으므로 하한이다."""
    import re
    text = re.sub(r"<[^>]+>", "", (item.get("title") or "") + " " + (item.get("description") or ""))
    return all(w in text for w in token.split())


def _query_one(blog_url: str, headers: dict[str, str], kw: str, token: str) -> dict:
    """질의 하나 — 최신순 최대 1,000건의 게시일과 total. 실패는 error 필드로 남긴다(조용히 0 으로 만들지 않는다).

    `precision` = 받은 글 중 거점 토큰이 제목·스니펫에 든 비율. 낮으면 질의가 거점이 아니라 「맛집」 전반을 잰 것이다
    (11-17 실측: `서울 숙대입구 맛집` total 594만 · 최신 100건 중 2건만 포함 → 정확일치 `"숙대입구" 맛집` 은 18.7만 · 92건)."""
    dates: list[str] = []
    hits = 0
    total = None
    err = None
    for page in range(_MAX_START // _DISPLAY):
        resp_json = None
        for attempt in range(3):
            try:
                resp = requests.get(blog_url, headers=headers, timeout=15,
                                    params={"query": kw, "display": _DISPLAY,
                                            "start": page * _DISPLAY + 1, "sort": "date"})
                if resp.status_code == 429:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                resp_json = resp.json()
                break
            except Exception as exc:  # noqa: BLE001 — 사유만 남기고 다음 질의로
                err = type(exc).__name__
                time.sleep(0.5)
        if resp_json is None:
            err = err or "no_response"
            break
        if total is None:
            total = resp_json.get("total")
        items = resp_json.get("items", [])
        dates += [it.get("postdate", "") for it in items]
        hits += sum(1 for it in items if token_hit(it, token))
        time.sleep(_SLEEP)
        if len(items) < _DISPLAY:
            break
    capped = len(dates) >= _MAX_START
    oldest = min((d for d in dates if d), default=None)
    days, rate = window_stats(oldest, len(dates), dt.date.today())
    out = {"total": total, "n": len(dates), "capped": capped, "oldest": oldest,
           "window_days": days, "rate_per_day": rate,
           "precision": round(hits / len(dates), 3) if dates else None, "query": kw,
           "complete_from": complete_from(oldest, capped), "months": month_histogram(dates)}
    if err:
        out["error"] = err
    return out


def collect_blog_exposure(only: set[str] | None = None) -> dict:
    from data.config.page_hubs import ACTIVE_HUBS
    from data.config.platform_places import DISTRICT_PLACES
    from data.collectors import naver_datalab as nd

    req = naver_api.search_request("blog")
    if req is None or requests is None:
        print("[exposure] 네이버 검색 키 미설정 — 수집하지 않는다")
        return {}
    blog_url, headers = req[0], req[1]

    hubs: dict[str, dict] = {}
    targets = [(s, DISTRICT_PLACES[s][3]) for s, h in sorted(ACTIVE_HUBS.items())
               if h.city == "seoul" and s in DISTRICT_PLACES and (not only or s in only)]
    for i, (slug, name) in enumerate(targets, 1):
        # 「서울 {거점명} 맛집」 은 거점 토큰이 약해져 「서울 맛집」 전반으로 번진다 → 정확일치 + 데이터랩과 같은 거점 키워드
        token = nd._hub_keywords(slug, name)[0]
        hubs[slug] = {"name": name, "token": token, "queries": {
            suf: _query_one(blog_url, headers, f'"{token}" {suf}', token) for suf in _QUERY_SUFFIX}}
        if i % 10 == 0 or i == len(targets):
            print(f"[exposure:blog] {i}/{len(targets)}거점")
    out = {"collected_at": dt.date.today().isoformat(), "unit": "hub", "queries": list(_QUERY_SUFFIX),
           "note": "months=최신 1,000건의 월별 게시 건수. complete_from 이전 달은 창 밖이라 과소 집계다.",
           "hubs": hubs}
    if only:
        from data.collectors.common import load_latest
        prev = (load_latest(SLUG, "naver_blog_exposure.json") or {}).get("hubs") or {}
        out["hubs"] = {**{k: v for k, v in prev.items() if k not in only}, **hubs}
    save_json(out, SLUG, "naver_blog_exposure.json")
    # 압축 패널(git 추적) — 이번에 새로 받은 거점만 같은 (날짜·거점·질의) 행을 덮어쓴다
    from data.collectors import digital_exposure_panel as panel

    n = panel.upsert_panel(panel.snapshot_rows({"collected_at": out["collected_at"], "hubs": hubs}))
    print(f"[exposure:blog] 패널 {panel.PANEL_PATH.name} — 전체 {n}행")
    return out


def collect_datalab_long(only: set[str] | None = None) -> dict:
    """데이터랩 월별 시계열(2016-01~지난달) — 배치 원본(기준어 포함)을 그대로 남긴다."""
    from data.collectors import naver_datalab as nd
    from data.config.page_hubs import ACTIVE_HUBS

    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not cid or not secret or requests is None:
        print("[exposure] NAVER_CLIENT_ID/SECRET 없음 — 수집하지 않는다")
        return {}
    end = dt.date.today().replace(day=1) - dt.timedelta(days=1)  # 끝나지 않은 달은 요청하지 않는다
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret, "Content-Type": "application/json"}
    items = sorted((s, h) for s, h in ACTIVE_HUBS.items() if h.city == "seoul" and (not only or s in only))
    batches = []
    for i in range(0, len(items), nd._HUB_BATCH):
        chunk = items[i:i + nd._HUB_BATCH]
        groups = [{"groupName": s, "keywords": nd._hub_keywords(s, h.name)} for s, h in chunk]
        groups.append({"groupName": nd._ANCHOR_NAME, "keywords": nd._ANCHOR_KEYWORDS})
        data = nd._post_with_retry(headers, {"startDate": _LONG_START, "endDate": end.isoformat(),
                                             "timeUnit": "month", "keywordGroups": groups})
        if data is None:
            print(f"[exposure:datalab] 배치 {i // nd._HUB_BATCH + 1} 실패 — 건너뛴다")
            continue
        series = {(r.get("title") or r.get("groupName")): [{"period": p["period"], "ratio": p["ratio"]}
                                                          for p in r.get("data", [])]
                  for r in data.get("results", [])}
        anchor = series.pop(nd._ANCHOR_NAME, [])
        batches.append({"hubs": [s for s, _ in chunk], "keywords": {s: g["keywords"] for (s, _), g in zip(chunk, groups)},
                        "anchor": anchor, "series": series})
        print(f"[exposure:datalab] {min(i + nd._HUB_BATCH, len(items))}/{len(items)}거점")
        time.sleep(0.3)
    out = {"collected_at": dt.date.today().isoformat(), "start": _LONG_START, "end": end.isoformat(),
           "anchor_keywords": nd._ANCHOR_KEYWORDS,
           "note": "ratio 는 배치(요청) 안 최댓값=100 의 상대치. 거점 간 비교는 ratio/anchor 로 한다. 거점 안 시간 비교는 그대로 된다.",
           "batches": batches}
    if batches:
        save_json(out, SLUG, "naver_datalab_hub_trend_long.json")
    return out


if __name__ == "__main__":
    import sys

    load_env()
    only = None
    if "--hubs" in sys.argv:
        i = sys.argv.index("--hubs")
        only = {s for s in (sys.argv[i + 1] if i + 1 < len(sys.argv) else "").split(",") if s} or None
    if "--blog" in sys.argv:
        collect_blog_exposure(only)
    if "--datalab-long" in sys.argv:
        collect_datalab_long(only)
    if "--panel-rebuild" in sys.argv:  # Bronze 의 모든 스냅샷에서 패널 CSV 를 다시 짓는다(복구·최초 적재)
        from data.collectors import digital_exposure_panel as panel
        from data.collectors.common import BRONZE

        print(f"[exposure:panel] {panel.rebuild_from_bronze(BRONZE / SLUG)}행 → {panel.PANEL_PATH}")
    if not ({"--blog", "--datalab-long", "--panel-rebuild"} & set(sys.argv)):
        print(__doc__)
