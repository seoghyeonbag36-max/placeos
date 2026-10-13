"""공실 인근 교통 접근성 라우터 — 지하철역·버스정류장 도보시간, 주차장 위치."""
from fastapi import APIRouter

from app.schemas.travel import AccessRequest, AccessResponse
from app.services.travel import get_transit_access

router = APIRouter()


@router.post("/access", response_model=AccessResponse)
async def travel_access(request: AccessRequest) -> AccessResponse:
    return await get_transit_access(request)
