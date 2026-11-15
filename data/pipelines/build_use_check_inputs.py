"""입점 점검 재료 — 필지 지역지구(V-World) + 지역지구별 행위제한(토지이음) Bronze → Silver → Gold.

    python -m data.pipelines.build_use_check_inputs --city seoul --date 2026-11-15

입력  BRONZE/landuse/<city>/<date>/vworld/<구>/<pnu>.json   (data.collectors.eum_landuse ①)
      BRONZE/landuse/<city>/<date>/eum/<구>/<행위명>__*.xml  (data.collectors.eum_landuse ②)
Silver SILVER/landuse/<city>/parcel_zones.json · act_rules.json
Gold   data/gold/page_use_check_inputs.json  ← apps/backend/app/services/use_check.py 가 정적 서빙

Gold 모양(키를 짧게 — 6,578필지 기준 1MB 안쪽):
  zone_names {코드: 이름}
  parcels    {pnu: [[코드, "포함"|"저촉"], ...]}              「접함」은 그 필지에 걸리지 않아 뺀다
  acts       {구: {행위명: {코드: [행, ...]}}}                  키가 없으면 미조회 · [] 면 「그 지역지구에 그 행위 규정 없음」
             행 = {"reg": "가능"|"금지", "c": [조건 id], "laws": [{"ho", "mok", "ref", "d": 정의 id, "min", "max"}]}
  conds/defs 문구 표(중복 제거) · basis 기준일

⚠ 이 파일은 **허가 판정이 아니다**. 토지이음 행위제한은 국토계획법·조례의 지역지구별 규정이고,
  지구단위계획 결정도서·개별 법령(식품위생법 등)·건물 상태는 들어 있지 않다.
⚠ 면적 기준(min/max)은 토지이음 응답의 정의(DEF_REF, 별표1 문언)에서 읽는다 — 손으로 적지 않는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path

from data.collectors.common import BRONZE, GOLD, SILVER
from data.collectors.eum_landuse import APPLY_REL, parse_eum

OUT = GOLD / "page_use_check_inputs.json"

_LAW = re.compile(r"별표\s*1\s*제(\d+)호(?:([가-힣])목)?")
_AREA = re.compile(r"바닥면적의\s*합계가\s*([\d,]+|\d+천)\s*제곱미터\s*(미만|이하|이상|초과)")


def _num(s: str) -> float:
    s = s.replace(",", "")
    return float(s[:-1]) * 1000 if s.endswith("천") else float(s)


def area_bounds(defn: str) -> tuple[float | None, float | None]:
    """정의 문언 → (하한 이상, 상한 미만). 이하·초과는 경계를 같은 쪽으로 본다(㎡ 단위 경계값은 판정에 안 쓴다)."""
    lo = hi = None
    for v, op in _AREA.findall(defn or ""):
        if op in ("미만", "이하"):
            hi = _num(v)
        else:
            lo = _num(v)
    return lo, hi


class Interner:
    def __init__(self) -> None:
        self.items: list[str] = []
        self._ix: dict[str, int] = {}

    def __call__(self, s: str) -> int:
        s = (s or "").strip()
        if s not in self._ix:
            self._ix[s] = len(self.items)
            self.items.append(s)
        return self._ix[s]


def parcel_zones(root: Path) -> tuple[dict, dict, list[str]]:
    parcels: dict[str, list[list[str]]] = {}
    names: dict[str, str] = {}
    dates: list[str] = []
    for p in sorted((root / "vworld").glob("*/*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        seen: dict[str, str] = {}
        for page in d["pages"]:
            for f in page.get("field") or []:
                code, rel = f.get("prposAreaDstrcCode"), f.get("cnflcAtNm")
                if not code:
                    continue
                names.setdefault(code, f.get("prposAreaDstrcCodeNm") or code)
                if f.get("lastUpdtDt"):
                    dates.append(f["lastUpdtDt"])
                if rel in APPLY_REL and seen.get(code) != "포함":  # 같은 코드가 포함·저촉 둘 다면 포함
                    seen[code] = rel
        parcels[d["pnu"]] = [[c, r] for c, r in sorted(seen.items())]
    return parcels, names, dates


def act_rules(root: Path, conds: Interner, defs: Interner) -> dict:
    acts: dict = defaultdict(lambda: defaultdict(dict))
    for p in sorted((root / "eum").glob("*/*.xml")):
        gu = p.parent.name
        act = p.stem.split("__")[0]
        doc = parse_eum(p.read_bytes())
        qtext = {}
        for q in doc.iter("QnodeCond"):
            for rn, desc in zip(q.findall("RNUM"), q.findall("QNODE_DESC")):
                qtext[(rn.text or "").strip()] = desc.text or ""
        for it in doc.iter("item"):
            code = (it.findtext("UCODE") or "").strip()
            if not code:
                continue
            rows = []
            for a in it.findall("actRegList"):
                reg = (a.findtext("REG_NM") or "").strip()
                laws = []
                for lu in a.findall("luInfoList"):
                    if (lu.findtext("NODE_DESC") or "").strip() == "검색결과 없음":
                        continue
                    ref = " ".join((lu.findtext("LU_REF_LAW_NM1") or "").split())
                    m = _LAW.search(ref)
                    lo, hi = area_bounds(lu.findtext("DEF_REF") or "")
                    laws.append({"ho": int(m.group(1)) if m else None, "mok": (m.group(2) if m else None),
                                 "ref": ref, "d": defs(lu.findtext("DEF_REF") or ""), "min": lo, "max": hi})
                if not reg or not laws:
                    continue
                c = [conds(qtext.get((r.text or "").strip(), (r.text or "").strip())) for r in a.findall("QNODE_CONDS/RNUM")]
                rows.append({"reg": reg, "c": c, "laws": laws})
            acts[gu][act][code] = rows
    return {g: dict(v) for g, v in acts.items()}


def build(city: str, date: str) -> dict:
    root = BRONZE / "landuse" / city / date
    if not (root / "vworld").exists():
        raise SystemExit(f"Bronze 없음: {root} — 먼저 python -m data.collectors.eum_landuse --city {city} --date {date}")
    conds, defs = Interner(), Interner()
    parcels, names, dates = parcel_zones(root)
    acts = act_rules(root, conds, defs)

    silver = SILVER / "landuse" / city
    silver.mkdir(parents=True, exist_ok=True)
    (silver / "parcel_zones.json").write_text(json.dumps({"date": date, "parcels": parcels, "zone_names": names},
                                                         ensure_ascii=False), encoding="utf-8")
    (silver / "act_rules.json").write_text(json.dumps({"date": date, "acts": acts, "conds": conds.items,
                                                       "defs": defs.items}, ensure_ascii=False), encoding="utf-8")
    gold = {
        "source": ("V-World 토지이용계획속성(ned/data/getLandUseAttr · 필지별 지역지구) + "
                   "토지이음 토지이용규제 행위제한정보(data.go.kr 15058410 · DTarLandUseInfo)"),
        "built_at": dt.datetime.now().isoformat(timespec="seconds"),
        "city": city,
        "note": ("허가 판정이 아니다 — 지역지구별 행위 가능여부(국토계획법·조례)와 건축법 시행령 별표1 분류만 담는다. "
                 "지구단위계획 결정도서·개별 법령·건물 상태는 없다. 「접함」 지역지구는 그 필지에 걸리지 않아 뺐다."),
        "basis": {"vworld_updated_min": min(dates) if dates else None,
                  "vworld_updated_max": max(dates) if dates else None,
                  "eum_fetched": date},
        "zone_names": dict(sorted(names.items())),
        "parcels": parcels,
        "acts": acts,
        "conds": conds.items,
        "defs": defs.items,
    }
    OUT.write_text(json.dumps(gold, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n_codes = len({c for v in parcels.values() for c, _ in v})
    print(f"[use_check_inputs] 필지 {len(parcels)} · 지역지구 코드 {n_codes} · 구 {len(acts)} · "
          f"행위 {len({a for g in acts.values() for a in g})} · 조건 {len(conds.items)} · "
          f"{OUT.stat().st_size / 1e6:.2f}MB → {OUT}")
    return gold


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--city", default="seoul")
    ap.add_argument("--date", required=True)
    a = ap.parse_args()
    build(a.city, a.date)


if __name__ == "__main__":
    main()
