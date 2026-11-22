"""Program — 네트워킹 · 오프라인 마케팅 실행 카드(2026-11-07 리뉴얼 · 2026-11-22 두 기능으로 좁힘).

2026-11-22 사용자 정의 「Program = 개업 후 계약을 맺은 공실에 대한 네트워킹·오프라인 마케팅」 — 화면은 /network 와
/plan(mode=actual_open · 기본값)만 부른다. `/support`(지원 공고)는 부르는 화면이 없어 **지웠다**
→ docs/decision-program-post-opening-2026-11-22.md.

둘 다 **공개 분석 API** 다(로그인 없이 열린다 — PPPP 화면 보존 규칙 ⑤). LLM 을 부르지 않는다.
네트워킹은 공고 원천을 서버에서 부르고 캐시한다(services/program_sources) — 키가 없거나 원천이
실패하면 그 원천만 상태로 밝히고 200 을 준다. 모르는 거점만 404 다.
캠페인(인증 필요)은 같은 접두어의 /program/campaigns 에 따로 있다.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.program import ExecutionPlan, ProgramNetwork
from app.services import program_network, program_plan

router = APIRouter()

_STAGE = Query(None, pattern="^(pre_founder|founder)$",
               description="pre_founder(예비창업자) | founder(기창업자 — Program 네트워킹은 개업한 자리 기준으로 이 값을 쓴다)")


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
    # 화면은 actual_open(개업 뒤)만 부른다(2026-11-22). 나머지 셋은 계약 전 검증이라 Program 에서 제외됐고 값으로만 남는다
    mode: str = Query("actual_open", pattern="^(popup|soft_open|mvp|actual_open)$"),
) -> dict:
    out = program_plan.plan(district_id, industry, mode)
    if out is None:
        raise HTTPException(404, "알 수 없는 상권입니다")
    return out
