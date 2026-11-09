"""[Posting·Platform] 점포 요약 · 체인 추정 표 · 업종 동시 입지 lift.

산출물
  gold/{거점}/stores_lite.json.gz          반경 경쟁(`/nearby-stores`) · 트윈 호실 대조의 재료. 전화 없음 · 호수는 2026-11-09 부터 싣는다
  gold/platform_store_brands.json          체인 추정 표
  gold/platform_industry_colocation.json   함께 모이는 업종(관측) — 100m 격자 동시 입지 lift

원천은 bronze `stores_raw.json`(소상공인 상가정보 · 공공데이터 — 재배포 가능, 판은 `latest_bronze`).
`PLACEOS_BRONZE_ROOT` 로 다른 체크아웃의 bronze 를 읽을 수 있다(`data/collectors/common.py`).

## 체인 추정 — 기준
상호를 `name_key`(소문자 · 괄호·기호·공백 제거 · 끝 지점 토큰 제거)로 맞춘 뒤 다음 중 하나면 체인 추정이다.
  manual  `data/config/store_brands.MANUAL_BRANDS` — 직영이라 공정위 목록에 없거나 표기가 갈리는 브랜드
  ftc     공정위 정보공개서(bronze `pppp_supplement/*/*/additional/ftc/`)와 키가 같고, 가맹점 ≥ FTC_MIN_FRCS,
          업종 대분류가 맞고, 우리 표본에서 2개 시군구 이상
  repeat  공정위에 없어도 ≥ REPEAT_MIN_SIGUNGU 개 시군구 · ≥ REPEAT_MIN_STORES 곳 · 지점명(`brchNm`) 비율 ≥ REPEAT_MIN_BRANCH
공정위 ≥ FTC_PREFIX_MIN_FRCS 브랜드는 상호 앞머리로도 맞춘다("오렌즈신사" → "오렌즈") — 이때 소분류가 그 브랜드 주력과 같아야 한다.
일반명사는 `NOT_CHAIN`·`GENERIC_SUFFIXES` 로 뺀다. **가맹 여부를 확인한 값이 아니다** — 표기는 「체인 추정」.

## 동시 입지 lift
격자 칸 하나를 표본으로, lift = P(A∩B) / (P(A)·P(B)). 분모는 그 범위에서 점포가 하나라도 있는 칸이다.
표본 하한: 두 업종 각 ≥ COLOC_MIN_CELLS 칸 · 함께 있는 칸 ≥ COLOC_MIN_BOTH · 관측의 95% 하한(정규근사)이 기대값을 넘을 것.
그래서 작은 도시는 쌍이 비어 있을 수 있다 — 빈 것은 「표본 부족」이지 「함께 안 모인다」가 아니다.
거점 반경 안의 점포만 세므로 「거점들의 관측」이지 도시 전체가 아니다. 인과·매출 효과를 말하지 않는다.

실행: python -m data.pipelines.build_stores_lite [거점 ...]   (인자가 없으면 ACTIVE_HUBS 전부)
"""
from __future__ import annotations

import gzip
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from data.collectors.common import BRONZE, GOLD, latest_bronze
from data.config.industry_details import BY_KEY as DETAIL_BY_KEY, classify as classify_detail
from data.config.page_hubs import ACTIVE_HUBS
from data.config.store_brands import CORP_PREFIXES, GENERIC_SUFFIXES, MANUAL_BRANDS, NOT_CHAIN
from data.config.store_industries import INDUSTRY_LABELS, industry_of

LITE_NAME = "stores_lite.json.gz"
BRANDS_OUT = "platform_store_brands.json"
COLOC_OUT = "platform_industry_colocation.json"

FTC_MIN_FRCS = 5
FTC_PREFIX_MIN_FRCS = 100
FTC_PREFIX_MIN_LEN = 3
REPEAT_MIN_SIGUNGU = 5
REPEAT_MIN_STORES = 8
REPEAT_MIN_BRANCH = 0.5

GRID_DLAT, GRID_DLNG = 0.0009, 0.00113     # ≈100m — 히트맵 격자와 같은 해상도
COLOC_MIN_CELLS = 30
COLOC_MIN_BOTH = 10
COLOC_TOP = 5

# 층 값 — 지하는 음수. 상가정보의 「지」(지하인데 층 번호 없음)만 이 값으로 싣는다.
BASEMENT_UNKNOWN = -99
# 이보다 큰 flrNo 는 호수 오기다('401'·'511'). 층이 아니라 null 로 싣는다.
MAX_STORE_FLOOR = 99

_FTC_LCLS = {
    "외식": {"음식"},
    "도소매": {"소매"},
    "서비스": {"수리·개인", "교육", "예술·스포츠", "시설관리·임대", "과학·기술", "숙박", "보건의료", "부동산", "소매"},
}

def _clean(text: object) -> str:
    s = unicodedata.normalize("NFKC", str(text or "")).lower().strip()
    return re.sub(r"\(.*?\)|\[.*?\]", " ", s).strip()


def _compact(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def name_key(name: object, branch: object = "") -> str:
    """상호 → 비교 키. 지점명·끝 지점 토큰·법인명을 뗀다('스타벅스 신사역점' → '스타벅스')."""
    s, b = _clean(name), _clean(branch)
    if b and s.endswith(b) and len(s) > len(b):
        s = s[: -len(b)].strip()
    tokens = s.split()
    if len(tokens) > 1 and tokens[-1].endswith("점"):
        tokens = tokens[:-1]
    key = _compact("".join(tokens))
    for prefix in CORP_PREFIXES:
        if key.startswith(prefix) and len(key) > len(prefix) + 1:
            return key[len(prefix):]
    return key


def _is_generic(key: str) -> bool:
    return key in NOT_CHAIN or len(key) < 2 or key.endswith(GENERIC_SUFFIXES)


def store_floor(raw: object) -> int | None:
    """flrNo → 층. 지하는 음수, 「지」는 BASEMENT_UNKNOWN, 공란·호수 오기·해석 불가는 None."""
    s = str(raw if raw is not None else "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d+", s):
        n = int(s)
        return n if 0 < n <= MAX_STORE_FLOOR else None
    m = re.fullmatch(r"[Bb](\d+)", s)
    if m and int(m.group(1)) > 0:
        return -int(m.group(1))
    if s in ("지", "지하", "B", "b"):
        return BASEMENT_UNKNOWN
    return None


def load_ftc(bronze: Path | None = None) -> dict[str, dict]:
    """공정위 브랜드 목록 → {키: {name, frcs, lcls, mlsfc, yr}}. 같은 키는 가맹점이 많은 행을 남긴다."""
    root = bronze or BRONZE
    out: dict[str, dict] = {}
    for p in sorted(root.glob("pppp_supplement/*/*/additional/ftc/*/*.json")):
        try:
            items = json.loads(p.read_text(encoding="utf-8")).get("items") or []
        except (OSError, ValueError):
            continue
        for it in items:
            key = name_key(it.get("brandNm"))
            frcs = int(it.get("frcsCnt") or 0)
            if key and (key not in out or frcs > out[key]["frcs"]):
                out[key] = {"name": str(it.get("brandNm")).strip(), "frcs": frcs,
                            "lcls": it.get("indutyLclasNm"), "mlsfc": it.get("indutyMlsfcNm"),
                            "yr": str(it.get("yr"))}
    return out


def _store_lcls(row: dict) -> str:
    return str(row.get("indsLclsNm") or "").strip()


def _ftc_fits(ftc_row: dict, lcls: str) -> bool:
    return lcls in _FTC_LCLS.get(str(ftc_row.get("lcls")), set())


class BrandMatcher:
    """상호 키 → 브랜드 id. `fit()` 이 전체 점포로 표를 세우고 `match()` 가 한 점포에 답한다."""

    def __init__(self, ftc: dict[str, dict]):
        self.ftc = ftc
        self.manual: dict[str, tuple[str, tuple[str, ...]]] = {}
        for display, (variants, lcls) in MANUAL_BRANDS.items():
            for v in variants:
                self.manual[v] = (display, lcls)
        self.manual_lens = sorted({len(k) for k in self.manual}, reverse=True)
        self.brands: dict[str, dict] = {}       # 브랜드 id → {basis, name, ftc_frcs}
        self.exact: dict[str, str] = {}         # 상호 키 → 브랜드 id (ftc·repeat)
        self.prefix: dict[str, tuple[str, set[str]]] = {}   # 앞머리 → (브랜드 id, 허용 소분류)
        self.prefix_lens: list[int] = []

    def _manual(self, key: str, lcls: str) -> str | None:
        for n in self.manual_lens:
            hit = self.manual.get(key[:n])
            # 영문 앞머리는 낱말 경계까지 맞춘다 — 'cu' 가 'cube'·'custom' 을 먹지 않게.
            if hit and lcls in hit[1] and not (key[n - 1:n + 1].isascii() and key[n - 1:n + 1].isalpha()
                                               and len(key) > n):
                return hit[0]
        return None

    def fit(self, rows) -> None:
        agg: dict[str, dict] = defaultdict(
            lambda: {"n": 0, "sg": set(), "br": 0, "lcls": Counter(), "scls": Counter()})
        for r in rows:
            key = name_key(r.get("bizesNm"), r.get("brchNm"))
            lcls = _store_lcls(r)
            display = self._manual(key, lcls)
            if display:
                self.brands.setdefault(display, {"basis": "manual", "name": display})
                continue
            if not key:
                continue
            a = agg[key]
            a["n"] += 1
            a["sg"].add(r.get("signguCd"))
            a["br"] += bool(str(r.get("brchNm") or "").strip())
            a["lcls"][lcls] += 1
            a["scls"][r.get("indsSclsCd")] += 1

        for key, a in agg.items():
            if key in NOT_CHAIN or len(key) < 2:
                continue
            top_lcls = a["lcls"].most_common(1)[0][0]
            f = self.ftc.get(key)
            if f and f["frcs"] >= FTC_MIN_FRCS and _ftc_fits(f, top_lcls) and len(a["sg"]) >= 2 \
                    and (len(key) > 2 or f["frcs"] >= FTC_PREFIX_MIN_FRCS):
                self.brands[key] = {"basis": "ftc", "name": f["name"], "ftc_frcs": f["frcs"]}
                self.exact[key] = key
                if f["frcs"] >= FTC_PREFIX_MIN_FRCS and len(key) >= FTC_PREFIX_MIN_LEN:
                    self.prefix[key] = (key, {c for c, _ in a["scls"].most_common(3)})
            elif not _is_generic(key) and len(a["sg"]) >= REPEAT_MIN_SIGUNGU and a["n"] >= REPEAT_MIN_STORES \
                    and a["br"] / a["n"] >= REPEAT_MIN_BRANCH:
                self.brands[key] = {"basis": "repeat", "name": key}
                self.exact[key] = key
        self.prefix_lens = sorted({len(k) for k in self.prefix}, reverse=True)

    def match(self, row: dict) -> str | None:
        key = name_key(row.get("bizesNm"), row.get("brchNm"))
        if not key:
            return None
        lcls = _store_lcls(row)
        display = self._manual(key, lcls)
        if display:
            return display
        hit = self.exact.get(key)
        if hit:
            return hit
        for n in self.prefix_lens:
            if n >= len(key):
                continue
            p = self.prefix.get(key[:n])
            if p and row.get("indsSclsCd") in p[1]:
                return p[0]
        return None


def load_hub_rows(slug: str) -> tuple[list[dict], str | None]:
    """거점 점포 원본과 그 판(수집일). 판은 `latest_bronze` 가 고른다."""
    path = latest_bronze(slug, "stores_raw.json")
    if path is None:
        return [], None
    return json.loads(path.read_text(encoding="utf-8")), path.parent.name


def _coord(row: dict) -> tuple[float, float] | None:
    try:
        lat, lng = float(row["lat"]), float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return (lat, lng) if lat and lng else None


# 호수(`ho`)는 2026-11-09 사용자 요청으로 남긴다 — 트윈이 집합건물 전유부 호실(`hoNm`)과 점포를 맞춘다
# (apps/backend/app/services/store_units.py). 끝에 붙여 앞 8칸의 자리는 그대로다. 그 전 판(8칸)은 `LITE_FIELDS_V1`.
# 상가정보는 호를 비워 두는 행이 많다(공란은 null — 「그 호실이 비었다」가 아니다).
LITE_FIELDS_V1 = ["name", "brand", "mcls", "scls", "lat", "lng", "floor", "lno"]
LITE_FIELDS = [*LITE_FIELDS_V1, "ho"]


def store_ho(raw: object) -> str | None:
    """hoNo → 공백을 걷은 원문(「101호」 · 「B01」). 공란은 None. 호실과 맞추는 정규화는 서버(store_units.ho_key)가 한다."""
    s = re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(raw if raw is not None else "")))
    return s or None


def lite_doc(slug: str, rows: list[dict], as_of: str | None, matcher: BrandMatcher) -> dict:
    """거점 하나의 stores_lite. 행은 지번 순으로 묶어 gzip 이 잘 먹게 한다."""
    out, seen = [], set()
    cats: dict[str, str] = {}
    for r in rows:
        sid = r.get("bizesId")
        pt = _coord(r)
        if pt is None or sid in seen:
            continue
        seen.add(sid)
        scls, mcls = str(r.get("indsSclsCd") or ""), str(r.get("indsMclsCd") or "")
        if scls:
            cats[scls] = str(r.get("indsSclsNm") or "").strip()
        if mcls:
            cats[mcls] = str(r.get("indsMclsNm") or "").strip()
        out.append([str(r.get("bizesNm") or "").strip(), matcher.match(r), mcls or None, scls or None,
                    round(pt[0], 5), round(pt[1], 5), store_floor(r.get("flrNo")), r.get("lnoCd") or None,
                    store_ho(r.get("hoNo"))])
    out.sort(key=lambda x: (x[7] or "", x[0]))
    return {
        "slug": slug, "as_of": as_of, "n": len(out),
        "source": "소상공인시장진흥공단 상가(상권)정보 (bronze stores_raw — 전화 제외)",
        "note": ("brand 는 체인 추정(platform_store_brands.json)이고 가맹 여부 확인값이 아니다. 좌표는 건물 단위라 같은 "
                 f"건물 점포는 좌표가 같다. floor 는 지하 음수 · {BASEMENT_UNKNOWN} = 지하(층 번호 없음) · null = 층 미상. "
                 "ho 는 상가정보 호(공백 제거 원문) · null = 호 미상(호실이 비었다는 뜻이 아니다)."),
         "n_with_ho": sum(1 for x in out if x[8]),
        "fields": LITE_FIELDS, "categories": dict(sorted(cats.items())), "rows": out,
    }


def write_gz(doc: dict, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # mtime=0 — 내용이 같으면 바이트도 같아 커밋 diff 가 안 생긴다.
    with path.open("wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(raw)
    return path.stat().st_size


def brand_table(rows_by_hub: dict[str, list[dict]], unique: dict[str, dict], matcher: BrandMatcher) -> dict:
    agg: dict[str, dict] = defaultdict(lambda: {"n": 0, "sg": set(), "br": 0, "hubs": set(), "scls": Counter()})
    for r in unique.values():
        b = matcher.match(r)
        if b:
            a = agg[b]
            a["n"] += 1
            a["sg"].add(r.get("signguCd"))
            a["br"] += bool(str(r.get("brchNm") or "").strip())
            a["scls"][str(r.get("indsSclsNm") or "").strip()] += 1
    for slug, rows in rows_by_hub.items():
        for r in rows:
            b = matcher.match(r)
            if b:
                agg[b]["hubs"].add(slug)
    brands = {}
    for bid, a in sorted(agg.items(), key=lambda kv: (-kv[1]["n"], kv[0])):
        meta = matcher.brands.get(bid, {"basis": "repeat", "name": bid})
        brands[bid] = {"name": meta["name"], "basis": meta["basis"], "n": a["n"], "n_sigungu": len(a["sg"]),
                       "n_hubs": len(a["hubs"]), "branch_share": round(a["br"] / a["n"], 3),
                       "ftc_frcs": meta.get("ftc_frcs"), "top_scls": a["scls"].most_common(1)[0][0]}
    return {
        "label": "체인 추정",
        "note": ("정규화 상호가 공정위 정보공개서 목록과 맞거나 여러 시군구에 지점명과 함께 반복되는 것을 모은 **추정**이다. "
                 "가맹 여부를 확인한 값이 아니고, n 은 서빙 거점 반경 안 점포 수(전국 점포 수가 아니다)다."),
        "criteria": {
            "ftc": f"공정위 목록과 키 일치 · 가맹점 ≥ {FTC_MIN_FRCS} · 업종 대분류 일치 · 2개 시군구 이상",
            "ftc_prefix": (f"가맹점 ≥ {FTC_PREFIX_MIN_FRCS} · 키 {FTC_PREFIX_MIN_LEN}자 이상 브랜드는 "
                           "상호 앞머리로도 맞춤(주력 소분류 일치)"),
            "repeat": (f"≥ {REPEAT_MIN_SIGUNGU}개 시군구 · ≥ {REPEAT_MIN_STORES}곳 · 지점명 비율 ≥ {REPEAT_MIN_BRANCH} "
                       "· 일반명사 제외"),
            "manual": "data/config/store_brands.MANUAL_BRANDS (직영·표기 갈림)",
        },
        "source": "소상공인 상가정보(bronze stores_raw) · 공정위 가맹사업 정보공개서(bronze pppp_supplement/additional/ftc)",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stores_unique": len(unique),
        "brands": brands,
    }


def _cell(pt: tuple[float, float]) -> tuple[int, int]:
    return math.floor(pt[0] / GRID_DLAT), math.floor(pt[1] / GRID_DLNG)


def top_pairs(cells_of: dict[str, set], n_total: int, label) -> dict:
    """키별 lift 상위. 표본 하한은 모듈 머리말 참조 — 기대값과 못 가르는 쌍은 싣지 않는다."""
    out = {}
    for a, ca in cells_of.items():
        if len(ca) < COLOC_MIN_CELLS:
            continue
        ranked = []
        for b, cb in cells_of.items():
            if a == b or len(cb) < COLOC_MIN_CELLS:
                continue
            both = len(ca & cb)
            if both < COLOC_MIN_BOTH:
                continue
            expected = len(ca) * len(cb) / n_total
            lower = both - 1.96 * math.sqrt(both)
            if lower <= expected:
                continue
            ranked.append({"key": b, "label": label(b), "lift": round(both / expected, 2),
                           "lift_lo": round(lower / expected, 2), "n_both": both})
        ranked.sort(key=lambda x: (-x["lift"], x["key"]))
        out[a] = {"n_cells": len(ca), "top": ranked[:COLOC_TOP]}
    return out


def colocation_doc(unique: dict[str, dict], cities_of: dict[str, set[str]]) -> dict:
    scopes: dict[str, dict] = {}
    cities = sorted({c for v in cities_of.values() for c in v})
    for city in cities:
        by_ind: dict[str, set] = defaultdict(set)
        by_det: dict[str, set] = defaultdict(set)
        all_cells: set = set()
        n_stores = 0
        for sid, r in unique.items():
            if city not in cities_of[sid]:
                continue
            pt = _coord(r)
            if pt is None:
                continue
            cell = _cell(pt)
            all_cells.add(cell)
            n_stores += 1
            if (ind := industry_of(r.get("indsSclsCd"))):
                by_ind[ind].add(cell)
            if (det := classify_detail(str(r.get("indsSclsNm") or "").strip())):
                by_det[det].add(cell)
        n = len(all_cells)
        if not n:
            continue
        details = {
            key: {**val, "parent": DETAIL_BY_KEY[key]["parent"]}
            for key, val in top_pairs(by_det, n, lambda k: DETAIL_BY_KEY[k]["label"]).items()
        }
        scopes[city] = {"n_cells": n, "n_stores": n_stores,
                        "industries": top_pairs(by_ind, n, INDUSTRY_LABELS.__getitem__),
                        "details": details}
    return {
        "label": "함께 모이는 업종(관측)",
        "note": ("100m 격자에서 두 업종이 같은 칸에 있는 정도(lift)다. 관측일 뿐 인과·매출 효과가 아니고, 서빙 거점 반경 안의 "
                 "점포만 센다. 쌍이 없으면 표본 부족일 수 있다."),
        "grid": {"dlat": GRID_DLAT, "dlng": GRID_DLNG},
        "min_sample": {"cells_each": COLOC_MIN_CELLS, "cells_both": COLOC_MIN_BOTH,
                       "rule": "관측 − 1.96√관측 > 기대값 인 쌍만"},
        "industry_labels": INDUSTRY_LABELS,
        "source": "소상공인 상가정보(bronze stores_raw)",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scopes": scopes,
    }


def run(slugs: list[str] | None = None, log=print) -> dict:
    """전체 거점으로 표를 세우고, `slugs`(없으면 전부)의 stores_lite 를 쓴다."""
    rows_by_hub: dict[str, list[dict]] = {}
    as_of: dict[str, str | None] = {}
    unique: dict[str, dict] = {}
    cities_of: dict[str, set[str]] = defaultdict(set)
    for slug, hub in ACTIVE_HUBS.items():
        rows, as_of[slug] = load_hub_rows(slug)
        rows_by_hub[slug] = rows
        for r in rows:
            if (sid := r.get("bizesId")):
                unique[sid] = r
                cities_of[sid].add(hub.city)
    log(f"[stores-lite] 원본 {sum(map(len, rows_by_hub.values()))}행 · 중복 제거 {len(unique)}")
    matcher = BrandMatcher(load_ftc())
    matcher.fit(unique.values())
    log(f"[stores-lite] 체인 추정 후보 {len(matcher.brands)}")

    total = 0
    for slug in slugs or list(ACTIVE_HUBS):
        total += write_gz(lite_doc(slug, rows_by_hub[slug], as_of[slug], matcher), GOLD / slug / LITE_NAME)
    log(f"[stores-lite] stores_lite 합 {total / 1e6:.1f}MB (gz)")

    (GOLD / BRANDS_OUT).write_text(json.dumps(brand_table(rows_by_hub, unique, matcher), ensure_ascii=False,
                                              separators=(",", ":")), encoding="utf-8")
    (GOLD / COLOC_OUT).write_text(json.dumps(colocation_doc(unique, cities_of), ensure_ascii=False,
                                             separators=(",", ":")), encoding="utf-8")
    log(f"[stores-lite] {BRANDS_OUT} {(GOLD / BRANDS_OUT).stat().st_size / 1e6:.2f}MB · "
        f"{COLOC_OUT} {(GOLD / COLOC_OUT).stat().st_size / 1e6:.2f}MB")
    return {"stores_lite_bytes": total, "unique": len(unique)}


def main() -> None:
    run(sys.argv[1:] or None)


if __name__ == "__main__":
    main()
