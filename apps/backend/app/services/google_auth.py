"""구글 로그인 — ID 토큰 검증 (2026-10-05).

## 왜 구글인가

비밀번호 해시·세션·재설정 흐름을 직접 만들면 취약점이 생기기 쉽다
(docs/decision-lightweight-first-2026-10-05.md §1). 구글 ID 토큰 흐름에서는 **비밀번호를
우리가 받지 않는다** — 브라우저가 구글에서 받은 서명된 토큰(JWT)을 넘기면, 서버는 구글
공개키로 서명·대상(aud)·발급자(iss)·만료만 확인한다. 클라이언트 비밀(secret)도 없다.

## 받는 것은 검증된 이메일 하나

토큰에는 이름·사진도 실려 오지만 **꺼내지 않는다**(수집 최소화). `email_verified` 가 참이
아닌 토큰은 거절한다 — 구글이 소유를 확인하지 않은 주소로 계정을 열면 남의 이메일을
선점할 수 있다.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import jwt

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
# 구글 문서가 두 표기를 모두 쓴다. PyJWT 2.9 는 issuer 목록을 **list** 로만 받는다(tuple 은 문자열 비교로 떨어진다).
GOOGLE_ISSUERS = ["accounts.google.com", "https://accounts.google.com"]
# 서버와 구글의 시계 차이 허용(초). 토큰 수명이 1시간이라 1분은 넉넉하다.
LEEWAY_S = 60


class GoogleTokenInvalid(Exception):
    """서명·대상·발급자·만료·이메일 확인 중 하나라도 어긋났다 → 401."""


class GoogleKeysUnavailable(Exception):
    """구글 공개키를 받지 못했다(네트워크) → 503. 토큰 잘못이 아니므로 401 과 가른다."""


_jwks_client: jwt.PyJWKClient | None = None


def _signing_key(credential: str) -> Any:
    """토큰 머리의 kid 에 맞는 구글 공개키. 키 묶음은 한 시간 캐시한다(구글이 하루 단위로 돌린다)."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(GOOGLE_JWKS_URL, cache_jwk_set=True, lifespan=3600, timeout=5)
    try:
        return _jwks_client.get_signing_key_from_jwt(credential).key
    except jwt.PyJWKClientConnectionError as e:
        raise GoogleKeysUnavailable(str(e)) from e
    except (jwt.PyJWKClientError, jwt.PyJWTError) as e:
        raise GoogleTokenInvalid(str(e)) from e


def verify_id_token(credential: str, client_id: str,
                    key_for: Callable[[str], Any] | None = None) -> str:
    """구글 ID 토큰 → 구글이 확인한 이메일(소문자). 하나라도 어긋나면 `GoogleTokenInvalid`.

    `key_for` 는 테스트가 구글 공개키 대신 로컬 키를 꽂는 자리다. 기본값을 시그니처에 묶지 않고
    호출 때 모듈 속성을 읽는 이유: 엔드포인트 테스트가 `_signing_key` 를 monkeypatch 할 수 있어야 한다.
    """
    if not client_id:
        raise GoogleTokenInvalid("구글 로그인이 설정되지 않았다(GOOGLE_CLIENT_ID)")
    key = (key_for or _signing_key)(credential)
    try:
        claims = jwt.decode(
            credential, key, algorithms=["RS256"], audience=client_id, issuer=GOOGLE_ISSUERS,
            leeway=LEEWAY_S, options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as e:
        raise GoogleTokenInvalid(str(e)) from e
    # 구글은 불리언으로 주지만 옛 토큰은 문자열 "true" 였다.
    if claims.get("email_verified") not in (True, "true"):
        raise GoogleTokenInvalid("구글이 이메일 소유를 확인하지 않았다")
    email = claims.get("email")
    if not isinstance(email, str) or "@" not in email:
        raise GoogleTokenInvalid("토큰에 이메일이 없다")
    return email.strip().lower()
