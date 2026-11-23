"""상권 단위 `GET /marketing/{district_id}` 의 LLM 문 — 로그인한 호출에만 열린다 (2026-10-03).

2026-11-22: `POST /marketing/generate`(검증 프로그램 생성)의 문 테스트(익명 차단 · 신원 열림 · 잘못된 자격증명 401 · 서비스 기본값)는
그 엔드포인트와 함께 지웠다 → docs/decision-program-post-opening-2026-11-22.md. 상권 단위의 같은 문과 실패 캐시만 남는다.

## 여기서 고정하는 계약

  ⑤ **익명은 시드이고, 캐시에 이미 있는 AI 결과도 익명에게 보이지 않는다**
     (같은 거점이 호출자에 따라 달라지지 않게 · "로그인하면 AI 생성" 안내가 거짓이 되지 않게).
  ⑥ **실패도 비용이다.** 응답이 비었거나 파싱·호출이 예외로 끝나면 종전에는 캐시할 결과가 없어
     같은 요청이 올 때마다 LLM 을 다시 쳤다. 이제 실패는 시간 제한을 두고 캐시한다 —
     시간이 지나면 다시 시도하고(일시 장애 복구), 입력(컨텍스트 mtime)이 바뀌면 즉시 다시 친다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.schemas.marketing import LLMDistrictContents
from app.services import marketing as mkt

client = TestClient(app)
V1 = "/api/v1"

# ── 상권 단위 ────────────────────────────────────────────────────────────────

_DISTRICT = "garosugil"
_DISTRICT_CTX = "블로그 언급 키워드: 팝업(120건)"
_GOOD_COPY = "가로수길 팝업 지도 #가로수길 #팝업"


@pytest.fixture
def district_llm(monkeypatch):
    """LLM 키·컨텍스트를 켜고 `_call_district_llm` 호출 수를 센다.

    `state["behavior"]` 로 응답을 바꾼다: "ok"(정상) · "empty"(빈 목록) · "boom"(예외).
    실호출은 어떤 경우에도 일어나지 않는다.
    """
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(mkt, "_district_context", lambda d: _DISTRICT_CTX)
    mkt.clear_district_cache()
    state = {"calls": 0, "behavior": "ok"}

    def fake(name, sub, ctx):
        state["calls"] += 1
        if state["behavior"] == "boom":
            raise RuntimeError("api down")
        if state["behavior"] == "empty":
            return LLMDistrictContents(online_contents=[], ha_check="ok")
        return LLMDistrictContents(online_contents=[_GOOD_COPY], ha_check="ok")

    monkeypatch.setattr(mkt, "_call_district_llm", fake)
    yield state
    mkt.clear_district_cache()


def _get(headers=None):
    return client.get(f"{V1}/marketing/{_DISTRICT}", headers=headers).json()


def test_district_anonymous_gets_seed_and_never_reaches_llm(district_llm):
    """⑤ 키·컨텍스트가 다 있어도 익명이면 시드이고 LLM 호출이 0건이다."""
    for _ in range(3):
        body = _get()
        assert body["source"] == "seed"
        assert body["online_contents"], "시드 카피까지 비면 화면이 빈다"
    assert district_llm["calls"] == 0, "익명 요청이 LLM 을 불렀다 — 토큰이 샌다"


def test_district_anonymous_never_sees_cached_llm_result(district_llm, signed_in):
    """⑤ 로그인한 사용자가 채운 캐시를 익명이 읽지 않는다 — 호출자에 따라 거점이 달라지지 않는다."""
    assert _get(signed_in)["source"] == "llm"
    assert district_llm["calls"] == 1
    assert _get()["source"] == "seed"
    assert district_llm["calls"] == 1


def test_district_signed_in_reaches_llm(district_llm, signed_in):
    body = _get(signed_in)
    assert body["source"] == "llm"
    assert body["online_contents"] == [_GOOD_COPY]
    # 행사는 LLM 과 무관하다 — 익명에게도 같은 출처로 나간다.
    assert _get()["events_source"] == body["events_source"]


def test_district_empty_response_is_not_retried(district_llm, signed_in):
    """⑥ 응답이 비어도 같은 요청이 LLM 을 다시 치지 않는다."""
    district_llm["behavior"] = "empty"
    for _ in range(3):
        assert _get(signed_in)["source"] == "seed"
    assert district_llm["calls"] == 1, "빈 응답이 캐시되지 않아 LLM 을 반복해서 쳤다"


def test_district_exception_is_not_retried(district_llm, signed_in):
    """⑥ 호출이 예외로 끝나도(파싱·스키마 실패 포함) 같은 요청이 LLM 을 다시 치지 않는다."""
    district_llm["behavior"] = "boom"
    for _ in range(3):
        assert _get(signed_in)["source"] == "seed"
    assert district_llm["calls"] == 1, "실패가 캐시되지 않아 LLM 을 반복해서 쳤다"


def test_district_failure_cache_expires_and_recovers(district_llm, signed_in, monkeypatch):
    """⑥ 실패 캐시는 영구가 아니다 — 일시 장애가 풀리면 AI 콘텐츠가 돌아온다."""
    monkeypatch.setattr(mkt, "_DISTRICT_FAILURE_TTL_S", 0.0)   # 기록하자마자 만료
    district_llm["behavior"] = "boom"
    assert _get(signed_in)["source"] == "seed"
    assert district_llm["calls"] == 1

    district_llm["behavior"] = "ok"                            # 장애가 풀렸다
    body = _get(signed_in)
    assert district_llm["calls"] == 2, "만료됐는데 재시도하지 않았다 — 시드에 붙잡혔다"
    assert body["source"] == "llm"


def test_district_failure_cache_yields_to_changed_input(district_llm, signed_in, monkeypatch):
    """⑥ 입력(컨텍스트 mtime)이 바뀌면 시간이 안 지나도 다시 친다 — 파이프라인을 다시 돌린 직후."""
    district_llm["behavior"] = "boom"
    assert _get(signed_in)["source"] == "seed"
    assert district_llm["calls"] == 1

    monkeypatch.setattr(mkt, "_context_mtime", lambda d: 12345.0)
    district_llm["behavior"] = "ok"
    assert _get(signed_in)["source"] == "llm"
    assert district_llm["calls"] == 2
