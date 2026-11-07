"""Program 리뉴얼(2026-11-07) — 지원 프로그램 · 네트워킹 · 오프라인 마케팅 실행 카드.

셋 다 **공개 분석 API** 다(로그인 없이 열린다 — PPPP 화면 보존 규칙 ⑤). LLM 을 부르지 않는다.
지원·네트워킹은 공고 원천을 서버에서 부르고 캐시한다(services/program_sources) — 키가 없거나 원천이
실패하면 그 원천만 상태로 밝히고 200 을 준다. 모르는 거점만 404 다.
캠페인(인증 필요)은 같은 접두어의 /program/campaigns 에 따로 있다.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.program import ExecutionPlan, ProgramNetwork, SupportPrograms
from app.services import program_network, program_plan, program_support

router = APIRouter()

_STAGE = Query(None, pattern="^(pre_founder|founder)$",
               description="pre_founder(예비창업자 — 「내 사업」 창업) | founder(업종 바꾸기·상권 옮기기)")


@router.get("/support", response_model=SupportPrograms)
def get_support_programs(
    district_id: str = Query(..., max_length=64),
    stage: str | None = _STAGE,
    industry: str | None = Query(None, max_length=40, description="업종 이름(언급 표시용 — 거르지 않는다)"),
) -> dict:
    out = program_support.support_programs(district_id, stage, industry)
    if out is None:
        raise HTTPException(404, "알 수 없는 상권입니다")
    return out


@router.get("/network", response_model=ProgramNetwork)
def get_program_network(
    district_id: str = Query(..., max_length=64),
    industry: str | None = Query(None, max_length=40, description="업종 키(/ai/industries 의 key)"),
    industry_label: str | None = Query(None, max_length=40),
    stage: str | None = _STAGE,
) -> dict:
    out = program_network.network(district_id, industry, industry_label, stage)
    if out is None:
        raise HTTPException(404, "알 수 없는 상권입니다")
    return out


@router.get("/plan", response_model=ExecutionPlan)
def get_execution_plan(
    district_id: str = Query(..., max_length=64),
    industry: str | None = Query(None, max_length=40, description="업종 키(/ai/industries 의 key)"),
    mode: str = Query("popup", pattern="^(popup|soft_open|mvp|actual_open)$"),
) -> dict:
    out = program_plan.plan(district_id, industry, mode)
    if out is None:
        raise HTTPException(404, "알 수 없는 상권입니다")
    return out
