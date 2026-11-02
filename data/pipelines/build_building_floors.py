"""[Page] 지번별 전 층 — gold/{거점}/building_floors.json.gz.

층별개요(bronze `bldg_flr_raw`)의 지상·**지하**·옥탑 전 층, 표제부(bronze `bldg_ledger_raw`)의 도로명·사용승인일·층수,
전유부 호실(silver `expos_units.json` — 있는 거점만)을 지번으로 묶는다. 기존 파이프라인은 지상 상업층만 남겨 지하 표기를 버렸다.
판 병합은 기존 규칙이다 — 층별개요·표제부는 날짜 오름차순으로 덮어 최신이 이긴다(`build_vacant_floor_units._load_floor_rows`).

## 건물 id 조인 규칙
건물 id 는 `{pnu}-{n}` 이고 유닛은 그 앞에 `vu-`/`vfu-` 가 붙는다 → `pnu_of_building_id`. 이 파일의 키는 **pnu 뿐**이다.
`n` 은 그 지번의 폴리곤 번호이고 **대장의 동(dongNm)이 아니다** — 같은 지번에 동이 여럿이면 층 행의 `dong` 으로 갈리지만
폴리곤 하나가 어느 동인지는 자료에 없다. 지어내지 말고 지번 단위로 보여 주거나 동을 고르게 한다.

## 층 값
`kind` G 지상 · B 지하 · R 옥탑 · ? 미상, `no` 는 층 번호(지하도 양수, 번호가 없으면 null). 같은 (동·kind·no·주부속) 행은 면적을 더하고
용도는 면적이 가장 큰 행을 쓴다. 호실 `flr` 은 대장 표기 원문이고, 상업 전유만 있다.

실행: python -m data.pipelines.build_building_floors [거점 ...]
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata

from data.collectors.common import BRONZE, GOLD, SILVER
from data.config.page_hubs import ACTIVE_HUBS
from data.pipelines.build_building_attrs import stream_rows
from data.pipelines.build_stores_lite import write_gz
from data.pipelines.build_vacant_floor_units import _load_floor_rows

NAME = "building_floors.json.gz"
FLOOR_FIELDS = ["dong", "kind", "no", "raw", "area_m2", "purps", "etc", "strct", "atch"]
UNIT_FIELDS = ["flr", "kind", "no", "ho", "area_m2", "purps"]
MAX_FLOOR_NO = 150      # 이보다 크면 호수 오기('101')다

_KOREAN_NO = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9, "십": 10}
_GB_KIND = {"지상": "G", "지하": "B", "옥탑": "R"}


def _no(text: str) -> int | None:
    m = re.search(r"\d+", text)
    n = int(m.group()) if m else None
    return n if n and n <= MAX_FLOOR_NO else None


def parse_floor(raw: object) -> tuple[str, int | None]:
    """층 표기 → (kind, 번호). '지1층'·'B1'·'지하1층' → ('B', 1) · '옥탑' → ('R', None) · 해석 불가 → ('?', None)."""
    s = unicodedata.normalize("NFKC", str(raw if raw is not None else "")).strip().upper()
    s = re.sub(r"\((증축|기존|內|내)\)", "", s).strip()
    s = s.strip("()").replace(" ", "")
    if not s:
        return "?", None
    if s.startswith("옥"):
        return "R", _no(s)
    if s.startswith("지상"):
        n = _no(s)
        return ("G", n) if n else ("?", None)
    if s.startswith("지") or re.match(r"B\d", s):
        return "B", _no(s)
    if re.fullmatch(r"\d+-\d+호?|\d+호|\d+,\d+층?", s) or s.startswith("각"):
        return "?", None             # 호수를 층 칸에 적은 것 · 여러 층 묶음
    if (m := re.search(r"동(\d+)층?", s)) or (m := re.match(r"(\d+)층", s)) or (m := re.fullmatch(r"(\d+)F?", s)):
        n = int(m.group(1))
        return ("G", n) if 0 < n <= MAX_FLOOR_NO else ("?", None)
    if (m := re.fullmatch(r"(?:중|복수층\(.*\))(\d+)층?", s)):
        return "G", int(m.group(1))
    if len(s) >= 2 and s[0] in _KOREAN_NO and s[1] == "층":
        return "G", _KOREAN_NO[s[0]]
    return "?", None


def floor_of_row(row: dict) -> tuple[str, int | None]:
    """층별개요 행 → (kind, 번호). 구조화 값(flrGbCdNm·flrNo)을 먼저 믿고, 0·공란이면 표기를 푼다."""
    kind = _GB_KIND.get(str(row.get("flrGbCdNm") or "").strip())
    try:
        no = int(row.get("flrNo") or 0)
    except (TypeError, ValueError):
        no = 0
    if kind and 0 < no <= MAX_FLOOR_NO:
        return kind, no
    parsed_kind, parsed_no = parse_floor(row.get("flrNoNm"))
    if kind and kind != parsed_kind:
        return kind, None
    return parsed_kind, parsed_no


def pnu_of_building_id(building_id: str) -> str:
    """'vu-1168…0014-1' · 'vfu-…' · '1168…0014-1' → pnu."""
    return re.sub(r"^vf?u-", "", building_id).split("-", 1)[0]


def _text(v: object) -> str | None:
    s = str(v if v is not None else "").strip()
    return s or None


def fold_floors(rows: list[dict]) -> list[list]:
    """층 행 → 동·층별 한 줄. 정렬은 동 → 위층부터(옥탑 → 지상 → 지하)."""
    agg: dict[tuple, dict] = {}
    for r in rows:
        kind, no = floor_of_row(r)
        raw = str(r.get("flrNoNm") or "").strip()
        atch = 1 if "부속" in str(r.get("mainAtchGbCdNm") or "") else 0
        key = (str(r.get("dongNm") or "").strip(), kind, no, atch, raw if kind == "?" else "")
        area = float(r.get("area") or 0)
        cur = agg.get(key)
        if cur is None:
            agg[key] = cur = {"raw": raw, "area": 0.0, "top": -1.0, "purps": None, "etc": None, "strct": None}
        cur["area"] += area
        if area > cur["top"]:
            cur.update(top=area, purps=_text(r.get("mainPurpsCdNm")), etc=_text(r.get("etcPurps")),
                       strct=_text(r.get("strctCdNm")))
    rank = {"R": 0, "G": 1, "B": 2, "?": 3}
    ordered = sorted(agg.items(), key=lambda kv: (
        kv[0][0], kv[0][3], rank[kv[0][1]],
        (kv[0][2] or 0) if kv[0][1] == "B" else -(kv[0][2] or 0), kv[0][4]))
    return [[k[0], k[1], k[2], c["raw"], round(c["area"], 2), c["purps"],
             None if c["etc"] == c["purps"] else c["etc"], c["strct"], k[3]] for k, c in ordered]


def load_titles(slug: str, keep: set[str]) -> dict[str, dict]:
    """표제부 → 지번별 대표(주건축물 중 연면적 최대). 날짜 오름차순으로 지번째 덮는다."""
    merged: dict[str, dict] = {}
    for path in sorted((BRONZE / slug).glob("*/bldg_ledger_raw.json")):
        cur: dict[str, dict] = {}
        for pnu, lst, row in stream_rows(path, 6):
            if row is None or lst != "title" or pnu not in keep:
                continue
            main = "부속" not in str(row.get("mainAtchGbCdNm") or "")
            area = float(row.get("totArea") or 0)
            best = cur.get(pnu)
            n_titles = (best["n_titles"] if best else 0) + 1
            if best is None or (main, area) > (best["_main"], best["_area"]):
                best = cur[pnu] = {"_main": main, "_area": area, "road": _text(row.get("newPlatPlc")),
                                   "bld_nm": _text(row.get("bldNm")), "use_apr": _text(row.get("useAprDay")),
                                   "grnd": int(row.get("grndFlrCnt") or 0), "ugrnd": int(row.get("ugrndFlrCnt") or 0)}
            best["n_titles"] = n_titles
        merged.update(cur)
    for v in merged.values():
        v.pop("_main"), v.pop("_area")
    return merged


def master_lots(slug: str) -> set[str]:
    fc = json.loads((GOLD / slug / "page_building_master.geojson").read_text(encoding="utf-8"))
    return {f["properties"]["pnu"] for f in fc["features"] if f["properties"].get("pnu")}


def load_units(slug: str, keep: set[str]) -> dict[str, list[list]]:
    path = SILVER / slug / "expos_units.json"
    if not path.exists():
        return {}
    out: dict[str, list[list]] = {}
    for pnu, val in json.loads(path.read_text(encoding="utf-8")).get("pnu", {}).items():
        if pnu in keep:
            out[pnu] = [[u.get("flr"), *parse_floor(u.get("flr")), u.get("ho"), u.get("area_m2"), u.get("purps")]
                        for u in val.get("units", [])]
    return out


def hub_doc(slug: str) -> dict:
    keep = master_lots(slug)
    floor_rows = {p: r for p, r in _load_floor_rows(slug).items() if p in keep and isinstance(r, list)}
    titles = load_titles(slug, keep)
    units = load_units(slug, keep)
    lots: dict[str, dict] = {}
    for pnu in sorted(set(floor_rows) | set(titles) | set(units)):
        rows = floor_rows.get(pnu) or []
        title = dict(titles.get(pnu) or {})
        road = title.pop("road", None) or next((_text(r.get("newPlatPlc")) for r in rows if _text(r.get("newPlatPlc"))), None)
        lot = {"road": road, **title, "floors": fold_floors(rows)}
        if pnu in units:
            lot["units"] = units[pnu]
        lots[pnu] = lot
    return {
        "slug": slug, "n_lots": len(lots), "n_master_lots": len(keep),
        "source": "건축물대장 층별개요·표제부(bronze) · 전유부(silver expos_units, 상업 전유만)",
        "note": ("키는 지번(pnu)이다. 건물 id {pnu}-{n} 의 n 은 폴리곤 번호이고 대장의 동이 아니다. 대장 기재값이라 현재 "
                 "임대 상태·실제 용도와 다를 수 있다. kind: G 지상·B 지하·R 옥탑·? 미상."),
        "floor_fields": FLOOR_FIELDS, "unit_fields": UNIT_FIELDS, "lots": lots,
    }


def run(slugs: list[str] | None = None, log=print) -> dict:
    total = n_lots = unknown = rows = 0
    for slug in slugs or list(ACTIVE_HUBS):
        doc = hub_doc(slug)
        size = write_gz(doc, GOLD / slug / NAME)
        total += size
        n_lots += doc["n_lots"]
        for lot in doc["lots"].values():
            rows += len(lot["floors"])
            unknown += sum(1 for f in lot["floors"] if f[1] == "?")
        log(f"[floors] {slug} 지번 {doc['n_lots']}/{doc['n_master_lots']} · {size / 1e3:.0f}KB")
    log(f"[floors] 합 {total / 1e6:.1f}MB · 지번 {n_lots} · 층 행 {rows} · 층 미상 {unknown}")
    return {"bytes": total, "lots": n_lots, "rows": rows, "unknown": unknown}


if __name__ == "__main__":
    run(sys.argv[1:] or None)
