"""[Page·분자 보강] NEIS 학원·교습소 — bronze 정규화와 로더 (**API 콜 없음**).

나이스 학원교습소정보(`acaInsTiInfo`, 서울교육청 B10)는 상세주소(`FA_RDNDA`)에 층을 적는다
(", 3층 301호 (개포동, 삼성빌딩)" — 2026-10-10 수집분 25,527건 중 62.4%). 상가정보 flrNo 공란과
인허가가 못 덮는 상층부 학원의 **층 근거**다. 소비처: pipelines/build_building_attrs (aca_flr_nos).

수집 원본은 `acquire_priority_public` 이 `bronze/priority_acquisition/<날짜>/<실행>/neis_NNN.json`
페이지로 남겼다. 이 모듈은 그 페이지를 검증해 한 파일로 모은다:

  bronze/neis/<날짜>/academies_raw.json   응답 행(row) 그대로의 list — 필드를 고치지 않는다

검증: 모든 페이지의 행 합 == list_total_count · ACA_ASNUM 중복 0 · 교육청 코드 전부 B10.
하나라도 어긋나면 쓰지 않는다(부분 수집본이 최신이 되면 학원 층 근거가 조용히 줄어든다).

⚠ 공개 교습비·정원은 실제 수납·재원생이 아니다. 여기서는 **영업 위치와 층**만 쓴다.
TODO(갱신): 재수집은 `acquire_priority_public`(NEIS_API_KEY) → 이 모듈 import 순서다.

실행:
  python -m data.collectors.neis_academies import data/bronze/priority_acquisition/2026-10-10/125226 --dry-run
  python -m data.collectors.neis_academies import data/bronze/priority_acquisition/2026-10-10/125226
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from data.collectors.common import latest_bronze, save_json

DISTRICT = "neis"            # bronze/neis/<날짜>/ — 거점 폴더가 아니라 서울 전역 원본
FILE = "academies_raw.json"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def read_run(run: Path) -> tuple[list[dict], dict]:
    """neis_NNN.json 페이지 → (행 list, 검증 정보). 검증을 못 넘으면 빈 list."""
    rows: list[dict] = []
    totals: set[int] = set()
    pages = sorted(run.glob("neis_*.json"))
    for p in pages:
        blocks = json.loads(p.read_text(encoding="utf-8")).get("acaInsTiInfo") or []
        for blk in blocks:
            for h in blk.get("head") or []:
                if "list_total_count" in h:
                    totals.add(int(h["list_total_count"]))
            rows += blk.get("row") or []
    ids = [r.get("ACA_ASNUM") for r in rows]
    info = {"pages": len(pages), "rows": len(rows), "totals": sorted(totals),
            "unique_ids": len(set(ids)),
            "non_b10": sum(1 for r in rows if r.get("ATPT_OFCDC_SC_CODE") != "B10")}
    ok = (len(totals) == 1 and len(rows) == next(iter(totals)) and info["unique_ids"] == len(rows)
          and all(ids) and not info["non_b10"])
    return (rows if ok else []), info | {"complete": ok}


def load_latest_academies() -> list[dict]:
    """가장 최근 정규화본. 없으면 빈 list — 소비처는 학원 층 근거 없이 종전대로 돈다."""
    p = latest_bronze(DISTRICT, FILE)
    return json.loads(p.read_text(encoding="utf-8")) if p else []


def main() -> None:
    ap = argparse.ArgumentParser(description="NEIS 학원·교습소 수집분 → bronze/neis 정규화")
    ap.add_argument("cmd", choices=["import"])
    ap.add_argument("run", help="bronze/priority_acquisition/<날짜>/<실행> 폴더")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    # resolve() 는 쓰지 않는다 — bronze 가 junction 인 작업 트리에서 실제 경로로 풀린다.
    run = Path(args.run).absolute()
    date = next((p for p in (run.name, run.parent.name) if _DATE.match(p)), None)
    if date is None:
        raise SystemExit(f"[neis] 실행 폴더에서 수집일을 못 읽었다: {run}")
    rows, info = read_run(run)
    print(f"[neis] {info}")
    if not rows:
        raise SystemExit("[neis] 검증 실패 — 쓰지 않는다")
    if args.dry_run:
        print(f"[neis] dry-run — bronze/{DISTRICT}/{date}/{FILE} 에 {len(rows)}행을 쓸 예정")
        return
    save_json(rows, DISTRICT, FILE, date=date)


if __name__ == "__main__":
    main()
