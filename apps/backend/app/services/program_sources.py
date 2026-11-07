"""[Program] 공고·행사 원천 클라이언트 — K-Startup · 정부24 혜택 · 기업마당(지원사업정보·행사정보).

2026-11-07 Program 리뉴얼의 「지원 프로그램」·「네트워킹」이 쓴다.

**왜 서버에서 부르나.** 공고는 매일 바뀌고 「모집 중」이 핵심인데, 이 저장소는 스케줄러가 돌지 않아
(Airflow DAG 은 골격뿐) Gold 스냅샷이 금방 낡는다. 그래서 요청 때 부르고 프로세스 메모리에 캐시한다 —
성공 6시간 · 실패 5분. **둘 다 도출한 값이 아니라 고른 값이다**(공고는 하루 단위로 바뀌고, 실패는 일시
장애일 수 있다 — marketing 의 실패 캐시와 같은 이유). 인스턴스마다 따로 센다(Cloud Run 최대 3대).

원천 상태 — 화면이 「왜 비었는지」를 말하게 한다:
  ok      불렀고 응답을 받았다(0건일 수 있다)
  no_key  키가 설정되지 않았다(로컬 data/.env · Cloud Run 환경변수) — 캐시하지 않는다
  error   불렀는데 실패했다(네트워크·인증·형식) — **지난 목록을 최신처럼 보이지 않는다**

키 값·호출 URL(키가 쿼리에 들어간다)은 로그·응답 어디에도 남기지 않는다 — 예외는 형식 이름과 HTTP 코드만 적는다.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger("placeos.program.sources")

# ── 호출 주소 ──────────────────────────────────────────────────────────────
# 창업진흥원 K-Startup 사업공고(data.go.kr 15125364) — 공용 키(DATA_GO_KR_SERVICE_KEY)에 활용신청.
KSTARTUP_URL = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
# 응답의 detl_pg_url 은 공고 번호 없는 목록 주소다. 아래 형식은 2026-11-07 에 실제 번호(179744)로 열어
# 그 공고 제목이 있는 것을, 없는 번호(1)로는 제목이 없는 것을 확인했다(docs/renewal-program-2026-11-07.md).
KSTARTUP_DETAIL = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={sn}"
# 행정안전부 대한민국 공공서비스(혜택)(data.go.kr 15113968) — 같은 공용 키.
GOV24_URL = "https://api.odcloud.kr/api/gov24/v3/serviceList"
# 기업마당 — API 가 둘이고 키도 따로 나온다(공식 명세 apiDetail.do?id=bizinfoApi · id=bizinfoEventApi).
BIZINFO_SUPPORT_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
BIZINFO_EVENT_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoEventApi.do"

TTL_OK_S = 6 * 3600
TTL_FAIL_S = 300
_TIMEOUT_S = 20
_MAX_PAGES = 10

SOURCE_LABEL = {
    "kstartup": "K-Startup",
    "gov24": "정부24 혜택",
    "bizinfo": "기업마당",
    "bizinfo_event": "기업마당 행사정보",
}


@dataclass
class Fetched:
    status: str                                   # ok | no_key | error
    rows: list[dict] = field(default_factory=list)
    fetched_at: str | None = None
    note: str | None = None


_cache: dict[str, tuple[float, Fetched]] = {}


def clear_cache() -> None:
    _cache.clear()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fetch_json(url: str, params: dict[str, Any]) -> Any:
    """GET → JSON. 테스트는 이 함수를 바꿔 끼워 네트워크를 타지 않는다."""
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                 headers={"Accept": "application/json", "User-Agent": "PlaceOS/1.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as r:
        return json.loads(r.read().decode("utf-8"))


def _error_note(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"원천 응답 오류(HTTP {exc.code}) — 키 활용신청·인증 상태를 확인하세요"
    if isinstance(exc, (urllib.error.URLError, TimeoutError, OSError)):
        return "원천에 연결하지 못했습니다(네트워크)"
    return f"원천 응답을 읽지 못했습니다({type(exc).__name__})"


def _cached(key: str, load: Callable[[], Fetched]) -> Fetched:
    now = time.monotonic()
    hit = _cache.get(key)
    if hit is not None:
        at, got = hit
        if now - at < (TTL_OK_S if got.status == "ok" else TTL_FAIL_S):
            return got
    try:
        got = load()
    except SourceError as exc:
        got = Fetched("error", note=str(exc))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, KeyError, TypeError) as exc:
        logger.warning("program source %s failed: %s", key, type(exc).__name__)
        got = Fetched("error", note=_error_note(exc))
    _cache[key] = (now, got)
    return got


# 키 없음 — 로그인 없이 보는 공개 화면에 나가는 문구다. 환경변수 이름은 운영자 몫이라 싣지 않는다
# (원천 id → 변수 이름은 docs/api-keys-and-specs.md §8). 상태 코드 no_key 가 운영자에게 같은 말을 한다.
NO_KEY_NOTE = "원문 포털에서 직접 확인해 주세요"   # 화면은 상태 낱말 「연결 전」 뒤에 이 문장을 붙인다(SourceStatusLine)


class SourceError(Exception):
    """원천이 정상 HTTP 로 오류 문구를 돌려줬다(기업마당 reqErr 등) — 문구를 그대로 화면에 밝힌다."""


# ── K-Startup ─────────────────────────────────────────────────────────────
def kstartup_open() -> Fetched:
    """모집 중(rcrt_prgs_yn=Y) 공고 전부. 11-07 실측 213건(전체 30,540건 중)."""
    key = settings.data_go_kr_service_key
    if not key:
        return Fetched("no_key", note=NO_KEY_NOTE)   # DATA_GO_KR_SERVICE_KEY

    def load() -> Fetched:
        rows: list[dict] = []
        for page in range(1, _MAX_PAGES + 1):
            j = _fetch_json(KSTARTUP_URL, {"serviceKey": key, "page": page, "perPage": 100,
                                           "returnType": "json", "cond[rcrt_prgs_yn::EQ]": "Y"})
            data = j.get("data") or []
            rows += data
            total = int(j.get("matchCount") or j.get("totalCount") or 0)
            if not data or len(rows) >= total:
                break
        return Fetched("ok", rows, _now_iso())

    return _cached("kstartup", load)


# ── 정부24 공공서비스(혜택) ──────────────────────────────────────────────────
def gov24_smallbiz() -> Fetched:
    """사용자구분에 「소상공인」이 든 혜택 전부. 11-07 실측 369건(전체 10,942건 중)."""
    key = settings.data_go_kr_service_key
    if not key:
        return Fetched("no_key", note=NO_KEY_NOTE)   # DATA_GO_KR_SERVICE_KEY

    def load() -> Fetched:
        rows: list[dict] = []
        for page in range(1, _MAX_PAGES + 1):
            j = _fetch_json(GOV24_URL, {"serviceKey": key, "page": page, "perPage": 1000,
                                        "returnType": "JSON", "cond[사용자구분::LIKE]": "소상공인"})
            data = j.get("data") or []
            rows += data
            total = int(j.get("matchCount") or j.get("totalCount") or 0)
            if not data or len(rows) >= total:
                break
        return Fetched("ok", rows, _now_iso())

    return _cached("gov24", load)


# ── 기업마당 ───────────────────────────────────────────────────────────────
_BIZINFO_ITEM_KEYS = ("pblancId", "pblancNm", "eventInfoId", "nttNm", "seq", "title")


def _find_items(node: Any, depth: int = 0) -> list[dict] | None:
    """기업마당 JSON 에서 공고·행사 목록을 찾는다 — 명세가 RSS 필드만 적고 JSON 껍데기는 적지 않았다."""
    if depth > 5:
        return None
    if isinstance(node, list):
        if node and all(isinstance(x, dict) for x in node) and any(
                any(k in x for k in _BIZINFO_ITEM_KEYS) for x in node):
            return node
        for x in node:
            if (found := _find_items(x, depth + 1)) is not None:
                return found
        return None
    if isinstance(node, dict):
        for k in ("jsonArray", "items", "item", "data", "channel", "rss"):
            if k in node and (found := _find_items(node[k], depth + 1)) is not None:
                return found
        for v in node.values():
            if isinstance(v, (list, dict)) and (found := _find_items(v, depth + 1)) is not None:
                return found
    return None


def bizinfo(kind: str, hashtag: str) -> Fetched:
    """kind: "support"(지원사업정보) | "event"(행사정보). hashtag: 지역 해시태그(서울·경기·전남광주·전북 …)."""
    if kind == "support":
        key, url = settings.bizinfo_support_api_key, BIZINFO_SUPPORT_URL   # BIZINFO_SUPPORT_API_KEY
    else:
        key, url = settings.bizinfo_event_api_key, BIZINFO_EVENT_URL       # BIZINFO_EVENT_API_KEY
    if not key:
        return Fetched("no_key", note=NO_KEY_NOTE)

    def load() -> Fetched:
        j = _fetch_json(url, {"crtfcKey": key, "dataType": "json", "searchCnt": 300, "hashtags": hashtag})
        if isinstance(j, dict) and j.get("reqErr"):
            # 키 없음·등록되지 않은 IP 등 — 기업마당이 준 문구를 그대로 밝힌다(키 값은 들어 있지 않다)
            raise SourceError(f"기업마당 응답: {str(j['reqErr'])[:120]}")
        items = _find_items(j)
        return Fetched("ok", items or [], _now_iso())

    return _cached(f"bizinfo:{kind}:{hashtag}", load)


def status_of(source_id: str, got: Fetched, count: int) -> dict:
    return {"id": source_id, "name": SOURCE_LABEL.get(source_id, source_id), "status": got.status,
            "count": count, "fetched_at": got.fetched_at, "note": got.note}
