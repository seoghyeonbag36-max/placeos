"""교통 예상시간 조회 라우터."""
from fastapi import APIRouter

from app.schemas.travel import TravelRequest, TravelResponse, AddressSearchRequest, AddressSearchResponse
from app.services.travel import get_travel_times, search_addresses

router = APIRouter()


@router.post("/times", response_model=TravelResponse)
async def travel_times(request: TravelRequest) -> TravelResponse:
    return await get_travel_times(request)


@router.post("/addresses", response_model=AddressSearchResponse)
async def travel_addresses(request: AddressSearchRequest) -> AddressSearchResponse:
    return await search_addresses(request.query)
