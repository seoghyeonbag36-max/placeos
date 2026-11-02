"""전주 2구 완주 인허가 원본을 점포 주소의 구·동으로 나눈다. 일반음식점만 포함한다."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from data.collectors.common import latest_bronze, load_latest, save_json
from data.collectors.gg_licensing import _place
from data.config.page_hubs import JEONJU_HUBS

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "bronze" / "jeonju_licensing"
_LABEL = "일반음식점"


def _find_rows(obj) -> list[dict]:
    """응답 JSON 에서 행 리스트를 찾는다 — 래퍼 구조가 바뀌어도 깨지지 않게 가장 큰 dict 리스트를 쓴다."""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and len(obj[0]) > 8:
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_rows(v)
            if found:
                return found
    return []


def norm(r: dict) -> dict:
    """행안부 일반음식점 1행 → 서울 인허가 스키마(소비층 계약). `CRS` 는 일부러 안 단다(모듈 머리말)."""
    state = str(r.get("SALS_STTS_NM") or "").strip()
    return {
        "MGTNO": r.get("MNG_NO"),
        "BPLCNM": r.get("BPLC_NM"),
        "UPTAENM": r.get("BZSTAT_SE_NM") or r.get("SNTTN_BZSTAT_NM"),
        # 서울 코드로 옮긴다 — 소비층이 「01」 과 이름의 「영업」 둘 다 본다
        "TRDSTATEGBN": "01" if "영업" in state else "02",
        "TRDSTATENM": state,
        "DTLSTATEGBN": None,
        "DTLSTATENM": r.get("DTL_SALS_STTS_NM"),
        "DCBYMD": r.get("CLSBIZ_YMD"),
        "APVPERMYMD": r.get("LCPMT_YMD"),
        "SITEWHLADDR": r.get("LOTNO_ADDR"),
        "RDNWHLADDR": r.get("ROAD_NM_ADDR"),
        "SITEAREA": r.get("LCTN_AREA"),
        "X": r.get("CRD_INFO_X"),
        "Y": r.get("CRD_INFO_Y"),
    }


def hub_places(slug: str) -> set[tuple[str, str]]:
    """거점 점포 주소의 (구, 동) 집합."""
    out: set[tuple[str, str]] = set()
    for s in load_latest(slug, "stores_raw.json") or []:
        p = _place(str(s.get("lnoAdr") or ""))
        if p:
            out.add((p[1], p[2]))
    return out


def bucket(rows: list[dict], places: dict[str, set[tuple[str, str]]]) -> dict[str, list[dict]]:
    """행을 거점 버킷으로 나눈다. 주소를 못 읽은 행은 버린다(어느 거점도 아니다)."""
    index: dict[tuple[str, str], list[str]] = {}
    for slug, pl in places.items():
        for key in pl:
            index.setdefault(key, []).append(slug)
    out: dict[str, list[dict]] = {s: [] for s in places}
    for r in rows:
        p = _place(str(r.get("LOTNO_ADDR") or ""))
        if not p:
            continue
        for slug in index.get((p[1], p[2]), ()):
            out[slug].append(norm(r))
    return out


def load_source_rows() -> list[dict]:
    """도시 단위 완주·고유 관리번호 건수를 확인한다. 부분 원본은 쓰지 않는다."""
    markers = sorted(SRC.glob('*/city_complete.json'))
    if not markers:
        raise SystemExit('[jj-lic] 전주 인허가 완주 원본 없음')
    marker = markers[-1]
    report = json.loads(marker.read_text(encoding='utf-8'))
    rows = json.loads((marker.parent / 'city_rows.json').read_text(encoding='utf-8'))
    if not report.get('complete') or len(rows) != report['rows'] or len({r['MNG_NO'] for r in rows}) != len(rows):
        raise SystemExit('[jj-lic] 전주 인허가 완주 검증 불일치')
    return rows


def main(argv: list[str]) -> None:
    force = "--force" in argv
    slugs = [a for a in argv if not a.startswith("-")] or list(JEONJU_HUBS)
    unknown = [s for s in slugs if s not in JEONJU_HUBS]
    if unknown:
        raise SystemExit(f"[jj-lic] 전주 거점이 아니다: {unknown}")
    todo = [s for s in slugs if force or latest_bronze(s, "licensing_biz.json") is None]
    if not todo:
        print("[jj-lic] 이미 있음 — 건너뜀 (--force 로 다시)")
        return
    places = {s: hub_places(s) for s in todo}
    empty = [s for s, p in places.items() if not p]
    if empty:
        raise SystemExit(f"[jj-lic] 점포 원본이 없어 대상 동을 못 만든다: {empty}")
    rows = load_source_rows()
    parts = bucket(rows, places)
    print(f"[jj-lic] 원본 {len(rows):,}행 → 거점 {len(todo)}곳")
    for s in todo:
        alive = sum(1 for r in parts[s] if r["TRDSTATEGBN"] == "01" and not (r.get("DCBYMD") or "").strip())
        save_json(parts[s], s, "licensing_biz.json")
        print(f"[jj-lic:{s}] {len(parts[s]):,}행 (영업 {alive:,}) · 동 {len(places[s])}개")


if __name__ == "__main__":
    main(sys.argv[1:])
