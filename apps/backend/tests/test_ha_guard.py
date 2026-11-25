"""Humanistic Authority 후처리 검증기 테스트 (services/ha_guard.py) — 상권 단위 온라인 카피.

## 이 스위트가 지키는 것 두 가지

1. **위반을 잡는가** — 지어낸 금액·확정 트렌드 역행은 violation 으로 응답이 폐기돼야 한다.
2. **정상 산출물을 죽이지 않는가** — 이쪽이 더 중요하다. 사전 기반 규칙은 세게 걸면
   진짜 산출물까지 죽인다(2026-08-01 동명이지 정제에서 체험단 필터를 포기한 것과 같은
   이유). 그래서 오탐이 날 만한 문장을 **음성 대조로 명시해 고정한다** — "손님을 늘리는
   전단"(목표이지 주장이 아니다), "최대한 활용"(최대가 아니다), "경쟁력"(비방이 아니다).

2026-11-22: 검증 프로그램 생성(`check_program` · 미검증 경험 · 검증 지표 · 채널 균형 · 행사 인용 · 예산)을 지우면서 그 테스트도 지웠다
→ docs/decision-program-post-opening-2026-11-22.md. 금액·트렌드·최상급·비방 규칙은 상권 카피(`check_district`)가 그대로 쓰므로 직접 고정한다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.marketing import LLMDistrictContents
from app.services import ha_guard

client = TestClient(app)
V1 = "/api/v1"


@pytest.fixture(autouse=True)
def _isolate_marketing_cache():
    """상권 콘텐츠 캐시 격리 — 앞 테스트의 캐시를 물면 폐기/생성 판정을 검증하지 못한다."""
    from app.services import marketing as mkt
    mkt.clear_district_cache()
    yield
    mkt.clear_district_cache()


_CTX_DOWN = "검색 트렌드(최근 6개월, 방향은 계산된 값이다): 가로수길 하락(26.3→21.4, -18.6%)"
_CTX_UP = "검색 트렌드(최근 6개월, 방향은 계산된 값이다): 가로수길 상승(21.4→26.3, +22.9%)"
_CTX_MIXED = _CTX_DOWN + "; 신사동 상승(60.0→70.0, +16.7%)"


def _copy(*contents: str, ha_check: str = "점검 통과") -> LLMDistrictContents:
    return LLMDistrictContents(online_contents=list(contents), ha_check=ha_check)


def _codes(findings) -> set[str]:
    return {f.code for f in findings}


# ── 규칙 직접 (check_district) ───────────────────────────────────────────────

def test_fabricated_price_is_violation():
    findings = ha_guard.check_district(_copy("오픈 기념 6,000원 쿠폰 #가로수길"), "상권 컨텍스트에는 가격이 없다")
    assert "fabricated_price" in _codes(findings) and ha_guard.has_violation(findings)


def test_man_won_notation_is_caught():
    assert "fabricated_price" in _codes(ha_guard.check_district(_copy("월 3만원 이벤트 #골목"), "키워드: 브런치"))


def test_no_price_anywhere_passes():
    assert not ha_guard.has_violation(ha_guard.check_district(_copy("브런치 골목 산책 #가로수길"), "키워드: 브런치"))


def test_trend_contradiction_is_violation():
    findings = ha_guard.check_district(_copy("요즘 발걸음이 늘고 있는 골목 #가로수길"), _CTX_DOWN)
    assert "trend_contradiction" in _codes(findings) and ha_guard.has_violation(findings)


def test_standalone_surge_word_is_violation_when_trend_falls():
    assert "trend_contradiction" in _codes(ha_guard.check_district(_copy("붐비는 골목 #가로수길"), _CTX_DOWN))


def test_growth_goal_is_not_a_claim():
    """「손님을 늘리는 전단」은 목표이지 주장이 아니다 — 하락 트렌드에서도 통과해야 한다."""
    assert "trend_contradiction" not in _codes(ha_guard.check_district(_copy("손님을 늘리는 전단 #가로수길"), _CTX_DOWN))


def test_increase_claim_allowed_when_trend_rises():
    assert "trend_contradiction" not in _codes(ha_guard.check_district(_copy("발걸음이 늘고 있는 골목 #가로수길"), _CTX_UP))


def test_mixed_trend_does_not_block():
    assert "trend_contradiction" not in _codes(ha_guard.check_district(_copy("발걸음이 늘고 있는 골목 #가로수길"), _CTX_MIXED))


def test_unsupported_superlative_is_warning_not_violation():
    findings = ha_guard.check_district(_copy("서울 최고의 브런치 골목 #가로수길"), "키워드: 브런치")
    assert findings and not ha_guard.has_violation(findings)


def test_choedaehan_is_not_superlative():
    # 트렌드 라벨이 든 컨텍스트로 — 라벨이 없으면 「역행 검사를 못 돌렸다」(trend_unverified) 경고가 따로 뜬다
    assert not ha_guard.check_district(_copy("골목을 최대한 즐기는 법 #가로수길"), _CTX_UP)


def test_disparagement_is_warning():
    findings = ha_guard.check_district(_copy("다른 가게보다 훨씬 낫다 #가로수길"), "키워드: 브런치")
    assert findings and not ha_guard.has_violation(findings)


def test_competitiveness_word_is_not_disparagement():
    assert not ha_guard.check_district(_copy("골목의 경쟁력을 키우는 산책 #가로수길"), _CTX_UP)


# ── 배선 (상권 단위) ─────────────────────────────────────────────────────────

def test_district_violation_falls_back_to_seed(monkeypatch, signed_in):
    """상권 카피가 확정 트렌드를 뒤집으면 시드로 내려간다 (08-01 사고의 회귀 방지)."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(mkt, "_district_context", lambda d: _CTX_DOWN)
    bad = LLMDistrictContents(
        online_contents=["신사동을 찾는 발걸음이 다시 늘고 있는 요즘 #가로수길 #산책"],
        ha_check="점검 통과")
    monkeypatch.setattr(mkt, "_call_district_llm", lambda name, sub, ctx: bad)

    body = client.get(f"{V1}/marketing/garosugil", headers=signed_in).json()
    assert body["source"] == "seed", "위반인데 생성 카피가 그대로 나갔다"
    assert "trend_contradiction" in {f["code"] for f in body["ha_findings"]}
    assert not any("늘고 있는" in c for c in body["online_contents"])


def test_district_violation_is_cached(monkeypatch, signed_in):
    """폐기된 결과도 캐시한다 — 안 그러면 호출마다 같은 위반을 다시 생성하며 크레딧을 태운다."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(mkt, "_district_context", lambda d: _CTX_DOWN)
    calls: list[int] = []

    def spy(name, sub, ctx):
        calls.append(1)
        return LLMDistrictContents(
            online_contents=["붐비는 골목 #가로수길 #카페"], ha_check="ok")

    monkeypatch.setattr(mkt, "_call_district_llm", spy)

    first = client.get(f"{V1}/marketing/garosugil", headers=signed_in).json()
    second = client.get(f"{V1}/marketing/garosugil", headers=signed_in).json()
    assert len(calls) == 1, "폐기된 결과가 캐시되지 않아 LLM 을 다시 쳤다"
    assert first["source"] == second["source"] == "seed"
    assert second["ha_findings"], "캐시 경로가 폐기 사유를 잃었다"


def test_district_clean_output_is_served(monkeypatch, signed_in):
    """정상 카피는 그대로 나가고 findings 는 비어 있다 (음성 대조)."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(mkt, "_district_context", lambda d: _CTX_DOWN)
    good = LLMDistrictContents(
        online_contents=["골목마다 다른 커피 취향 #가로수길 #카페투어"], ha_check="ok")
    monkeypatch.setattr(mkt, "_call_district_llm", lambda name, sub, ctx: good)

    body = client.get(f"{V1}/marketing/garosugil", headers=signed_in).json()
    assert body["source"] == "llm"
    assert body["ha_findings"] == []
