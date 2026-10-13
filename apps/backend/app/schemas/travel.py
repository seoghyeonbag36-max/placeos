"""공실 인근 교통 접근성 계약 — 제공사 값·공공데이터와 계산·추정을 구분한다.

도보시간은 TMAP 보행자 경로의 값이다. 실패하면 null 과 이유(status)만 남기고
직선거리·보행속도로 시간을 채우지 않는다.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TravelPoint(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False, strict=True)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False, strict=True)


class AccessRequest(BaseModel):
    destination: TravelPoint


class WalkTime(BaseModel):
    """한 장소에서 공실까지의 보행 경로 값. `ok` 가 아니면 수치는 모두 null 이다."""
    status: Literal["ok", "not_configured", "no_route", "upstream_error", "quota_exceeded"]
    source: Literal["tmap_pedestrian"] = "tmap_pedestrian"
    duration_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    distance_meters: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_status(self) -> "WalkTime":
        if self.status == "ok" and self.duration_seconds is None:
            raise ValueError("성공 응답에는 제공사 도보시간이 필요합니다.")
        if self.status != "ok" and (self.duration_seconds is not None or self.distance_meters is not None):
            raise ValueError("실패 응답에 도보 수치를 채울 수 없습니다.")
        return self


class AccessPlace(BaseModel):
    kind: Literal["subway", "bus_stop", "parking"]
    name: str = Field(min_length=1)
    # 지하철: 노선 목록 · 버스: 정류소 번호 없이 이용량 설명 · 주차장: 주소
    detail: str | None = None
    point: TravelPoint
    # 공실 좌표와 이 장소 좌표 사이 직선거리(m). 제공사 값이 아니라 좌표에서 계산한다.
    straight_meters: float = Field(ge=0, allow_inf_nan=False)
    # 지하철·버스만. 주차장은 도보시간을 묻지 않는다.
    walk: WalkTime | None = None
    # 버스만: 정류소 일평균 승차+하차 인원(교통카드 · 모든 노선 합)과 지나는 노선 수.
    daily_riders: int | None = Field(default=None, ge=0)
    route_count: int | None = Field(default=None, ge=0)
    source: Literal["kakao_local", "seoul_open_data"]
    place_url: str | None = None


class AccessGroup(BaseModel):
    """한 종류(지하철·버스·주차장)의 결과. 한 종류가 실패해도 다른 종류를 숨기지 않는다."""
    status: Literal["ok", "no_results", "not_configured", "upstream_error", "quota_exceeded", "unavailable"]
    radius_meters: int
    items: list[AccessPlace] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_items(self) -> "AccessGroup":
        if self.status != "ok" and self.items:
            raise ValueError("실패·빈 결과에 항목을 채울 수 없습니다.")
        return self


class AccessResponse(BaseModel):
    destination: TravelPoint
    queried_at: datetime
    subway: AccessGroup
    bus_stops: AccessGroup
    parking: AccessGroup
    # 버스 이용량 산출 기간(없으면 null). 화면이 기준 시점을 밝히는 데 쓴다.
    bus_window: dict[str, str | int] | None = None
