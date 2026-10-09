"""계정층 API — 가입(조직 생성)·로그인·본인 확인·탈퇴.

docs/decision-infra-layer-2026-08-25.md §6 결정 A 의 첫 배선. 분석 API(buildings·
districts·ai·...)는 이 라우터와 무관하게 그대로 공개로 남는다 — 여기서 하는 건
파일럿 온보딩에 필요한 최소 계정 기능이지, 기존 서빙을 인증 뒤로 숨기는 게 아니다.

2026-10-05: 구글 로그인(`/google`)과 탈퇴(`DELETE /me`)를 더했다. 비밀번호 재설정 흐름은
**만들지 않는다** — 직접 만들면 취약점이 생기기 쉬운 자리라, 잊은 사람은 같은 이메일의
구글 계정으로 들어오게 한다(docs/decision-lightweight-first-2026-10-05.md §1).
"""
from __future__ import annotations
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user, issue_access_token, _bearer
from app.schemas.auth import (
    ApiKeyCreatedResponse, ApiKeyCreateRequest, ApiKeyOut, AuthProviders, GoogleLoginRequest,
    LoginRequest, MeResponse, OrgOut, SignupRequest, TokenResponse, BusinessWorkspaceData,
    SavedResultIn, SavedResultOut,
    SocialStartRequest, SocialStartResponse, SocialLoginRequest,
)
from app.services import auth_service, business_workspace, google_auth, rate_limit, social_auth

router = APIRouter()


def _require_admin(current: CurrentUser) -> None:
    """키 발급·폐기는 관리자만 — 일반 멤버가 조직 전체 접근 권한을 찍어낼 수 없게 한다."""
    if current.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "이 작업은 조직 관리자만 할 수 있습니다")


def _too_many(retry_after: int, detail: str) -> HTTPException:
    """429 — `Retry-After` 를 함께 싣는다(services/rate_limit)."""
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail,
                         headers={"Retry-After": str(retry_after)})


_SIGNUP_LIMITED = "지금은 새 가입이 몰려 잠시 막혀 있습니다. 잠시 뒤 다시 시도해 주세요"


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user, org = auth_service.signup(db, req.org_name, req.email, req.password)
    except auth_service.EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 가입된 이메일입니다")
    except auth_service.SignupRateLimited as e:
        raise _too_many(e.retry_after, _SIGNUP_LIMITED)
    return TokenResponse(access_token=issue_access_token(user, org))


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """비밀번호 로그인. 같은 이메일로 15분에 `login_failures_per_email` 번 틀리면 429 (2026-10-06).

    키가 IP 가 아니라 이메일인 이유는 services/rate_limit 머리말. 막히는 것은 그 이메일의
    **비밀번호** 로그인뿐이다 — 진짜 주인은 구글로 들어올 수 있다.
    """
    retry = rate_limit.login_retry_after(req.email)
    if retry:
        raise _too_many(retry, "로그인 시도가 너무 많습니다. 잠시 뒤 다시 시도해 주세요")
    try:
        token, _user, _org, _role = auth_service.login(db, req.email, req.password)
    except auth_service.InvalidCredentials:
        rate_limit.record_login_failure(req.email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다")
    rate_limit.clear_login_failures(req.email)
    return TokenResponse(access_token=token)


@router.get("/providers", response_model=AuthProviders)
def providers(response: Response) -> AuthProviders:
    """화면이 어떤 로그인 수단을 그릴지. 설정이 비어 있으면 구글 버튼을 그리지 않는다."""
    response.headers["Cache-Control"] = "no-store"
    return AuthProviders(google_client_id=settings.google_client_id or None,
                         naver_enabled=social_auth.enabled("naver"), kakao_enabled=social_auth.enabled("kakao"))


@router.post("/social/{provider}/start", response_model=SocialStartResponse)
def social_start(provider: Literal["naver", "kakao"], req: SocialStartRequest,
                 response: Response) -> SocialStartResponse:
    if not social_auth.enabled(provider):
        raise HTTPException(404, "이 로그인 수단이 설정되지 않았습니다")
    response.headers["Cache-Control"] = "no-store"
    return SocialStartResponse(**social_auth.start(provider, req.org_name))


@router.post("/social/{provider}/callback", response_model=TokenResponse)
def social_callback(provider: Literal["naver", "kakao"], req: SocialLoginRequest,
                    response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    if not social_auth.enabled(provider):
        raise HTTPException(404, "이 로그인 수단이 설정되지 않았습니다")
    response.headers["Cache-Control"] = "no-store"
    try:
        social_auth.validate_state(provider, req.state, req.verifier)
        identity = social_auth.exchange(provider, req.code, req.state)
    except social_auth.SocialAuthInvalid:
        raise HTTPException(401, "로그인 요청을 확인하지 못했습니다. 로그인 버튼부터 다시 시작해 주세요")
    except social_auth.SocialAuthUnavailable:
        raise HTTPException(503, "인증 서버에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요")
    try:
        token, created = auth_service.login_with_social(db, identity.provider, identity.subject, identity.email, req.org_name)
    except auth_service.SocialEmailRequired:
        raise HTTPException(422, "첫 가입에는 이메일 제공 동의가 필요합니다. 계정의 이메일을 확인한 뒤 다시 시도해 주세요")
    except auth_service.SocialSchemaUnavailable:
        raise HTTPException(503, "로그인 저장소 준비가 완료되지 않았습니다. 운영자가 DB 마이그레이션을 적용해야 합니다")
    except auth_service.EmailAlreadyRegistered:
        raise HTTPException(409, "같은 이메일의 계정이 있습니다. 기존 가입 수단으로 로그인해 주세요. 계정을 자동 연결하지 않습니다")
    except auth_service.InvalidCredentials:
        raise HTTPException(401, "로그인을 확인하지 못했습니다")
    except auth_service.SignupRateLimited as exc:
        raise _too_many(exc.retry_after, _SIGNUP_LIMITED)
    if created:
        response.status_code = 201
    return TokenResponse(access_token=token)


@router.post("/google", response_model=TokenResponse)
def google_login(req: GoogleLoginRequest, response: Response,
                 db: Session = Depends(get_db)) -> TokenResponse:
    """구글 ID 토큰으로 로그인 — 처음이면 201(가입), 아니면 200."""
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "구글 로그인이 설정되지 않았습니다")
    try:
        email = google_auth.verify_id_token(req.credential, settings.google_client_id)
    except google_auth.GoogleKeysUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "구글 인증 서버에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요")
    except google_auth.GoogleTokenInvalid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "구글 로그인을 확인하지 못했습니다")
    try:
        token, created = auth_service.login_with_google(db, email, req.org_name)
    except auth_service.InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "구글 로그인을 확인하지 못했습니다")
    except auth_service.SignupRateLimited as e:
        raise _too_many(e.retry_after, _SIGNUP_LIMITED)
    if created:
        response.status_code = status.HTTP_201_CREATED
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(current: CurrentUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        user_id=current.user.id,
        email=current.user.email,
        org=OrgOut(id=current.org.id, name=current.org.name),
        role=current.role,
    )


@router.delete("/me")
def delete_me(current: CurrentUser = Depends(get_current_user),
              db: Session = Depends(get_db)) -> dict[str, bool]:
    """회원 탈퇴 — 내 정보와 혼자 쓰던 조직을 바로 지운다(auth_service.delete_account)."""
    auth_service.delete_account(db, current.user)
    return {"ok": True}


# ── API 키 ─────────────────────────────────────────────────────────────────────


@router.post("/api-keys", response_model=ApiKeyCreatedResponse,
             status_code=status.HTTP_201_CREATED)
def create_api_key(req: ApiKeyCreateRequest,
                   current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> ApiKeyCreatedResponse:
    """조직 API 키 발급. **원문은 이 응답에만 실린다** — 다시 볼 수 없다."""
    _require_admin(current)
    rec, raw = auth_service.issue_api_key(
        db, org_id=current.org.id, user_id=current.user.id, name=req.name)
    return ApiKeyCreatedResponse(
        id=rec.id, name=rec.name, created_at=rec.created_at,
        revoked_at=rec.revoked_at, key=raw)


@router.get("/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(current: CurrentUser = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> list[ApiKeyOut]:
    """내 조직 키 목록(폐기분 포함 — 언제까지 유효했는지가 감사 정보다)."""
    return [ApiKeyOut.model_validate(k)
            for k in auth_service.list_api_keys(db, org_id=current.org.id)]


@router.delete("/api-keys/{key_id}", response_model=ApiKeyOut)
def revoke_api_key(key_id: str,
                   current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> ApiKeyOut:
    _require_admin(current)
    try:
        rec = auth_service.revoke_api_key(
            db, org_id=current.org.id, user_id=current.user.id, key_id=key_id)
    except auth_service.ApiKeyNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "키를 찾을 수 없습니다")
    return ApiKeyOut.model_validate(rec)


@router.get("/workspace", response_model=BusinessWorkspaceData)
def get_workspace(current: CurrentUser = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> BusinessWorkspaceData:
    return business_workspace.load(db, current.user.id)


@router.post("/workspace", response_model=BusinessWorkspaceData)
def save_workspace(req: BusinessWorkspaceData,
                   current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> BusinessWorkspaceData:
    return business_workspace.save(db, current.user.id, req)


# ── 저장한 결과 (2026-10-06) ───────────────────────────────────────────────────
# Posting 계산·Program 생성 결과를 사용자가 고른 것만 남긴다. **본인 것**이라 JWT 사용자만 쓴다 —
# 조직 API 키(사람이 없는 연동)로는 읽지도 쓰지도 못한다. 보관 상한·저장 위치는 services/business_workspace.


@router.get("/results", response_model=list[SavedResultOut])
def list_results(current: CurrentUser = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> list[SavedResultOut]:
    return business_workspace.list_results(db, current.user.id)


@router.post("/results", response_model=SavedResultOut, status_code=status.HTTP_201_CREATED)
def save_result(req: SavedResultIn,
                current: CurrentUser = Depends(get_current_user),
                db: Session = Depends(get_db)) -> SavedResultOut:
    return business_workspace.add_result(db, current.user.id, req)


@router.delete("/results/{result_id}")
def delete_result(result_id: str,
                  current: CurrentUser = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> dict[str, bool]:
    try:
        business_workspace.delete_result(db, current.user.id, result_id)
    except business_workspace.SavedResultNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "저장한 결과를 찾을 수 없습니다")
    return {"ok": True}


@router.post("/logout")
def logout(current: CurrentUser = Depends(get_current_user),
           creds: HTTPAuthorizationCredentials = Depends(_bearer),
           db: Session = Depends(get_db)) -> dict[str, bool]:
    business_workspace.logout(db, creds.credentials)
    return {"ok": True}
