"""Platform 벤치마킹 후보 탐색. 외부 상세는 카카오맵에서 확인한다."""
from fastapi import APIRouter, HTTPException, Query
from app.schemas.benchmark import BenchmarkPlaces
from app.services import benchmark

router = APIRouter()


@router.get("/industries")
async def industries() -> dict:
    return {"industries": benchmark.options()}


@router.get("/places", response_model=BenchmarkPlaces)
async def places(district_id: str = Query(..., max_length=40),
                 industry_key: str = Query(..., max_length=60)) -> dict:
    try:
        return await benchmark.search(district_id, industry_key)
    except benchmark.SearchError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
