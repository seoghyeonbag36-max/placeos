"""Program 공고 원천 — 프로덕션(Cloud Run · Direct VPC egress + Cloud NAT) 연결 지연에 견디는가(2026-11-08).

11-08 키를 넣은 새 리비전의 첫 K-Startup 호출이 연결 단계에서 20초를 다 쓰고 실패했고, 그 실패가 5분 캐시됐다
(5분 뒤 같은 호출은 3초 만에 성공). 원천은 전부 가짜다(네트워크 없음). 못 박는 것:
  - 전송 오류(연결·TLS·읽기 시간 초과·끊김·본문 잘림)만 예산 안에서 다시 시도한다 — 원천이 응답한 오류는 한 번
  - 인스턴스 시작 직후(콜드 스타트 창)의 전송 오류만 짧게(TTL_FAIL_NET_S), 창 밖의 전송 오류와 원천이 응답한 오류는
    길게(TTL_FAIL_S) 캐시한다
  - 본문이 잘려도(IncompleteRead) 끝점은 500 이 아니라 그 원천만 「error」다
  - 한 화면의 원천은 동시에 부른다 — 하나가 멈춰도 다른 원천을 기다리게 하지 않는다
  - 로그에 키·쿼리가 없다
"""
from __future__ import annotations

import http.client
import logging
import ssl
import threading
import urllib.error

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import program_network, program_sources, program_support

client = TestClient(app)
SECRET = "sk-test-secret-key-value"


class FakeTime:
    """program_sources 의 time 을 바꿔 끼운다 — 시계는 sleep·멈춘 호출만 움직인다."""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.now += s


@pytest.fixture
def keys(monkeypatch):
    s = program_sources.settings
    for k in ("data_go_kr_service_key", "bizinfo_support_api_key", "bizinfo_event_api_key"):
        monkeypatch.setattr(s, k, SECRET, raising=False)
    program_sources.clear_cache()
    yield
    program_sources.clear_cache()


@pytest.fixture
def clock(monkeypatch):
    """가짜 시계 — 인스턴스가 막 뜬 때(콜드 스타트 창 안)에서 시작한다."""
    t = FakeTime()
    monkeypatch.setattr(program_sources, "time", t)
    monkeypatch.setattr(program_sources, "_STARTED_AT", t.now)
    return t


def _hung(clock: FakeTime):
    """연결이 멈춰 소켓 타임아웃까지 기다린 뒤 urllib 이 감싸 올리는 오류(11-08 Cloud Run 로그: URLError)."""
    clock.now += program_sources._TIMEOUT_S
    return urllib.error.URLError(TimeoutError("timed out"))


KS_OK = {"data": [{"pbanc_sn": "1", "biz_pbanc_nm": "공고", "supt_regin": "전국", "biz_enyy": "예비창업자",
                   "supt_biz_clsfc": "사업화", "pbanc_rcpt_end_dt": "20991231"}], "matchCount": 1}


# ── 다시 시도 ───────────────────────────────────────────────────────────────
def test_transport_error_is_retried_then_ok(keys, clock, monkeypatch):
    calls = []

    def flaky(url, params):
        calls.append(url)
        if len(calls) == 1:
            raise _hung(clock)
        return KS_OK

    monkeypatch.setattr(program_sources, "_fetch_json", flaky)
    got = program_sources.kstartup_open()
    assert got.status == "ok" and len(got.rows) == 1
    assert len(calls) == 2, "첫 연결이 멈추면 예산 안에서 한 번 더 부른다"


def test_retries_stop_at_budget_and_failure_is_cached_briefly(keys, clock, monkeypatch):
    calls = []

    def dead(url, params):
        calls.append(url)
        raise _hung(clock)

    monkeypatch.setattr(program_sources, "_MAX_ATTEMPTS", 99)      # 예산만으로 멈추는지 본다
    monkeypatch.setattr(program_sources, "_fetch_json", dead)
    got = program_sources.kstartup_open()
    assert got.status == "error" and "네트워크" in got.note
    # 예산 35초 · 한 번 10초 · 쉬기 1초 → 0~10 · 11~21 · 22~32, 넷째(33~43)는 예산을 넘는다
    assert len(calls) == 3
    assert clock.now - 1000.0 <= program_sources._SOURCE_BUDGET_S, "한 원천이 예산을 넘겨 기다리지 않는다"

    clock.now += program_sources.TTL_FAIL_NET_S - 1
    program_sources.kstartup_open()
    assert len(calls) == 3, "전송 오류도 잠깐은 캐시한다(매 요청이 30초씩 기다리지 않게)"
    clock.now += 2
    program_sources.kstartup_open()
    assert len(calls) > 3, "전송 오류는 TTL_FAIL_NET_S 뒤 다시 부른다(5분을 기다리지 않는다)"


def test_transport_failure_outside_cold_start_window_is_cached_long(keys, clock, monkeypatch):
    calls = []

    def dead(url, params):
        calls.append(url)
        raise _hung(clock)

    monkeypatch.setattr(program_sources, "_fetch_json", dead)
    clock.now += program_sources._COLD_START_WINDOW_S + 1      # 인스턴스가 뜬 지 오래 — 원천 장애로 본다
    assert program_sources.kstartup_open().status == "error"
    n = len(calls)
    clock.now += program_sources.TTL_FAIL_NET_S + 1
    program_sources.kstartup_open()
    assert len(calls) == n, "창 밖의 전송 오류는 5분 캐시 — 장애 중에 매분 누군가 30초씩 기다리지 않게"
    clock.now += program_sources.TTL_FAIL_S
    program_sources.kstartup_open()
    assert len(calls) > n


def test_fast_failures_stop_at_max_attempts(keys, clock, monkeypatch):
    calls = []

    def refused(url, params):
        calls.append(url)                      # 시계를 움직이지 않는다 — 곧바로 실패하는 오류
        raise urllib.error.URLError(ConnectionRefusedError(111, "refused"))

    monkeypatch.setattr(program_sources, "_fetch_json", refused)
    assert program_sources.kstartup_open().status == "error"
    assert len(calls) == program_sources._MAX_ATTEMPTS, "예산이 남아도 곧바로 실패하는 오류는 횟수에서 멈춘다"


def test_http_error_is_not_retried_and_cached_long(keys, clock, monkeypatch):
    calls = []

    def forbidden(url, params):
        calls.append(url)
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(program_sources, "_fetch_json", forbidden)
    got = program_sources.kstartup_open()
    assert got.status == "error" and "HTTP 403" in got.note
    assert len(calls) == 1, "원천이 응답한 오류는 다시 불러도 안 풀린다"
    clock.now += program_sources.TTL_FAIL_NET_S + 1
    program_sources.kstartup_open()
    assert len(calls) == 1, "키·인증 오류는 TTL_FAIL_S 동안 캐시한다"
    clock.now += program_sources.TTL_FAIL_S
    program_sources.kstartup_open()
    assert len(calls) == 2


def test_bizinfo_reqerr_is_not_retried(keys, clock, monkeypatch):
    calls = []

    def reqerr(url, params):
        calls.append(url)
        return {"reqErr": "등록되지 않은 IP 입니다."}

    monkeypatch.setattr(program_sources, "_fetch_json", reqerr)
    got = program_sources.bizinfo("support", "서울")
    assert got.status == "error" and "등록되지 않은 IP" in got.note and len(calls) == 1


@pytest.mark.parametrize("exc", [http.client.IncompleteRead(b"partial"), http.client.RemoteDisconnected("closed"),
                                 ConnectionResetError(104, "reset"), TimeoutError("read timed out"),
                                 ssl.SSLError(8, "EOF occurred in violation of protocol")])
def test_other_transport_errors_are_retried(keys, clock, monkeypatch, exc):
    calls = []

    def once(url, params):
        calls.append(url)
        if len(calls) == 1:
            raise exc
        return KS_OK

    monkeypatch.setattr(program_sources, "_fetch_json", once)
    assert program_sources.kstartup_open().status == "ok" and len(calls) == 2


def test_kstartup_asks_for_everything_in_one_call(keys, monkeypatch):
    seen = []

    def one(url, params):
        seen.append(params["perPage"])
        return {"data": KS_OK["data"] * 212, "matchCount": 212}

    monkeypatch.setattr(program_sources, "_fetch_json", one)
    assert len(program_sources.kstartup_open().rows) == 212
    assert seen == [1000], "모집 중 212건(11-08)을 한 번에 — 연결 수가 곧 콜드 스타트 위험이다"


# ── 끝점 — 본문이 잘려도 500 이 아니다 · 동시에 부른다 ───────────────────────────
def _router(broken: str | None = None, exc_factory=None, barrier: threading.Barrier | None = None):
    first = set()
    lock = threading.Lock()

    def fake(url, params):
        with lock:
            is_first = url not in first
            first.add(url)
        if barrier is not None and is_first:
            barrier.wait()          # 차례대로 부르면 다른 원천이 오지 않아 시간 초과(BrokenBarrierError)로 깨진다
        if url == broken:
            raise exc_factory()
        if url == program_sources.KSTARTUP_URL:
            return KS_OK
        if url == program_sources.GOV24_URL:
            return {"data": [], "matchCount": 0}
        return {"jsonArray": []}

    return fake


def test_truncated_body_is_source_error_not_500(keys, monkeypatch):
    monkeypatch.setattr(program_sources, "_RETRY_PAUSE_S", 0)
    monkeypatch.setattr(program_sources, "_fetch_json",
                        _router(program_sources.BIZINFO_SUPPORT_URL, lambda: http.client.IncompleteRead(b"{")))
    r = client.get("/api/v1/program/support", params={"district_id": "garosugil"})
    assert r.status_code == 200, "11-08 까지는 IncompleteRead 를 못 잡아 화면 전체가 500 이었다"
    st = {s["id"]: s["status"] for s in r.json()["sources"]}
    assert st == {"kstartup": "ok", "bizinfo": "error", "gov24": "ok"}


def test_support_sources_are_fetched_concurrently(keys, monkeypatch):
    monkeypatch.setattr(program_sources, "_fetch_json", _router(barrier=threading.Barrier(3, timeout=5)))
    out = program_support.support_programs("garosugil", None)
    assert [s["status"] for s in out["sources"]] == ["ok", "ok", "ok"]
    assert [s["id"] for s in out["sources"]] == ["kstartup", "bizinfo", "gov24"], "상태 순서는 그대로다"


def test_network_sources_are_fetched_concurrently(keys, monkeypatch):
    monkeypatch.setattr(program_sources, "_fetch_json", _router(barrier=threading.Barrier(2, timeout=5)))
    out = program_network.network("garosugil")
    assert [(s["id"], s["status"]) for s in out["sources"]] == [("kstartup", "ok"), ("bizinfo_event", "ok")]


def test_logs_carry_no_secret_or_query(keys, clock, monkeypatch, caplog):
    def dead(url, params):
        raise _hung(clock)

    # 마이그레이션 테스트의 alembic fileConfig 가 이미 만들어진 로거를 꺼 둔다(disable_existing_loggers) — 순서와 무관하게 켠다
    monkeypatch.setattr(program_sources.logger, "disabled", False)
    monkeypatch.setattr(program_sources, "_fetch_json", dead)
    with caplog.at_level(logging.WARNING, logger="placeos.program.sources"):
        assert program_sources.kstartup_open().status == "error"
    text = caplog.text
    assert "transport retry" in text and "URLError(TimeoutError)" in text, "재시도와 원인 형식은 남긴다(진단용)"
    assert SECRET not in text and "serviceKey" not in text and "?" not in text
