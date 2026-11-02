"""교통 라우터 — 공실 인근 접근성(`/access`) · 출발지→목적지 소요(`/times`) · 주소 검색(`/addresses`)."""
from typing import Annotated

from fastapi import APIRouter, Query

from app.schemas.travel import (
    AccessRequest, AccessResponse, AddressSearchRequest, AddressSearchResponse, TravelRequest, TravelResponse,
)
from app.services.travel import get_transit_access, get_travel_times, search_addresses

router = APIRouter()


@router.post("/access", response_model=AccessResponse)
async def travel_access(request: AccessRequest) -> AccessResponse:
    return await get_transit_access(request)


@router.post("/times", response_model=TravelResponse)
async def travel_times(request: TravelRequest) -> TravelResponse:
    return await get_travel_times(request)


@router.get("/addresses", response_model=AddressSearchResponse)
async def travel_addresses(
    q: Annotated[str, Query(min_length=2, max_length=200)],
) -> AddressSearchResponse:
    """주소 검색. ⚠ 쿼리스트링은 접근 로그에 남는다 — 앱 화면은 본문으로 보내는 POST 를 쓴다."""
    return await search_addresses(q)


@router.post("/addresses", response_model=AddressSearchResponse)
async def travel_addresses_post(request: AddressSearchRequest) -> AddressSearchResponse:
    return await search_addresses(request.query)
