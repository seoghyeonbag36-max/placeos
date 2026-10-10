"""카카오 검색 후보 계약. 점포 등록을 현재 영업 확인으로 해석하지 않는다."""
from typing import Literal
from pydantic import BaseModel


class BenchmarkPlace(BaseModel):
    id: str
    name: str
    category: str
    address: str
    phone: str | None
    lat: float
    lng: float
    place_url: str
    distance_m: int


class BenchmarkPlaces(BaseModel):
    district_id: str
    industry_key: str
    source: Literal["kakao_local"] = "kakao_local"
    scope: Literal["measured_cells"] = "measured_cells"
    queried_at: str
    truncated: bool
    note: str
    places: list[BenchmarkPlace]
