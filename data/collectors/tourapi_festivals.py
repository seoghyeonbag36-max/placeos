"""[Program] TourAPI 행사정보 수집기 — 전국 행사 Gold 의 둘째 원천(큰 축제 보완).

한국관광공사 국문 관광정보 서비스(KorService2)의 행사정보조회(`searchFestival2`)는 전국 축제·공연·행사에
좌표(`mapx`=경도 · `mapy`=위도)·기간·주소·전화를 붙여 준다.

## 원천 (2026-11-07 공공데이터포털 상세 페이지 확인)
- 데이터셋 15101578 — 이용허락범위 **제한 없음** · 무료. 「저작권 등에 구애 없이 자유롭게 활용 가능한 정보만
  선별」해 제공한다고 적혀 있다. 단 **사진**은 공공누리 1·3유형(`cpyrhtDivCd` Type1·Type3 — 3유형은 변경 금지)이고
  피사체 명예훼손·기업 CI/BI 사용이 금지다 → 사진 URL 은 Bronze 원응답에만 남고 Silver·Gold 로 넘기지 않는다.
- 필수 인자: MobileOS·MobileApp·eventStartDate(YYYYMMDD). `_type=json`.
- `cat1~3`·`areaCode`·`sigunguCode` 는 명세상 「미사용항목(삭제예정)」이고 실제로 빈 값이 온다 — 분류는
  `lclsSystm1~3`(분류체계)로 읽고, 이름은 같은 서비스의 분류체계 코드조회(`lclsSystmCode2`, `lclsSystm1=EV`)로 받아 같이 둔다.
- 목록에는 상세 URL·요금·주최가 없다(상세는 detailCommon2·detailIntro2 를 1건씩 불러야 한다 — 부르지 않는다).

## eventStartDate = 기준일 − 120일
명세의 설명은 「행사시작일(형식 :YYYYMMDD)」 한 줄뿐이라 그날 **이후 시작**인지 그날 **진행 중인 것까지**인지
적혀 있지 않다. 기준일 120일 전으로 넉넉히 부르고, 실제로 돌아온 시작일 분포로 뜻을 판정해 남긴다
(`start_param_semantics`). 끝난 행사는 파이프라인이 기준일로 거른다.

## Bronze
`data/bronze/national_events/<as_of>/tourapi_festivals.json` — 쪽마다 원응답 JSON 그대로 + 분류체계 코드 응답.
append-only · 받은 행 수(고유 contentid 수)가 totalCount 와 다르면 저장하지 않는다.

실행: python -m data.collectors.tourapi_festivals --as-of YYYY-MM-DD
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date, timedelta

from data.collectors.common import bronze_dir, load_env, save_json
from data.collectors.culture_portal import KEY_ENV, Getter, brief, get_text, service_key, utc_now

SOURCE_ID = "tourapi"
NAME = "한국관광공사 국문 관광정보 서비스(TourAPI KorService2) 행사정보조회"
ENDPOINT = "https://apis.data.go.kr/B551011/KorService2/searchFestival2"
CODES_ENDPOINT = "https://apis.data.go.kr/B551011/KorService2/lclsSystmCode2"
DATASET_PAGE = "https://www.data.go.kr/data/15101578/openapi.do"
LICENSE = ("공공데이터포털 이용허락범위 제한 없음 (데이터셋 15101578 상세 페이지 · 2026-11-07 확인) — "
           "사진은 공공누리 1·3유형이라 이 산출물에 싣지 않는다")

BRONZE_SLUG = "national_events"
OUT_NAME = "tourapi_festivals.json"
LOOKBACK_DAYS = 120
PAGE_SIZE = 100
MAX_PAGES = 100
BASE_PARAMS = {"MobileOS": "ETC", "MobileApp": "PlaceOS", "_type": "json"}
CODES_PARAMS = {**BASE_PARAMS, "lclsSystm1": "EV", "lclsSystmListYn": "Y", "numOfRows": 200, "pageNo": 1}

_YMD = re.compile(r"\d{8}")


def event_start_param(as_of: date) -> str:
    """eventStartDate 인자 — 기준일 120일 전(YYYYMMDD)."""
    return (as_of - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")


def parse_page(text: str, op: str = "searchFestival2") -> tuple[int, list[dict]]:
    """KorService2 JSON 응답 → (totalCount, item 행). 정상 코드(`0000`)가 아니면 RuntimeError.

    0건이면 `items` 가 빈 문자열로 오고, 1건일 때 `item` 이 사전 하나로 올 수 있어 둘 다 목록으로 편다.
    게이트웨이 오류는 `_type=json` 이어도 XML 로 온다 — JSON 해석 실패로 걸린다.
    """
    try:
        j = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{op}: JSON 이 아니다 — {brief(text)}") from e
    resp = j.get("response") if isinstance(j, dict) else None
    if not isinstance(resp, dict):
        raise RuntimeError(f"{op}: 응답 형식 밖 — {brief(text)}")
    code = str((resp.get("header") or {}).get("resultCode") or "")
    if code != "0000":
        raise RuntimeError(f"{op}: resultCode={code or '?'} — {brief(text)}")
    body = resp.get("body") or {}
    total = int(body.get("totalCount") or 0)
    items = body.get("items")
    if not isinstance(items, dict):
        return total, []
    item = items.get("item") or []
    return total, [item] if isinstance(item, dict) else list(item)


def fetch_all(key: str, start_param: str, get: Getter = get_text) -> tuple[list[dict], list[dict], int]:
    """행사정보 전량 → (쪽 원응답, 행, totalCount). 건수·고유 contentid 가 totalCount 와 다르면 RuntimeError."""
    pages: list[dict] = []
    rows: list[dict] = []
    total: int | None = None
    for page_no in range(1, MAX_PAGES + 1):
        params = {**BASE_PARAMS, "numOfRows": PAGE_SIZE, "pageNo": page_no, "eventStartDate": start_param}
        status, text = get(ENDPOINT, params, key)
        if status != 200:
            raise RuntimeError(f"searchFestival2 pageNo={page_no}: HTTP {status} — {brief(text)}")
        page_total, items = parse_page(text)
        pages.append({"pageNo": page_no, "http": status, "body": json.loads(text)})
        total = page_total if total is None else total
        rows.extend(items)
        if not items or len(rows) >= total:
            break
    else:
        raise RuntimeError(f"searchFestival2: {MAX_PAGES}쪽을 넘었다 — 원천이 바뀐 것인지 확인할 것")
    total = total or 0
    if len(rows) != total:
        raise RuntimeError(f"searchFestival2: 받은 행 {len(rows)} != totalCount {total} — 저장하지 않는다")
    ids = {r.get("contentid") for r in rows}
    if len(ids) != total:
        raise RuntimeError(f"searchFestival2: 고유 contentid {len(ids)} != totalCount {total} "
                           "— 쪽 사이에 목록이 바뀌었다. 다시 받을 것")
    return pages, rows, total


def fetch_codes(key: str, get: Getter = get_text) -> dict:
    """분류체계 코드(EV = 축제/공연/행사) — lclsSystm3 코드의 공식 이름을 Bronze 에 같이 둔다."""
    status, text = get(CODES_ENDPOINT, CODES_PARAMS, key)
    if status != 200:
        raise RuntimeError(f"lclsSystmCode2: HTTP {status} — {brief(text)}")
    total, items = parse_page(text, "lclsSystmCode2")
    if not items or len(items) != total:
        raise RuntimeError(f"lclsSystmCode2: 받은 코드 {len(items)} != totalCount {total}")
    return {"endpoint": CODES_ENDPOINT, "params": dict(CODES_PARAMS), "http": status, "body": json.loads(text)}


def start_param_semantics(rows: list[dict], start_param: str) -> dict:
    """돌아온 시작일 분포로 eventStartDate 의 뜻을 판정한다(관측 — 명세가 말하지 않는다).

    - 인자보다 일찍 시작한 행이 없다 → 「이후 시작」
    - 그런 행이 있고 전부 인자 날 이후에 끝난다 → 「진행 중 포함」
    - 인자 전에 시작해 인자 전에 끝난 행까지 있다 → 「판정 불가」(필터가 날짜를 안 본다는 뜻일 수 있다)
    """
    starts = sorted(r["eventstartdate"] for r in rows if _YMD.fullmatch(r.get("eventstartdate") or ""))
    before = [r for r in rows if _YMD.fullmatch(r.get("eventstartdate") or "") and r["eventstartdate"] < start_param]
    ongoing = sum((r.get("eventenddate") or "") >= start_param for r in before)
    if not before:
        verdict = "이후 시작 — 시작일이 인자보다 이른 행이 0건이다(관측)"
    elif ongoing == len(before):
        verdict = "진행 중 포함 — 인자보다 일찍 시작한 행이 있고 모두 인자 날 이후에 끝난다(관측)"
    else:
        verdict = "판정 불가 — 인자 전에 시작해 인자 전에 끝난 행이 있다"
    return {
        "param": start_param, "rows": len(rows),
        "start_min": starts[0] if starts else None, "start_max": starts[-1] if starts else None,
        "starts_before_param": len(before), "of_which_end_on_or_after_param": ongoing,
        "start_by_month": dict(sorted(Counter(f"{s[:4]}-{s[4:6]}" for s in starts).items())),
        "semantics": verdict,
    }


def collect(as_of: date, get: Getter = get_text) -> dict:
    load_env()
    key = service_key()
    if not key:
        raise RuntimeError(f"{KEY_ENV} 미설정 — 키 싣기 실행기로 돌릴 것")
    folder = bronze_dir(BRONZE_SLUG, as_of.isoformat())
    if (folder / OUT_NAME).exists():
        raise FileExistsError(f"{folder / OUT_NAME} 이 이미 있다 — Bronze 는 덮어쓰지 않는다")
    if as_of != date.today():
        print(f"[tourapi_festivals] ⚠ --as-of {as_of} 가 오늘이 아니다 — 원천은 지금 목록을 준다")

    start_param = event_start_param(as_of)
    fetched_at = utc_now()
    pages, rows, total = fetch_all(key, start_param, get)
    codes = fetch_codes(key, get)
    cut = as_of.strftime("%Y%m%d")
    doc = {
        "source_id": SOURCE_ID, "name": NAME, "endpoint": ENDPOINT, "dataset_page": DATASET_PAGE,
        "license": LICENSE, "as_of": as_of.isoformat(), "fetched_at": fetched_at,
        "params": {**BASE_PARAMS, "numOfRows": PAGE_SIZE, "eventStartDate": start_param},  # 키 제외
        "lookback_days": LOOKBACK_DAYS,
        "start_param_semantics": start_param_semantics(rows, start_param),
        "rows_ended_before_as_of": sum(_YMD.fullmatch(r.get("eventenddate") or "") is not None
                                       and r["eventenddate"] < cut for r in rows),
        "total_count": total, "rows": len(rows), "calls": len(pages) + 1,
        "pages": pages,
        "lcls_codes": codes,
    }
    save_json(doc, BRONZE_SLUG, OUT_NAME, as_of.isoformat())
    return doc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="스냅샷 기준일 YYYY-MM-DD")
    args = ap.parse_args()
    doc = collect(args.as_of)
    s = doc["start_param_semantics"]
    coords = sum(bool(r.get("mapx")) and bool(r.get("mapy"))
                 for p in doc["pages"] for r in parse_page(json.dumps(p["body"]))[1])
    print(f"[tourapi_festivals] eventStartDate={s['param']} · totalCount {doc['total_count']} · 받은 행 {doc['rows']} · "
          f"{doc['calls']}콜 · 좌표 있는 행 {coords}")
    print(f"[tourapi_festivals] 시작일 {s['start_min']}~{s['start_max']} · 인자 전 시작 {s['starts_before_param']}"
          f"(그중 인자 뒤 종료 {s['of_which_end_on_or_after_param']}) → {s['semantics']}")
    print(f"[tourapi_festivals] 시작 월별 {s['start_by_month']} · 기준일 전에 끝난 행 {doc['rows_ended_before_as_of']}")


if __name__ == "__main__":
    main()
