"""인테리어 참고 이미지 입력 계약 — 사용자 제공 조건이며 시공·수요 검증이 아니다."""
from typing import Literal

from pydantic import BaseModel, Field


class InteriorReference(BaseModel):
    kind: Literal["plan", "photo"]
    mime: Literal["image/png", "image/jpeg", "image/webp"]
    data: str = Field(min_length=8, max_length=4_000_000)


class InteriorRequest(BaseModel):
    district: str = Field(min_length=1, max_length=100)
    industry: str = Field(min_length=1, max_length=100)
    style: str = Field(min_length=1, max_length=500)
    strategy: Literal["고급화", "가성비", "기능중심"]
    area_py: float | None = Field(default=None, gt=0, le=3000, allow_inf_nan=False)
    constraints: str = Field(default="", max_length=1500)
    links: list[str] = Field(default_factory=list, max_length=5)
    references: list[InteriorReference] = Field(default_factory=list, max_length=2)
    consent: Literal[True]


class InteriorResult(BaseModel):
    source: Literal["ai_generated"] = "ai_generated"
    image_data_url: str
    model: str
    note: str
