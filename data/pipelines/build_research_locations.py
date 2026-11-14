"""광주·전주 탐색 위치(대장 Gold 완주분)를 지도 「조사 위치」 레이어용 요약 Gold 로 만든다.

결정: docs/decision-research-locations-layer-2026-11-09.md (2026-11-09 사용자 선택 「조사 위치 레이어」)

이 위치들은 **정식 상권도, 서빙 거점도 아니다.** 일반음식점 인허가 주소에서 찾은 700m 조사 원이고 서로 겹친다.
그래서 여기서는 관측값만 옮긴다 — 공실률·순위·임대료·상권 경계는 만들지 않는다. 받은 대장은 점포가 확인된
지번뿐이라(빈 건물이 없다) 공실률의 분모가 없다. 거점 승격은 hub-chain(경계·폴리곤·빈 건물 대장·앵커)이 따로 한다.

입력(전부 해시 대조 — 어긋나면 멈춘다)
- reports/regional_research_gold.json — `status == "checked"` 이고 위치마다 `ledger_gold_complete`
- 위치별 ledger_evidence.json.gz · program_content_context.csv — 보고서의 sha256 과 대조
- 좌표·700m 점포 프로브: reports/regional_hub_candidates_2026-11-03.json(181곳)
  · reports/jeonju_requested_areas_2026-11-06.json(전주 보완 25곳)

출력: data/gold/platform_research_locations.json (`services/research_locations` 가 서빙)

    python -m data.pipelines.build_research_locations --root <Bronze·Gold 가 있는 체크아웃>

`--root` 는 원천이 있는 체크아웃이다. 대장 Gold·Bronze 는 git 밖이라 worktree 에는 없다. 출력은 이 파일이 든
저장소의 data/gold 로 간다(`--out` 으로 바꿀 수 있다). 네트워크 호출은 없다.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import math

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "gold" / "platform_research_locations.json"
GOLD_REPORT = "reports/regional_research_gold.json"
CANDIDATES = "reports/regional_hub_candidates_2026-11-03.json"
JEONJU_ADDED = "reports/jeonju_requested_areas_2026-11-06.json"
KST = timezone(timedelta(hours=9))
SCHEMA_VERSION = 1
TOP_CATEGORIES = 5

# 대장 수집 원장의 지역 라벨 → 지도 묶음 키(districtMapModel.RANK_GROUPS). 전주권(완주 혁신도시)은 전주 묶음이다.
GROUP_OF = {"광주": "gwangju", "전주": "jeonju", "전주권": "jeonju"}
# 라벨 앞의 시도·시 이름은 묶음 이름과 겹쳐 지도 칩만 길게 만든다.
_PREFIXES = ("전남광주통합특별시 ", "전주시 ")

NOTE = ("조사 위치는 일반음식점 인허가 주소에서 찾은 700m 조사 원이다. 정식 상권·공식 경계·서빙 거점이 아니고 "
        "반경이 서로 겹쳐 점포 수를 합산하지 않는다. 대장은 상가정보 점포가 확인된 지번만 받아 빈 건물이 없으므로 "
        "공실률·순위·임대료를 만들지 않는다.")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def short_name(label: str) -> str:
    for p in _PREFIXES:
        if label.startswith(p):
            return label[len(p):]
    return label


def coord_index(root: Path) -> dict[str, dict]:
    """위치 id → 좌표·700m 점포 프로브. 두 보고서 모두 실호출 원본에서 나온 값이다."""
    out: dict[str, dict] = {}
    cand = read_json(root / CANDIDATES)
    for rows in cand["discovery"].values():
        for r in rows:
            m = (r.get("store_probe") or {}).get("metrics") or {}
            out[r["candidate_id"]] = dict(lat=r["lat"], lng=r["lon"], radius_m=(r.get("store_probe") or {}).get("radius_m", 700),
                                          metrics=m, nearest_hub=r.get("nearest_registered_hub"),
                                          nearest_hub_m=r.get("nearest_registered_m"))
    added = read_json(root / JEONJU_ADDED)
    for r in added["added_centers"]:
        out[r["id"]] = dict(lat=r["lat"], lng=r["lon"], radius_m=r.get("radius_m", 700),
                            metrics=(r.get("store_probe") or {}).get("metrics") or {}, nearest_hub=None, nearest_hub_m=None)
    return out


def ledger_summary(observations: list[dict]) -> dict:
    """지번별 관측을 센다. 호실·층은 관측이지 공실이 아니다."""
    return dict(
        pnus=len(observations),
        pnus_with_commercial_floor=sum(bool(o.get("commercial_ground_floor_numbers")) for o in observations),
        pnus_with_expos=sum((o.get("expos_rows") or 0) > 0 for o in observations),
        commercial_expos_units=sum(int(o.get("commercial_expos_units") or 0) for o in observations),
        pnus_without_ledger=sum(not o.get("expos_rows") and not o.get("floor_rows") for o in observations),
    )


def top_categories(csv_bytes: bytes) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
    rows = [(r["key"], int(r["value"])) for r in reader if r.get("kind") == "category"]
    rows.sort(key=lambda kv: (-kv[1], kv[0]))
    return [dict(name=k, count=v) for k, v in rows[:TOP_CATEGORIES]]


def build(root: Path) -> dict:
    report_path = root / GOLD_REPORT
    report = read_json(report_path)
    if report.get("status") != "checked":
        raise ValueError(f"대장 Gold 보고서가 검증 완료 상태가 아니다: {report.get('status')}")
    coords = coord_index(root)
    locations, problems = [], []
    for entry in report["locations"]:
        group = GROUP_OF.get(entry["region"])
        if group is None:
            continue
        if entry.get("status") != "ledger_gold_complete":
            problems.append(f"{entry['id']}: {entry.get('status')}")
            continue
        if entry.get("serving_eligible") is not False:
            # 거점 승격 경로가 생기면 이 레이어가 아니라 hub-chain 이 맡는다 — 섞이지 않게 멈춘다.
            raise ValueError(f"serving_eligible 이 거짓이 아닌 위치: {entry['id']}")
        arts = {Path(a["path"]).name: a for a in entry["artifacts"]}
        evidence_ref, context_ref = arts.get("ledger_evidence.json.gz"), arts.get("program_content_context.csv")
        if not evidence_ref or not context_ref:
            problems.append(f"{entry['id']}: 산출물 누락")
            continue
        ev_path, ctx_path = root / evidence_ref["path"], root / context_ref["path"]
        if sha256(ev_path) != evidence_ref["sha256"] or sha256(ctx_path) != context_ref["sha256"]:
            problems.append(f"{entry['id']}: 산출물 해시 불일치")
            continue
        evidence = read_json(ev_path)
        if evidence.get("candidate_id") != entry["id"] or evidence.get("seed") is not False:
            problems.append(f"{entry['id']}: 근거 문서 불일치")
            continue
        c = coords.get(entry["id"])
        if c is None:
            problems.append(f"{entry['id']}: 좌표 없음")
            continue
        m = c["metrics"]
        locations.append(dict(
            id=entry["id"], label=entry["label"], name=short_name(entry["label"]),
            region=entry["region"], group=group, lat=round(c["lat"], 6), lng=round(c["lng"], 6), radius_m=c["radius_m"],
            stores=m.get("stores"), buildings=m.get("buildings"), stores_per_building=m.get("stores_per_building"),
            top10_building_pct=m.get("top10_building_pct"), density_verdict=m.get("verdict"),
            ledger=ledger_summary(evidence.get("observations") or []),
            top_categories=top_categories(ctx_path.read_bytes()),
            nearest_hub=c["nearest_hub"], nearest_hub_m=c["nearest_hub_m"],
            evidence=dict(path=evidence_ref["path"], sha256=evidence_ref["sha256"]),
        ))
    if problems:
        raise ValueError("조사 위치 요약을 만들 수 없다 — " + "; ".join(problems[:10]))
    # 서빙 거점으로 승격한 조사 위치는 레이어에서 뺀다 — 같은 자리를 거점과 조사 위치로 두 번 그리지 않는다
    # (2026-11-09 광주·전주 2차 · docs/decision-gwangju-jeonju-batch2-2026-11-09.md). 승격 사실은 `promoted` 에 남긴다.
    from data.config.page_hubs import ACTIVE_HUBS, GJ_JJ_BATCH2_RESEARCH_ID, GJ_JJ_BATCH2_SERVED_HUBS
    promoted = {GJ_JJ_BATCH2_RESEARCH_ID[s]: s for s in sorted(GJ_JJ_BATCH2_SERVED_HUBS)}
    locations = [loc for loc in locations if loc["id"] not in promoted]
    # 「가까운 거점」은 탐색 당시 값이 아니라 **지금 서빙 중인** 같은 도시 거점에서 다시 잰다 — 승격으로 더 가까운 거점이 생긴다.
    served = [h for h in ACTIVE_HUBS.values() if h.city in ("gwangju", "jeonju")]
    for loc in locations:
        same = [(h.slug, h.cy, h.cx) for h in served if h.city == loc["group"]]
        if same:
            slug, dist = min(((slug, _meters(loc["lat"], loc["lng"], lat, lng)) for slug, lat, lng in same), key=lambda x: x[1])
            loc["nearest_hub"], loc["nearest_hub_m"] = slug, int(round(dist))
    # 같은 라벨(「효자동1가 보완」 등)은 서쪽부터 번호를 붙인다 — 칩에서 구별되게.
    by_name: dict[str, list[dict]] = defaultdict(list)
    for loc in locations:
        by_name[loc["name"]].append(loc)
    for same in by_name.values():
        if len(same) > 1:
            for i, loc in enumerate(sorted(same, key=lambda x: (x["lng"], x["lat"])), 1):
                loc["name"] = f"{loc['name']} {i}"
    locations.sort(key=lambda x: (x["group"], -(x["stores"] or 0), x["id"]))
    return dict(
        schema_version=SCHEMA_VERSION, built_at=datetime.now(KST).isoformat(timespec="seconds"),
        source="건축HUB 전유부·층별개요(검증 완료 대장 Gold) · 소상공인 상가정보 700m 실호출 · 일반음식점 인허가 좌표",
        seed=False, serving_eligible=False, note=NOTE,
        inputs=dict(gold_report=dict(path=GOLD_REPORT, sha256=sha256(report_path), checked_at=report.get("checked_at"),
                                     plan_sha256=report.get("plan_sha256")),
                    candidates=dict(path=CANDIDATES, sha256=sha256(root / CANDIDATES)),
                    jeonju_added=dict(path=JEONJU_ADDED, sha256=sha256(root / JEONJU_ADDED))),
        counts=dict(Counter(loc["group"] for loc in locations)),
        promoted=[dict(id=rid, hub=slug) for rid, slug in sorted(promoted.items(), key=lambda kv: kv[1])],
        locations=locations,
    )


def _meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 점 사이 거리(m) — 하버사인."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=REPO, help="Bronze·대장 Gold 가 있는 체크아웃(기본: 이 저장소)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    doc = build(args.root.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # 한 줄 한 위치 — diff 가 위치 단위로 읽히고 크기는 들여쓰기판의 절반 남짓이다.
    head = {k: v for k, v in doc.items() if k != "locations"}
    body = ",\n".join(json.dumps(loc, ensure_ascii=False, separators=(",", ":")) for loc in doc["locations"])
    text = json.dumps(head, ensure_ascii=False, separators=(",", ":"))[:-1] + ',"locations":[\n' + body + "\n]}\n"
    json.loads(text)  # 손으로 이은 문자열이 JSON 인지 쓰기 전에 확인한다
    args.out.write_text(text, encoding="utf-8")
    print(f"조사 위치 {len(doc['locations'])}곳 {doc['counts']} → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
