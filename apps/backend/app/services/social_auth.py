"""네이버·카카오 authorization code 검증. 토큰은 교환 후 메모리에서만 사용한다.

공식 계약: developers.naver.com/docs/login/api/api.md ·
developers.kakao.com/docs/ko/kakaologin/rest-api.
state는 10분짜리 서명값이며 URL에 싣지 않는 브라우저 verifier와 결합한다.
쿠키를 제거하는 Firebase Hosting 경로에서도 브라우저에 인증 시도를 귀속시킨다.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.config import settings


class SocialAuthInvalid(Exception):
    pass


class SocialAuthUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    provider: str
    subject: str
    email: str | None


def configuration(provider: str) -> tuple[str, str, str]:
    if provider not in {"naver", "kakao"}:
        return "", "", ""
    return tuple(getattr(settings, f"{provider}_login_{field}")
                 for field in ("client_id", "client_secret", "redirect_uri"))


def enabled(provider: str) -> bool:
    client_id, secret, redirect = configuration(provider)
    if not all((client_id, secret, redirect)):
        return False
    try:
        url = urlsplit(redirect)
        local = not settings.is_prod and url.hostname in {"localhost", "127.0.0.1"}
        return bool(url.netloc and not url.username and not url.password and not url.fragment
                    and (url.scheme == "https" or (local and url.scheme == "http"))
                    and parse_qs(url.query).get("social") == [provider])
    except ValueError:
        return False


def start(provider: str, org_name: str | None) -> dict[str, str]:
    client_id, _, redirect = configuration(provider)
    verifier = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    state = jwt.encode({"purpose": "social_login", "provider": provider,
                        "verifier_hash": hashlib.sha256(verifier.encode()).hexdigest(),
                        "redirect_uri": redirect,
                        "iat": now, "exp": now + timedelta(minutes=10)},
                       settings.jwt_secret, algorithm=settings.jwt_algorithm)
    host = "https://nid.naver.com/oauth2.0/authorize" if provider == "naver" else "https://kauth.kakao.com/oauth/authorize"
    params = {"response_type": "code", "client_id": client_id,
              "redirect_uri": redirect, "state": state}
    return {"authorization_url": host + "?" + urlencode(params), "state": state, "verifier": verifier}


def validate_state(provider: str, state: str, verifier: str) -> None:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
                             options={"require": ["exp", "iat", "purpose", "provider", "verifier_hash", "redirect_uri"]})
        if (payload["purpose"] != "social_login" or payload["provider"] != provider
                or payload["redirect_uri"] != configuration(provider)[2]
                or not hmac.compare_digest(str(payload["verifier_hash"]), hashlib.sha256(verifier.encode()).hexdigest())):
            raise SocialAuthInvalid()
    except (jwt.PyJWTError, TypeError, ValueError) as exc:
        raise SocialAuthInvalid() from exc


def exchange(provider: str, code: str, state: str) -> Identity:
    """서버에서 코드를 토큰으로 교환하고 제공자 프로필의 ID를 확인한다."""
    client_id, secret, redirect = configuration(provider)
    token_url = "https://nid.naver.com/oauth2.0/token" if provider == "naver" else "https://kauth.kakao.com/oauth/token"
    profile_url = "https://openapi.naver.com/v1/nid/me" if provider == "naver" else "https://kapi.kakao.com/v2/user/me"
    data = {"grant_type": "authorization_code", "client_id": client_id,
            "client_secret": secret, "code": code, "redirect_uri": redirect}
    if provider == "naver":
        data["state"] = state
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            token_response = client.post(token_url, data=data)
            if token_response.status_code >= 500:
                raise SocialAuthUnavailable()
            token = token_response.json()
            access = token.get("access_token") if isinstance(token, dict) else None
            if token_response.status_code != 200 or not isinstance(access, str) or not access or token.get("error"):
                raise SocialAuthInvalid()
            profile_response = client.get(profile_url, headers={"Authorization": f"Bearer {access}"})
            if profile_response.status_code >= 500:
                raise SocialAuthUnavailable()
            if profile_response.status_code != 200:
                raise SocialAuthInvalid()
            profile = profile_response.json()
        if not isinstance(profile, dict):
            raise SocialAuthInvalid()
        if provider == "naver":
            if profile.get("resultcode") != "00":
                raise SocialAuthInvalid()
            account = profile.get("response", {})
            subject = account.get("id")
            email = account.get("email")
        else:
            subject = profile.get("id")
            account = profile.get("kakao_account", {})
            email = account.get("email") if account.get("is_email_valid") is True and account.get("is_email_verified") is True else None
        if isinstance(subject, bool) or not isinstance(subject, (str, int)) or not str(subject).strip() or len(str(subject)) > 255:
            raise SocialAuthInvalid()
        try:
            email = str(TypeAdapter(EmailStr).validate_python(email)).lower() if email else None
        except ValidationError:
            email = None
        return Identity(provider, str(subject), email)
    except httpx.RequestError as exc:
        raise SocialAuthUnavailable() from exc
    except (ValueError, TypeError, AttributeError) as exc:
        raise SocialAuthInvalid() from exc
