"""광주 거점별 인허가 — `gwangju_licensing` 의 5구 원본을 거점 버킷(licensing_biz.json)으로 나눈다 (2026-10-31).

`gwangju_licensing.py` 는 행안부 일반음식점 API 를 구 단위 페이지 원본으로만 저장한다. Page Gold 의 분자 보강
(`build_page_master._licensed_pip`)과 건물 이력(`build_building_history`)은 **거점별 `bronze/{slug}/{날짜}/licensing_biz.json`
(서울 인허가와 같은 스키마)** 을 읽으므로, 이 어댑터가 그 사이를 잇는다. 없으면 광주 Gold 는 인허가 없이 서고 공실이 과대다
(경기 10-28 실측: 수원역 +2.4 → −0.5%p).

## 좌표계
행안부 응답의 `CRD_INFO_X/Y` 는 서울 인허가와 같은 중부원점 TM 이다(광주 X≈182k · Y≈185k — 서부원점이면 X 가 360k 대).
그래서 **`CRS` 를 달지 않는다** — 소비층이 서울 경로(EPSG:2097 → 4326 + 주소 매칭 자가 보정)를 그대로 탄다.
경기(`gg_licensing`)처럼 `CRS: EPSG:4326` 을 달면 변환을 건너뛰어 PIP 가 조용히 0건이 된다.

## 거점 귀속
거점의 점포 주소(`lnoAdr`)에서 (시도, 구, 동) 집합을 파생한다(`gg_licensing._hub_places` 와 같은 원칙 — 반경이 바뀌어도 낡지 않는다).
같은 동이 두 거점에 걸치면 양쪽에 담는다. 이것은 거친 필터이고, 건물 귀속은 좌표 PIP 가 정한다.

실행: python -m data.collectors.gwangju_licensing_hubs [slug ...] [--force]   (비우면 GWANGJU_HUBS 전부)
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

from data.collectors.common import latest_bronze, load_latest, save_json
from data.collectors.gg_licensing import _place
from data.config.page_hubs import GWANGJU_HUBS

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "bronze" / "gwangju_licensing"
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
    """5구 원본 전량 — 구별 `_complete.json` 이 없으면(= 수집이 끝나지 않았다) 중단한다. 부분 원본은 쓰지 않는다."""
    latest = sorted(p for p in SRC.glob("*") if p.is_dir())
    if not latest:
        raise SystemExit("[gj-lic] data/bronze/gwangju_licensing 이 없다 — python -m data.collectors.gwangju_licensing 먼저")
    day = latest[-1]
    gus = sorted(day.glob("*_complete.json"))
    if len(gus) < 5:
        raise SystemExit(f"[gj-lic] {day.name} 에 완주한 구가 {len(gus)}/5 다 — 수집을 마친 뒤에 돌릴 것")
    rows: list[dict] = []
    for gu in gus:
        stem = gu.name.replace("_complete.json", "")
        for page in sorted(day.glob(f"{stem}_*_0*.json")):
            rows.extend(_find_rows(json.loads(page.read_text(encoding="utf-8"))))
    return rows


def main(argv: list[str]) -> None:
    force = "--force" in argv
    slugs = [a for a in argv if not a.startswith("-")] or list(GWANGJU_HUBS)
    unknown = [s for s in slugs if s not in GWANGJU_HUBS]
    if unknown:
        raise SystemExit(f"[gj-lic] 광주 거점이 아니다: {unknown}")
    todo = [s for s in slugs if force or latest_bronze(s, "licensing_biz.json") is None]
    if not todo:
        print("[gj-lic] 이미 있음 — 건너뜀 (--force 로 다시)")
        return
    places = {s: hub_places(s) for s in todo}
    empty = [s for s, p in places.items() if not p]
    if empty:
        raise SystemExit(f"[gj-lic] 점포 원본이 없어 대상 동을 못 만든다: {empty}")
    rows = load_source_rows()
    parts = bucket(rows, places)
    print(f"[gj-lic] 원본 {len(rows):,}행 → 거점 {len(todo)}곳")
    for s in todo:
        alive = sum(1 for r in parts[s] if r["TRDSTATEGBN"] == "01" and not (r.get("DCBYMD") or "").strip())
        save_json(parts[s], s, "licensing_biz.json")
        print(f"[gj-lic:{s}] {len(parts[s]):,}행 (영업 {alive:,}) · 동 {len(places[s])}개")


if __name__ == "__main__":
    main(sys.argv[1:])
