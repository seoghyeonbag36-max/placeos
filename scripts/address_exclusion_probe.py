"""이력 주소 제외 원인·실데이터 복구 후보 조사. 기존 Gold/후보는 쓰지 않는다."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.config.page_hubs import ACTIVE_HUBS
from data.collectors.common import latest_bronze
from data.pipelines.build_building_history import address_codes, address_pnu, _clean_date, _is_open

OUT = ROOT / "reports" / "address_exclusion_2026-10-15"
PREFIX = re.compile(r"([가-힣]+구)\s+([가-힣0-9]+(?:동|가|리))\s*(산\s*)?(\d{1,4})(?:\s*-\s*(\d{1,4}))?(?!\d|가)")
ROAD = re.compile(r"([가-힣]+구)\s+([가-힣0-9·.]+(?:대로|로|길))\s+(지하\s*)?(\d{1,4})(?:-(\d{1,4}))?(?![\d-])")
PAIR = re.compile(r"([가-힣]+구)\s+([가-힣0-9]+(?:동|가|리))")
INNER = re.compile(r"\(([가-힣0-9]+(?:동|가|리))\s*(산\s*)?(\d{1,4})(?:-(\d{1,4}))?\)")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def road_key(addr):
    m = ROAD.search(str(addr or ""))
    return (m[1], m[2], bool(m[3]), int(m[4]), int(m[5] or 0)) if m else None


def lot_proposal(addr, codes):
    """조사 전용: 명시된 번지·괄호 번지만 읽는다. 잘린 부번은 추측하지 않는다."""
    match, pair = PREFIX.search(addr), PAIR.search(addr)
    if not addr.strip():
        return None, "empty_address"
    if match:
        tail = addr[match.end():].strip()
        # '---------', '----호', '----동 ----호'는 번지가 아닌 빈 상세주소다.
        placeholder = tail.count("-") >= 2 and re.fullmatch(r"[-\s동호]+", tail)
        if tail.startswith("-") and not placeholder:
            return None, "multiple_or_broken_lot_suffix"
        found = codes.get((match[1], match[2]), set())
        if len(found) != 1:
            return None, "missing_or_ambiguous_dong_code"
        return (f"{next(iter(found))}{'2' if match[3] else '1'}{int(match[4]):04d}{int(match[5] or 0):04d}",
                "parser_rejects_complete_lot")
    if pair:
        found = codes.get((pair[1], pair[2]), set())
        if len(found) != 1:
            return None, "missing_or_ambiguous_dong_code"
        inside = [m for m in INNER.finditer(addr) if m[1] == pair[2]]
        pnus = {f"{next(iter(found))}{'2' if m[2] else '1'}{int(m[3]):04d}{int(m[4] or 0):04d}"
                for m in inside}
        if len(pnus) == 1:
            return next(iter(pnus)), "parenthetical_complete_lot"
    return None, "missing_or_unparseable_lot"


def record(row):
    return {"start_date": _clean_date(row.get("APVPERMYMD")),
            "end_date": None if _is_open(row) else _clean_date(row.get("DCBYMD")),
            "industry_type": str(row.get("UPTAENM") or "").strip(),
            "business_name": str(row.get("BPLCNM") or "").strip(),
            "source": "localdata", "closure_reason_summary": None}


def token(row):
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def test_probe_address_rules():
    assert road_key("서울특별시 강남구 압구정로2길 46, 지상1층") == ("강남구", "압구정로2길", False, 46, 0)
    assert road_key("서울 중구 을지로 지하 131, 318-2호") == ("중구", "을지로", True, 131, 0)
    assert road_key("서울 강남구 도산대로 10-12345") is None
    assert PREFIX.search("서울 영등포구 당산동5가 코트론빌딩 201호") is None
    assert PREFIX.search("서울 마포구 동교동162-4(4층)")[2] == "동교동"
    assert PREFIX.search("서울 중구 을지로3가 12-4")[2] == "을지로3가"
    codes = {("강남구", "신사동"): {"1168010700"}, ("강북구", "미아동"): {"1130510100"}}
    assert lot_proposal("서울 강남구 신사동 510-11 ---------", codes)[0] == "1168010700105100011"
    assert lot_proposal("서울 강남구 신사동 510-11 ----동 ----호", codes)[0] == "1168010700105100011"
    assert lot_proposal("서울 강남구 신사동 510-11 -12", codes)[0] is None
    assert lot_proposal("서울 강남구 신사동 510-", codes)[0] is None
    assert lot_proposal("서울 강북구 미아동 호 대지길 39(미아동 44-15)", codes)[0] == "1130510100100440015"


def main():
    test_probe_address_rules()
    OUT.mkdir(parents=True, exist_ok=True)
    references = {}
    global_codes = defaultdict(set)
    roads = defaultdict(set)
    road_sources = defaultdict(set)
    masters = {}
    for slug in ACTIVE_HUBS:
        p = latest_bronze(slug, "stores_raw.json")
        stores = read(p)
        codes = address_codes(stores)
        references[slug] = {"stores": p, "codes": codes}
        for k, v in codes.items():
            global_codes[k].update(v)
        for s in stores:
            pnu, key = str(s.get("lnoCd") or ""), road_key(s.get("rdnmAdr"))
            if key and len(pnu) == 19 and pnu.isdigit() and pnu.startswith("11"):
                roads[key].add(pnu)
                road_sources[(key, pnu)].add(str(p.relative_to(ROOT)))
        master = read(ROOT / "data" / "gold" / slug / "page_building_master.geojson")
        masters[slug] = {f["properties"]["pnu"] for f in master["features"]}
    excluded, removed, summaries = [], [], []
    for slug, hub in ACTIVE_HUBS.items():
        path = latest_bronze(slug, "licensing_biz.json")
        rows = read(path)
        codes = references[slug]["codes"]
        old = read(ROOT / "data" / "gold" / slug / "building_history.json")
        candidate = read(ROOT / "reports" / "page_quality_2026-10-15" / "candidate_gold" / slug / "building_history.json")
        old_entries = Counter((pnu, token(r)) for pnu, rs in old["lots"].items() for r in rs)
        candidate_entries = Counter((pnu, token(r)) for pnu, rs in candidate["lots"].items() for r in rs)
        lost = old_entries - candidate_entries
        raw_by_record = defaultdict(list)
        rejected = []
        missing_start = 0
        for row in rows:
            rec = record(row)
            raw_by_record[token(rec)].append(row)
            if rec["start_date"] is None:
                missing_start += 1
                continue
            addr = str(row.get("SITEWHLADDR") or "")
            if address_pnu(addr, codes) is not None:
                continue
            direct, reason = lot_proposal(addr, global_codes)
            key = road_key(row.get("RDNWHLADDR"))
            road_hits = roads.get(key, set())
            road_pnu = next(iter(road_hits)) if len(road_hits) == 1 else None
            conflict = bool(direct and road_pnu and direct != road_pnu)
            proposal = None if conflict else direct or road_pnu
            method = ("conflict_hold" if conflict else "lot_and_road_agree" if direct and road_pnu
                      else "complete_lot_only" if direct else "unique_local_road" if road_pnu
                      else "ambiguous_local_road" if len(road_hits) > 1 else "needs_external_evidence")
            identity = f"{row.get('svc')}|{row.get('MGTNO')}" if row.get("MGTNO") else hashlib.sha256(token(row).encode()).hexdigest()
            item = {"hub": slug, "hub_name": hub.name, "record_key": identity,
                    "business_name": row.get("BPLCNM"), "service": row.get("svc"),
                    "mgtno": row.get("MGTNO"), "site_address": addr,
                    "road_address": row.get("RDNWHLADDR"), "reason": reason,
                    "proposal_method": method, "proposed_pnu": proposal,
                    "in_hub_master": proposal in masters[slug] if proposal else False,
                    "in_existing_candidate": proposal in candidate["lots"] if proposal else False,
                    "direct_pnu": direct, "road_pnus": sorted(road_hits),
                    "road_evidence_files": sorted(road_sources.get((key, road_pnu), set())),
                    "has_xy": bool(str(row.get("X") or "").strip() and str(row.get("Y") or "").strip()),
                    "start_date": rec["start_date"], "end_date": rec["end_date"],
                    "raw_file": str(path.relative_to(ROOT)),
                    "stores_file": str(references[slug]["stores"].relative_to(ROOT))}
            excluded.append(item)
            rejected.append(item)
        rejected_lookup = {i["record_key"]: i for i in rejected}
        for (old_pnu, key), count in lost.items():
            matching = raw_by_record[key]
            traces = []
            for raw in matching:
                identity = f"{raw.get('svc')}|{raw.get('MGTNO')}" if raw.get("MGTNO") else hashlib.sha256(token(raw).encode()).hexdigest()
                trace = rejected_lookup.get(identity)
                resolved = address_pnu(str(raw.get("SITEWHLADDR") or ""), codes)
                traces.append({"mgtno": raw.get("MGTNO"), "site_address": raw.get("SITEWHLADDR"),
                               "road_address": raw.get("RDNWHLADDR"), "current_resolved_pnu": resolved,
                               "excluded_reason": trace["reason"] if trace else None,
                               "recovery_pnu": trace["proposed_pnu"] if trace else None,
                               "proposal_method": trace["proposal_method"] if trace else None})
            removed.append({"hub": slug, "old_pnu": old_pnu, "count": count,
                            "record": json.loads(key), "source_traces": traces})
        summaries.append({"hub": slug, "name": hub.name, "raw_rows": len(rows),
                          "missing_start_date": missing_start, "address_excluded": len(rejected),
                          "reasons": dict(Counter(i["reason"] for i in rejected)),
                          "proposal_methods": dict(Counter(i["proposal_method"] for i in rejected)),
                          "recoverable_in_master": sum(i["in_hub_master"] for i in rejected),
                          "new_lots": len({i["proposed_pnu"] for i in rejected if i["in_hub_master"] and not i["in_existing_candidate"]}),
                          "removed_old_records": sum(lost.values())})
        print(slug, len(rejected), flush=True)
    unique = {i["record_key"] for i in excluded}
    report = {"scope": "ACTIVE_HUBS 81; existing local Bronze only; no Gold changes",
              "counts_include_hub_overlap": True, "excluded_occurrences": len(excluded),
              "unique_records": len(unique), "reasons": dict(Counter(i["reason"] for i in excluded)),
              "methods": dict(Counter(i["proposal_method"] for i in excluded)),
              "recoverable_in_master": sum(i["in_hub_master"] for i in excluded),
              "removed_old_records": sum(i["count"] for i in removed),
              "hubs": summaries, "excluded": excluded, "removed": removed}
    (OUT / "details.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT / "excluded.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(excluded[0]))
        writer.writeheader()
        writer.writerows(excluded)
    assert sum(h["address_excluded"] for h in summaries) == len(excluded)
    assert sum(h["removed_old_records"] for h in summaries) == sum(r["count"] for r in removed)
    assert all(i["proposed_pnu"] is None for i in excluded if i["proposal_method"] == "conflict_hold")
    print(json.dumps({k: v for k, v in report.items() if k not in ("hubs", "excluded", "removed")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
