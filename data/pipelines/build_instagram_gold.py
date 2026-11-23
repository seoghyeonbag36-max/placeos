"""인스타그램 해시태그 Bronze → Platform Gold (data/gold/platform_instagram.json · 2026-11-22).

백엔드 컨테이너에는 data/gold 만 들어간다(Dockerfile) — 그래서 **해시태그 대응표도 Gold 에 싣는다**. 수집 전(공식 API 연결 전)이어도
이 파일은 서울 거점마다 대표 해시태그와 「pending」을 싣는다 — 화면이 「#가로수길 — 아직 수집 전」을 말할 수 있게(지어낸 수치는 없다).

거점 항목:
  hashtag · status(collected | pending | no_hashtag | error) · collected_at · recent_24h · recent_capped · top_n ·
  top_likes_median · top_likes_hidden · top_comments_median · media_mix · co_tags · sample_posts · shared_with
태그가 바뀐 거점은 지난 수집값을 버리고 pending 으로 돌린다(다른 태그의 값을 그 거점 값처럼 보이지 않게).

실행: python -m data.pipelines.build_instagram_gold   (Bronze 가 없으면 「연결 전」 파일을 쓴다)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from data.collectors.common import GOLD
from data.config import instagram_hashtags as ig_config

OUT = GOLD / "platform_instagram.json"
SOURCE = ("인스타그램 공식 Graph API — 해시태그 검색(인기 게시물 · 최근 24시간 게시물) · 거점마다 대표 해시태그 하나 · "
          "계정·본문·링크는 저장하지 않음")
STALE_AFTER_DAYS = 30
KEEP = ("collected_at", "recent_24h", "recent_capped", "top_n", "top_likes_median", "top_likes_hidden",
        "top_comments_median", "media_mix", "co_tags", "sample_posts", "refresh_error")


def build(state: dict | None, hubs: dict, built_at: str) -> dict:
    targets = ig_config.targets(hubs)
    by_tag: dict[str, list[str]] = {}
    for slug, tag in targets.items():
        by_tag.setdefault(tag, []).append(slug)
    collected = (state or {}).get("hubs") or {}
    out: dict[str, dict] = {}
    for slug, tag in targets.items():
        rec = collected.get(slug) or {}
        entry: dict = {"hashtag": tag, "status": "pending"}
        if rec.get("hashtag") == tag and rec.get("status") in {"collected", "no_hashtag", "error"}:
            entry["status"] = rec["status"]
            entry.update({k: rec[k] for k in KEEP if k in rec})
        entry["shared_with"] = [s for s in by_tag[tag] if s != slug]
        out[slug] = entry
    return {
        "built_at": built_at,
        "source": SOURCE,
        "connected": bool((state or {}).get("connected")),
        "api_version": (state or {}).get("version"),
        "window": "최근 24시간",
        "stale_after_days": STALE_AFTER_DAYS,
        "target_n": len(out),
        "collected_n": sum(1 for e in out.values() if e["status"] == "collected"),
        "hubs": out,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    from data.collectors.instagram_hashtags import load_state
    from data.config.page_hubs import ACTIVE_HUBS

    state = load_state()
    gold = build(state if state.get("hubs") or state.get("connected") else None, ACTIVE_HUBS,
                 dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat())
    path = Path(args.out)
    path.write_text(json.dumps(gold, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[instagram:gold] {path} · 대상 {gold['target_n']}거점 · 수집 {gold['collected_n']} · 연결 {gold['connected']}")


if __name__ == "__main__":
    main()
