"""건물 관련 엔드포인트 — 공실 히스토리."""
from fastapi import APIRouter, HTTPException

from app.schemas.building import BuildingHistory
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
