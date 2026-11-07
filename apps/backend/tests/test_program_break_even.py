"""가설 검증 목표선 — Posting 하루 손익분기에서만 숫자를 끌어낸다(2026-11-07 리뉴얼).

예전 규칙 스텁은 팝업 「일 60명」·「70% 미만 기각」, 가오픈 「객단가 12,000원」, MVP 「전환율 8%」·「4% 미만」을
냈다 — 그 자리의 본전과 무관한 고정값이다(KPI 규칙 1: 임계값을 발명하지 않는다).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.marketing import ProgramBrief
from app.services import marketing, program_brief

_BRIEF = {"item": "제철 디저트 팝업", "category": "카페·디저트", "mode": "popup", "stage": "pre_founder"}


def _first_signal(**extra) -> dict:
    return marketing.generate_program({**_BRIEF, **extra})["signals"][0]


def test_no_break_even_means_no_invented_target():
    s = _first_signal()
    assert "목표선 미정" in s["target"] and "판정하지 않는다" in s["decision"]
    blob = s["target"] + s["decision"]
    for invented in ("60명", "70%", "12,000원", "8%", "4%"):
        assert invented not in blob, f"지어낸 목표선이 남았다: {invented}"


def test_break_even_sets_target_and_reject_rule():
    s = _first_signal(break_even_daily=264, break_even_basis="월 손익분기 3,314만원 ÷ (객단가 0.45만원 × 28일)",
                      reject_ratio=80)
    assert s["target"].startswith("하루 결제 264건") and "Posting 손익분기" in s["target"]
    assert "212건" in s["decision"] and "80%" in s["decision"], "기각선 = ceil(264 × 0.8) = 212"


def test_break_even_without_ratio_defers_judgement():
    s = _first_signal(break_even_daily=100)
    assert "100건" in s["target"] and "미정" in s["decision"]


def test_soft_open_uses_break_even_and_mvp_never_invents():
    soft = marketing.generate_program({**_BRIEF, "mode": "soft_open", "break_even_daily": 50, "reject_ratio": 70})
    assert "50건" in soft["signals"][0]["target"] and "35건" in soft["signals"][0]["decision"]
    mvp = marketing.generate_program({**_BRIEF, "mode": "mvp", "break_even_daily": 50})
    assert "지어내지 않는다" in mvp["signals"][0]["target"]


def test_brief_context_carries_break_even_for_llm():
    ctx = program_brief.brief_context({**_BRIEF, "break_even_daily": 264, "break_even_basis": "근거", "reject_ratio": 80})
    assert "하루 손익분기: 264건 (근거)" in ctx and "기각선: 목표선의 80%" in ctx


def test_schema_bounds():
    ProgramBrief(**_BRIEF, break_even_daily=1, reject_ratio=10)
    for bad in ({"break_even_daily": 0}, {"reject_ratio": 5}, {"reject_ratio": 101}):
        with pytest.raises(ValidationError):
            ProgramBrief(**_BRIEF, **bad)
