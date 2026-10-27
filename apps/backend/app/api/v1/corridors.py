"""상권 흐름 라우터 — 파주-고양-서울을 고객 유입 흐름으로 잇는다(2026-10-26).

원천은 서울시×KT 수도권 생활이동(출발→도착 집계)이다. 한 사람의 동선이 아니다.
"""
from fastapi import APIRouter, HTTPException, Query

from app.schemas.corridor import CorridorResponse, CorridorSummary
from app.services import business_fit
from app.services import corridor as corridor_svc

router = APIRouter()


@router.get("", response_model=list[CorridorSummary])
async def list_corridors() -> list[dict]:
    return corridor_svc.list_corridors()


@router.get("/{corridor_id}", response_model=CorridorResponse)
async def get_corridor(corridor_id: str,
                       industry: str | None = Query(default=None, max_length=40)) -> dict:
    """흐름 하나. `industry`(업종 key)를 주면 마디의 거점에 입지 적합도·순위를 붙인다."""
    if industry is not None and business_fit.get(industry) is None:
        raise HTTPException(status_code=400, detail=f"unknown industry: {industry}")
    doc = corridor_svc.get(corridor_id, industry=industry)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"no corridor: {corridor_id}")
    return doc
