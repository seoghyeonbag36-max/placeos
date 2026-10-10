"""교통 제공사가 계산한 예상시간 계약 — 실측·시드와 구분한다."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TravelPoint(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False, strict=True)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False, strict=True)


class TravelRequest(BaseModel):
    origin: TravelPoint
    destination: TravelPoint


class TravelResult(BaseModel):
    mode: Literal["driving", "transit"]
    provider: Literal["kakao_mobility", "odsay"]
    status: Literal["ok", "not_configured", "no_route", "unsupported_route", "upstream_error", "quota_exceeded"]
    source: Literal["provider_estimate"] = "provider_estimate"
    # 차량은 현재 출발 기준, ODsay 도시내 경로는 시간표 기반 실시간 도착 보장이 아니다.
    time_basis: Literal["current_departure", "standard_route"]
    duration_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    distance_meters: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    fare_won: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    transfers: int | None = Field(default=None, ge=0)
    walk_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_status(self) -> "TravelResult":
        if self.status == "ok" and self.duration_seconds is None:
            raise ValueError("성공 응답에는 제공사 소요시간이 필요합니다.")
        if self.status != "ok" and any(value is not None for value in (
            self.duration_seconds, self.distance_meters, self.fare_won,
            self.transfers, self.walk_seconds,
        )):
            raise ValueError("실패 응답에 교통 수치를 채울 수 없습니다.")
        return self


class TravelResponse(BaseModel):
    origin: TravelPoint
    destination: TravelPoint
    queried_at: datetime
    results: list[TravelResult]
