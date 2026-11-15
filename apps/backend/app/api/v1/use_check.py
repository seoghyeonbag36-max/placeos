"""입점 점검 API — `GET /api/v1/buildings/{building_id}/use-check`.

「이 빈 층에 내 업종이 들어갈 수 있나」를 대장 용도코드 × 필지 용도지역 × 토지이음 행위제한으로 답한다
(`services/use_check` · 허가 판정 아님). 층의 대장 행은 실시간 건축HUB(용도코드 포함)를 먼저 쓰고, 실패하면
Gold 층 대장(`building_floors` · 용도코드 없음)으로 물러난다 — 그때는 별표1 호를 정하지 못해 확인 필요로 답한다.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from app.schemas.use_check import UseCheck
from app.services import building_floors, building_ledger_live, use_check

router = APIRouter()


@router.get("/{building_id}/use-check", response_model=UseCheck)
async def get_use_check(
    building_id: str,
    district: str = Query(..., min_length=1, max_length=40),
    floor: int = Query(..., ge=-10, le=200, description="층(지하는 음수)"),
    industry: str = Query(..., min_length=1, max_length=20, description="services/business_fit.INDUSTRIES 의 key"),
    area_m2: float | None = Query(None, gt=0, le=100_000, description="이 자리 면적(면적 기준 판단용 · 없으면 대장 행 면적)"),
    purps: str | None = Query(None, max_length=40, description="이 자리의 대장 용도(빈 층 유닛의 purps) — 층의 행을 이 용도로 좁힌다"),
) -> dict:
    if industry not in use_check.INDUSTRY_ACTS:
        raise HTTPException(status_code=400, detail=f"unknown industry: {industry}")
    pnu = building_floors.pnu_of(building_id)
    if not (len(pnu) == 19 and pnu.isdigit()):
        raise HTTPException(status_code=404, detail=f"unknown building: {building_id}")
    if building_floors.load(district) is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district}")
    live = await run_in_threadpool(building_ledger_live.ledger, pnu)
    parts, basis = use_check.floor_parts(live, district, pnu, floor, purps)
    if area_m2 is None and parts:
        area_m2 = max(p.get("area_m2") or 0 for p in parts) or None
    out = use_check.check(pnu, industry, parts=parts, area_m2=area_m2, ledger_date=basis)
    if out is None:  # INDUSTRY_ACTS 를 위에서 걸렀으니 오지 않는다
        raise HTTPException(status_code=400, detail=f"unknown industry: {industry}")
    out["ledger_live_status"] = live.get("status")
    return out
