"""건축HUB 대장 응답 캐시 — 광주·전주 조사 원장(Bronze)의 검증된 페이지를 같은 요청에 다시 쓴다 (2026-11-09).

## 왜
조사 수집기(`scripts/collect_regional_research_ledgers.py`)가 받은 전유부(getBrExposPubuseAreaInfo)·층별개요
(getBrFlrOulnInfo) 페이지는, 대장 수집기(`building_vacancy` · `floor_capacity`)가 **같은 지번에 보내는 요청과 파라미터가
같다**(`_type=json` · `numOfRows=100` · `pageNo` · `_jibun(pnu)`). 그 지번을 거점으로 승격할 때 같은 응답을 다시 받느라
일일 쿼터(오퍼레이션당 10,000콜)를 태우지 않게, 조사 원장의 응답을 그대로 돌려준다. 2026-11-09 광주·전주 2차 51곳 승격에서
점포 지번 20,358곳의 전유부·층별개요가 이미 받아져 있었다 → docs/decision-gwangju-jeonju-batch2-2026-11-09.md

## 무엇을 믿나
- 완료 표식 `data/bronze/regional_research_ledgers/2026-11-03/{expos|floors}/{pnu}/complete.json` 이 `complete: true` 이고
  `received == total` 인 지번만 쓴다. 조사 수집기는 페이지마다 헤더·전체 건수·중복을 검증한 뒤에만 이 표식을 쓴다.
- 페이지 파일은 표식에 적힌 sha256 과 대조한 뒤에만 돌려준다. 어긋나면 캐시를 쓰지 않고 실호출로 넘긴다.
- 표제부(getBrTitleInfo)는 조사에서 받지 않았으므로 **늘 실호출**이다. 다른 엔드포인트도 손대지 않는다.

## 켜는 법
**기본으로 켜져 있다** — 끄려면 환경변수 `PLACEOS_LEDGER_CACHE=0`. 기본값을 켬으로 둔 이유: 대장 수집은 쿼터가 끝나면 다음 날
예약 작업(`resume_hub_chain.py`)이 배치를 되살리는데, 그 환경에는 이 변수가 없다. 꺼짐이 기본이면 되살아난 배치가 같은 응답을
다시 받느라 전유부 쿼터를 통째로 태운다(51곳 기준 약 2만 콜). 캐시는 같은 파라미터의 검증된 응답만 주므로 켜 둬도 결과가 같다.
캐시가 없는 지번(서울 등 조사 밖)은 지금과 똑같이 실호출이다.
응답 본문은 API 가 준 JSON 그대로라 Bronze `bldg_ledger_raw.json` · `bldg_flr_raw.json` 의 형식도 같다.
"""
from __future__ import annotations

import atexit
import gzip
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKERS = ROOT / "data" / "bronze" / "regional_research_ledgers" / "2026-11-03"
_EP_DIR = {"getBrExposPubuseAreaInfo": "expos", "getBrFlrOulnInfo": "floors"}

STATS: Counter = Counter()
_markers: dict[tuple[str, str], dict | None] = {}


def enabled() -> bool:
    return os.getenv("PLACEOS_LEDGER_CACHE", "1") != "0"


def pnu_of(params: dict) -> str | None:
    """`building_vacancy._jibun` 의 역. platGbCd 0→1(대지) · 1→2(산). 같은 파라미터면 같은 응답이라 역산이 안전하다."""
    try:
        sigungu, bjdong = str(params["sigunguCd"]), str(params["bjdongCd"])
        plat, bun, ji = int(params["platGbCd"]), str(params["bun"]), str(params["ji"])
    except (KeyError, TypeError, ValueError):
        return None
    if len(sigungu) != 5 or len(bjdong) != 5 or len(bun) != 4 or len(ji) != 4 or plat not in (0, 1):
        return None
    return f"{sigungu}{bjdong}{plat + 1}{bun}{ji}"


def _marker(ep_dir: str, pnu: str) -> dict | None:
    key = (ep_dir, pnu)
    if key not in _markers:
        path = MARKERS / ep_dir / pnu / "complete.json"
        doc = None
        try:
            m = json.loads(path.read_text(encoding="utf-8"))
            if (m.get("complete") is True and m.get("pnu") == pnu and isinstance(m.get("total"), int)
                    and m.get("received") == m.get("total") and m.get("pages")):
                doc = m
        except (OSError, ValueError):
            doc = None
        _markers[key] = doc
    return _markers[key]


def lookup(url: str, params: dict) -> dict | None:
    """캐시에 정확히 같은 요청의 검증된 응답이 있으면 그 JSON, 아니면 None(→ 호출부가 실호출)."""
    if not enabled():
        return None
    ep_dir = _EP_DIR.get(url.rsplit("/", 1)[-1])
    if ep_dir is None:
        return None
    try:
        if str(params.get("_type")) != "json" or int(params.get("numOfRows", 0)) != 100:
            STATS["skip_params"] += 1
            return None
        page = int(params.get("pageNo", 1))
    except (TypeError, ValueError):
        return None
    pnu = pnu_of(params)
    marker = _marker(ep_dir, pnu) if pnu else None
    if marker is None:
        STATS[f"miss_{ep_dir}"] += 1
        return None
    want = f"page_{page:05d}.json"
    entry = next((p for p in marker["pages"] if Path(p["path"]).name.startswith(want)), None)
    if entry is None:
        STATS[f"miss_page_{ep_dir}"] += 1
        return None
    path = ROOT / entry["path"]
    try:
        raw = path.read_bytes()
    except OSError:
        STATS[f"miss_file_{ep_dir}"] += 1
        return None
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        STATS[f"hash_mismatch_{ep_dir}"] += 1
        return None
    body = gzip.decompress(raw) if path.suffix == ".gz" else raw
    STATS[f"hit_{ep_dir}"] += 1
    return json.loads(body.decode("utf-8"))


@atexit.register
def _report() -> None:
    if enabled() and STATS:
        print("[ledger-cache] " + " · ".join(f"{k} {v:,}" for k, v in sorted(STATS.items())), flush=True)
