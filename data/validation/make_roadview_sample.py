"""로드뷰 지상검증(ground truth) 샘플 생성 — poc §3-2 (PoC exit 판정 재료).

page_building_master 에서 status 층화 샘플 30동을 뽑아
  data/validation/roadview_sample.csv   ← 사용자가 label_actual 채움
  data/validation/roadview_sample.md    ← 클릭 가능한 네이버 지도 링크 목록
을 만든다. 라벨 규칙(label_actual): 공실 / 부분공실 / 영업 / 불명

판정 기준은 **건물 전체 호실**(1층이 아니라). status 의 분모 capacity 가 건물 전체
호수이므로 라벨도 같은 척도여야 한다. 링크는 상호명이 아닌 pnu 지번주소로 만든다.

채점: 라벨 입력 후 python -m data.validation.score_labels

실행: python -m data.validation.make_roadview_sample

## 층 단위 모드 (`--floors`, 2026-10-08)

위 건물 단위 30동은 **가로수길 한 곳 · status 층화**라 "화면에 걸린 빈 층이 맞는가"를 재지
못한다(2026-10-08 실측: 28건 · 공실 4건 · '항상 partial' 상수가 모델보다 높았다). 이 모드는
서빙 81거점의 **(지번, 층)** 을 모집단으로 무작위 층화 표본을 뽑는다.

- 모집단 = 상업층 전부(`com_floors`)를 네 계층으로 **빠짐없이** 나눈 것이다.
  `vacant_confirmed`·`vacant_probable`(화면의 빈 층 목록 = `vacant_floor_units.json`) ·
  `occupied`(`occ_floors` — 영업 확인) · `unlisted`(둘 다 아님: 만실 건물·면적 필터로 목록에서
  빠진 층). 빈 층만 뽑으면 precision 만 나오고 **놓친 공실(recall)** 과 층 공실률은 못 잰다.
- 계층 = 위 네 가지 × 1층/2층↑. 계층마다 `N_h / n_h` 가중치를 `design.json` 에 남긴다.
- 라벨러는 **모델 예측을 보지 못한다.** `labels.csv`(블라인드)와 `key.csv`(예측·계층·가중치)를
  분리한다. 라벨러는 key.csv 를 열지 않는다.
- 인접 거점은 같은 (지번, 층)을 중복으로 든다(실측 10.8%). 고유 (지번, 층)으로 접고 첫 거점이 갖는다.
- 라벨이 한 건이라도 채워진 시트는 `--force` 로도 덮지 않는다 — 다른 `--tag` 를 쓴다.
- 서빙 목록이 마스터보다 낡았으면(`build_vacant_floor_units` 미실행) **멈춘다** — 화면과 다른
  목록을 검증하게 되기 때문이다.

실행:
  python -m data.validation.make_roadview_sample --floors --dry-run     # 계층 크기만 본다
  python -m data.validation.make_roadview_sample --floors --tag 20261008
  python -m data.validation.make_roadview_sample --floors --hubs garosugil,seongsu --scale 0.3
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

from data.collectors.common import GOLD, load_latest
from data.config.garosugil import SLUG
from data.config.page_hubs import ACTIVE_HUBS
from data.pipelines.build_page_master import _build_dong_map, _label
# 모집단 규칙은 화면의 빈 층 목록을 만드는 쪽의 상수를 **그대로** 쓴다 — 복제하면 목록이 세는
# 건물과 표본이 세는 건물이 조용히 갈라진다(build_vacant_floor_units 가 같은 경고를 적고 있다).
from data.pipelines.build_vacant_floor_units import _COUNTED_METHODS, _COUNTED_SOURCE_PREFIX

_OUT = Path(__file__).resolve().parent
_QUOTA = {"empty": 12, "high": 8, "partial": 5, "full": 5}   # 계 30동
_SEED = 42   # 재현 가능 샘플

# gold 의 name 이 상호명이 아니라 지번(폴백 라벨)인 경우를 표에서 숨기기 위한 판별.
# 구 gold 는 부번 0 을 "신사동 512-0" 으로 기록했으므로 그 형태도 함께 잡는다.
_JIBUN_RE = re.compile(r"^\S+동\s+\d+(-\d+)?$")


def _center(geom: dict) -> tuple[float, float]:
    ring = geom["coordinates"][0]
    lons = [c[0] for c in ring]
    lats = [c[1] for c in ring]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def run() -> None:
    src = GOLD / SLUG / "page_building_master.geojson"
    fc = json.loads(src.read_text(encoding="utf-8"))
    dong_map = _build_dong_map(load_latest(SLUG, "stores_raw.json") or [])
    rng = random.Random(_SEED)

    rows: list[dict] = []
    for status, n in _QUOTA.items():
        pool = [f for f in fc["features"] if f["properties"]["status"] == status]
        for f in rng.sample(pool, min(n, len(pool))):
            p = f["properties"]
            lat, lon = _center(f["geometry"])
            # 링크는 항상 pnu 지번주소로 만든다. name 은 상가정보 상호명이라
            # 잘리거나("제", "지") 동명 건물이 여럿("○○빌딩")이라 건물 특정이 안 된다.
            jibun = _label(p["pnu"], "", dong_map)
            addr = f"서울 강남구 {jibun}"
            rows.append({
                "id": p["id"], "name": p["name"], "jibun": jibun,
                "status_predicted": status,
                "vacancy_rate": p["vacancy_rate"],
                "active": p["active"], "capacity": p["capacity"],
                "floors": p.get("floors", ""),
                "naver_link": f"https://map.naver.com/p/search/{quote(addr)}",
                "coord": f"{lat:.6f},{lon:.6f}",
                "label_actual": "",   # ← 공실 / 부분공실 / 영업 / 불명
                "memo": "",
            })
    rng.shuffle(rows)   # 상태가 뭉치지 않게 섞어 블라인드에 가깝게

    csv_path = _OUT / "roadview_sample.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    md = ["# 로드뷰 검증 샘플 30동 — 라벨은 roadview_sample.csv 에 기입",
          "",
          "링크 클릭 → 네이버 지도에서 해당 건물 → **거리뷰**로 확인.",
          "링크는 지번주소 검색이다. 표의 `건물`(상호명)은 참고용이며, 건물 특정은 "
          "지번 또는 CSV 의 `coord`(폴리곤 중심좌표)를 기준으로 한다.",
          "",
          "## 판정 기준 — 건물 전체 호실 (1층만 보지 않는다)",
          "",
          "예측 `status` 의 분모 `capacity` 가 **건물 전체 호수**(건축물대장 호수 또는 층수×2)이므로,",
          "라벨도 전체 호실 기준이어야 채점이 성립한다. 1층만 보고 판정하면 상층 공실이 있는 건물이",
          "일괄 `영업` 으로 라벨되어 정확도가 체계적으로 깎인다.",
          "",
          "거리뷰에서 **간판·층별 안내판·창문/블라인드·임대 현수막**으로 상층부까지 판정할 것.",
          "",
          "| label_actual | 의미 |",
          "|---|---|",
          "| `공실` | 영업 중인 호실이 없거나 사실상 전무 (전층 공실·임대 현수막) |",
          "| `부분공실` | 영업 호실과 빈 호실이 섞여 있음 |",
          "| `영업` | 빈 호실이 없거나 거의 없음 |",
          "| `불명` | 거리뷰 미제공·가림·신축 등으로 판정 불가 → 채점 제외 |",
          "",
          "## 대상 30동",
          "",
          "| # | 지번 | 건물(상호) | 예측 | 공실률 | 층 | 지도 |",
          "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        name = "—" if (not r["name"] or _JIBUN_RE.match(r["name"])) else r["name"]
        md.append(f"| {i} | {r['jibun']} | {name} ({r['active']}/{r['capacity']}호) "
                  f"| {r['status_predicted']} | {r['vacancy_rate']}% | {r['floors']}F "
                  f"| [열기]({r['naver_link']}) |")
    (_OUT / "roadview_sample.md").write_text("\n".join(md), encoding="utf-8")

    print(f"[validation] {csv_path.name} / roadview_sample.md — {len(rows)}동")


# ══════════════════════════════════════════════════════════════════════════════
# 층 단위 무작위 층화 표본 (--floors)
# ══════════════════════════════════════════════════════════════════════════════

_CLASSES = ("vacant_confirmed", "vacant_probable", "occupied", "unlisted")
_BANDS = ("1F", "2F+")
_STRATA = tuple(f"{c}|{b}" for c in _CLASSES for b in _BANDS)

# 계층 → 목표 표본 수. 계층 크기 N 이 이보다 작으면 전수(가중치 1)다.
# 크기 근거: precision 80% 를 ±8%p(95%) 로 말하려면 계층당 약 100층이 든다. 화면의 빈 층의
# 83% 가 2층↑ 이고 76% 가 confirmed 라 그 계층(confirmed·2층↑)에 가장 많이 건다.
# unlisted 는 서빙 81거점 기준 11,455층(상업층의 14%)이라 5 가 아니라 이만큼 잡았다.
# 합계 365층. --scale 로 일괄 조정한다.
_FLOOR_QUOTA: dict[str, int] = {
    "vacant_confirmed|2F+": 100, "vacant_confirmed|1F": 50,
    "vacant_probable|2F+": 50,   "vacant_probable|1F": 20,
    "occupied|2F+": 60,          "occupied|1F": 40,
    "unlisted|2F+": 30,          "unlisted|1F": 15,
}

_TAG_RE = re.compile(r"^[0-9A-Za-z_-]{1,32}$")        # 출력 디렉터리 이름 — 경로 조작 차단
_GU_TOKEN = re.compile(r"([가-힣]+구)(?![가-힣])")

# labels.csv 에서 라벨러가 채우는 열. 비어 있지 않은 한 건이라도 있으면 시트를 덮지 않는다.
_LABEL_COLS = ("label_actual", "label_use", "label_date", "label_method", "memo")
_LABEL_VALUES = ("공실", "부분공실", "영업", "불명")


class StaleInventory(RuntimeError):
    """`vacant_floor_units.json` 이 현재 마스터와 어긋난다 — 화면과 다른 목록을 검증하게 된다."""


def _band(floor: int) -> str:
    return "1F" if floor == 1 else "2F+"


def _sha12(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def floor_population(slug: str) -> tuple[list[dict], dict]:
    """한 거점의 (지번, 층) 모집단과 입력 스냅샷 지문.

    건물 단위가 아니라 **지번 단위**다 — 층 근거(`com_floors`·`occ_floors`)를 Page 마스터가
    지번당 산출하기 때문이다(build_vacant_floor_units._units_for 와 같은 접기 규칙).
    마스터가 없으면 `([], {})`.
    """
    master_p = GOLD / slug / "page_building_master.geojson"
    units_p = GOLD / slug / "vacant_floor_units.json"
    if not master_p.exists():
        return [], {}

    units_doc = (json.loads(units_p.read_text(encoding="utf-8"))
                 if units_p.exists() else {"units": []})
    listed = {(str(u["pnu"]), int(u["floor"])): u for u in units_doc.get("units") or []}

    by_pnu: dict[str, list[dict]] = {}
    for feat in json.loads(master_p.read_text(encoding="utf-8"))["features"]:
        p = feat["properties"]
        if p.get("capacity_method") not in _COUNTED_METHODS:
            continue
        if not str(p.get("source") or "").startswith(_COUNTED_SOURCE_PREFIX):
            continue
        if not (p.get("com_floors") or []):
            continue
        by_pnu.setdefault(str(p.get("pnu") or ""), []).append(feat)

    rows: list[dict] = []
    seen_listed: set[tuple[str, int]] = set()
    contradictions = 0
    for pnu, feats in by_pnu.items():
        feat = max(feats, key=lambda f: f["properties"].get("floors") or 0)
        p = feat["properties"]
        occ = {int(f) for f in (p.get("occ_floors") or [])}
        lat, lon = _center(feat["geometry"])
        for fl in sorted({int(f) for f in p["com_floors"] if int(f) >= 1}):
            u = listed.get((pnu, fl))
            if u is not None:
                if u.get("certainty") not in ("confirmed", "probable") or fl in occ:
                    contradictions += 1
                    continue
                seen_listed.add((pnu, fl))
                cls = f"vacant_{u['certainty']}"
            else:
                cls = "occupied" if fl in occ else "unlisted"
            rows.append({
                "slug": slug, "pnu": pnu, "floor": fl, "band": _band(fl),
                "cls": cls, "stratum": f"{cls}|{_band(fl)}",
                "bldg_id": p.get("id") or "", "bldgs_on_pnu": len(feats),
                "bld_floors": p.get("floors") or 0,
                "lat": round(lat, 6), "lng": round(lon, 6),
                "certainty": (u or {}).get("certainty", ""),
                "area_m2": (u or {}).get("area_m2", ""),
                "purps": (u or {}).get("purps", ""),
                "was": (u or {}).get("was", ""),
            })

    orphans = set(listed) - seen_listed
    if orphans or contradictions:
        raise StaleInventory(
            f"{slug}: 서빙 빈 층 목록이 마스터와 어긋난다 (마스터에 없는 유닛 {len(orphans)} · "
            f"모순 {contradictions}) — python -m data.pipelines.build_vacant_floor_units {slug} "
            f"를 먼저 돌릴 것")

    snap = {"master_sha12": _sha12(master_p),
            "units_sha12": _sha12(units_p) if units_p.exists() else "",
            "units_built_at": units_doc.get("built_at", ""),
            "rows": len(rows)}
    return rows, snap


def build_frame(slugs: list[str]) -> tuple[list[dict], dict]:
    """여러 거점의 모집단을 **고유 (지번, 층)** 으로 접는다.

    인접 거점은 같은 건물을 각자 든다(서빙 81거점 실측: 85,316행 → 고유 76,424, 10.8% 중복).
    접지 않으면 모집단이 부풀고 같은 층이 두 번 뽑힐 수 있다. 첫 거점이 갖고, 거점 간 판정이
    갈리는 층은 건수로 남긴다(실측 100/76,424).
    """
    frame: dict[tuple[str, int], dict] = {}
    snaps: dict[str, dict] = {}
    skipped: list[str] = []
    for slug in slugs:
        rows, snap = floor_population(slug)
        if not rows:
            skipped.append(slug)
            continue
        snaps[slug] = snap
        for r in rows:
            key = (r["pnu"], r["floor"])
            first = frame.get(key)
            if first is None:
                r["also_in"] = []
                r["conflict"] = False
                frame[key] = r
            else:
                first["also_in"].append(slug)
                if first["cls"] != r["cls"]:
                    first["conflict"] = True
    out = list(frame.values())
    meta = {
        "rows_with_duplicates": sum(s["rows"] for s in snaps.values()),
        "unique": len(out),
        "cross_hub_duplicates": sum(1 for r in out if r["also_in"]),
        "cross_hub_class_conflicts": sum(1 for r in out if r["conflict"]),
        "skipped_hubs": skipped,
        "snapshots": snaps,
    }
    return out, meta


def scaled_quota(scale: float) -> dict[str, int]:
    return {k: (max(1, math.ceil(v * scale)) if v > 0 else 0) for k, v in _FLOOR_QUOTA.items()}


def draw_floor_sample(frame: list[dict], quota: dict[str, int],
                      seed: int) -> tuple[list[dict], dict]:
    """계층별 단순 무작위 추출. 같은 틀 + 같은 시드면 같은 표본이다.

    틀을 (거점, 지번, 층)으로 정렬한 뒤 뽑는다 — 입력 순서(dict·파일 순서)가 표본을 바꾸지
    못하게 한다. 가중치 = N_h / n_h (그 계층의 틀 크기 / 뽑은 수).
    """
    pools: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(frame, key=lambda r: (r["slug"], r["pnu"], r["floor"])):
        pools[r["stratum"]].append(r)
    rng = random.Random(seed)
    sample: list[dict] = []
    design: dict[str, dict] = {}
    for key in _STRATA:
        pool = pools.get(key, [])
        n_pop, target = len(pool), int(quota.get(key, 0))
        n = min(target, n_pop)
        picked = rng.sample(pool, n) if n else []
        weight = round(n_pop / n, 6) if n else None
        design[key] = {"N": n_pop, "target": target, "n": n, "weight": weight,
                       "census": bool(n) and n == n_pop}
        for r in picked:
            sample.append({**r, "weight": weight, "N_h": n_pop, "n_h": n})
    return sample, design


def _build_gu_map(stores: list[dict]) -> dict[str, str]:
    """stores_raw 에서 {시군구코드5: 구명}. `_build_dong_map` 과 같은 방식이다."""
    m: dict[str, str] = {}
    for s in stores:
        lno = s.get("lnoCd", "")
        if len(lno) != 19 or lno[:5] in m:
            continue
        hit = _GU_TOKEN.search(s.get("lnoAdr", "") or "")
        if hit:
            m[lno[:5]] = hit.group(1)
    return m


def _hub_geo(slug: str) -> tuple[dict[str, str], dict[str, str]]:
    stores = load_latest(slug, "stores_raw.json") or []
    return _build_dong_map(stores), _build_gu_map(stores)


def _address(r: dict, geo: dict[str, tuple[dict, dict]]) -> str:
    """지번 주소. 구·동을 못 찾으면 거점 이름으로 물러난다 — 검색은 항상 걸리게."""
    slug, pnu = r["slug"], r["pnu"]
    if slug not in geo:
        geo[slug] = _hub_geo(slug)
    dong_map, gu_map = geo[slug]
    if len(pnu) != 19:
        return f"{ACTIVE_HUBS[slug].name} {pnu}"
    jibun = _label(pnu, "", dong_map)
    gu = gu_map.get(pnu[:5])
    return f"서울 {gu} {jibun}" if gu else f"{ACTIVE_HUBS[slug].name} {jibun}"


def _filled_labels(path: Path) -> int:
    """라벨러가 채운 칸이 있는 행 수."""
    with path.open(encoding="utf-8-sig", newline="") as fp:
        return sum(1 for row in csv.DictReader(fp)
                   if any((row.get(c) or "").strip() for c in _LABEL_COLS))


def _guard_overwrite(out_dir: Path, force: bool) -> None:
    labels = out_dir / "labels.csv"
    if not labels.exists():
        return
    filled = _filled_labels(labels)
    if filled:
        raise SystemExit(
            f"[floor-sample] {labels} 에 라벨 {filled}행이 이미 있다 — --force 로도 덮지 않는다. "
            f"다른 --tag 를 쓸 것")
    if not force:
        raise SystemExit(f"[floor-sample] {labels} 이(가) 이미 있다 — 덮으려면 --force (라벨 0행일 때만)")


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


_LABEL_FIELDS = ["id", "hub", "address", "floor", "bld_floors", "bldgs_on_pnu", "naver_link",
                 "coord", *_LABEL_COLS]
# 모델이 아는 것(계층·판정·면적·가중치·과거 업종)은 전부 여기에만 둔다 — labels.csv 에 새면 블라인드가 깨진다.
_KEY_FIELDS = ["id", "slug", "pnu", "floor", "band", "stratum", "cls", "certainty", "weight",
               "N_h", "n_h", "bldg_id", "bldgs_on_pnu", "bld_floors", "area_m2", "purps", "was",
               "lat", "lng", "also_in", "conflict"]

_GUIDE_HEAD = """# 층 단위 공실 검증 표본 — 라벨은 `labels.csv` 에 기입

**이 시트를 채울 때 지킬 것 (블라인드)**
- 같은 폴더의 `key.csv`·`design.json` 을 열지 않는다. 앱(PlaceOS)의 해당 건물 화면도 보지 않는다 —
  우리 예측을 알고 보면 라벨이 예측 쪽으로 기운다.
- 라벨은 **그 층의 현재 상태**다. 확인한 **날짜**를 `label_date`(YYYY-MM-DD)에 반드시 적는다.

## 판정 단위 — (지번, 층)
`labels.csv` 한 행 = 한 지번의 한 층. 한 지번에 동이 여럿이면(`bldgs_on_pnu` > 1) 그 지번의
같은 층 **전체**를 하나로 본다(층 근거가 지번 단위로 산출되기 때문이다). 층 번호는 지상 기준이다.

| label_actual | 의미 |
|---|---|
| `공실` | 그 층에 영업·입주 중인 호실이 없다 (임대 현수막·잠김·빈 사무실·철거 중 포함) |
| `부분공실` | 입주한 호실과 빈 호실이 섞여 있다 |
| `영업` | 빈 호실이 없거나 거의 없다 — **점포가 아니라 사무실·학원·병원·주거로 쓰여도 `영업`** |
| `불명` | 들어가 볼 수 없고 외부 정보로도 판정 불가 → 채점 제외 |

`영업`·`부분공실` 이면 `label_use` 에 입주 용도를 적는다: 점포 / 사무실 / 학원 / 의원 / 주거 /
창고 / 기타. 점포 밖 입주(사무실·학원 등)가 "빈 층"으로 잡히는 정도를 이 열로 잰다.

`label_method` 는 어떻게 알았는지다: 현장 / 전화 / 중개사 / 로드뷰 / 기타.
**거리뷰만으로 본 상층 판정은 `로드뷰`로 적는다** — 촬영 시점이 몇 년 전일 수 있어 분석에서
따로 갈라 본다.

## 대상
"""


def _write_floor_sample(out_dir: Path, sample: list[dict], design: dict, geo_cache: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    hub_order = {s: i for i, s in enumerate(ACTIVE_HUBS)}
    # 거점 → 지번 → 층 순. 계층은 이 순서에서 읽히지 않는다(계층은 거점 안에서 섞여 있다).
    ordered = sorted(sample, key=lambda r: (hub_order.get(r["slug"], 10**6), r["pnu"], r["floor"]))

    labels, keys, md = [], [], []
    for i, r in enumerate(ordered, 1):
        rid = f"fs-{r['pnu']}-{r['floor']}"
        addr = _address(r, geo_cache)
        link = f"https://map.naver.com/p/search/{quote(addr)}"
        hub = ACTIVE_HUBS[r["slug"]].name
        labels.append({
            "id": rid, "hub": hub, "address": addr, "floor": f"{r['floor']}층",
            "bld_floors": r["bld_floors"], "bldgs_on_pnu": r["bldgs_on_pnu"],
            "naver_link": link, "coord": f"{r['lat']:.6f},{r['lng']:.6f}",
            **{c: "" for c in _LABEL_COLS},
        })
        keys.append({**{k: r.get(k, "") for k in _KEY_FIELDS if k != "id"}, "id": rid,
                     "also_in": "|".join(r["also_in"])})
        md.append(f"| {i} | {hub} | {addr} | {r['floor']}층 | `{rid}` | [열기]({link}) |")

    _write_csv(out_dir / "labels.csv", _LABEL_FIELDS, labels)
    _write_csv(out_dir / "key.csv", _KEY_FIELDS, keys)
    (out_dir / "design.json").write_text(
        json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")
    guide = _GUIDE_HEAD + f"\n{len(ordered)}층 (지번·층 단위)\n\n" + "\n".join(
        ["| # | 거점 | 주소 | 층 | id | 지도 |", "|---|---|---|---|---|---|", *md]) + "\n"
    (out_dir / "GUIDE.md").write_text(guide, encoding="utf-8")


def run_floors(slugs: list[str], *, scale: float = 1.0, seed: int = _SEED,
               tag: str | None = None, dry_run: bool = False, force: bool = False) -> dict:
    """층 단위 표본을 뽑아 `data/validation/floor_sample_<tag>/` 에 쓴다. 설계 요약을 돌려준다."""
    tag = tag or date.today().strftime("%Y%m%d")
    if not _TAG_RE.match(tag):
        raise SystemExit(f"[floor-sample] --tag 는 영숫자·_- 1~32자여야 한다: {tag!r}")
    if scale <= 0:
        raise SystemExit("[floor-sample] --scale 은 0 보다 커야 한다")

    out_dir = _OUT / f"floor_sample_{tag}"
    if not dry_run:
        _guard_overwrite(out_dir, force)          # 틀을 만들기 전에 — 라벨을 지키는 게 먼저다

    frame, meta = build_frame(slugs)
    if not frame:
        raise SystemExit("[floor-sample] 모집단이 비었다 — 거점의 page_building_master 가 없다")
    quota = scaled_quota(scale)
    sample, strata = draw_floor_sample(frame, quota, seed)

    by_hub = Counter(r["slug"] for r in sample)
    design = {
        "kind": "floor-stratified-random",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tag": tag, "seed": seed, "scale": scale,
        "hubs": slugs, "n_hubs_in_frame": len(meta["snapshots"]),
        "frame": {k: v for k, v in meta.items() if k != "snapshots"},
        "snapshots": meta["snapshots"],
        "unit": "(pnu, floor) — 고유 지번·층. 인접 거점 중복은 첫 거점이 가진다",
        "strata": strata,
        "n_total": len(sample),
        "sample_by_hub": dict(sorted(by_hub.items(), key=lambda kv: -kv[1])),
        "inference": (
            "가중치 w = N_h / n_h. 추론 범위는 `hubs` 에 든 거점의 틀(frame)이다 — 거점을 일부만 "
            "골랐으면 81거점으로 일반화하지 않는다. 화면 빈 층의 precision = 계층 "
            "vacant_confirmed·vacant_probable 안에서 라벨이 공실인 비율(엄격) 또는 공실+부분공실"
            "(관대) — 둘 다 보고한다. 놓친 공실(recall)과 층 공실률은 occupied·unlisted 계층의 "
            "라벨을 w 로 가중해 얻는다. 같은 지번의 여러 층은 상관되니 구간은 pnu 단위 군집 부트스트랩으로."),
        "label_values": list(_LABEL_VALUES),
    }

    if not dry_run:
        _write_floor_sample(out_dir, sample, design, {})
    return design


def _print_design(design: dict, dry_run: bool, out_dir: Path) -> None:
    f = design["frame"]
    print(f"[floor-sample] 틀 {f['unique']:,}층 (거점별 행 {f['rows_with_duplicates']:,} → 고유 · "
          f"거점 간 중복 {f['cross_hub_duplicates']:,} · 판정 불일치 {f['cross_hub_class_conflicts']:,}) "
          f"· 거점 {design['n_hubs_in_frame']}")
    print(f"  {'계층':24}{'N':>9}{'목표':>6}{'n':>6}{'가중치':>10}")
    for key, s in design["strata"].items():
        w = "-" if s["weight"] is None else f"{s['weight']:.1f}" + ("(전수)" if s["census"] else "")
        print(f"  {key:24}{s['N']:>9,}{s['target']:>6}{s['n']:>6}{w:>10}")
    top = list(design["sample_by_hub"].items())[:6]
    print(f"  표본 {design['n_total']}층 · 거점 {len(design['sample_by_hub'])}곳 에 분산 "
          f"(상위 {', '.join(f'{k} {v}' for k, v in top)})")
    if f["skipped_hubs"]:
        print(f"  ⚠ 마스터 없는 거점 건너뜀: {', '.join(f['skipped_hubs'])}")
    print("  (dry-run — 파일을 쓰지 않았다)" if dry_run else f"  → {out_dir}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="로드뷰 검증 표본 생성. 인자 없이: 가로수길 건물 30동(기존). --floors: 층 단위 무작위 층화.")
    ap.add_argument("--floors", action="store_true", help="층 단위 무작위 층화 표본")
    ap.add_argument("--hubs", default="all", help="all 또는 slug,slug,… (기본 서빙 81거점 전부)")
    ap.add_argument("--scale", type=float, default=1.0, help="계층별 목표 표본 수 배율 (예: 0.3)")
    ap.add_argument("--seed", type=int, default=_SEED)
    ap.add_argument("--tag", default=None, help="출력 폴더 floor_sample_<tag> (기본 오늘 날짜)")
    ap.add_argument("--dry-run", action="store_true", help="계층 크기·가중치만 출력하고 쓰지 않는다")
    ap.add_argument("--force", action="store_true", help="라벨이 0행인 기존 시트를 덮어쓴다")
    a = ap.parse_args(argv)
    # Windows 콘솔(cp949)에는 em dash·화살표가 없어 출력에서 죽는다 — score_labels 와 같은 처리.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not a.floors:
        stray = [f for f in ("hubs", "scale", "seed", "tag", "dry_run", "force")
                 if getattr(a, f) != ap.get_default(f)]
        if stray:
            ap.error(f"--{', --'.join(s.replace('_', '-') for s in stray)} 는 --floors 와 함께만 쓴다")
        run()
        return

    slugs = list(ACTIVE_HUBS) if a.hubs == "all" else [s.strip() for s in a.hubs.split(",") if s.strip()]
    unknown = [s for s in slugs if s not in ACTIVE_HUBS]
    if unknown or not slugs:
        ap.error(f"서빙 거점이 아니다: {unknown or '(비었음)'}")
    try:
        design = run_floors(slugs, scale=a.scale, seed=a.seed, tag=a.tag,
                            dry_run=a.dry_run, force=a.force)
    except StaleInventory as e:
        raise SystemExit(f"[floor-sample] {e}") from e
    _print_design(design, a.dry_run, _OUT / f"floor_sample_{design['tag']}")


if __name__ == "__main__":
    main(sys.argv[1:])
