"""검증된 Bronze를 Silver 정규화 후 화면용 Gold로 승격한다."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from data.collectors.common import BRONZE, GOLD, SILVER
from data.collectors.seoul_events import _coords, _dist_m, _end_date, RADIUS_M
from data.config.page_hubs import ACTIVE_HUBS
from data.pipelines.build_events import _event


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify(root: Path) -> dict:
    if not root.resolve().is_relative_to(BRONZE.resolve()):
        raise ValueError("Bronze 실행 경로만 허용")
    manifest = read(root / "manifest.json")
    for entry in manifest["entries"]:
        if "path" not in entry:
            continue
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("원본 경로 이탈")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("원본 해시 불일치")
    return manifest


def run(digital: Path, public: Path, followup: Path, stores: Path, today: date) -> dict:
    """행정동 소비를 상권 매출로 합산하지 않는다. 검색 자료는 표본이다."""
    manifest, pub, follow = verify(digital), verify(public), verify(followup)
    if len(manifest["entries"]) != 426 or any(e["status"] != "success" for e in manifest["entries"]):
        raise ValueError("검색 81거점 수집이 미완료")
    if follow.get("facts", {}).get("seoul_consumption", {}).get("status") != "complete":
        raise ValueError("소비 전량 수집 확인 없음")
    consumption: dict[str, dict] = {}
    for e in follow["entries"]:
        if not e["source"].startswith("seoul_consumption/"):
            continue
        if e["status"] != "success":
            raise ValueError("소비 수집 미완료")
        for row in read(followup / e["path"])["VwsmAdstrdNcmCnsmpW"]["row"]:
            key = str(row["ADSTRD_CD"])
            if key not in consumption or str(row["STDR_YYQU_CD"]) > str(consumption[key]["STDR_YYQU_CD"]):
                consumption[key] = row
    contexts = {}
    for slug in ACTIVE_HUBS:
        posts: dict[str, dict] = {}
        timestamps = []
        for e in manifest["entries"]:
            channel, stem = e["source"].split("/", 1)
            if channel not in {"blog", "cafearticle", "news"} or not stem.startswith(slug + "_"):
                continue
            timestamps.append(e["requested_at"])
            for row in read(digital / e["path"])["items"]:
                link = row.get("originallink") or row.get("link", "")
                if urlparse(link).scheme not in {"http", "https"} or not urlparse(link).hostname:
                    continue
                posts.setdefault(link, {"channel": channel,
                    "title": html.unescape(re.sub(r"<[^>]*>", "", row.get("title", ""))).strip(),
                    "link": link, "published_at": row.get("postdate") or row.get("pubDate"),
                    "query": e["parameters"]["query"]})
        # 공식 행정동 코드로만 조인한다. 인접 행정동을 임의로 보간하지 않는다.
        folder = stores / "stores_resume" / slug
        if not folder.exists():
            folder = stores / "stores" / slug
        codes: Counter = Counter()
        for path in folder.glob("*.json"):
            if not path.name.endswith(".meta.json"):
                codes.update(str(r.get("adongCd", "")) for r in read(path)["body"]["items"])
        matched = [{"code": code, "name": consumption[code]["ADSTRD_CD_NM"],
                    "quarter": str(consumption[code]["STDR_YYQU_CD"]),
                    "total_won": consumption[code]["EXPNDTR_TOTAMT"]}
                   for code, _ in codes.most_common() if code in consumption]
        contexts[slug] = {"online": {"items": list(posts.values()), "sample_count": len(posts),
            "collected_at": max(timestamps) if timestamps else None,
            "note": "네이버 검색 표본입니다. 광고성·지역 귀속은 검증되지 않았으며 원문에서 확인하세요."},
            "consumption": {"districts": matched, "source": "서울 열린데이터광장 VwsmAdstrdNcmCnsmpW",
                "note": "행정동 전체의 추정 소비액입니다. 상권·점포 매출이나 소득이 아닙니다. 4분기 갱신 후 다음 1~3분기 값은 동일할 수 있습니다."}}
    event_rows = []
    for e in pub["entries"]:
        if e["source"].startswith("seoul/culturalEventInfo/"):
            event_rows.extend(read(public / e["path"])["culturalEventInfo"]["row"])
    if not event_rows:
        raise ValueError("문화행사 원본 없음")
    event_entries = [e for e in pub["entries"] if e["source"].startswith("seoul/culturalEventInfo/")]
    if any(e["status"] != "success" for e in event_entries) or {e["total"] for e in event_entries} != {len(event_rows)}:
        raise ValueError("문화행사 원본 전량 불일치")
    districts: dict[str, list] = {slug: [] for slug in ACTIVE_HUBS}
    for row in event_rows:
        coords, end = _coords(row), _end_date(row)
        if coords is None or end is None or end < today or not row.get("TITLE"):
            continue
        for slug, hub in ACTIVE_HUBS.items():
            distance = _dist_m(coords[0], coords[1], hub.cy, hub.cx)
            if distance <= RADIUS_M:
                districts[slug].append({**row, "distance_m": round(distance)})
    events = {slug: [_event(r, i) for i, r in enumerate(sorted(rows,
        key=lambda r: (r["distance_m"], str(r.get("STRTDATE", "")))), 1)]
        for slug, rows in districts.items()}
    normalized = {"built_at": datetime.now(timezone.utc).isoformat(), "as_of": today.isoformat(),
        "contexts": contexts, "events": events, "tourapi": follow["facts"]["tourapi"],
        "inputs": [p.as_posix() for p in [digital, public, followup, stores]]}
    # Silver를 먼저 저장하고 Gold는 그 정규화 결과에서 만든다.
    silver = SILVER / "collected_context.json"
    silver.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    normalized = read(silver)
    for context in normalized["contexts"].values():
        # 채널별 5개 제목·링크만 표시한다. 본문·요약은 재배포하지 않는다.
        context["online"]["items"] = [item for channel in ["blog", "cafearticle", "news"]
            for item in [x for x in context["online"]["items"] if x["channel"] == channel][:5]]
    (GOLD / "platform_collected_context.json").write_text(json.dumps({
        "built_at": normalized["built_at"], "districts": normalized["contexts"],
        "tourapi": normalized["tourapi"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (GOLD / "platform_events.json").write_text(json.dumps({
        "source": "서울열린데이터광장 문화행사(culturalEventInfo)",
        "built_at": normalized["built_at"], "as_of": today.isoformat(),
        "note": "종료 행사 제외. TourAPI의 0건은 별도 기록하며 이 목록을 대체하지 않는다.",
        "districts": normalized["events"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"hubs": len(contexts), "events": sum(map(len, events.values())),
            "consumption_hubs": sum(bool(c["consumption"]["districts"]) for c in contexts.values())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ["digital", "public", "followup", "stores"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    print(run(args.digital, args.public, args.followup, args.stores, args.as_of))
