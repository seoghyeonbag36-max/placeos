"""필지 용도지역(V-World) + 용도지역별 행위제한(토지이음) 수집 — Bronze 전용.

Page 2단계 「이 빈 층에 내 업종이 들어갈 수 있나」의 공적 재료다(docs/finding-eum-landuse-2026-11-15.md).

  ① V-World ``ned/data/getLandUseAttr`` (pnu 1콜) — 그 필지가 포함·저촉·접하는 지역지구 코드
  ② 토지이음 ``arLandUseInfoService/DTarLandUseInfo`` (시군구 × 행위명 1콜, 지역지구 코드는 쉼표로 묶음)
     — 지역지구별 그 행위의 가능여부 · 조건 · 건축법 시행령 별표1 조문과 정의(면적 기준 포함)

대상 필지는 서빙 거점 빈 층 유닛(``data/gold/<거점>/vacant_floor_units.json``)의 pnu 다.

    python -m data.collectors.eum_landuse --city seoul                 # ①→② 전부
    python -m data.collectors.eum_landuse --city seoul --stage vworld --date 2026-11-15   # 같은 날짜로 재개
    python -m data.collectors.eum_landuse --city seoul --pnus-file <pnu 배열.json>        # 표본 필지 추가

⚠ 응답 원문만 남긴다(Bronze). 해석·판정은 ``data/pipelines/build_use_check_inputs.py`` 와
  ``apps/backend/app/services/use_check.py`` 몫이다. 이 결과는 **허가 판정이 아니다**.
⚠ 토지이음 응답은 XML 선언 없이 cp949 로 온다(2026-11-15 실측) — ``parse_eum`` 이 처리한다.
⚠ 키는 출력·저장하지 않는다. 응답에 키가 메아리치면 저장을 거부하고 멈춘다.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import threading
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import requests

from data.collectors.common import BRONZE, GOLD, load_env

VWORLD_URL = "https://api.vworld.kr/ned/data/getLandUseAttr"
VWORLD_DOMAIN = "http://localhost:5173"  # 키 발급 때 등록한 도메인(vworld_bldg 와 같다)
EUM_URL = "https://apis.data.go.kr/1613000/arLandUseInfoService/DTarLandUseInfo"

# 12업종(services/business_fit.INDUSTRIES)이 쓰는 토지이음 행위명 — DTsearchLunCd 로 표기를 확인한 것만.
# (2026-11-15 실측: 「소매점」은 정확히 일치하는 행위명이 없고 「일용품을 판매하는 소매점」이 별표1 제3호가목으로 답한다.
#  「공연장」「전시장」은 DTarLandUseInfo 가 빈 응답이라 전시는 「미술관」(제5호라목)으로 본다.)
ACT_NAMES: tuple[str, ...] = (
    "휴게음식점", "일반음식점", "단란주점", "미용원", "의원", "일용품을 판매하는 소매점",
    "학원", "체력단련장", "노래연습장", "일반숙박시설", "미술관",
)
UCODE_CHUNK = 8           # 한 콜에 묶는 지역지구 코드 수(쉼표 구분) — 11-15 실측: 10개 정상 · 11개부터 오류 10
SKIP_PREFIX = ("UQA0",)    # 도시지역(UQA01X) 같은 상위 구분 — 오류 98(SERVICE_ERROR). 행위제한은 하위 용도지역이 답한다
APPLY_REL = ("포함", "저촉")  # 「접함」은 그 필지에 걸리지 않는다

# RLock — 진행 중 매니페스트 flush 가 이미 잡은 잠금 안에서 다시 잡는다(Lock 이면 500건째에 교착 · 2026-11-15 실측)
_lock = threading.RLock()


def parse_eum(raw: bytes) -> ET.Element:
    """토지이음 XML — 선언 없는 cp949, 또는 ``encoding="EUC-KR"`` 선언(ElementTree 가 거부)을 푼다."""
    try:
        return ET.fromstring(raw)
    except (ET.ParseError, ValueError):
        text = raw.decode("cp949", errors="replace").lstrip("﻿")
        if text.startswith("<?xml"):
            text = text[text.index("?>") + 2:]
        return ET.fromstring(text)


def target_pnus(city: str, gold_src: Path) -> list[str]:
    from data.config import page_hubs as ph

    out: set[str] = set()
    for slug, hub in ph.ACTIVE_HUBS.items():
        if hub.city != city:
            continue
        p = gold_src / slug / "vacant_floor_units.json"
        if not p.exists():
            print(f"[skip] {slug}: vacant_floor_units.json 없음")
            continue
        for u in json.loads(p.read_text(encoding="utf-8")).get("units", []):
            if u.get("pnu"):
                out.add(str(u["pnu"]))
    return sorted(out)


class Saver:
    """원문 저장 + 키 메아리 차단 + 매니페스트(키 제외 요청 조건)."""

    def __init__(self, root: Path, secrets: list[str]):
        self.root = root
        self.secrets = [s.encode() for s in secrets if s]
        self.rows: list[dict] = []

    def save(self, rel: str, raw: bytes, meta: dict) -> None:
        for s in self.secrets:
            if s in raw:
                raise RuntimeError("credential_echo — 응답에 키가 들어 있어 저장하지 않는다")
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        with _lock:
            self.rows.append({"file": rel, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), **meta})

    def flush(self, name: str) -> None:
        with _lock:
            (self.root / name).write_text(json.dumps(self.rows, ensure_ascii=False, indent=1), encoding="utf-8")


def fetch_vworld(pnus: list[str], root: Path, workers: int) -> dict:
    key = os.environ["VWORLD_API_KEY"]
    saver = Saver(root, [key, os.environ.get("DATA_GO_KR_SERVICE_KEY", "")])
    todo = [p for p in pnus if not (root / "vworld" / p[:5] / f"{p}.json").exists()]
    print(f"[vworld] 대상 {len(pnus)} · 이미 받음 {len(pnus) - len(todo)} · 남음 {len(todo)}")
    stats = defaultdict(int)
    stop = threading.Event()

    def one(pnu: str) -> None:
        if stop.is_set():
            return
        pages, page, total = [], 1, None
        while True:
            for attempt in range(3):
                try:
                    r = requests.get(VWORLD_URL, params={"key": key, "domain": VWORLD_DOMAIN, "pnu": pnu,
                                                         "format": "json", "numOfRows": 100, "pageNo": page},
                                     timeout=(10, 40))
                    break
                except requests.RequestException:
                    time.sleep(2 + attempt * 3)
            else:
                with _lock:
                    stats["network_fail"] += 1
                return
            try:
                lu = r.json().get("landUses") or {}
            except ValueError:
                lu = {}
            if r.status_code != 200 or lu.get("resultCode"):
                with _lock:
                    stats[f"error:{r.status_code}:{lu.get('resultCode')}"] += 1
                    if sum(v for k, v in stats.items() if k.startswith("error")) >= 20:
                        stop.set()  # 쿼터·키 문제 — 더 두드리지 않는다
                return
            pages.append(lu)
            total = int(lu.get("totalCount") or 0)
            if page * 100 >= total:
                break
            page += 1
        raw = json.dumps({"pnu": pnu, "pages": pages}, ensure_ascii=False).encode("utf-8")
        saver.save(f"vworld/{pnu[:5]}/{pnu}.json", raw, {"pnu": pnu, "totalCount": total})
        with _lock:
            stats["ok"] += 1
            stats["empty" if not total else "with_rows"] += 1
            if stats["ok"] % 500 == 0:
                print(f"[vworld] {stats['ok']}/{len(todo)}", flush=True)
                saver.flush("vworld_manifest.part.json")

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, todo))
    saver.flush(f"vworld_manifest_{dt.datetime.now():%H%M%S}.json")
    print(f"[vworld] 끝 {dict(stats)}" + (" — 오류가 쌓여 멈췄다" if stop.is_set() else ""))
    return dict(stats)


def parcel_codes(root: Path) -> dict[str, set[str]]:
    """시군구(pnu 앞 5자리) → 그 구 필지에 걸리는(포함·저촉) 지역지구 코드."""
    by_gu: dict[str, set[str]] = defaultdict(set)
    for p in (root / "vworld").glob("*/*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        for page in d["pages"]:
            for f in page.get("field") or []:
                code = f.get("prposAreaDstrcCode")
                if f.get("cnflcAtNm") in APPLY_REL and code and not code.startswith(SKIP_PREFIX):
                    by_gu[d["pnu"][:5]].add(code)
    return by_gu


def fetch_eum(root: Path, workers: int, key_env: str = "DATA_GO_KR_SERVICE_KEY") -> dict:
    """⚠ 개발계정 일일 한도 — 11-15 에 약 1,000콜째부터 HTTP 429 · returnReasonCode 22(일일 요청제한 초과).
    한도에 걸리면 남은 콜을 두드리지 않고 멈춘다. 같은 날짜로 다시 돌리면 받은 파일은 건너뛴다(자정 뒤 재개)."""
    key = os.environ[key_env]
    saver = Saver(root, [key, os.environ.get("VWORLD_API_KEY", ""), os.environ.get("EUM_API_KEY", "")])
    by_gu = parcel_codes(root)
    jobs = []
    for gu, codes in sorted(by_gu.items()):
        codes = sorted(codes)
        for i in range(0, len(codes), UCODE_CHUNK):
            chunk = codes[i:i + UCODE_CHUNK]
            for act in ACT_NAMES:
                tag = hashlib.sha1(",".join(chunk).encode()).hexdigest()[:8]
                rel = f"eum/{gu}/{act}__{tag}.xml"
                if not (root / rel).exists():
                    jobs.append((gu, chunk, act, rel))
    print(f"[eum] 구 {len(by_gu)} · 남은 콜 {len(jobs)}")
    stats = defaultdict(int)
    quota = threading.Event()

    def one(job) -> None:
        if quota.is_set():
            with _lock:
                stats["skipped_after_quota"] += 1
            return
        gu, chunk, act, rel = job
        params = {"areaCd": gu, "ucodeList": ",".join(chunk), "landUseNm": act}
        for attempt in range(3):
            try:
                r = requests.get(EUM_URL, params={**params, "serviceKey": key}, timeout=(10, 30))
                break
            except requests.RequestException:
                time.sleep(2 + attempt * 3)
        else:
            with _lock:
                stats["network_fail"] += 1
            return
        try:
            doc = parse_eum(r.content)
            code = doc.findtext(".//resultCode") or doc.findtext(".//returnReasonCode")
        except ET.ParseError:
            code = "unparsable"
        if r.status_code == 429 or code == "22":
            quota.set()
        if r.status_code != 200 or code not in ("0", "00"):
            with _lock:
                stats[f"error:{r.status_code}:{code}"] += 1
                if stats[f"error:{r.status_code}:{code}"] <= 2:  # 원인 확인용으로 오류 원문 2건만 남긴다
                    saver.save(f"eum_errors/{gu}_{act}_{code}.xml", r.content,
                               {"params_wo_key": params, "http_status": r.status_code, "resultCode": code})
            return
        saver.save(rel, r.content, {"params_wo_key": params, "http_status": r.status_code, "resultCode": code})
        with _lock:
            stats["ok"] += 1
            if stats["ok"] % 100 == 0:
                print(f"[eum] {stats['ok']}/{len(jobs)}", flush=True)
                saver.flush("eum_manifest.part.json")

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, jobs))
    saver.flush(f"eum_manifest_{dt.datetime.now():%H%M%S}.json")
    print(f"[eum] 끝 {dict(stats)}" + (" — 일일 한도 초과로 멈췄다(같은 날짜로 자정 뒤 재개)" if quota.is_set() else ""))
    return dict(stats)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--city", default="seoul")
    ap.add_argument("--stage", choices=("vworld", "eum", "all"), default="all")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="같은 날짜를 주면 그 실행을 이어 받는다")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="스모크용 — 앞 N 필지만")
    ap.add_argument("--key-env", default="DATA_GO_KR_SERVICE_KEY",
                    help="토지이음 콜에 쓸 키의 환경변수 이름(같은 서비스에 승인된 키만 — 예: EUM_API_KEY)")
    ap.add_argument("--pnus-file", type=Path, default=None,
                    help="빈 층 대신 이 JSON 배열의 pnu 를 받는다(사전등록 채점 표본 필지 등) — 이미 받은 필지는 건너뛴다")
    ap.add_argument("--gold-src", type=Path, default=Path(os.environ.get("PLACEOS_GOLD_SRC") or GOLD),
                    help="vacant_floor_units.json 을 읽을 Gold 루트(worktree 에서는 메인 체크아웃을 가리킨다)")
    a = ap.parse_args()
    if os.environ.get("PLACEOS_ENV_FILE"):  # worktree 에는 data/.env 가 없다 — 메인 체크아웃의 것을 가리킨다
        from data.run_collection import _load_env

        _load_env(Path(os.environ["PLACEOS_ENV_FILE"]))
    else:
        load_env()
    root = BRONZE / "landuse" / a.city / a.date
    root.mkdir(parents=True, exist_ok=True)
    summary: dict = {"city": a.city, "date": a.date, "started_at": dt.datetime.now().isoformat(timespec="seconds")}
    if a.stage in ("vworld", "all"):
        pnus = (json.loads(a.pnus_file.read_text(encoding="utf-8")) if a.pnus_file
                else target_pnus(a.city, a.gold_src))
        if a.limit:
            pnus = pnus[:a.limit]
        summary["target_pnus"] = len(pnus)
        (root / "target_pnus.json").write_text(json.dumps(pnus), encoding="utf-8")
        summary["vworld"] = fetch_vworld(pnus, root, a.workers)
    if a.stage in ("eum", "all"):
        summary["eum"] = fetch_eum(root, max(1, min(a.workers, 4)), a.key_env)
    summary["finished_at"] = dt.datetime.now().isoformat(timespec="seconds")
    (root / f"run_{dt.datetime.now():%H%M%S}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                                               encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
