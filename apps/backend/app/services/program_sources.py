"""[Program] 공고·행사 원천 클라이언트 — K-Startup · 정부24 혜택 · 기업마당(지원사업정보·행사정보).

2026-11-07 Program 리뉴얼의 「지원 프로그램」·「네트워킹」이 쓴다.

**왜 서버에서 부르나.** 공고는 매일 바뀌고 「모집 중」이 핵심인데, 이 저장소는 스케줄러가 돌지 않아
(Airflow DAG 은 골격뿐) Gold 스냅샷이 금방 낡는다. 그래서 요청 때 부르고 프로세스 메모리에 캐시한다 —
성공 6시간 · 실패 5분(인스턴스 시작 3분 안의 전송 오류만 1분). **모두 도출한 값이 아니라 고른 값이다**(공고는 하루 단위로
바뀌고, 실패는 일시 장애일 수 있다 — marketing 의 실패 캐시와 같은 이유). 인스턴스마다 따로 센다(Cloud Run 최대 3대).

원천 상태 — 화면이 「왜 비었는지」를 말하게 한다:
  ok      불렀고 응답을 받았다(0건일 수 있다)
  no_key  키가 설정되지 않았다(로컬 data/.env · Cloud Run 환경변수) — 캐시하지 않는다
  error   불렀는데 실패했다(네트워크·인증·형식) — **지난 목록을 최신처럼 보이지 않는다**

키 값·호출 URL(키가 쿼리에 들어간다)은 로그·응답 어디에도 남기지 않는다 — 예외는 형식 이름과 HTTP 코드만 적는다.

**새 인스턴스의 첫 연결이 멈춘다(2026-11-08 프로덕션 실측).** 프로덕션 Cloud Run 은 ODsay 허용 IP 때문에
Direct VPC egress + Cloud NAT(고정 출구 IP)로 나간다. Google 문서가 밝히듯 이 구성은 인스턴스가 뜬 직후 연결
수립이 30초~1분 넘게 늦어질 수 있다 — 키를 넣은 새 리비전의 첫 K-Startup 호출이 연결 단계에서 20초를 다 쓰고
실패했고(그 실패가 5분 캐시됐다), 5분 뒤 같은 호출은 3초 만에 성공했다. 11-07 캠페인 원장(DB)의 60초 시간 초과도
같은 자리(인스턴스 시작 12초 뒤)였다. 그래서
  - 소켓 한 동작(연결·TLS·한 번 읽기)의 상한을 _TIMEOUT_S 로 짧게 두고, **전송 오류만** 원천마다 _SOURCE_BUDGET_S
    안에서 최대 _MAX_ATTEMPTS 번 부른다. 원천이 응답한 오류(HTTP·reqErr·형식)는 다시 시도하지 않는다 — 기다려도 안 풀린다.
  - 인스턴스 시작 _COLD_START_WINDOW_S 안의 전송 오류는 TTL_FAIL_NET_S 만 캐시한다 — 경로가 열리면 곧 다시 부른다.
    그 밖의 전송 오류(원천 장애)와 원천이 응답한 오류는 TTL_FAIL_S.
  - 한 화면이 쓰는 원천을 동시에 부른다(fetch_all) — 응답 시간이 원천들의 합이 아니라 가장 느린 하나다.
    Firebase Hosting·Cloud Run 이 60초에 끊으므로 예산은 그 안쪽이다.
"""
from __future__ import annotations

import http.client
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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

# 아래 값은 모두 도출이 아니라 고른 값이다(근거 수치는 2026-11-08 실측).
TTL_OK_S = 6 * 3600         # 공고는 하루 단위로 바뀐다
TTL_FAIL_S = 300            # 원천이 응답한 오류(HTTP·reqErr·형식 — 키·활용신청 문제는 기다려도 안 풀린다) ·
                            # 콜드 스타트 창 밖의 전송 오류
TTL_FAIL_NET_S = 60         # 콜드 스타트 창 안의 전송 오류(연결·TLS·끊김) — 지연(문서상 30초~1분+)이 풀릴 무렵 다시 부른다
_COLD_START_WINDOW_S = 180  # 인스턴스 시작 뒤 이 시간 안의 전송 오류만 콜드 스타트 지연으로 본다. 그 밖(원천 장애)은
                            # TTL_FAIL_S — 매분 누군가 재시도 세 번(최대 약 32초)을 기다리지 않게
_STARTED_AT = time.monotonic()   # 모듈을 읽은 때 ≈ 프로세스(Cloud Run 인스턴스) 시작
_TIMEOUT_S = 10             # 소켓 한 동작(연결·TLS·한 번 읽기)의 상한 — 전송 전체가 아니다. us-central1 에서 연결+TLS
                            # 0.5~1.2초(Cloud Build 실측) · 가장 큰 응답(기업마당 지원사업 899KiB)이 콜드에서 약 7초
_SOURCE_BUDGET_S = 35       # 한 원천이 다시 시도까지 쓰는 시간 — 원천은 동시에 돌고, 60초 컷 안쪽이어야 한다
_MAX_ATTEMPTS = 3           # 곧바로 실패하는 오류(이름 풀이·연결 거부)가 예산 내내 두드리지 않게
_RETRY_PAUSE_S = 1.0
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
    """GET → JSON, 한 번. 테스트는 이 함수를 바꿔 끼워 네트워크를 타지 않는다(다시 시도는 _get 이 한다)."""
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                 headers={"Accept": "application/json", "User-Agent": "PlaceOS/1.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as r:
        return json.loads(r.read().decode("utf-8"))


def _is_transport(exc: BaseException) -> bool:
    """전송 오류인가 — 연결·TLS·보내기(urllib 이 URLError 로 감싼다) · 읽기 시간 초과 · 연결 끊김 · 읽는 중 TLS 오류 ·
    본문 잘림(IncompleteRead). _fetch_json 이 내는 OSError 는 모두 네트워크에서 온다(URLError·TimeoutError·
    ConnectionError·ssl.SSLError 가 다 OSError 다).

    HTTPError 는 URLError 의 하위형이지만 원천이 **응답한** 것이라 전송 오류가 아니다.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return False
    return isinstance(exc, (OSError, http.client.HTTPException))


def _kind(exc: BaseException) -> str:
    """로그용 형식 이름 — URLError 는 감싼 원인의 형식까지(「URLError(TimeoutError)」). 메시지·URL 은 싣지 않는다."""
    reason = getattr(exc, "reason", None)
    if isinstance(exc, urllib.error.URLError) and isinstance(reason, BaseException):
        return f"{type(exc).__name__}({type(reason).__name__})"
    return type(exc).__name__


def _get(url: str, params: dict[str, Any], started: float) -> Any:
    """_fetch_json + 전송 오류만 다시 시도 — 최대 _MAX_ATTEMPTS 번, started(time.monotonic)부터 _SOURCE_BUDGET_S 안에서.

    다음 시도가 예산 안에 끝날 수 없으면 마지막 오류를 그대로 올린다(_cached 가 상태로 바꾼다).
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return _fetch_json(url, params)
        except Exception as exc:
            elapsed = time.monotonic() - started
            if (not _is_transport(exc) or attempt >= _MAX_ATTEMPTS
                    or elapsed + _RETRY_PAUSE_S + _TIMEOUT_S > _SOURCE_BUDGET_S):
                raise
            # WARNING 인 이유: 앱에 로깅 설정이 없어 INFO 는 Cloud Run 로그에 안 남는다(services/interior 주석과 같은 사정).
            # 다시 시도해 성공한 경우도 남겨야 콜드 스타트 연결 지연이 얼마나 자주 나는지 셀 수 있다.
            logger.warning("program source %s transport retry %d: %s (%.1fs)",
                           urllib.parse.urlsplit(url).netloc, attempt, _kind(exc), elapsed)
            time.sleep(_RETRY_PAUSE_S)


def _error_note(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"원천 응답 오류(HTTP {exc.code}) — 키 활용신청·인증 상태를 확인하세요"
    if _is_transport(exc):
        return "원천에 연결하지 못했습니다(네트워크)"
    return f"원천 응답을 읽지 못했습니다({type(exc).__name__})"


def _cached(key: str, load: Callable[[], Fetched]) -> Fetched:
    hit = _cache.get(key)
    if hit is not None and time.monotonic() < hit[0]:
        return hit[1]
    ttl = TTL_FAIL_S
    try:
        got = load()
        if got.status == "ok":
            ttl = TTL_OK_S
    except SourceError as exc:
        got = Fetched("error", note=str(exc))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, KeyError, TypeError,
            http.client.HTTPException) as exc:
        # http.client.HTTPException(IncompleteRead 등)은 11-08 까지 잡지 않아, 본문이 잘리면 화면 전체가 500 이었다
        logger.warning("program source %s failed: %s", key, _kind(exc))
        got = Fetched("error", note=_error_note(exc))
        if _is_transport(exc) and time.monotonic() - _STARTED_AT < _COLD_START_WINDOW_S:
            ttl = TTL_FAIL_NET_S
    _cache[key] = (time.monotonic() + ttl, got)     # 만료 시각
    return got


def fetch_all(*loaders: Callable[[], Fetched]) -> list[Fetched]:
    """원천을 동시에 부른다 — 결과는 넘긴 순서대로. 각 원천의 실패는 _cached 가 상태로 바꾼다.

    FastAPI 의 동기 끝점은 이미 작업 스레드에서 돈다. 여기서 원천 수만큼 스레드를 더 쓴다(최대 3).
    """
    if len(loaders) <= 1:
        return [fn() for fn in loaders]
    with ThreadPoolExecutor(max_workers=len(loaders), thread_name_prefix="program-src") as ex:
        futures = [ex.submit(fn) for fn in loaders]
        return [f.result() for f in futures]


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
        started = time.monotonic()
        rows: list[dict] = []
        for page in range(1, _MAX_PAGES + 1):
            # perPage 1000 — 11-08 실측에서 한 번에 212건을 다 줬다(100 이면 세 번 연결한다 · 정부24 와 같은 값)
            j = _get(KSTARTUP_URL, {"serviceKey": key, "page": page, "perPage": 1000,
                                    "returnType": "json", "cond[rcrt_prgs_yn::EQ]": "Y"}, started)
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
        started = time.monotonic()
        rows: list[dict] = []
        for page in range(1, _MAX_PAGES + 1):
            j = _get(GOV24_URL, {"serviceKey": key, "page": page, "perPage": 1000,
                                 "returnType": "JSON", "cond[사용자구분::LIKE]": "소상공인"}, started)
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
        j = _get(url, {"crtfcKey": key, "dataType": "json", "searchCnt": 300, "hashtags": hashtag}, time.monotonic())
        if isinstance(j, dict) and j.get("reqErr"):
            # 키 없음·등록되지 않은 IP 등 — 기업마당이 준 문구를 그대로 밝힌다(키 값은 들어 있지 않다)
            raise SourceError(f"기업마당 응답: {str(j['reqErr'])[:120]}")
        items = _find_items(j)
        return Fetched("ok", items or [], _now_iso())

    return _cached(f"bizinfo:{kind}:{hashtag}", load)


def status_of(source_id: str, got: Fetched, count: int) -> dict:
    return {"id": source_id, "name": SOURCE_LABEL.get(source_id, source_id), "status": got.status,
            "count": count, "fetched_at": got.fetched_at, "note": got.note}
