"""교통 예상시간 조회 라우터."""
from fastapi import APIRouter

from app.schemas.travel import TravelRequest, TravelResponse
from app.services.travel import get_travel_times

router = APIRouter()


@router.post("/times", response_model=TravelResponse)
async def travel_times(request: TravelRequest) -> TravelResponse:
    return await get_travel_times(request)
