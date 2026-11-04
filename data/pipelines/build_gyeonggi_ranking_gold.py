"""경기 순위 확장용 Gold와 수집 완료 조사 후보의 대장 근거를 별도로 산출한다.

기존 공개 Gold·모델·서빙 목록을 덮지 않는다. 점포는 Bronze → Silver 정제 → Gold
그래프로, 완주 대장은 원본 검증 → Silver 행 → Gold 근거표로 만든다.
조사 후보의 대장 완주는 상권 경계·앵커·입지 점수의 검증을 대신하지 않는다.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def write_once(path: Path, data: bytes) -> None:
    """같은 산출물의 재실행만 허용한다. 기존 값을 조용히 교체하지 않는다."""
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"기존 산출물과 다름: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def json_bytes(doc: dict) -> bytes:
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def parse_page(payload: dict) -> tuple[int, list[dict]]:
    """보관된 대장의 정상 응답과 페이지 완전성을 검사한다."""
    response = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(response, dict):
        raise ValueError("API_RESPONSE_INVALID")
    header, body = response.get("header"), response.get("body")
    if not isinstance(header, dict) or str(header.get("resultCode")) not in {"0", "00"}:
        raise ValueError("API_HEADER_INVALID")
    if not isinstance(body, dict):
        raise ValueError("API_BODY_INVALID")
    total = body.get("totalCount")
    if total is None or isinstance(total, bool) or not str(total).isdigit():
        raise ValueError("API_TOTAL_INVALID")
    total = int(total)
    wrapped = body.get("items")
    rows = wrapped.get("item", []) if isinstance(wrapped, dict) else [] if not wrapped else None
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("API_ITEMS_INVALID")
    if len(rows) > 100 or (not rows and total > 0) or len(rows) > total:
        raise ValueError("API_PAGE_PARTIAL")
    return total, rows


def ledger_rows(root: Path, plan: dict, pnu: str, endpoint: str) -> tuple[list[dict], list[dict]]:
    """완료 표식뿐 아니라 페이지 해시·정상 헤더·건수·중복까지 확인한다."""
    marker = root / "data/bronze/regional_research_ledgers/2026-11-03" / endpoint / pnu / "complete.json"
    if marker.exists():
        done = read(marker)
        if done.get("complete") is not True or done.get("pnu") != pnu or done.get("endpoint") != endpoint:
            raise ValueError(f"미완료·식별자 불일치: {pnu}/{endpoint}")
        rows: list[dict] = []
        sources = []
        for source in done.get("pages", []):
            path = root / source["path"]
            if digest(path) != source["sha256"]:
                raise ValueError(f"원본 해시 불일치: {source['path']}")
            total, page_rows = parse_page(read(path))
            if total != done["total"]:
                raise ValueError(f"전체 건수 불일치: {pnu}/{endpoint}")
            rows.extend(page_rows)
            sources.append(source)
        if not sources or len(rows) != done.get("received") or len(rows) != done.get("total"):
            raise ValueError(f"페이지 미완주: {pnu}/{endpoint}")
        if len({json_bytes(row) for row in rows}) != len(rows):
            raise ValueError(f"페이지 중복: {pnu}/{endpoint}")
        return rows, sources
    legacy = plan.get("legacy_expos", {}).get(pnu) if endpoint == "expos" else None
    if not legacy:
        raise ValueError(f"완료 원본 없음: {pnu}/{endpoint}")
    path = root / legacy["source"]
    expected = plan["legacy_sources"][legacy["source"]]
    if digest(path) != expected:
        raise ValueError(f"기존 원본 해시 불일치: {path}")
    record = read(path)[pnu]
    rows = record.get("expos")
    if not isinstance(rows, list) or record.get("expos_capped") or len(rows) != record.get("expos_total"):
        raise ValueError(f"기존 전유부 미완주: {pnu}")
    return rows, [{"path": legacy["source"], "sha256": expected}]


def completed_research(root: Path = ROOT) -> dict:
    plan_path = root / "data/silver/regional_research_ledgers/targets_2026-11-03.json"
    if not plan_path.exists():
        return {"complete": [], "incomplete": [], "reason": "조사 작업표 없음"}
    plan = read(plan_path)
    complete, incomplete = [], []
    raw = root / "data/bronze/regional_research_ledgers/2026-11-03"
    for location in plan["locations"]:
        if location["region"] != "경기":
            continue
        pnus = location["pnus"]
        counts = {endpoint: sum((raw / endpoint / pnu / "complete.json").exists()
                               or (endpoint == "expos" and pnu in plan.get("legacy_expos", {})) for pnu in pnus)
                  for endpoint in ("expos", "floors")}
        entry = {"id": location["id"], "name": location["label"], "lots": len(pnus), **counts}
        if location["unresolved"] or not pnus or any(n != len(pnus) for n in counts.values()):
            incomplete.append(entry)
            continue
        source = root / location["source"]
        if digest(source) != location["source_sha256"]:
            raise ValueError(f"점포 원본 해시 불일치: {location['id']}")
        lots, sources = {}, {location["source"]: location["source_sha256"]}
        for pnu in pnus:
            lots[pnu] = {}
            for endpoint in ("expos", "floors"):
                rows, evidence = ledger_rows(root, plan, pnu, endpoint)
                lots[pnu][endpoint] = rows
                sources.update({r["path"]: r["sha256"] for r in evidence})
        silver = {"id": location["id"], "lots": lots, "sources": sources,
                  "source": "건축HUB 전유부·층별개요 정상 응답", "seed": False}
        silver_path = root / "data/silver" / location["id"] / "collected_ledger_rows.json.gz"
        write_once(silver_path, gzip.compress(json_bytes(silver), mtime=0))
        normalized = read(silver_path)
        gold = {"id": location["id"], "name": location["label"], "status": "collected_evidence",
                "source": normalized["source"], "seed": False, "public": False,
                "silver_sha256": digest(silver_path), "lots": normalized["lots"],
                "counts": {"lots": len(lots), **{e + "_rows": sum(len(r[e]) for r in lots.values()) for e in counts}},
                "unavailable": ["상권 경계·건물 폴리곤", "R-ONE 앵커 검증", "입지 추천 모델"],
                "note": "대장에 기록된 근거만 산출했다. 공실률·입지 점수·순위를 산출한 자료가 아니다."}
        gold_path = root / "data/gold" / location["id"] / "collected_ledger_evidence.json.gz"
        write_once(gold_path, gzip.compress(json_bytes(gold), mtime=0))
        entry.update(gold=gold_path.relative_to(root).as_posix(), sha256=digest(gold_path), counts=gold["counts"])
        complete.append(entry)
    return {"complete": complete, "incomplete": incomplete, "source_plan_sha256": digest(plan_path)}


def ranking_graph(root: Path = ROOT) -> dict:
    """공개 경기 전체의 학습 재료를 별도 경로에 산출한다. 모델 추론·교체는 하지 않는다."""
    import pandas as pd
    from app.data.cities import CITIES
    from data.config.page_hubs import ACTIVE_HUBS
    from data.pipelines.build_gold import _store_node_rows
    from data.pipelines.build_store_graph_edges import build_edges
    from data.pipelines.build_page_building_features import _district_table
    from ml.training.graph_dedup import one_row_per_store

    hubs = {s: h for s, h in ACTIVE_HUBS.items() if CITIES[h.city].sido == "경기도"}
    out = root / "data/gold/gyeonggi_ranking_20261104"
    manifest = out / "manifest.json"
    if manifest.exists():
        previous = read(manifest)
        if set(previous["hubs"]) != set(hubs):
            raise ValueError("공개 상권 목록 변경: 새 버전의 Gold 산출 필요")
        for name, sha in previous["existing_gold_sha256"].items():
            if digest(root / name) != sha:
                raise ValueError(f"입력 Gold 변경: 새 버전 산출 필요: {name}")
        for name, sha in previous["bronze_sha256"].items():
            if digest(root / name) != sha:
                raise ValueError(f"점포 원본 변경: 새 버전 산출 필요: {name}")
        for name, sha in previous["output_sha256"].items():
            if digest(out / name) != sha:
                raise ValueError(f"Gold 무결성 불일치: {name}")
        return previous
    rows, sources, baseline = [], {}, {}
    for slug in hubs:
        for name in ("page_building_master.geojson", "coverage.json", "calibration.json", "vacant_units.json", "vacant_floor_units.json"):
            path = root / "data/gold" / slug / name
            if not path.exists():
                raise ValueError(f"선행 Gold 누락: {path}")
            baseline[path.relative_to(root).as_posix()] = digest(path)
        bronze = sorted((root / "data/bronze" / slug).glob("*/stores_raw.json"))
        if not bronze:
            raise ValueError(f"점포 원본 없음: {slug}")
        sources[bronze[-1].relative_to(root).as_posix()] = digest(bronze[-1])
        got = _store_node_rows(slug, slug)
        if not got:
            raise ValueError(f"정제한 점포 없음: {slug}")
        rows.extend(got)
    silver = root / "data/silver/gyeonggi_ranking_20261104/store_graph_nodes.parquet"
    if silver.exists() or out.exists():
        raise ValueError("미완료 산출 경로가 있다. 원인을 확인한 뒤 별도 버전으로 실행할 것")
    silver.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(silver, index=False)
    nodes, dropped = one_row_per_store(pd.read_parquet(silver), {s: (h.cx, h.cy) for s, h in hubs.items()})
    if set(nodes["district_id"]) != set(hubs):
        raise ValueError("중복 제거 후 경기 공개 상권 누락")
    out.mkdir(parents=True)
    nodes_path = out / "platform_store_graph_nodes.parquet"
    nodes.to_parquet(nodes_path, index=False)
    build_edges(nodes_path, out / "platform_store_graph_edges.parquet")
    parts = []
    for slug, group in nodes.groupby("district_id"):
        part = _district_table(str(slug), group)
        if part is None or len(part) != len(group):
            raise ValueError(f"건물 피처 산출 실패: {slug}")
        parts.append(part)
    features = pd.concat(parts, ignore_index=True)
    features.to_parquet(out / "page_building_features.parquet", index=False)
    for name, sha in baseline.items():
        if digest(root / name) != sha:
            raise ValueError(f"기존 Gold 변경 감지: {name}")
    doc = {"scope": "경기도 공개 상권 전체", "seed": False, "hubs": sorted(hubs),
           "cities": sorted({h.city for h in hubs.values()}), "nodes": len(nodes), "duplicates_removed": dropped,
           "building_matched_pct": round(float(features["bld_matched"].mean() * 100), 2),
           "silver_sha256": digest(silver), "bronze_sha256": sources, "existing_gold_sha256": baseline,
           "output_sha256": {p.name: digest(p) for p in out.glob("*.parquet")},
           "status": "model_input_ready", "note": "기존 서빙 모델은 변경하지 않았다. 새 상권의 모델 피처·검증이 선행돼야 순위를 낼 수 있다."}
    write_once(manifest, json_bytes(doc))
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-only", action="store_true")
    args = parser.parse_args()
    result = {"research": completed_research()}
    if not args.research_only:
        result["ranking_graph"] = ranking_graph()
    report = ROOT / "reports/gyeonggi_ranking_gold_2026-11-04.json"
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"complete_research": result["research"]["complete"],
                      "incomplete_research": len(result["research"]["incomplete"]),
                      "ranking_hubs": len(result.get("ranking_graph", {}).get("hubs", []))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
