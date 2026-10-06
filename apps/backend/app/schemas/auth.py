"""계정층 요청/응답 스키마 — 가입은 곧 조직 생성이다(개인 계정 없음)."""
from __future__ import annotations

from datetime import datetime

from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class SignupRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    """구글 버튼이 넘겨준 ID 토큰(credential). 처음이면 가입까지 한다 — 사업 이름은 선택이다."""
    credential: str = Field(min_length=1, max_length=4096)
    org_name: str | None = Field(default=None, max_length=200)


class AuthProviders(BaseModel):
    """화면이 그릴 로그인 수단. 구글 클라이언트 ID 는 공개값이다(구글 버튼이 그대로 싣는다)."""
    google_client_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrgOut(BaseModel):
    id: str
    name: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    org: OrgOut
    role: str


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100,
                      description="용도 식별용 이름 — 어디에 쓴 키인지 나중에 알아보려면 필요하다")


class ApiKeyOut(BaseModel):
    """목록·폐기 응답. **원문(key)은 없다** — 발급 응답에만 한 번 실린다."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime
    revoked_at: datetime | None = None


class ApiKeyCreatedResponse(ApiKeyOut):
    key: str = Field(description="원문 키. 이 응답에서만 볼 수 있고 서버에 저장되지 않는다")


class BusinessProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: Literal["start", "pivot", "move"]
    # 창업·옮기기면 **할** 업종, 바꾸기면 **지금** 업종(Platform 이 지금 상권의 업종 순위를 매기는 기준).
    industryKey: str = Field(min_length=1, max_length=200)
    homeDistrictId: str | None = Field(default=None, max_length=200)
    businessName: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    # 바꾸기만: **바꿀** 업종(2026-10-06). 아직 모르면 비운다. Posting·Program 의 업종 기본값이 이것이다 —
    # 종전에는 바꾸기 사용자에게도 industryKey(버릴 업종)가 기본값으로 채워졌다(finding-project-review §2-1).
    targetIndustryKey: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def require_district(self) -> "BusinessProfile":
        if self.goal != "start" and not self.homeDistrictId:
            raise ValueError("현재 상권이 필요합니다")
        if self.goal != "pivot" and self.targetIndustryKey:
            raise ValueError("바꿀 업종은 업종 바꾸기에서만 정합니다")
        return self


class BusinessWorkspaceData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["unset", "browsing", "set"]
    profile: BusinessProfile | None = None
    source: Literal["user_input"] = "user_input"

    @model_validator(mode="after")
    def require_profile(self) -> "BusinessWorkspaceData":
        if (self.status == "set") != (self.profile is not None):
            raise ValueError("설정 상태와 사업 정보가 일치해야 합니다")
        return self
