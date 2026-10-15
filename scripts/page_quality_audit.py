"""서울 서빙 거점의 Page 산출물 품질을 전수 점검한다(네트워크·Gold 쓰기 없음).

완료율을 발명하지 않는다. 구조 오류, 관측 커버리지, 미확인 항목을 분리한다.
실행: python scripts/page_quality_audit.py --output reports/page_quality_2026-10-15.json
      --candidate-root reports/page_quality_2026-10-15/candidate_gold
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.config.page_hubs import ACTIVE_HUBS

RUNTIME_FILES = (
    "coverage.json", "page_building_master.geojson", "calibration.json",
    "building_history.json", "vacant_floor_units.json", "vacant_units.json",
    "district_zones.json", "program_content_context.csv",
)


def load(path: Path, errors: list[str]):
    """없는 파일과 읽기 실패를 모두 근거 경로와 함께 남긴다."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(f"{path}: {type(exc).__name__}: {exc}")
        return None


def valid_profile(profile: dict) -> bool:
    """24시간 양쪽 프로파일과 양의 면적이 있어야 밀도를 검증할 수 있다."""
    def finite(v):
        return isinstance(v, (int, float)) and math.isfinite(v)
    return (finite(profile.get("area_m2")) and profile["area_m2"] > 0
            and all(isinstance(profile.get(k), list) and len(profile[k]) == 24
                    and all(finite(v) and v >= 0 for v in profile[k])
                    for k in ("wd", "we")))


def history_metrics(master: dict, history: dict, errors: list[str]) -> dict:
    props = [f["properties"] for f in master["features"]]
    ids = {p["id"]: p.get("pnu") for p in props}
    if len(ids) != len(props):
        errors.append("master: 건물 id 중복")
    if history.get("schema") != "lot-history/1":
        errors.append("history: 알 수 없는 스키마")
    lots, buildings = history.get("lots", {}), history.get("buildings", {})
    bad = [bid for bid, pnu in buildings.items()
           if bid not in ids or ids[bid] != pnu or not lots.get(pnu)]
    if bad:
        errors.append(f"history: 건물/지번 참조 오류 {len(bad)}건")
    linked = sum(bool(lots.get(buildings.get(bid))) for bid in ids)
    return {"buildings": len(ids), "linked": linked,
            "linked_pct": round(linked / len(ids) * 100, 2) if ids else None,
            "lots": len(lots), "records": sum(len(v) for v in lots.values()),
            "gu_codes": dict(Counter(str(p.get("pnu") or "")[:5] for p in props))}


def floor_metrics(master: dict, floors: dict, errors: list[str]) -> dict:
    """공유 지번은 한 번만 세고, 층 공실 확정이 기존 배정 규칙과 맞는지 검사한다."""
    props = {f["properties"]["id"]: f["properties"] for f in master["features"]}
    units, seen = floors.get("units", []), set()
    for unit in units:
        p = props.get(unit.get("building_id"))
        key = (unit.get("pnu"), unit.get("floor"))
        if key in seen:
            errors.append(f"floor: 지번/층 중복 {key}")
        seen.add(key)
        if p is None or p.get("pnu") != unit.get("pnu"):
            errors.append(f"floor: 건물 참조 오류 {unit.get('id')}")
            continue
        candidates = sorted(set(p.get("com_floors", [])) - set(p.get("occ_floors", [])))
        unknown = max(int(p.get("unknown_n") or 0), 0)
        expected = "confirmed" if unit.get("floor") in candidates[unknown:] else "probable"
        if (p.get("status") == "full" or unit.get("floor") not in candidates
                or unit.get("certainty") != expected):
            errors.append(f"floor: 확정/추정 배정 불일치 {unit.get('id')}")
        if not isinstance(unit.get("area_m2"), (float, int)) or unit["area_m2"] <= 0:
            errors.append(f"floor: 면적 없음 {unit.get('id')}")
    if floors.get("counts", {}).get("units") != len(units):
        errors.append("floor: counts.units 불일치")
    return {"units": len(units), "buildings": len({u.get("building_id") for u in units}),
            "certainty": dict(Counter(u.get("certainty") for u in units))}


def audit(gold: Path, hubs: dict, candidate_root: Path | None = None) -> dict:
    global_errors: list[str] = []
    foot = load(gold / "page_footfall_jipgyegu.json", global_errors) or {}
    hourly = load(gold / "page_footfall_hourly.json", global_errors) or {}
    rents = load(gold / "platform_posting_inputs.json", global_errors) or {}
    rows = []
    for slug, hub in hubs.items():
        errors: list[str] = []
        docs = {}
        for name in RUNTIME_FILES:
            path = gold / slug / name
            if name.endswith(".csv"):
                try:
                    docs[name] = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
                except (OSError, ValueError) as exc:
                    errors.append(f"{path}: {exc}")
            else:
                docs[name] = load(path, errors)
        master = docs.get("page_building_master.geojson")
        history = docs.get("building_history.json")
        cov = docs.get("coverage.json") or {}
        record = {"slug": slug, "name": hub.name, "tier": cov.get("tier"),
                  "built_at": cov.get("built_at"),
                  "reference_coverage_pct": cov.get("reference_coverage_pct"),
                  "excluded_unknown": cov.get("excluded_unknown"), "errors": errors}
        if master is not None and history is not None:
            record["history"] = history_metrics(master, history, errors)
            if cov.get("shown") != len(master["features"]):
                errors.append("coverage.shown과 master.features 불일치")
            floors = docs.get("vacant_floor_units.json")
            if floors is not None:
                record["floors"] = floor_metrics(master, floors, errors)
            if candidate_root is not None:
                candidate = load(candidate_root / slug / "building_history.json", errors)
                if candidate is not None:
                    record["candidate_history"] = history_metrics(master, candidate, errors)
                    record["history_link_delta"] = record["candidate_history"]["linked"] - record["history"]["linked"]
                    # 레코드 전체를 세어 잘못 붙었던 이력의 제거도 감춘 순증가로 보고하지 않는다.
                    def entries(doc):
                        return Counter((pnu, json.dumps(r, sort_keys=True, ensure_ascii=False))
                                       for pnu, rs in doc["lots"].items() for r in rs)
                    before, after = entries(history), entries(candidate)
                    record["history_records_added"] = sum((after - before).values())
                    record["history_records_removed"] = sum((before - after).values())
        jg = foot.get("districts", {}).get(slug, {})
        cells = jg.get("cells", {})
        missing = sorted({oa for oa in cells.values() if not valid_profile(foot.get("oa", {}).get(oa, {}))})
        record["footfall"] = {"cells": len(cells), "oa_count": len(set(cells.values())),
                              "invalid_profiles": missing, "sample_days": foot.get("sample_days"),
                              "adong_hourly_available": slug in hourly.get("districts", {})}
        if not cells or missing:
            errors.append("footfall: 집계구 셀/24시간 프로파일/면적 불완전")
        rent = rents.get("districts", {}).get(slug, {}).get("rent_per_m2_krw_thousand")
        record["rent"] = {"per_m2_krw_thousand": rent, "source": rents.get("source"),
                          "quarter": rents.get("quarter"), "floor_factor": rents.get("floor_factor"),
                          "note": "거점 대표 임대료와 층 계수 추정. 개별 매물 실측 월세가 아니다."}
        if not isinstance(rent, (int, float)) or not math.isfinite(rent) or rent <= 0:
            errors.append("rent: 대표 임대료 없음")
        rows.append(record)
    return {"generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
            "scope_source": "data/config/page_hubs.py:ACTIVE_HUBS", "hub_count": len(hubs),
            "reference": "garosugil", "global_errors": global_errors,
            "limitations": ["Page 게이트 100%는 개별 데이터 품질 100%가 아니다.",
                "이력 연결률은 인허가 업종·지번 주소 범위의 관측값이다. 100%를 목표로 결측을 채우지 않는다.",
                "가로수길 HTML의 보행망 도보 거리는 시안 계산이다. 운영 Gold에 동일 산출물이 없어 81거점 동등성 미확인.",
                "행정동 hourly가 없어도 완전한 집계구 24시간 자료가 있으면 해당 레이어의 결측이 아니다.",
                "검토용 candidate는 운영 Gold에 반영하지 않았다."],
            "hubs": rows}


def deployment(gold: Path, hubs: dict) -> dict:
    """현재 추적 여부와 ignore 규칙 자체를 따로 검사한다."""
    paths = [(gold / s / n).relative_to(ROOT).as_posix() for s in hubs for n in RUNTIME_FILES]
    paths += [(gold / n).relative_to(ROOT).as_posix() for n in
              ("page_footfall_jipgyegu.json", "page_footfall_hourly.json", "platform_posting_inputs.json")]
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                             capture_output=True).stdout.decode("utf-8").split("\0")
    # Windows text mode의 LF→CRLF 변환은 경로 끝에 실제 CR을 붙여 전부 무시됐다고
    # 오판한다. NUL 구분 바이너리 입력으로 경로를 그대로 전달한다.
    result = subprocess.run(["git", "check-ignore", "--no-index", "--stdin", "-z"], cwd=ROOT,
                            input=("\0".join(paths) + "\0").encode("utf-8"), capture_output=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    return {"untracked": sorted(set(paths) - set(tracked)),
            "ignored_by_rules": [p for p in result.stdout.decode("utf-8").split("\0") if p],
            "ignore_exit_code": result.returncode}


def markdown(report: dict) -> str:
    rows = report["hubs"]
    lines = ["# 서울 Page 데이터 품질 전수 점검", "", f"기준 시각: {report['generated_at']}", "",
             f"ACTIVE_HUBS 기준 {len(rows)}거점. Gold를 수정하지 않고 구조·연결 품질을 검사했다.", "",
             f"구조 오류 {sum(bool(r['errors']) for r in rows)}거점, 전역 오류 {len(report['global_errors'])}건.", ""]
    compared = [r for r in rows if "candidate_history" in r]
    if compared:
        total = sum(r["history"]["buildings"] for r in compared)
        before = sum(r["history"]["linked"] for r in compared)
        after = sum(r["candidate_history"]["linked"] for r in compared)
        changed = sum(bool(r["history_records_added"] or r["history_records_removed"]) for r in compared)
        lines += [f"이력 후보 {len(compared)}거점 검증. 내용 변경 {changed}거점.", "",
                  f"거점별 건물 합산 {total:,}동(거점 간 중복 포함). 이력 연결 {before:,} → {after:,}동 "
                  f"({before / total:.2%} → {after / total:.2%}).", "",
                  f"지번별 기록 추가 {sum(r['history_records_added'] for r in compared):,}건, "
                  f"제거 {sum(r['history_records_removed'] for r in compared):,}건. "
                  "구 코드 혼합으로 다른 지번에 붙었던 기록과 불완전한 지번 주소의 제외를 포함한다.", ""]
    deploy = report.get("deployment", {})
    if deploy:
        lines += [f"배포 파일 미추적 {len(deploy['untracked'])}개, ignore 규칙에 막힌 파일 "
                  f"{len(deploy['ignored_by_rules'])}개.", ""]
    lines += [f"- {s}" for s in report["limitations"]]
    lines += ["", "|거점|Tier|대표 커버리지 %|기존 이력 동/전체|후보 이력 동|연결 증감|층 매물|집계구/셀|오류|",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        h, c, f = r.get("history", {}), r.get("candidate_history", {}), r["footfall"]
        lines.append(f"|{r['name']} ({r['slug']})|{r['tier']}|{r['reference_coverage_pct']}|"
                     f"{h.get('linked')}/{h.get('buildings')}|{c.get('linked', '미생성')}|"
                     f"{r.get('history_link_delta', '미검증')}|{r.get('floors', {}).get('units')}|"
                     f"{f['oa_count']}/{f['cells']}|{len(r['errors'])}|")
    for r in rows:
        if r["errors"]:
            lines += ["", f"## {r['slug']} 오류", ""] + [f"- {s}" for s in r["errors"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path)
    args = parser.parse_args()
    report = audit(ROOT / "data" / "gold", ACTIVE_HUBS, args.candidate_root)
    report["deployment"] = deployment(ROOT / "data" / "gold", ACTIVE_HUBS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    errors = len(report["global_errors"]) + sum(len(r["errors"]) for r in report["hubs"])
    print(f"hubs={report['hub_count']} errors={errors} report={args.output}")
    return 1 if errors or report["deployment"]["untracked"] or report["deployment"]["ignored_by_rules"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
