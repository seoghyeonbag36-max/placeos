"""건물 관련 엔드포인트 — 공실 히스토리."""
import asyncio

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.schemas.building import BuildingHistory
from app.schemas.renewal import BuildingTwin
from app.services import building_floors, building_ledger_live, building_twin, twin_roads
from app.services.building_history import get_history

router = APIRouter()


@router.get("/{building_id}/history", response_model=BuildingHistory)
async def get_building_history(building_id: str) -> BuildingHistory:
    """Return LocalData licensing history for a building."""
    if not building_id:
        raise HTTPException(status_code=404, detail="Building not found")
    history, history_source, lot_buildings = get_history(building_id)
    return BuildingHistory(
        building_id=building_id,
        history_source=history_source,
        lot_buildings=lot_buildings,
        history=history,
    )


@router.get("/{building_id}/twin", response_model=BuildingTwin)
async def get_building_twin(
    building_id: str,
    district: str = Query(..., min_length=1, max_length=40),
) -> dict:
    """3D 트윈 입력 — 실측 외곽선 · 층별 상태(`/floor-vacancies` 와 같은 근거) · 주변 건물 · 기준별 공실률
    · 주변 실제 도로(OSM · 폭은 추정). 도로를 못 받아도 트윈은 그대로 나간다(`roads_error`)."""
    out = building_twin.twin(district, building_id)
    if out is None:
        raise HTTPException(status_code=404, detail=f"unknown building: {building_id}")
    # 도로 타일 · 대장 실시간 조회는 블로킹 네트워크 호출 — 스레드풀에서 동시에 부른다(느린 쪽만큼만 기다린다).
    roads, ledger = await asyncio.gather(
        run_in_threadpool(twin_roads.roads_for_twin, out["lat"], out["lng"], out.get("ring"), out.get("road_addr")),
        run_in_threadpool(building_ledger_live.ledger, building_floors.pnu_of(out.get("id") or building_id)),
    )
    out.update(roads)
    out["ledger_live"] = ledger
    return out


@router.get("/{building_id}/model")
async def get_building_model(building_id: str) -> dict[str, str]:
    """glTF 경로를 만들어 돌려주는 **stub** — 지금은 부르는 곳이 없다.

    프론트도 테스트도 부르지 않고, `/static/models/*.glb` 는 **한 번도 존재한 적이 없다**(경로를
    문자열로 조립해 돌려줄 뿐 파일 유무를 확인하지 않는다).

    2026-10-27 사용자 결정으로 계획상가(집합건물)는 3D 디지털 트윈이 맡는다(CLAUDE.md §3D 디지털 트윈 ·
    docs/feature-posting.md §0-V). 그 형상 원천이 정해지면 이 자리를 실제 파일·형상으로 채우거나 바꾼다 —
    그 전에는 화면이 이 경로를 실측 모델로 읽게 하지 말 것.
    """
    return {"building_id": building_id, "model_url": f"/static/models/{building_id}.glb"}
