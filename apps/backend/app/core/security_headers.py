"""응답 보안 헤더 (2026-10-06) — 모든 응답(API·프론트 정적 파일)에 붙인다.

## 왜 필요한가

2026-10-06 점검에서 운영 응답의 보안 헤더가 Firebase Hosting 이 붙이는 HSTS 하나뿐이었다
(CSP·X-Frame-Options·nosniff·Referrer-Policy·Permissions-Policy 0). 프론트는 JWT(7일)와
관리자 토큰을 sessionStorage 에 두므로, 서드파티 스크립트 오염이나 새 XSS 한 번이면 둘이 함께 샌다.

## 왜 firebase.json 이 아니라 여기인가

`firebase.json` 의 hosting 설정은 CI → Deploy 경로로 반영되지 않는다(수동 `firebase deploy --only hosting`).
여기 두면 main 머지가 곧 반영이고, 테스트로 잠글 수 있다. Firebase Hosting 은 Cloud Run 응답 헤더를 그대로 넘긴다.

## CSP 는 아직 **Report-Only** 다

네이버 지도 SDK 는 스크립트·타일·파노라마를 여러 출처에서 다시 불러오고, 구글 로그인은 iframe·스타일을
쓴다. 출처 목록은 2026-10-06 로컬 실측(로그인 상태로 네 트랙 + 건물 상세 거리뷰 + 로그인 화면을 열어
요청 출처와 위반 보고를 모음)으로 정했다. 강제(`Content-Security-Policy`)로 바꾸기 전에 운영 콘솔에서
`[Report Only]` 위반이 없는지 본다 — 막히면 지도가 통째로 안 뜨는 종류라 한 번에 강제하지 않는다.
나머지 헤더는 바로 강제한다(깨뜨릴 것이 없다: 앱은 iframe 을 쓰지 않고, 위치·카메라를 묻지 않는다).
"""
from __future__ import annotations

# 지시어별 허용 출처. 바꿀 때는 tests/test_security_headers.py 의 기대값도 같이 본다.
_CSP_DIRECTIVES: dict[str, list[str]] = {
    "default-src": ["'self'"],
    # 네이버 SDK 는 oapi 의 maps.js 뒤에 지도 스타일·인증을 JSONP(<script>)로 다시 부른다(실측).
    # 스타일 JSONP 호스트가 **페이지 스킴마다 다르다**: http 에서는 nrbe.map.naver.net, https(운영)에서는
    # nrbe.pstatic.net — 로컬 실측에서는 안 보였고 운영 Report-Only 보고 3건으로 잡았다(2026-10-06).
    "script-src": ["'self'", "https://oapi.map.naver.com", "https://nrbe.pstatic.net", "https://nrbe.map.naver.net",
                   "https://apis.naver.com", "https://accounts.google.com/gsi/client"],
    # 네이버 SDK 와 구글 버튼이 <style> 을 넣는다.
    "style-src": ["'self'", "'unsafe-inline'", "https://accounts.google.com/gsi/style"],
    # 지도 타일·파노라마·아이콘은 출처가 많고 이미지는 실행되지 않는다 — https 전체를 허용한다.
    "img-src": ["'self'", "data:", "blob:", "https:"],
    "font-src": ["'self'", "data:"],
    # kr-col-ext.nelo.navercorp.com = 네이버 SDK 의 오류 수집. 막혀도 지도는 돌지만 보고가 시끄러워진다.
    "connect-src": ["'self'", "https://*.naver.com", "https://*.naver.net", "https://*.pstatic.net",
                    "https://kr-col-ext.nelo.navercorp.com", "https://accounts.google.com/gsi/"],
    "frame-src": ["https://accounts.google.com/gsi/"],
    "worker-src": ["'self'", "blob:"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
}

CSP = "; ".join(f"{name} {' '.join(srcs)}" for name, srcs in _CSP_DIRECTIVES.items())

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Content-Security-Policy-Report-Only": CSP,
}


def apply(headers) -> None:
    """응답 헤더에 보안 헤더를 더한다. 라우트가 이미 정한 값은 덮지 않는다(setdefault)."""
    for name, value in SECURITY_HEADERS.items():
        headers.setdefault(name, value)
