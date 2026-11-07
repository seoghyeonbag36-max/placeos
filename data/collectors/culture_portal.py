"""[Program] 문화포털 「한눈에보는문화정보」 기간별 목록 수집기 — 전국 행사 Gold 의 첫 원천.

서울 밖 거점(경기·광주·전주)은 행사 Gold(`platform_events.json` · 서울 문화행사 `culturalEventInfo`)가
비어 있다(2026-11-07 실측 77거점). 한국문화정보원 「한눈에보는문화정보조회서비스」의 기간별
문화정보목록조회(`cultureinfo/period2`)는 전국 공연·전시·행사에 좌표(`gpsX`=경도 · `gpsY`=위도)·
기간·장소·분야를 붙여 준다.

## 원천 (2026-11-07 공공데이터포털 상세 페이지 확인)
- 데이터셋 15138937 — 이용허락범위 **제한 없음** · 무료 · 자동승인 · XML 만.
- 공용 키 `DATA_GO_KR_SERVICE_KEY` 로 200 (활용신청 2026-10-17 — docs/finding-exhibit-performance-sources-2026-10-16.md §D).
- ⚠ 쪽 인자는 대소문자 그대로 `numOfrows`(≤100)·`PageNo` 다. `numOfRows`·`pageNo` 는 무시되고 10건만 온다.
- `from`·`to` 는 주지 않는다 — API 기본 창을 그대로 받는다(11-07: totalCount 1,181). 그 창이 무엇인지는
  명세에 없어서, 받은 행의 시작·종료일 범위를 요약(`window_observed`)으로 남긴다.
- 목록에는 상세 URL·요금·대상·주최가 **없다**(상세는 `detail2` 를 1건씩 불러야 한다 — 부르지 않는다).
- 제목이 이중 이스케이프돼 온다(`&amp;lt;` — XML 해석 뒤에도 `&lt;`). 풀어 쓰는 것은 Silver(파이프라인) 몫이다.

## Bronze
`data/bronze/national_events/<as_of>/culture_portal.json` — 쪽마다 **원응답 XML 본문 그대로**(+ 요청 인자, 키 제외).
append-only: 같은 기준일 파일이 있으면 덮어쓰지 않고 멈춘다. 받은 행 수가 totalCount 와 다르면 저장하지 않는다.
⚠ `--as-of` 는 스냅샷 이름표다. 원천은 **지금** 목록을 준다 — 과거 시점을 재현하지 않는다.

실행: python -m data.collectors.culture_portal --as-of YYYY-MM-DD
"""
from __future__ import annotations

import argparse
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import date, datetime, timezone

from data.collectors.common import bronze_dir, load_env, save_json

SOURCE_ID = "culture-portal"
NAME = "한국문화정보원 문화포털 「한눈에보는문화정보조회서비스」 기간별 문화정보목록조회"
ENDPOINT = "https://apis.data.go.kr/B553457/cultureinfo/period2"
DATASET_PAGE = "https://www.data.go.kr/data/15138937/openapi.do"
LICENSE = "공공데이터포털 이용허락범위 제한 없음 (데이터셋 15138937 상세 페이지 · 2026-11-07 확인)"
KEY_ENV = "DATA_GO_KR_SERVICE_KEY"

BRONZE_SLUG = "national_events"      # data/bronze/national_events/<as_of>/
OUT_NAME = "culture_portal.json"
PAGE_SIZE = 100                      # 이 API 의 numOfrows 상한
MAX_PAGES = 200                      # 폭주 방지 — 2만 행을 넘으면 원천이 바뀐 것이다

# (url, params, key) → (HTTP 코드 | None, 본문). 테스트가 가짜를 끼운다.
Getter = Callable[..., tuple]


# ── data.go.kr 공용 호출 도우미 (tourapi_festivals 도 쓴다) ─────────────────────────────

def service_key() -> str | None:
    """공용 키. 인코딩된 키(%2B…)가 들어 있으면 풀어 둔다 — urlencode 가 한 번 더 인코딩하지 않게."""
    k = (os.environ.get(KEY_ENV) or "").strip()
    if not k:
        return None
    return urllib.parse.unquote(k) if "%" in k else k


def redact(text: str, key: str | None) -> str:
    """본문·오류 문자열에서 키(원문·URL 인코딩 둘 다)를 지운다."""
    if not key or not text:
        return text
    return text.replace(key, "***").replace(urllib.parse.quote(key, safe=""), "***")


def get_text(url: str, params: dict, key: str, *, timeout: float = 30.0, tries: int = 3,
             opener=urllib.request.urlopen, sleep=time.sleep) -> tuple[int | None, str]:
    """GET → (HTTP 코드, 본문). 키는 본문·오류 어디에도 남기지 않는다(요청 URL 은 출력하지 않는다).

    네트워크 오류·5xx 는 `tries` 번까지 다시 부른다. 4xx 는 바로 돌려준다 — 키·활용신청 문제는
    재시도로 안 풀린다. 코드가 None 이면 네트워크 오류이고 본문 자리에 예외 이름만 둔다.
    """
    full = f"{url}?{urllib.parse.urlencode({**params, 'serviceKey': key})}"
    last: tuple[int | None, str] = (None, "")
    for i in range(tries):
        try:
            with opener(full, timeout=timeout) as resp:
                return resp.status, redact(resp.read().decode("utf-8", "replace"), key)
        except urllib.error.HTTPError as e:
            body = redact(e.read().decode("utf-8", "replace"), key)
            if e.code < 500:
                return e.code, body
            last = (e.code, body)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = (None, type(e).__name__)
        if i + 1 < tries:
            sleep(2 ** i)
    return last


_BRIEF = (re.compile(r"<returnAuthMsg>([^<]+)</returnAuthMsg>"),   # 게이트웨이 사유(키·활용신청)가 가장 구체적이다
          re.compile(r"<resultMsg>([^<]+)</resultMsg>"),
          re.compile(r'"resultMsg"\s*:\s*"([^"]+)"'),
          re.compile(r"<errMsg>([^<]+)</errMsg>"))


def brief(body: str) -> str:
    """오류 응답의 짧은 사유(코드·메시지) — 로그에 남길 만큼만. 구체적인 사유부터 찾는다."""
    for pat in _BRIEF:
        m = pat.search(body or "")
        if m:
            return m.group(1).strip()[:120]
    return (body or "")[:120].replace("\n", " ")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── period2 응답 해석 ────────────────────────────────────────────────────────────

def parse_page(xml_text: str) -> tuple[int, list[dict]]:
    """period2 응답 XML → (totalCount, item 행). item 은 자식 태그 → 텍스트(앞뒤 공백 제거) 사전이다.

    정상 코드(`00`)가 아니면 RuntimeError — 게이트웨이 오류(`OpenAPI_ServiceResponse`)도 여기서 걸린다.
    값은 손대지 않는다(이중 이스케이프 풀기·날짜 해석은 Silver).
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise RuntimeError(f"cultureinfo/period2: XML 이 아니다 — {brief(xml_text)}") from e
    code = (root.findtext("header/resultCode") or "").strip()
    if code != "00":
        raise RuntimeError(f"cultureinfo/period2: resultCode={code or '?'} — {brief(xml_text)}")
    total = int((root.findtext("body/totalCount") or "0").strip() or 0)
    items = [{child.tag: (child.text or "").strip() for child in item}
             for item in root.iterfind("body/items/item")]
    return total, items


def fetch_all(key: str, get: Getter = get_text) -> tuple[list[dict], list[dict], int]:
    """전량 페이징 → (쪽 원응답 목록, 해석한 행, totalCount).

    첫 쪽의 totalCount 를 기준으로 삼고, 받은 행 수나 고유 `seq` 수가 그와 다르면 저장하지 않도록
    RuntimeError 를 낸다(쪽 사이에 목록이 바뀌면 다시 받는다).
    """
    pages: list[dict] = []
    rows: list[dict] = []
    total: int | None = None
    for page_no in range(1, MAX_PAGES + 1):
        status, body = get(ENDPOINT, {"numOfrows": PAGE_SIZE, "PageNo": page_no}, key)
        if status != 200:
            raise RuntimeError(f"cultureinfo/period2 PageNo={page_no}: HTTP {status} — {brief(body)}")
        page_total, items = parse_page(body)
        pages.append({"PageNo": page_no, "http": status, "body": body})
        total = page_total if total is None else total
        rows.extend(items)
        if not items or len(rows) >= total:
            break
    else:
        raise RuntimeError(f"cultureinfo/period2: {MAX_PAGES}쪽을 넘었다 — 원천이 바뀐 것인지 확인할 것")
    total = total or 0
    if len(rows) != total:
        raise RuntimeError(f"cultureinfo/period2: 받은 행 {len(rows)} != totalCount {total} — 저장하지 않는다")
    seqs = {r.get("seq") for r in rows}
    if len(seqs) != total:
        raise RuntimeError(f"cultureinfo/period2: 고유 seq {len(seqs)} != totalCount {total} "
                           "— 쪽 사이에 목록이 바뀌었다. 다시 받을 것")
    return pages, rows, total


def window_observed(rows: list[dict], as_of: date) -> dict:
    """받은 행의 기간 범위 — 기본 창이 무엇이었는지 사후에 읽기 위한 요약(YYYYMMDD 문자열 비교)."""
    starts = sorted(r["startDate"] for r in rows if re.fullmatch(r"\d{8}", r.get("startDate") or ""))
    ends = sorted(r["endDate"] for r in rows if re.fullmatch(r"\d{8}", r.get("endDate") or ""))
    cut = as_of.strftime("%Y%m%d")
    return {
        "start_min": starts[0] if starts else None, "start_max": starts[-1] if starts else None,
        "end_min": ends[0] if ends else None, "end_max": ends[-1] if ends else None,
        "rows_without_start": len(rows) - len(starts), "rows_without_end": len(rows) - len(ends),
        "rows_ended_before_as_of": sum(e < cut for e in ends),
        "rows_with_coords": sum(bool(r.get("gpsX")) and bool(r.get("gpsY")) for r in rows),
    }


def collect(as_of: date, get: Getter = get_text) -> dict:
    """전량 수집 → Bronze 저장. 반환: 저장한 문서(쪽 본문 제외 요약은 main 이 찍는다)."""
    load_env()
    key = service_key()
    if not key:
        raise RuntimeError(f"{KEY_ENV} 미설정 — 키 싣기 실행기로 돌릴 것")
    folder = bronze_dir(BRONZE_SLUG, as_of.isoformat())
    if (folder / OUT_NAME).exists():
        raise FileExistsError(f"{folder / OUT_NAME} 이 이미 있다 — Bronze 는 덮어쓰지 않는다")
    if as_of != date.today():
        print(f"[culture_portal] ⚠ --as-of {as_of} 가 오늘이 아니다 — 원천은 지금 목록을 준다")

    fetched_at = utc_now()
    pages, rows, total = fetch_all(key, get)
    doc = {
        "source_id": SOURCE_ID, "name": NAME, "endpoint": ENDPOINT, "dataset_page": DATASET_PAGE,
        "license": LICENSE, "as_of": as_of.isoformat(), "fetched_at": fetched_at,
        "params": {"numOfrows": PAGE_SIZE},          # 키 제외 · 쪽 번호는 pages[].PageNo
        "window": "API 기본 창(from·to 미지정)",
        "window_observed": window_observed(rows, as_of),
        "total_count": total, "rows": len(rows), "calls": len(pages),
        "pages": pages,
    }
    save_json(doc, BRONZE_SLUG, OUT_NAME, as_of.isoformat())
    return doc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="스냅샷 기준일 YYYY-MM-DD")
    args = ap.parse_args()
    doc = collect(args.as_of)
    w = doc["window_observed"]
    print(f"[culture_portal] totalCount {doc['total_count']} · 받은 행 {doc['rows']} · {doc['calls']}콜 · "
          f"좌표 있는 행 {w['rows_with_coords']}")
    print(f"[culture_portal] 시작일 {w['start_min']}~{w['start_max']} · 종료일 {w['end_min']}~{w['end_max']} · "
          f"기준일 전에 끝난 행 {w['rows_ended_before_as_of']} · 날짜 없는 행 시작 {w['rows_without_start']}/종료 {w['rows_without_end']}")


if __name__ == "__main__":
    main()
