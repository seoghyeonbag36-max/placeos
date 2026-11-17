"""V-World 토지특성(`ned/data/getLandCharacteristics`) 수집 — 필지별 도로접면·개별공시지가·용도지역·면적(연도별).

연구(docs/finding-digital-premium-inputs-2026-11-17.md §2): 「입지 프리미엄」의 두 변수 — **도로접면**(대로변 여부)과
**개별공시지가**(가격 대리변수)가 같은 호출 한 번에 온다. 2013~ 연도별 행이라 시계열 패널이 된다.

    python -m data.collectors.vworld_landchar --hubs garosugil,hongdae,gangnam
    python -m data.collectors.vworld_landchar --city seoul            # 서울 81거점 전 필지(수만 콜 — 이어받기)
    python -m data.collectors.vworld_landchar --city seoul --limit 2000

대상 PNU 는 거점 건물 폴리곤 산출물(`data/gold/<거점>/page_building_master.geojson`)의 PNU 다.
결과: `data/bronze/landchar/landchar_seoul.json` 한 파일(필지 → 연도별 [연도, 접도코드명, 공시지가] + 정적 속성).
**이어받는다** — 이미 받은 필지는 건너뛰고, 500건마다 저장하며, 할당량·연속 실패가 보이면 멈춘다.

⚠ `VWORLD_API_KEY` 만 쓴다(토지이음 일일 한도 1,000콜과 별개 키). 키는 출력·저장하지 않는다.
⚠ 도로접면 **세부 코드**는 자주 바뀐다(한면↔각지) — 분석은 군(광대*/중로*/그외)으로 한다(`road_group`).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import time
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import BRONZE, GOLD, load_env

URL = "https://api.vworld.kr/ned/data/getLandCharacteristics"
DOMAIN = "http://localhost:5173"  # 키 발급 때 등록한 도메인(vworld_bldg 와 같다)
OUT = BRONZE / "landchar" / "landchar_seoul.json"
_SAVE_EVERY = 500
_MAX_CONSEC_FAIL = 25


def road_group(name: str | None) -> str:
    """도로접면 코드명 → 군. 광대*(광로·대로 접) = 대로변 / 중로* / 그외(소로·세로·지정되지않음 등)."""
    n = (name or "").strip()
    if n.startswith("광대"):
        return "대로변"
    if n.startswith("중로"):
        return "중로"
    return "그외"


def compact(rows: list[dict]) -> dict:
    """응답 행 → {"y": [[연도, 접도코드명, 공시지가]...](연도 오름차순·연도당 1행), "z": 용도지역, "a": 면적㎡}.

    같은 연도에 행이 여럿이면(기준월 차이) 기준월이 늦은 행을 쓴다. 가격은 문자열 → 정수, 없으면 None.
    """
    by_year: dict[str, dict] = {}
    for r in sorted(rows, key=lambda r: (r.get("stdrYear", ""), r.get("stdrMt", ""))):
        by_year[r.get("stdrYear", "")] = r
    ys = []
    for y, r in sorted(by_year.items()):
        try:
            price = int(float(r.get("pblntfPclnd")))
        except (TypeError, ValueError):
            price = None
        ys.append([int(y) if y.isdigit() else y, r.get("roadSideCodeNm") or None, price])
    last = by_year[max(by_year)] if by_year else {}
    try:
        area = float(last.get("lndpclAr"))
    except (TypeError, ValueError):
        area = None
    return {"y": ys, "z": last.get("prposArea1Nm") or None, "a": area}


def hub_pnus(slugs: list[str]) -> dict[str, list[str]]:
    out = {}
    for s in slugs:
        p = GOLD / s / "page_building_master.geojson"
        if p.exists():
            g = json.loads(p.read_text(encoding="utf-8"))
            out[s] = sorted({str(f["properties"]["pnu"]) for f in g["features"] if f["properties"].get("pnu")})
    return out


def _fetch(key: str, pnu: str) -> tuple[str, dict]:
    for attempt in range(3):
        try:
            r = requests.get(URL, timeout=30, params={"key": key, "domain": DOMAIN, "pnu": pnu, "format": "json",
                                                      "numOfRows": 60, "pageNo": 1})
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code != 200:
                return pnu, {"err": f"http{r.status_code}"}
            rows = (r.json().get("landCharacteristicss") or {}).get("field") or []
            return pnu, ({"v": compact(rows)} if rows else {"empty": True})
        except Exception as exc:  # noqa: BLE001 — 키가 담긴 URL 이 예외 문자열에 실릴 수 있어 종류만 남긴다
            err = type(exc).__name__
            time.sleep(0.5)
    return pnu, {"err": err}


def collect(pnus: list[str], out: Path = OUT, workers: int = 4, limit: int | None = None) -> dict:
    load_env()
    key = os.environ.get("VWORLD_API_KEY")
    if not key or requests is None:
        print("[landchar] VWORLD_API_KEY 없음 — 수집하지 않는다")
        return {}
    state = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"parcels": {}}
    parcels: dict = state["parcels"]
    todo = [p for p in pnus if p not in parcels or "err" in parcels[p]]
    if limit:
        todo = todo[:limit]
    print(f"[landchar] 대상 {len(pnus)} · 이미 받음 {len(pnus) - len(todo)} · 이번에 {len(todo)}", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)

    def flush() -> None:
        state["collected_at"] = dt.date.today().isoformat()
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, out)

    done = fail = consec = 0
    with cf.ThreadPoolExecutor(workers) as ex:
        for pnu, res in ex.map(lambda p: _fetch(key, p), todo):
            parcels[pnu] = res
            done += 1
            if "err" in res:
                fail += 1
                consec += 1
                if consec >= _MAX_CONSEC_FAIL:
                    print(f"[landchar] 연속 실패 {consec}건({res['err']}) — 할당량·장애로 보고 멈춘다. 저장한 만큼은 남는다", flush=True)
                    break
            else:
                consec = 0
            if done % _SAVE_EVERY == 0:
                flush()
                print(f"[landchar] {done}/{len(todo)} (실패 {fail})", flush=True)
    flush()
    print(f"[landchar] 끝 — 이번 {done}건 중 실패 {fail} · 파일 필지 수 {len(parcels)}", flush=True)
    return state


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hubs", help="거점 slug 쉼표 목록")
    ap.add_argument("--city", help="seoul 이면 서울 서빙 거점 전부")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.city:
        from data.config.page_hubs import ACTIVE_HUBS

        slugs = sorted(s for s, h in ACTIVE_HUBS.items() if h.city == a.city)
    else:
        slugs = [s for s in (a.hubs or "").split(",") if s]
    allp = sorted({p for v in hub_pnus(slugs).values() for p in v})
    collect(allp, limit=a.limit, workers=a.workers)
