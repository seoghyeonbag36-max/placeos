"""[Page] 체크리스트 수집분을 표준 bronze 스냅샷으로 옮긴다 — **API 콜 없음**.

2026-10-09 체크리스트 수집(`acquire_checklist_sources` · `complete_checklist_acquisition`)은
원본 보존을 위해 `bronze/api_acquisition/<날짜>/<실행>/` 에 응답 페이지를 그대로 남겼다.
Page 체인은 `bronze/<거점>/<날짜>/stores_raw.json` · `licensing_biz.json` 만 읽으므로
그 원본은 수집만 되고 서빙에 닿지 않았다(data/placeos-data-acquisition-result-2026-10-09.md
"기존 표준 수집 경로에 자동 덮어쓰지 않았으므로 … 별도 정규화·집계·검증 연결이 필요하다").
이 모듈이 그 연결이다. 수집기와 **같은 규칙**으로 변환해 수집일 폴더에 쓴다.

  stores_raw.json     상가정보 `storeListInRadius` 페이지의 body.items 를 이어 붙인다.
                      요청이 `building_vacancy.fetch_stores` 와 같다(엔드포인트·반경
                      `stores_radius_m`·중심 cx/cy·1000행 페이징) — 형식도 같은 list[dict].
                      거점별 수집 상태는 manifest 로 고른다: 최초 실패분은 recovery 원본을 쓴다
                      (2026-10-09 suyu: 2페이지에서 끊김 → recovery 5페이지 4,050행).
  licensing_biz.json  서울 LOCALDATA 전역 페이지를 `seoul_licensing` 과 같은 (구,동) 필터·
                      `_KEEP` 필드·`svc` 라벨로 거점에 나눈다. **완주한 업종만** 새 값으로 바꾼다
                      (모든 페이지 행 합 == list_total_count). 미완주 업종(첫 페이지만 받은
                      프로브 등)은 직전 거점 스냅샷의 그 업종 행을 그대로 옮긴다 — 업종이 빠진
                      파일이 최신이 되면 그 업종의 층 근거가 통째로 사라지기 때문이다.
                      업종별 출처(새 값/이월+원 날짜)는 변환 기록에 남긴다.

쓰기 규칙
  · 이미 같은 내용이면 쓰지 않는다(같은 원천 분기를 다시 받은 거점 — 중복 스냅샷 방지).
  · 대상 날짜보다 새 스냅샷이 이미 있으면 쓰지 않는다 — 옛 날짜 폴더는 최신이 되지 못한다.
  · 대상 날짜 폴더에 다른 내용이 이미 있으면 덮어쓰지 않는다(--force 로만).
  · 변환 기록: <실행 폴더>/import_manifest.json (거점·업종별 결과, 출력 sha256).

실행:
  python -m data.collectors.import_acquisition data/bronze/api_acquisition/2026-10-09/215933 --dry-run
  python -m data.collectors.import_acquisition data/bronze/api_acquisition/2026-10-09/215933
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

from data.collectors.common import BRONZE, DATA_ROOT, latest_bronze, save_json
from data.collectors.seoul_licensing import _GU_DONG, _KEEP, SERVICES, _hub_pairs
from data.config.page_hubs import ACTIVE_HUBS

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NL = chr(10)


def _pages(d: Path) -> list[Path]:
    """NNN.json 응답 페이지(메타 제외)를 페이지 번호 순으로."""
    return sorted(p for p in d.glob("*.json") if not p.name.endswith(".meta.json"))


def _run_date(run: Path) -> str:
    """bronze/api_acquisition/<YYYY-MM-DD>/<실행> → 수집일."""
    for part in (run.name, run.parent.name):
        if _DATE.match(part):
            return part
    raise SystemExit(f"[import] 실행 폴더에서 수집일을 못 읽었다: {run} — --date 로 지정")


def _store_status(run: Path) -> dict[str, str]:
    """거점별 상가정보 수집 상태 — recovery 가 최초 결과를 덮는다."""
    status: dict[str, str] = {}
    first = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    for e in first.get("entries") or []:
        src = str(e.get("source", ""))
        if src.startswith("stores/"):
            status[src.split("/", 1)[1]] = e.get("status", "")
    rec = run / "recovery_manifest.json"
    if rec.exists():
        for e in json.loads(rec.read_text(encoding="utf-8")) or []:
            src = str(e.get("source", ""))
            if src.startswith("stores/") and e.get("status") == "complete":
                status[src.split("/", 1)[1]] = "recovered"
    return status


def _read_stores(run: Path, slug: str, how: str) -> tuple[list[dict], dict]:
    """페이지 → (점포 list, 검증 정보). 완주가 아니면 빈 list."""
    d = run / ("recovery/stores" if how == "recovered" else "stores") / slug
    rows: list[dict] = []
    total = stdr = None
    for p in _pages(d):
        blob = json.loads(p.read_text(encoding="utf-8"))
        body = blob.get("body") or {}
        if total is None:
            total = int(body.get("totalCount") or 0)
            stdr = (blob.get("header") or {}).get("stdrYm")
        rows += body.get("items") or []
    ids = [r.get("bizesId") for r in rows]
    info = {"source": _rel(d), "pages": len(_pages(d)),
            "rows": len(rows), "total": total, "stdrYm": stdr,
            "unique_ids": len(set(ids)), "missing_ids": sum(1 for i in ids if not i)}
    ok = (total is not None and len(rows) == total and info["unique_ids"] == len(rows)
          and not info["missing_ids"])
    return (rows if ok else []), info | {"complete": ok}


def _canon(rows: list[dict]) -> str:
    """내용 비교용 정규형 — 행 순서와 무관하게 같은 점포 집합·같은 값이면 같다."""
    return hashlib.sha256(NL.join(sorted(json.dumps(r, ensure_ascii=False, sort_keys=True)
                                         for r in rows)).encode("utf-8")).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(p: Path) -> str:
    """data/ 기준 상대경로(기록용). 밖이면 그대로."""
    try:
        return str(p.relative_to(DATA_ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def _decide(slug: str, name: str, date: str, rows: list[dict], force: bool) -> tuple[str, Path | None]:
    """쓸지 말지 — (사유, 비교 대상 경로)."""
    latest = latest_bronze(slug, name)
    if latest is not None:
        ldate = latest.parent.name
        if ldate > date:
            return f"skip_newer_exists({ldate})", latest
        if _canon(json.loads(latest.read_text(encoding="utf-8"))) == _canon(rows):
            return f"unchanged({ldate})", latest
        if ldate == date and not force:
            return "skip_conflict_same_date", latest
    return "write", latest


def import_stores(run: Path, date: str, apply: bool, force: bool) -> tuple[dict, dict[str, list[dict]]]:
    """상가정보 → 거점 stores_raw.json. 반환: (거점별 기록, 거점별 점포 — 인허가 필터용)."""
    status = _store_status(run)
    out: dict[str, dict] = {}
    snap: dict[str, list[dict]] = {}
    for slug in ACTIVE_HUBS:
        how = status.get(slug, "")
        if how not in ("complete", "recovered"):
            out[slug] = {"result": f"skip_not_complete({how or 'absent'})"}
            continue
        rows, info = _read_stores(run, slug, how)
        if not rows:
            out[slug] = info | {"result": "skip_incomplete_pages"}
            continue
        result, prev = _decide(slug, "stores_raw.json", date, rows, force)
        rec = info | {"result": result,
                      "previous": _rel(prev) if prev else None}
        if prev is not None and result == "write":
            old = {r.get("bizesId") for r in json.loads(prev.read_text(encoding="utf-8"))}
            new = {r.get("bizesId") for r in rows}
            rec |= {"prev_rows": len(old), "added_ids": len(new - old), "dropped_ids": len(old - new)}
        if result == "write" and apply:
            path = save_json(rows, slug, "stores_raw.json", date=date)
            rec["sha256"] = _sha(path)
        out[slug] = rec
        # 인허가 (구,동) 필터는 **이 스냅샷이 최신이 된 뒤의** 점포로 만든다(수집기와 같은 입력).
        snap[slug] = rows if result.startswith(("write", "unchanged")) else []
    return out, snap


def _service_pages(run: Path, sid: str) -> tuple[list[Path], bool, dict]:
    """업종 하나의 전역 페이지와 완주 여부."""
    d = run / "seoul" / sid / "all"
    pages = _pages(d) if d.is_dir() else []
    n = 0
    total = None
    for p in pages:
        blk = json.loads(p.read_text(encoding="utf-8")).get(sid) or {}
        if not blk:
            return pages, False, {"pages": len(pages), "error": f"no_block:{p.name}"}
        total = int(blk.get("list_total_count") or 0)
        n += len(blk.get("row") or [])
    ok = bool(pages) and total is not None and n == total
    return pages, ok, {"pages": len(pages), "rows": n, "total": total}


def import_licensing(run: Path, date: str, snap: dict[str, list[dict]], apply: bool,
                     force: bool) -> dict:
    """서울 LOCALDATA 전역 페이지 → 거점 licensing_biz.json (완주 업종 교체 + 미완주 업종 이월)."""
    targets = [s for s, rows in snap.items() if rows]
    idx: dict[tuple[str, str], list[str]] = {}
    for s in targets:
        for pair in _hub_pairs(s, snap[s]):
            idx.setdefault(pair, []).append(s)

    stage = BRONZE / "_import_stage" / run.name
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True, exist_ok=True)
    services: dict[str, dict] = {}
    for label, sid in SERVICES.items():
        pages, ok, info = _service_pages(run, sid)
        services[label] = info | {"sid": sid, "complete": ok}
        if not ok:
            continue
        # 업종 하나씩 흘려 거점 jsonl 에 떨군다 — 일반음식점 한 종의 거점 적재가 57만 행이라
        # 메모리에 쌓지 않는다(seoul_licensing._merge_to_bronze 와 같은 이유).
        handles: dict[str, object] = {}
        kept = 0
        try:
            for p in pages:
                for r in (json.loads(p.read_text(encoding="utf-8")).get(sid) or {}).get("row") or []:
                    m = _GU_DONG.search(str(r.get("SITEWHLADDR", "")))
                    hits = idx.get((m.group(1), m.group(2))) if m else None
                    if not hits:
                        continue
                    row = {k: r.get(k) for k in _KEEP}
                    row["svc"] = label
                    line = json.dumps(row, ensure_ascii=False) + NL
                    for s in hits:
                        if s not in handles:
                            handles[s] = (stage / f"{s}.{sid}.jsonl").open("w", encoding="utf-8")
                        handles[s].write(line)
                        kept += 1
        finally:
            for h in handles.values():
                h.close()
        services[label]["hub_rows"] = kept

    hubs: dict[str, dict] = {}
    for s in targets:
        prev_path = latest_bronze(s, "licensing_biz.json")
        prev = json.loads(prev_path.read_text(encoding="utf-8")) if prev_path else []
        prev_date = prev_path.parent.name if prev_path else None
        rows: list[dict] = []
        per: dict[str, dict] = {}
        for label, sid in SERVICES.items():
            if services[label]["complete"]:
                p = stage / f"{s}.{sid}.jsonl"
                part = [json.loads(ln) for ln in p.open(encoding="utf-8")] if p.exists() else []
                per[label] = {"from": date, "rows": len(part)}
            else:
                part = [r for r in prev if r.get("svc") == label]
                per[label] = {"from": f"carried:{prev_date}", "rows": len(part)}
            rows += part
        result, latest = _decide(s, "licensing_biz.json", date, rows, force)
        rec = {"result": result, "rows": len(rows), "prev_rows": len(prev), "prev_date": prev_date,
               "by_service": per}
        if result == "write" and apply:
            path = save_json(rows, s, "licensing_biz.json", date=date)
            rec["sha256"] = _sha(path)
        hubs[s] = rec
    shutil.rmtree(stage, ignore_errors=True)
    return {"services": services, "hubs": hubs}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split(NL)[0])
    ap.add_argument("run", help="bronze/api_acquisition/<날짜>/<실행> 폴더")
    ap.add_argument("--date", help="쓸 스냅샷 날짜(기본: 실행 폴더의 수집일)")
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 결과만 출력")
    ap.add_argument("--force", action="store_true", help="같은 날짜에 다른 내용이 있어도 덮어쓴다")
    ap.add_argument("--no-licensing", action="store_true")
    args = ap.parse_args()

    # resolve() 는 쓰지 않는다 — bronze 가 junction 인 작업 트리에서 실제 경로로 풀리면
    # DATA_ROOT 기준 상대경로가 깨진다.
    run = Path(args.run).absolute()
    if not (run / "manifest.json").exists():
        raise SystemExit(f"[import] manifest.json 없음: {run}")
    date = args.date or _run_date(run)
    apply = not args.dry_run

    stores, snap = import_stores(run, date, apply, args.force)
    c = Counter(v["result"].split("(")[0] for v in stores.values())
    print(f"[import] 상가정보 {len(stores)}거점 → {dict(c)}")
    for s, v in stores.items():
        if v["result"] == "write":
            print(f"  {s:18s} {v.get('prev_rows', 0):6d} → {v['rows']:6d}행 "
                  f"(+{v.get('added_ids', 0)} / -{v.get('dropped_ids', 0)}) stdrYm={v.get('stdrYm')}")
        elif not v["result"].startswith("unchanged"):
            print(f"  {s:18s} {v['result']}")

    lic = None
    if not args.no_licensing:
        lic = import_licensing(run, date, snap, apply, args.force)
        done = [k for k, v in lic["services"].items() if v["complete"]]
        carried = [k for k, v in lic["services"].items() if not v["complete"]]
        print(f"[import] 인허가 완주 {len(done)}종 교체 · 미완주 {len(carried)}종 이월: {', '.join(carried)}")
        c = Counter(v["result"].split("(")[0] for v in lic["hubs"].values())
        print(f"[import] 인허가 {len(lic['hubs'])}거점 → {dict(c)}")

    record = {"run": _rel(run), "date": date,
              "applied": apply, "stores": stores, "licensing": lic}
    if apply:
        dst = run / "import_manifest.json"
        dst.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[import] 변환 기록 → {_rel(dst)}")
    else:
        print("[import] dry-run — 아무것도 쓰지 않았다.")


if __name__ == "__main__":
    sys.exit(main())
