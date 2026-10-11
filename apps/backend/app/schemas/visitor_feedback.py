"""방문자 의견 입력과 관리자 응답 계약."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class VisitorFeedbackIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    category: Literal["review", "bug", "suggestion"]
    message: str = Field(min_length=1, max_length=2000)
    page: str = Field(min_length=1, max_length=500, pattern=r"^/[^?]*$")
    contact: str | None = Field(default=None, min_length=1, max_length=320)

class VisitorFeedbackSaved(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime

class VisitorFeedbackOut(VisitorFeedbackSaved):
    category: str
    message: str
    page: str
    contact: str | None
    status: str
    notification_status: str

class VisitorFeedbackStatus(BaseModel):
    status: Literal["received", "reviewing", "completed"]
