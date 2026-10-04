"""`POST /marketing/generate` 의 LLM 문 — 로그인한 호출에만 열린다 (2026-10-03).

## 왜 이 문이 있나

이 엔드포인트는 호출 1회가 곧 Sonnet 1회(max_tokens 8192 + thinking)이고 결과 캐시가 없다.
분석 API 는 공개 데모라 익명을 통과시키므로(`get_optional_principal`), 문이 없으면 누구든
반복 호출로 크레딧을 태울 수 있었다.

## 여기서 고정하는 계약

  ① **익명이면 LLM 을 부르지 않는다.** 응답이 스텁인지만 보면 부족하다 — 스텁이 나와도
     호출이 일어났다면 토큰은 이미 나간 것이다. 그래서 `_call_llm` 이 불렸는지를 센다.
  ② **신원이 있으면(JWT · 조직 API 키) 열린다.** 문이 영영 안 열리면 LLM 경로가 죽은 코드가 된다.
  ③ **잘못된 자격증명은 401 이다.** 조용히 익명(=스텁)으로 강등하면 만료된 키가 계속
     200 을 받으면서 "왜 AI 결과가 안 나오는지"가 안 보인다.
  ④ **서비스 함수의 기본값도 닫혀 있다.** 나중에 호출부가 생겨 인자를 빠뜨려도 비용이 새지 않는다.

## 상권 단위 `GET /marketing/{district_id}` — 같은 문 + 실패 캐시 (2026-10-03)

  ⑤ 같은 문이다. 익명은 시드이고, **캐시에 이미 있는 AI 결과도 익명에게 보이지 않는다**
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
from app.schemas.marketing import LLMDistrictContents, LLMProgramPlan
from app.services import marketing as mkt
from tests.conftest import _act, _perf, _signal

client = TestClient(app)
V1 = "/api/v1"

_BRIEF = {
    "item": "제철 해산물 오마카세 가오픈",
    "category": "F&B",
    "mode": "soft_open",
    "stage": "founder",
    "district_id": "hongdae-yeonnam",
    "hypothesis": "연남동 저녁 수요가 객단가 5만원대를 받아준다",
    "start_date": "2026-10-05",
    "run_days": 14,
}


def _fake_plan() -> LLMProgramPlan:
    return LLMProgramPlan(
        online=[_perf(channel="인스타그램", content="릴스 게시", rationale="자리 근거")],
        offline=[_act(channel="전단", content="시식 이벤트", rationale="유동객 근거")],
        signals=[_signal()],
        ha_check="균형·공생·공감 점검 통과",
    )


@pytest.fixture
def llm_spy(monkeypatch):
    """LLM 키를 켜고 `_call_llm` 호출 횟수를 센다 — 실호출은 어떤 경우에도 일어나지 않는다."""
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    calls: list[dict] = []

    def spy(brief, ctx, site=None, brief_ctx=None):
        calls.append(brief)
        return _fake_plan()

    monkeypatch.setattr(mkt, "_call_llm", spy)
    # 컨텍스트 결합을 끊어 Gold 적재 상태에 좌우되지 않게 한다.
    monkeypatch.setattr(mkt, "_district_context", lambda d: None)
    return calls


def test_anonymous_gets_stub_and_never_reaches_llm(llm_spy):
    """① 키가 있어도 익명이면 스텁이고, LLM 호출 자체가 0건이다."""
    r = client.post(f"{V1}/marketing/generate", json=_BRIEF)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "rule-stub"
    assert llm_spy == [], "익명 요청이 LLM 을 불렀다 — 토큰이 샌다"
    # 스텁도 검증 프로그램의 모양을 지킨다(지표 없는 홍보 생성기로 돌아가지 않는다).
    assert body["online"] and body["offline"] and body["signals"]
    assert body["ha_findings"] == []


def test_repeated_anonymous_calls_stay_free(llm_spy):
    """① 반복 호출이 크레딧이 되던 것이 원래의 구멍이다 — 몇 번을 불러도 0건."""
    for _ in range(5):
        assert client.post(f"{V1}/marketing/generate", json=_BRIEF).json()["source"] == "rule-stub"
    assert llm_spy == []


def test_signed_in_reaches_llm(llm_spy, signed_in):
    """② 로그인하면 문이 열려 LLM 경로로 들어간다."""
    r = client.post(f"{V1}/marketing/generate", json=_BRIEF, headers=signed_in)
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "llm"
    assert len(llm_spy) == 1


def test_org_api_key_reaches_llm(llm_spy, signed_in):
    """② 조직 API 키(`X-API-Key`)로 부르는 B2B 연동도 열린다."""
    issued = client.post(f"{V1}/auth/api-keys", json={"name": "연동"}, headers=signed_in)
    assert issued.status_code == 201, issued.text
    key = issued.json()["key"]

    r = client.post(f"{V1}/marketing/generate", json=_BRIEF, headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "llm"
    assert len(llm_spy) == 1


def test_invalid_credentials_are_rejected_not_demoted(llm_spy, signed_in):
    """③ 잘못된 토큰·키는 401 — 조용히 익명으로 떨어뜨리지 않는다.

    `signed_in` 은 헤더가 아니라 **인메모리 DB 연결** 때문에 받는다 — 키 조회는 DB 를 친다.
    """
    bad_token = client.post(f"{V1}/marketing/generate", json=_BRIEF,
                            headers={"Authorization": "Bearer not-a-real-token"})
    assert bad_token.status_code == 401, bad_token.text

    bad_key = client.post(f"{V1}/marketing/generate", json=_BRIEF,
                          headers={"X-API-Key": "sk_placeos_" + "0" * 64})
    assert bad_key.status_code == 401, bad_key.text
    assert llm_spy == []


def test_signed_in_without_llm_key_still_stub(monkeypatch, signed_in):
    """문이 열려도 키가 없으면 스텁이다 — 문은 필요조건이지 충분조건이 아니다."""
    monkeypatch.setattr(settings, "llm_api_key", "")
    r = client.post(f"{V1}/marketing/generate", json=_BRIEF, headers=signed_in)
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "rule-stub"


def test_service_default_is_closed(llm_spy):
    """④ `allow_llm` 을 빠뜨린 직접 호출도 LLM 을 부르지 않는다(fail-closed)."""
    assert mkt.generate_program(dict(_BRIEF))["source"] == "rule-stub"
    assert llm_spy == []
    # 명시적으로 열었을 때만 간다.
    assert mkt.generate_program(dict(_BRIEF), allow_llm=True)["source"] == "llm"
    assert len(llm_spy) == 1


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
