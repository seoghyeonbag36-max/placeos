"""조사 결과에 상세주소·괄호번지 및 대장 도로명 교차검증을 추가한다."""
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.address_exclusion_probe import lot_proposal, road_key
from data.collectors.common import latest_bronze
from data.config.page_hubs import ACTIVE_HUBS
from data.pipelines.build_building_history import address_codes

OUT = Path(__file__).resolve().parent
r = json.loads((OUT / "details.json").read_text(encoding="utf-8"))
ledger = json.loads((OUT / "ledger_road_evidence.json").read_text(encoding="utf-8"))
codes = defaultdict(set)
for slug in ACTIVE_HUBS:
    stores = json.loads(latest_bronze(slug, "stores_raw.json").read_text(encoding="utf-8"))
    for key, values in address_codes(stores).items():
        codes[key].update(values)
masters, candidates = {}, {}
for slug in ACTIVE_HUBS:
    master = json.loads((ROOT / "data/gold" / slug / "page_building_master.geojson").read_text(encoding="utf-8"))
    masters[slug] = {f["properties"]["pnu"] for f in master["features"]}
    candidates[slug] = json.loads((ROOT / "reports/page_quality_2026-10-15/candidate_gold" / slug / "building_history.json").read_text(encoding="utf-8"))["lots"]
for i in r["excluded"]:
    direct, reason = lot_proposal(i["site_address"], codes)
    road_hits = i["road_pnus"]
    rp = road_hits[0] if len(road_hits) == 1 else None
    key = road_key(i["road_address"])
    evidence = ledger.get(json.dumps(key, ensure_ascii=False), {}) if key else {}
    lp = next(iter(evidence)) if len(evidence) == 1 else None
    options = {p for p in (direct, rp, lp) if p}
    conflict = len(options) > 1
    proposal = None if conflict else next(iter(options)) if options else None
    method = ("conflict_hold" if conflict else "ledger_road_confirmed" if lp
              else "lot_and_road_agree" if direct and rp else "complete_lot_only" if direct
              else "unique_local_road" if rp else "ambiguous_local_road" if len(road_hits) > 1 or len(evidence) > 1
              else "needs_external_evidence")
    # 대장이나 점포표가 다중 지번이면 단일값으로 단정하지 않는다.
    if proposal and ((road_hits and proposal not in road_hits) or (evidence and proposal not in evidence)):
        proposal, method = None, "conflict_hold"
    i.update(reason=reason, proposal_method=method, direct_pnu=direct, proposed_pnu=proposal,
             in_hub_master=proposal in masters[i["hub"]] if proposal else False,
             in_existing_candidate=proposal in candidates[i["hub"]] if proposal else False,
             ledger_pnus=sorted(evidence), ledger_files=sorted({p for paths in evidence.values() for p in paths}))
lookup = {(i["hub"], i["mgtno"]): i for i in r["excluded"]}
removed_counts = Counter()
removed_by_hub = defaultdict(Counter)
for row in r["removed"]:
    rejected = [t for t in row["source_traces"] if t["excluded_reason"]]
    if rejected:
        restored = False
        for t in rejected:
            i = lookup.get((row["hub"], t["mgtno"]))
            if i:
                t.update(recovery_pnu=i["proposed_pnu"], proposal_method=i["proposal_method"], excluded_reason=i["reason"])
                restored |= bool(i["proposed_pnu"] == row["old_pnu"] and i["in_hub_master"])
        category = "address_rejected_recoverable" if restored else "address_rejected_pending"
    else:
        category = "resolved_to_different_pnu"
    row["classification"] = category
    removed_counts[category] += row["count"]
    removed_by_hub[row["hub"]][category] += row["count"]
for h in r["hubs"]:
    items = [i for i in r["excluded"] if i["hub"] == h["hub"]]
    h.update(reasons=dict(Counter(i["reason"] for i in items)),
             proposal_methods=dict(Counter(i["proposal_method"] for i in items)),
             recoverable_in_master=sum(i["in_hub_master"] for i in items),
             new_lots=len({i["proposed_pnu"] for i in items if i["in_hub_master"] and not i["in_existing_candidate"]}),
             removed_classification=dict(removed_by_hub[h["hub"]]))
r.update(reasons=dict(Counter(i["reason"] for i in r["excluded"])),
         methods=dict(Counter(i["proposal_method"] for i in r["excluded"])),
         recoverable_in_master=sum(i["in_hub_master"] for i in r["excluded"]),
         recoverable_unique_records=len({i["record_key"] for i in r["excluded"] if i["in_hub_master"]}),
         removed_classification=dict(removed_counts))
manifest = json.loads((ROOT / "reports/page_quality_2026-10-15/manifest.json").read_text(encoding="utf-8"))
assert all(hashlib.sha256((ROOT / c["target"]).read_bytes()).hexdigest() == c["original_sha256"] for c in manifest["changes"])
assert all(hashlib.sha256((ROOT / c["candidate"]).read_bytes()).hexdigest() == c["candidate_sha256"] for c in manifest["changes"])
assert sum(removed_counts.values()) == 328
assert len(r["excluded"]) == 4123
r["original_and_candidate_files_unchanged"] = True
(OUT / "details.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
with (OUT / "excluded.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(r["excluded"][0])); w.writeheader(); w.writerows(r["excluded"])
with (OUT / "removed_328.csv").open("w", encoding="utf-8-sig", newline="") as f:
    fields = ["hub", "old_pnu", "business_name", "count", "classification", "site_address", "road_address", "recovery_pnu"]
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
    for row in r["removed"]:
        trace = row["source_traces"][0] if row["source_traces"] else {}
        w.writerow({"hub":row["hub"], "old_pnu":row["old_pnu"], "business_name":row["record"]["business_name"],
                    "count":row["count"], "classification":row["classification"],
                    "site_address":trace.get("site_address"), "road_address":trace.get("road_address"),
                    "recovery_pnu":trace.get("recovery_pnu") or trace.get("current_resolved_pnu")})
print(json.dumps({k:v for k,v in r.items() if k not in ("hubs", "excluded", "removed")}, ensure_ascii=False))
