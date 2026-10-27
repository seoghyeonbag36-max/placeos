"""[Platform·흐름] 수도권 생활이동(출발-도착지 기준) 수집기 — 파주·고양·서울 사이의 유입 흐름.

## 이 데이터가 무엇인가

서울시×KT 「수도권 생활이동 (출발-도착지 기준)」(data.seoul.go.kr **OA-22300**). 수도권이
출발이거나 도착인 이동을 **행정동 → 행정동 · 출발/도착 시각 · 이동목적 7종 · 거리 · 시간 ·
인원**으로 집계한 일별 파일이다. 공공누리 1유형(출처표시 · **상업적 이용 가능**).

⚠ **동선이 아니다.** 한 사람의 궤적(A→B→C)은 원천에 없다 — 출발지별 도착 인원 집계다
(docs/finding-movement-viz-2026-09-17.md). 이 수집기가 만드는 것은 **유입 흐름**이다.

⚠ 경기데이터드림의 KT 행정동 OD(같은 축)는 **상업용 금지(공공누리 2유형)**라 쓰지 않는다
(2026-10-26 확인). 유료 SaaS 화면에 들어가는 숫자의 원천은 상업 이용이 허용돼야 한다.

## 받는 방법 (2026-10-26 실측)

로그인 없이 POST 한 번으로 ZIP 이 내려온다 — 09-17 문서의 「포털 로그인 뒤 수동」은 그때
환경(이그레스 차단)에서 확인하지 못한 것이었다. 하루치 ZIP 56~78MB · 풀면 CSV 약 465MB ·
670만 행. 원본은 저장소에 두지 않는다(`data/raw/`, gitignore).

## 열(실측 헤더) — 바뀌면 멈춘다

    o_admdong_cd, d_admdong_cd, st_time_cd, fns_time_cd, in_forn_div_nm, forn_citiz_nm,
    move_purpose, move_dist, move_time, cnt, etl_ymd

인코딩은 **cp949** 다(utf-8 로 읽으면 내/외국인 열이 깨진다). 헤더가 다르면 추측해서 잇지 않고
실제 헤더를 찍고 멈춘다 — 조용한 기본값이 gold 까지 흘러가는 것을 막는다.

## 해상도가 도시마다 다르다 (2026-10-26 실측 — 이 수집기의 설계가 갈리는 지점)

하루치 670만 행의 코드를 전수로 셌다: **서울 427개는 행정동**(8자리, 끝 3자리 ≠ 000)인데
**경기 47개 · 인천 11개는 전부 시군구**(`41480000` 파주시 · `41287000` 고양 일산서구 …)다.
즉 이 데이터로는 「금촌 사람들이 홍대로 간다」를 잴 수 없고 「**파주시** 사람들이 서교동으로
간다」까지만 잴 수 있다. 그래서 경기 거점은 자기 시군구 단위(`unit_level: "sgg"`)로 잇고,
서울 거점만 행정동 단위(`"adong"`)로 잇는다. 같은 시군구의 경기 거점들은 **같은 흐름 값을
공유한다** — 거점마다 다른 값인 척하지 않는다.

## 시각 코드도 섞여 있다

`st_time_cd`·`fns_time_cd` 는 대부분 `HH` 인데 출퇴근 시간대(07~09시 · 17~19시)만 20분 단위
`HHMM`(`0700` `0720` `0740` …)이다. 앞 두 자리로 묶어 0~23시로 센다.

## 이동목적 코드

서울시 빅데이터캠퍼스 자료안내서(B078 수도권 생활이동): 1 출근 · 2 등교 · 3 귀가 · 4 쇼핑 ·
5 관광 · 6 병원 · 7 기타. ⚠ 포털 설명문의 나열 순서(출근·등교·쇼핑·관광·병원·귀가·기타)와
**코드 순서가 다르다** — 나열 순서로 붙이면 3(귀가)이 쇼핑이 된다. 실측 분포도 안내서 쪽을
지지한다(파주·고양 관련 하루: 3번 165만 · 4번 1.3만 — 귀가가 쇼핑보다 100배 많을 수는 있어도
반대는 아니다).

산출: data/bronze/corridor/{날짜}/capital_od_{corridor}.json
실행:
    python -m data.collectors.capital_od --days 2026-09-14..2026-09-20
    python -m data.collectors.capital_od --days 2026-09-14..2026-09-20 --no-download
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from data.collectors.common import DATA_ROOT, load_env, save_json
from data.config.corridors import CORRIDORS, outer_group
from data.config.page_hubs import ACTIVE_HUBS

DATASET = "OA-22300"
_DOWNLOAD = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
SOURCE = "서울시×KT 수도권 생활이동(출발-도착지 기준) · data.seoul.go.kr OA-22300 · 공공누리 1유형"

PURPOSE: dict[str, str] = {
    "1": "출근", "2": "등교", "3": "귀가", "4": "쇼핑", "5": "관광", "6": "병원", "7": "기타",
}

_HEADER = ("o_admdong_cd", "d_admdong_cd", "st_time_cd", "fns_time_cd", "in_forn_div_nm",
           "forn_citiz_nm", "move_purpose", "move_dist", "move_time", "cnt", "etl_ymd")

# 거점 → 행정동 배정에서 버리는 꼬리. 거점 점포의 이 비율 미만인 행정동은 그 거점의 것이 아니다
# (반경 경계에 걸친 점포 몇 곳 때문에 행정동 하나가 통째로 붙지 않게).
ADONG_MIN_SHARE = 0.10


def raw_dir() -> Path:
    d = Path(os.environ.get("CAPITAL_OD_DIR") or (DATA_ROOT / "raw" / "capital_od"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _days(spec: str) -> list[dt.date]:
    """'2026-09-14..2026-09-20' 또는 '2026-09-14,2026-09-16'."""
    if ".." in spec:
        a, b = (dt.date.fromisoformat(x) for x in spec.split(".."))
        return [a + dt.timedelta(n) for n in range((b - a).days + 1)]
    return [dt.date.fromisoformat(x) for x in spec.split(",") if x]


def download(day: dt.date) -> Path:
    """하루치 ZIP. 이미 받은 것은 다시 받지 않는다(ZIP 으로 열리면 완료로 본다)."""
    out = raw_dir() / f"seoul_purpose_admdong3_{day:%Y%m%d}.zip"
    if out.exists() and zipfile.is_zipfile(out):
        return out
    body = urllib.parse.urlencode({"infId": DATASET, "seqNo": "", "seq": f"{day:%y%m%d}",
                                   "infSeq": "1"}).encode()
    req = urllib.request.Request(_DOWNLOAD, data=body, method="POST")
    tmp = out.with_suffix(".part")
    with urllib.request.urlopen(req, timeout=600) as r, tmp.open("wb") as f:
        head = r.read(4)
        if head != b"PK\x03\x04":
            # 로그인 페이지·오류 HTML 이 200 으로 오면 여기서 멈춘다 — ZIP 인 척 넘기지 않는다
            raise SystemExit(f"[capital_od] {day}: ZIP 이 아니다(앞 4바이트 {head!r}) — "
                             "포털이 다운로드 방식을 바꿨는지 확인할 것")
        f.write(head)
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.replace(out)
    print(f"[capital_od] {day} 받음 — {out.stat().st_size / 1e6:.1f}MB")
    return out


def _sgg_unit(adong_cd: str) -> str:
    """행정동 코드 → 이 데이터의 시군구 단위 코드(`41480510` → `41480000`)."""
    return f"{str(adong_cd)[:5]}000"


def unit_level(adong_cd: str) -> str:
    """이 데이터가 그 지역을 어떤 해상도로 싣는가 — 서울만 행정동, 나머지는 시군구(실측)."""
    return "adong" if str(adong_cd).startswith("11") else "sgg"


def hub_adong_shares(slugs) -> dict[str, dict[str, float]]:
    """거점 → {이 데이터의 단위 코드: 그 거점 점포 중 비중}. 상가정보 `adongCd` 로 정한다.

    카카오 역지오코딩(`build_hub_adong`) 없이 정해진다 — 점포가 이미 행정동을 들고 있다.
    `ADONG_MIN_SHARE` 미만은 버리고 남은 비중을 다시 1 로 맞춘다. 서울 밖 거점은 행정동을
    **시군구 단위로 접는다** — 이 데이터가 거기까지만 싣기 때문이다(모듈 머리말).
    """
    out: dict[str, dict[str, float]] = {}
    for slug in slugs:
        files = sorted((DATA_ROOT / "bronze" / slug).glob("*/stores_raw.json"))
        if not files:
            continue
        rows = json.loads(files[-1].read_text(encoding="utf-8"))
        items = rows if isinstance(rows, list) else rows.get("items", [])
        c = Counter()
        for x in items:
            cd = str(x.get("adongCd") or "")
            if cd:
                c[cd if unit_level(cd) == "adong" else _sgg_unit(cd)] += 1
        n = sum(c.values())
        kept = {k: v / n for k, v in c.items() if n and v / n >= ADONG_MIN_SHARE}
        s = sum(kept.values())
        if s:
            out[slug] = {k: round(v / s, 4) for k, v in kept.items()}
    return out


def _rows(path: Path):
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.lower().endswith(".csv"):
                continue
            with z.open(name) as fh:
                yield from csv.reader(io.TextIOWrapper(fh, encoding="cp949", errors="replace"))


def _acc() -> dict:
    return {"total": 0.0, "purpose": defaultdict(float), "arr_hour": defaultdict(float),
            "by_day": defaultdict(float), "min_sum": 0.0, "m_sum": 0.0}


def _add(a: dict, cnt: float, purpose: str, hour: str, ymd: str, mins: float, dist: float) -> None:
    a["total"] += cnt
    a["purpose"][purpose] += cnt
    a["arr_hour"][hour] += cnt
    a["by_day"][ymd] += cnt
    a["min_sum"] += mins * cnt
    a["m_sum"] += dist * cnt


def _dump(a: dict) -> dict:
    t = a["total"]
    return {
        "total": round(t, 1),
        "purpose": {PURPOSE.get(k, k): round(v, 1) for k, v in sorted(a["purpose"].items())},
        "arr_hour": {k: round(v, 1) for k, v in sorted(a["arr_hour"].items())},
        "by_day": {k: round(v, 1) for k, v in sorted(a["by_day"].items())},
        "avg_min": round(a["min_sum"] / t, 1) if t else None,
        "avg_km": round(a["m_sum"] / t / 1000, 2) if t else None,
    }


def collect(files: list[Path], corridor_id: str = "paju-goyang-seoul") -> dict:
    cor = CORRIDORS[corridor_id]
    # 추적 행정동 = 이 흐름 구간에 있는 서빙 거점의 행정동
    seg_keys = {s.key for s in cor.segments}
    hubs = {s: h for s, h in ACTIVE_HUBS.items() if h.city in seg_keys}
    shares = hub_adong_shares(hubs)
    tracked = {cd for m in shares.values() for cd in m}
    print(f"[capital_od] 파일 {len(files)}개 · 거점 {len(shares)}/{len(hubs)} · 추적 행정동 {len(tracked)}")

    seg_of_cache: dict[str, str] = {}

    def seg(cd: str) -> str:
        v = seg_of_cache.get(cd)
        if v is None:
            v = cor.segment_of(cd) or outer_group(cd)
            seg_of_cache[cd] = v
        return v

    city_od: dict[tuple[str, str], dict] = defaultdict(_acc)
    sgg_od: dict[tuple[str, str], dict] = defaultdict(_acc)
    adong_in: dict[str, dict] = defaultdict(lambda: {**_acc(), "from_seg": defaultdict(float),
                                                      "from_sgg": defaultdict(float)})
    adong_out: dict[str, dict] = defaultdict(lambda: {**_acc(), "to_seg": defaultdict(float),
                                                       "to_sgg": defaultdict(float)})
    pair: dict[tuple[str, str], dict] = defaultdict(_acc)
    scanned = kept = masked = 0
    foreign = 0.0
    days: list[str] = []

    for path in files:
        it = _rows(path)
        header = next(it, None)
        if header is None or tuple(h.strip().lower() for h in header) != _HEADER:
            raise SystemExit(f"[capital_od] {path.name}: 헤더가 다르다\n    실제: {header}\n"
                             f"    기대: {list(_HEADER)}\n    → 배포분 변경 — 추측으로 잇지 않는다")
        t0 = time.time()
        for row in it:
            scanned += 1
            o, d = row[0], row[1]
            so, sd = seg(o), seg(d)
            if so not in seg_keys and sd not in seg_keys:
                continue
            try:
                cnt = float(row[9])
            except ValueError:
                masked += 1                 # 비식별 가림(`*`) — 0 으로 접지 않는다
                continue
            kept += 1
            # 도착 시각 — 출퇴근대만 HHMM(20분)이라 앞 두 자리로 묶는다(모듈 머리말)
            purpose, hour, ymd = row[6], row[3][:2], row[10]
            try:
                dist, mins = float(row[7]), float(row[8])
            except ValueError:
                dist, mins = 0.0, 0.0
            if not row[4].startswith("내"):
                foreign += cnt
            _add(city_od[(so, sd)], cnt, purpose, hour, ymd, mins, dist)
            if so in seg_keys and sd in seg_keys:
                _add(sgg_od[(o[:5], d[:5])], cnt, purpose, hour, ymd, mins, dist)
            if d in tracked:
                a = adong_in[d]
                _add(a, cnt, purpose, hour, ymd, mins, dist)
                a["from_seg"]["self" if o == d else so] += cnt
                a["from_sgg"][o[:5]] += cnt
            if o in tracked:
                a = adong_out[o]
                _add(a, cnt, purpose, hour, ymd, mins, dist)
                a["to_seg"]["self" if o == d else sd] += cnt
                a["to_sgg"][d[:5]] += cnt
                if d in tracked and d != o:
                    _add(pair[(o, d)], cnt, purpose, hour, ymd, mins, dist)
        days.append(path.stem[-8:])
        print(f"[capital_od] {path.name} — 누적 {scanned:,}행 스캔 · {kept:,}행 사용 · {time.time() - t0:.0f}s")

    def top(m: dict, n: int = 30) -> dict:
        return {k: round(v, 1) for k, v in sorted(m.items(), key=lambda kv: -kv[1])[:n]}

    doc = {
        "corridor": corridor_id,
        "source": SOURCE,
        "dataset": DATASET,
        "days": sorted(days),
        "n_days": len(days),
        "rows_scanned": scanned,
        "rows_used": kept,
        "masked_rows": masked,
        "foreign_trips": round(foreign, 1),
        "purpose_codes": PURPOSE,
        "note": ("출발 → 도착 **집계**다. 한 사람의 동선이 아니다. 값은 기간 합계 — 일평균은 "
                 "n_days 로 나눈다. 도착시각(fns_time_cd) 기준 시간대. 서울은 행정동, 경기·인천은 "
                 "시군구 단위로만 실린다(같은 시군구의 경기 거점은 같은 값을 공유한다)."),
        "hub_adongs": shares,
        "unit_level": {cd: unit_level(cd) for m in shares.values() for cd in m},
        "city_od": {f"{a}|{b}": _dump(v) for (a, b), v in sorted(city_od.items())},
        "sgg_od": {f"{a}|{b}": {"total": round(v["total"], 1),
                                "purpose": {PURPOSE.get(k, k): round(x, 1) for k, x in v["purpose"].items()},
                                "avg_min": round(v["min_sum"] / v["total"], 1) if v["total"] else None}
                   for (a, b), v in sorted(sgg_od.items())},
        "adong_in": {cd: {**_dump(v), "from_seg": top(v["from_seg"]), "from_sgg": top(v["from_sgg"])}
                     for cd, v in sorted(adong_in.items())},
        "adong_out": {cd: {**_dump(v), "to_seg": top(v["to_seg"]), "to_sgg": top(v["to_sgg"])}
                      for cd, v in sorted(adong_out.items())},
        # 거점 행정동 ↔ 거점 행정동. 도착 시각까지 남긴다 — 「그 동네 사람이 몇 시에 이 상권에
        # 닿나」가 영업시간·검증 시간대를 정하는 재료다.
        "adong_pair": {f"{a}|{b}": {"total": round(v["total"], 1),
                                    "purpose": {PURPOSE.get(k, k): round(x, 1) for k, x in v["purpose"].items()},
                                    "arr_hour": {k: round(x, 1) for k, x in sorted(v["arr_hour"].items())},
                                    "avg_min": round(v["min_sum"] / v["total"], 1) if v["total"] else None}
                       for (a, b), v in sorted(pair.items()) if v["total"] >= 1.0},
    }
    save_json(doc, "corridor", f"capital_od_{corridor_id}.json")
    return doc


def main() -> None:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", required=True, help="2026-09-14..2026-09-20 또는 쉼표 목록")
    ap.add_argument("--corridor", default="paju-goyang-seoul", choices=sorted(CORRIDORS))
    ap.add_argument("--no-download", action="store_true", help="캐시에 있는 파일만 쓴다")
    a = ap.parse_args()
    files = []
    for day in _days(a.days):
        p = raw_dir() / f"seoul_purpose_admdong3_{day:%Y%m%d}.zip"
        if not a.no_download:
            p = download(day)
        if not p.exists():
            raise SystemExit(f"[capital_od] {p} 없음 — --no-download 를 빼고 다시")
        files.append(p)
    collect(files, a.corridor)


if __name__ == "__main__":
    sys.exit(main())
