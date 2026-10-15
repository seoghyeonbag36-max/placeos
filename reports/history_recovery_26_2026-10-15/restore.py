"""사용자가 승인한 이력 26건만 복구한다. 기존 Gold의 중복 추가는 금지한다."""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from data.collectors.common import latest_bronze
from data.pipelines.build_building_history import address_codes, address_pnu
from scripts.address_exclusion_probe import record

OUT = Path(__file__).resolve().parent
DETAILS = ROOT / "reports/address_exclusion_2026-10-15/details.json"
CANDIDATE = ROOT / "reports/page_quality_2026-10-15/candidate_gold"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def entries(doc):
    return Counter((pnu, json.dumps(row, ensure_ascii=False, sort_keys=True))
                   for pnu, rows in doc["lots"].items() for row in rows)


def main():
    investigation = read(DETAILS)
    selected = [r for r in investigation["removed"] if r["classification"] == "address_rejected_recoverable"]
    assert len(selected) == sum(r["count"] for r in selected) == 26
    by_hub = defaultdict(list)
    for item in selected:
        by_hub[item["hub"]].append(item)
    assert {s: len(v) for s, v in by_hub.items()} == {"garosugil": 23, "miasageori": 2, "suyu": 1}
    silver_rows, plans = [], []
    for slug, items in by_hub.items():
        licensing = latest_bronze(slug, "licensing_biz.json")
        stores = latest_bronze(slug, "stores_raw.json")
        raw = read(licensing)
        codes = address_codes(read(stores))
        licensing_hash, stores_hash = digest(licensing.read_bytes()), digest(stores.read_bytes())
        live_path = ROOT / "data/gold" / slug / "building_history.json"
        candidate_path = CANDIDATE / slug / "building_history.json"
        live_bytes, candidate_bytes = live_path.read_bytes(), candidate_path.read_bytes()
        live, candidate = json.loads(live_bytes), json.loads(candidate_bytes)
        master = read(ROOT / "data/gold" / slug / "page_building_master.geojson")
        master_ids = defaultdict(list)
        for feature in master["features"]:
            props = feature["properties"]
            master_ids[props["pnu"]].append(props["id"])
        expected = Counter()
        for item in items:
            traces = item["source_traces"]
            assert len(traces) == 1
            trace = traces[0]
            matching = [r for r in raw if r.get("MGTNO") == trace["mgtno"] and record(r) == item["record"]]
            assert len(matching) == 1, (slug, trace["mgtno"])
            source = matching[0]
            pnu = address_pnu(str(source.get("SITEWHLADDR") or ""), codes)
            assert pnu == trace["recovery_pnu"] == item["old_pnu"]
            assert pnu in master_ids
            key = (pnu, json.dumps(item["record"], ensure_ascii=False, sort_keys=True))
            expected[key] += 1
            silver_rows.append({"hub": slug, "pnu": pnu, "record": record(source),
                                "mgtno": source["MGTNO"], "site_address": source["SITEWHLADDR"],
                                "licensing_file": str(licensing.relative_to(ROOT)),
                                "licensing_sha256": licensing_hash,
                                "stores_file": str(stores.relative_to(ROOT)),
                                "stores_sha256": stores_hash,
                                "evidence": trace["proposal_method"]})
        # 기존 Gold는 후보 미반영 상태라 26건이 모두 있다. 중복 추가하지 않는다.
        assert not (expected - entries(live)), slug
        missing = expected - entries(candidate)
        before = entries(candidate)
        for (pnu, row_json), n in missing.items():
            candidate["lots"].setdefault(pnu, []).extend(json.loads(row_json) for _ in range(n))
            candidate["lots"][pnu].sort(key=lambda row: (row["start_date"], row["business_name"]))
            for bid in master_ids[pnu]:
                candidate["buildings"][bid] = pnu
        assert entries(candidate) - before == missing
        assert not (before - entries(candidate))
        plans.append({"slug": slug, "live_path": live_path, "candidate_path": candidate_path,
                      "live_bytes": live_bytes, "candidate_bytes": candidate_bytes,
                      "after": candidate, "restored": sum(missing.values()), "verified_live": len(items)})
    # Bronze에서 확인한 26행을 Silver에 저장하고 정규화 산출물의 행수를 검증한다.
    silver = ROOT / "data/silver/history_recovery_26_2026-10-15.json"
    silver.write_text(json.dumps({"source": "localdata", "rows": silver_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    assert len(read(silver)["rows"]) == 26
    backups = OUT / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    manifest = {"scope": "26 approved licensing records only", "source": "localdata",
                "production_gold_already_present": 26, "production_gold_added": 0,
                "candidate_restored": sum(p["restored"] for p in plans), "files": []}
    for plan in plans:
        slug = plan["slug"]
        for category, content in (("production_gold", plan["live_bytes"]), ("candidate_gold", plan["candidate_bytes"])):
            backup = backups / category / slug / "building_history.json"
            backup.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists():
                assert backup.read_bytes() == content or category == "candidate_gold"
            else:
                backup.write_bytes(content)
        assert plan["live_path"].read_bytes() == plan["live_bytes"]
        assert plan["candidate_path"].read_bytes() == plan["candidate_bytes"]
        data = json.dumps(plan["after"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if plan["restored"]:
            tmp = plan["candidate_path"].with_suffix(".recovery.tmp")
            tmp.write_bytes(data)
            tmp.replace(plan["candidate_path"])
        assert digest(plan["live_path"].read_bytes()) == digest(plan["live_bytes"])
        manifest["files"].append({"slug": slug, "verified_in_production_gold": plan["verified_live"],
                                  "restored_in_candidate": plan["restored"],
                                  "production_gold_sha256": digest(plan["live_bytes"]),
                                  "candidate_before_sha256": digest(plan["candidate_bytes"]),
                                  "candidate_after_sha256": digest(plan["candidate_path"].read_bytes())})
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
