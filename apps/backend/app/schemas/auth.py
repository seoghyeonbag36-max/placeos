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
    naver_enabled: bool = False
    kakao_enabled: bool = False


class SocialStartRequest(BaseModel):
    org_name: str | None = Field(default=None, max_length=200)


class SocialStartResponse(BaseModel):
    authorization_url: str
    state: str
    verifier: str


class SocialLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=1, max_length=4096)
    verifier: str = Field(min_length=32, max_length=128)
    org_name: str | None = Field(default=None, max_length=200)


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
    industryDetailKey: str | None = Field(default=None, max_length=100)
    targetIndustryDetailKey: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_district(self) -> "BusinessProfile":
        if self.goal != "start" and not self.homeDistrictId:
            raise ValueError("현재 상권이 필요합니다")
        if self.goal != "pivot" and self.targetIndustryKey:
            raise ValueError("바꿀 업종은 업종 바꾸기에서만 정합니다")
        from app.services.industry_detail import get
        for key, parent in ((self.industryDetailKey, self.industryKey),
                            (self.targetIndustryDetailKey, self.targetIndustryKey)):
            if key:
                item = get(key)
                if item is None or item["parent"] != parent:
                    raise ValueError("세부 업종이 선택한 상위 업종과 일치하지 않습니다")
        if self.goal != "pivot" and self.targetIndustryDetailKey:
            raise ValueError("바꿀 세부 업종은 업종 바꾸기에서만 정합니다")
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


# ── 저장한 결과 (2026-10-06) ───────────────────────────────────────────────────
# Posting 계산·Program 생성 결과를 사용자가 「결과 저장」으로 남긴다. 종전에는 화면 상태에만 있어
# 새로고침·탭 종료에 사라졌다(docs/finding-project-review-4roles-2026-10-06.md §2-4 · 소유자 결정).
# 서버는 payload 를 **해석하지 않는다** — 화면이 다시 그릴 입력·결과를 그대로 보관만 한다.

SAVED_RESULT_MAX_BYTES = 64 * 1024     # 한 건 상한. Program 결과 한 벌이 실측 수 KB~20KB 라 넉넉하다.


class SavedResultIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["posting", "program"]
    title: str = Field(min_length=1, max_length=200)
    districtId: str | None = Field(default=None, max_length=200)
    payload: dict[str, object]

    @model_validator(mode="after")
    def payload_fits(self) -> "SavedResultIn":
        import json  # noqa: PLC0415 — 검증에서만 쓴다

        size = len(json.dumps(self.payload, ensure_ascii=False, default=str).encode("utf-8"))
        if size > SAVED_RESULT_MAX_BYTES:
            raise ValueError(f"저장할 결과가 너무 큽니다({size // 1024}KB > {SAVED_RESULT_MAX_BYTES // 1024}KB)")
        return self


class SavedResultOut(SavedResultIn):
    id: str
    createdAt: datetime
