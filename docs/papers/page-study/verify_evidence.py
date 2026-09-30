"""보존 감사의 해시·집계와 새 체크아웃의 Gold→서빙을 검증한다. 원본은 읽기 전용이다."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import statistics
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
AUDIT = ROOT / "docs/papers/audits/page-analysis-20260906"
INPUT = ROOT / "docs/papers/audits/page-inventory-20260906/manifest.json"
READ_HASHES: dict[str, str] = {}
# baseline-serving 을 마지막으로 재현한 체크아웃(evidence-verification.json 의 09-07 실행).
# Gold→서빙 재계산은 이 커밋의 코드로 한다. 그 뒤 코드는 거점을 늘리고(66→81, 09-24)
# 서빙 결과에 키를 더했다(aligned_*, 09-28) — 동결 근거와 등식으로 비교할 대상이 아니다.
SERVING_CODE_COMMIT = "4a0dea0eeb55c69335ec6bdfea41f19bf481db42"
SERVING_CODE_PATHS = ["apps/backend/app", "data/__init__.py", "data/config"]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def eol_match(path: Path, expected: str) -> str | None:
    """매니페스트 해시와 어떻게 맞았는지 돌려준다. 안 맞으면 None.

    매니페스트는 Windows 체크아웃(autocrlf)에서 만들어졌고, 저장소 안의 텍스트 Gold 는 LF 다
    (`.gitattributes` 의 `* text=auto`). 그래서 같은 데이터도 체크아웃 플랫폼에 따라 바이트가
    다르다. 원본 바이트를 먼저 비교하고, 안 맞을 때만 줄바꿈을 CRLF·LF 로 정규화한 바이트를
    비교한다. 해시 비교는 건너뛰지 않는다 — 줄바꿈 말고 한 바이트라도 다르면 None 이다.
    """
    if sha(path) == expected:
        return "raw"
    lf = path.read_bytes().replace(b"\r\n", b"\n")
    for mode, data in (("crlf_normalized", lf.replace(b"\n", b"\r\n")), ("lf_normalized", lf)):
        if hashlib.sha256(data).hexdigest() == expected:
            return mode
    return None


def extract_serving_code(dest: Path) -> None:
    """동결 커밋의 서빙 코드를 dest 에 푼다. 작업 트리·.git 은 건드리지 않는다(git archive)."""
    try:
        blob = subprocess.run(["git", "archive", "--format=tar", SERVING_CODE_COMMIT, *SERVING_CODE_PATHS],
                              cwd=ROOT, check=True, capture_output=True).stdout
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"동결 커밋 {SERVING_CODE_COMMIT[:8]} 을 읽을 수 없다(얕은 클론이면 "
                         f"`git fetch --unshallow`): {e.stderr.decode(errors='replace').strip()}") from e
    with tempfile.TemporaryFile() as f:
        f.write(blob)
        f.seek(0)
        with tarfile.open(fileobj=f) as tar:
            tar.extractall(dest, filter="data")


def read(path: Path) -> Any:
    READ_HASHES[path.relative_to(ROOT).as_posix()] = sha(path)
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def guard(event: str, args: tuple[Any, ...]) -> None:
    if event == "socket.connect":
        raise RuntimeError("검증 중 외부 연결 금지")
    if event == "open":
        path, mode, flags = args
        writing = isinstance(mode, str) and any(c in mode for c in "wax+")
        writing |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing and isinstance(path, (str, bytes, os.PathLike)):
            if not Path(os.fsdecode(path)).resolve().is_relative_to(OUT.resolve()):
                raise RuntimeError("연구 출력 경계 밖 쓰기 금지")


def main() -> None:
    started = datetime.now(timezone.utc).isoformat()
    tracked = set(subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True, encoding="utf-8").splitlines())
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8").strip()
    # 가드를 걸기 전에 푼다 — 연구 출력 경계 밖(임시 디렉터리) 쓰기는 이것 하나뿐이다.
    frozen = Path(tempfile.mkdtemp(prefix="verify-evidence-"))
    try:
        extract_serving_code(frozen)
        sys.addaudithook(guard)
        run(started, tracked, commit, frozen)
    finally:
        shutil.rmtree(frozen, ignore_errors=True)


def run(started: str, tracked: set[str], commit: str, frozen: Path) -> None:
    hashes = read(AUDIT / "output-hashes.json")
    availability: list[dict[str, Any]] = []
    for item in hashes:
        path = AUDIT / item["path"]
        present = path.is_file()
        availability.append({"path": item["path"], "tracked": path.relative_to(ROOT).as_posix() in tracked,
                             "present": present, "hash_matches": sha(path) == item["sha256"] if present else None})
    invalid = [r for r in availability if r["hash_matches"] is False or (r["tracked"] and not r["present"])]
    assert not invalid, invalid
    manifest = read(INPUT)
    assert sha(INPUT) == INPUT.with_name("manifest.sha256").read_text().split()[0]
    data_availability = []
    for item in manifest["files"]:
        path = ROOT / item["path"]
        mode = eol_match(path, item["sha256"]) if path.is_file() else None
        data_availability.append({"path": item["path"], "layer": item["layer"], "present": path.is_file(),
                                  "hash_matches": mode is not None if path.is_file() else None,
                                  "hash_match_mode": mode})
    mismatched = [r["path"] for r in data_availability if r["hash_matches"] is False]
    assert not mismatched, mismatched
    audit = read(AUDIT / "structural-audit.json")
    rows = audit["hubs"]
    names = sorted(r["hub"] for r in rows)
    assert len(names) == len(set(names))
    rules = audit["rules"]
    polygons = sum(r["polygons"] for r in rows)
    assert polygons == rules["master_id_unique"]["pass"]
    copies = []
    for hub in names:
        base = read(AUDIT / "baseline-serving" / f"{hub}.json")
        first = read(AUDIT / "repeat-a/serving" / f"{hub}.json")
        second = read(AUDIT / "repeat-b/serving" / f"{hub}.json")
        assert base == first == second, hub
        cells = base["cells"]
        assert len({(c["i"], c["j"]) for c in cells}) == len(cells), hub
        for k, cell_key in [("capacity", "capacity"), ("sum_stores", "stores"),
                            ("sum_vac", "vac_n"), ("buildings", "buildings")]:
            assert sum(c[cell_key] for c in cells) == base[k], (hub, k)
        for c in cells:
            assert c["vac_n"] == c["capacity"] - c["stores"]
            assert c["v"] == round(100 * c["vac_n"] / c["capacity"], 2)
        assert base["avg_vacancy"] == round(100 * base["sum_vac"] / base["capacity"], 2)
        copies.append({"hub": hub, "stored_three_serving_copies_equal": True,
                       "cell_reaggregation_pass": True, "baseline_semantic_sha256": canonical(base)})
    order = read(AUDIT / "order-sensitivity.json")
    assert Counter(r["hub"] for r in order) == Counter({h: 3 for h in names})
    variants = {"reverse", "sort_by_id", "shuffle_seed_20260906"}
    assert all({r["variant"] for r in order if r["hub"] == h} == variants for h in names)
    affected = {r["hub"] for r in order if r["entered_cells"] or r["exited_cells"] or r["changed_common_capacity_or_active"]}
    widths = read(AUDIT / "impact-intervals.json")
    assert sorted(r["hub"] for r in widths) == names
    for r in widths:
        assert math.isclose(r["range_width_pp"], r["floor_vacancy_upper_pct"] - r["floor_vacancy_lower_pct"], abs_tol=1e-12)
    sample = read(AUDIT / "sample-design.json")
    sample_path = AUDIT / "independent-review-sample.csv"
    READ_HASHES[sample_path.relative_to(ROOT).as_posix()] = sha(sample_path)
    with sample_path.open(encoding="utf-8-sig", newline="") as f:
        labels = list(csv.DictReader(f))
    assert len(labels) == sample["actual_sample"]
    assert all(r["review_label"] == "unresolved" for r in labels)

    # 새 체크아웃에 있는 배포 Gold만 사용한다. Bronze→Gold 전체 재빌드는 아니다.
    # 코드는 동결 커밋 것(SERVING_CODE_COMMIT), Gold 는 이 체크아웃 것 — 위 매니페스트 해시로 확인한 그 파일이다.
    sys.path[:0] = [str(frozen), str(frozen / "apps/backend")]
    from app.services import building_vacancy, gold_vacancy
    building_vacancy._GOLD_DIR = gold_vacancy._GOLD_DIR = ROOT / "data/gold"
    from app.data.seoul_pages import DISTRICTS_BY_ID
    from app.data.measured_pages import _grid
    from data.config.page_hubs import ACTIVE_HUBS
    assert sorted(ACTIVE_HUBS) == names
    fresh = []
    for hub in names:
        master = ROOT / f"data/gold/{hub}/page_building_master.geojson"
        READ_HASHES[master.relative_to(ROOT).as_posix()] = sha(master)
        calibration = ROOT / f"data/gold/{hub}/calibration.json"
        if calibration.is_file():
            READ_HASHES[calibration.relative_to(ROOT).as_posix()] = sha(calibration)
        grid = DISTRICTS_BY_ID[hub]["grid"] if hub in DISTRICTS_BY_ID else _grid(ACTIVE_HUBS[hub])
        result = gold_vacancy.build_cells(hub, grid)
        old = read(AUDIT / "baseline-serving" / f"{hub}.json")
        assert result is not None and result == old, hub
        fresh.append({"hub": hub, "matches_archived_serving": True, "semantic_sha256": canonical(result)})
    imported_code = []
    for module in list(sys.modules.values()):
        file = getattr(module, "__file__", None)
        if not (file and Path(file).is_file()):
            continue
        p = Path(file).resolve()
        for base, origin in ((frozen.resolve(), SERVING_CODE_COMMIT), (ROOT.resolve(), "checkout")):
            if p.is_relative_to(base):
                imported_code.append({"path": p.relative_to(base).as_posix(), "origin": origin, "sha256": sha(p)})
                break
    assert all(sha(ROOT / p) == expected for p, expected in READ_HASHES.items())
    result = {
        "scope": "archived_evidence_reaggregation_and_fresh_checkout_gold_to_serving",
        "started_at_utc": started, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "checkout_commit": commit, "serving_code_commit": SERVING_CODE_COMMIT, "verifier_sha256": sha(Path(__file__)), "python": sys.version,
        "summary": {
            "available_archived_hashes_match": sum(r["present"] for r in availability),
            "unavailable_archived_files": sum(not r["present"] for r in availability),
            "inventory_files": len(data_availability), "inventory_present": sum(r["present"] for r in data_availability),
            "inventory_missing": sum(not r["present"] for r in data_availability),
            "inventory_hash_match_modes": dict(sorted(Counter(r["hash_match_mode"] for r in data_availability
                                                              if r["present"]).items())),
            "hubs": len(names), "polygons": polygons,
            "floor_checked_polygons": rules["floor_semantics"]["pass"],
            "temporal_not_evaluable_hubs": rules["temporal_observation_alignment"]["not_evaluable"],
            "stored_serving_comparisons_pass": len(copies), "cell_reaggregation_pass": len(copies),
            "fresh_gold_to_serving_matches": len(fresh), "order_trials": len(order),
            "order_aggregate_changed_trials": sum(not r["aggregate_unchanged"] for r in order),
            "order_cell_affected_hubs": len(affected),
            "floor_interval_median_width_pp": statistics.median(r["range_width_pp"] for r in widths),
            "floor_interval_max_width_pp": max(r["range_width_pp"] for r in widths),
            "unresolved_review_sample": len(labels), "all_consumed_inputs_unchanged": True},
        "not_claimed": ["full_bronze_to_gold_reproduction", "cloud_environment_execution", "independent_human_validation",
                        "field_vacancy_accuracy", "causal_improvement", "independent_team_replication"],
        "archived_file_availability": availability, "data_availability": data_availability,
        "serving_checks": copies, "fresh_serving_checks": fresh,
        "consumed_files": READ_HASHES, "imported_repository_code": sorted(imported_code, key=lambda x: x["path"])}
    (OUT / "evidence-verification.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
