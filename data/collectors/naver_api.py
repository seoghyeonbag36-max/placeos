"""네이버 검색·데이터랩 호출 주소와 인증 헤더 — NAVER API HUB 이관(2026-11-08)을 한곳에서 가른다.

네이버 개발자센터의 검색·데이터랩 API 가 네이버 클라우드 NAVER API HUB 로 옮겨 갔다. 공식 이관 가이드
(guide.ncloud-docs.com/docs/apihub-migration): 개발자센터 Client ID/Secret 으로는 HUB 를 부를 수 없고,
호출 주소(naverapihub.apigw.ntruss.com)와 인증 헤더(X-NCP-APIGW-API-KEY-ID · X-NCP-APIGW-API-KEY)가 바뀐다.
2차 출처: 옛 방식 호출은 2027-06-30 까지 — 그때까지 두 방식을 함께 둔다.

**HUB 경로는 실측으로 확인한 것만 쓴다.** 2026-11-08 사용자의 HUB 앱 키로 1콜씩:
  블로그   /search/v1/blog         200
  카페글   /search/v1/cafearticle  200
  뉴스     /search/v1/news         401 「요청한 API는 이 Application에서 활성화되어 있지 않습니다」 → 옛 방식
  데이터랩 후보 3개(/datalab/v1/search …) 전부 404 → 경로를 모른다 → 옛 방식(naver_datalab.py 는 그대로)
HUB 앱에서 뉴스를 켜거나 데이터랩 경로를 확인하면 _HUB_SEARCH 에 더한다 — 호출부는 바꿀 필요가 없다.

환경변수: NAVER_HUB_CLIENT_ID · NAVER_HUB_CLIENT_SECRET(새) · NAVER_CLIENT_ID · NAVER_CLIENT_SECRET(옛).
네이버 **로그인**(apps/backend/app/services/social_auth.py)은 다른 제품이라 여기와 무관하다.
"""
from __future__ import annotations

import os

HUB_BASE = "https://naverapihub.apigw.ntruss.com"
LEGACY_BASE = "https://openapi.naver.com"

_HUB_SEARCH = {"blog": "/search/v1/blog", "cafearticle": "/search/v1/cafearticle"}
_LEGACY_SEARCH = {"blog": "/v1/search/blog.json", "cafearticle": "/v1/search/cafearticle.json",
                  "news": "/v1/search/news.json", "local": "/v1/search/local.json"}
_LEGACY_DATALAB = "/v1/datalab/search"

_warned: set[str] = set()


def hub_creds() -> tuple[str, str] | None:
    cid, secret = os.getenv("NAVER_HUB_CLIENT_ID", "").strip(), os.getenv("NAVER_HUB_CLIENT_SECRET", "").strip()
    return (cid, secret) if cid and secret else None


def legacy_creds() -> tuple[str, str] | None:
    cid, secret = os.getenv("NAVER_CLIENT_ID", "").strip(), os.getenv("NAVER_CLIENT_SECRET", "").strip()
    return (cid, secret) if cid and secret else None


def hub_headers(creds: tuple[str, str]) -> dict[str, str]:
    return {"X-NCP-APIGW-API-KEY-ID": creds[0], "X-NCP-APIGW-API-KEY": creds[1]}


def legacy_headers(creds: tuple[str, str]) -> dict[str, str]:
    return {"X-Naver-Client-Id": creds[0], "X-Naver-Client-Secret": creds[1]}


def search_request(kind: str) -> tuple[str, dict[str, str], str] | None:
    """검색 API 하나의 (주소, 헤더, 방식). 방식은 "hub" | "legacy". 쓸 키가 없으면 None.

    HUB 키가 있고 그 검색이 HUB 에서 확인된 경로면 HUB, 아니면 옛 키. 질의 인자(query·display·start·sort)는
    두 방식이 같다. HUB 키는 있는데 경로가 미확인이라 옛 방식으로 돌리면 한 번만 알린다.
    """
    hub, legacy = hub_creds(), legacy_creds()
    if hub and kind in _HUB_SEARCH:
        return HUB_BASE + _HUB_SEARCH[kind], hub_headers(hub), "hub"
    if kind not in _LEGACY_SEARCH:
        raise ValueError(f"모르는 네이버 검색: {kind}")
    if hub and kind not in _warned:
        _warned.add(kind)
        print(f"[naver_api] HUB 키가 있지만 '{kind}' 의 HUB 경로를 확인하지 못해 옛 방식으로 부른다")
    if legacy:
        return LEGACY_BASE + _LEGACY_SEARCH[kind], legacy_headers(legacy), "legacy"
    return None


def datalab_request() -> tuple[str, dict[str, str], str] | None:
    """데이터랩 검색어 트렌드 — HUB 경로를 모른다(11-08 후보 3개 404). 옛 키로만 부른다."""
    legacy = legacy_creds()
    if not legacy:
        return None
    return LEGACY_BASE + _LEGACY_DATALAB, {**legacy_headers(legacy), "Content-Type": "application/json"}, "legacy"
