"""OpenAI Image API 어댑터. 가짜 이미지 폴백·외부 링크 자동 수집·원문 저장은 하지 않는다.

## 시간 한도 (2026-11-06)
프로덕션 `/api/**` 는 Firebase Hosting 리라이트를 거쳐 Cloud Run 으로 간다(firebase.json).
Hosting 은 Cloud Run 설정과 관계없이 **60초**가 넘는 요청을 504 로 끊는다. 그래서 공급자 호출
전체 한도(`settings.interior_image_timeout_s`, 기본 50초)를 그보다 짧게 둔다 — 넘으면 이쪽이 먼저
504 와 한국어 사유를 돌려준다(전에는 180초를 기다리는 동안 Hosting 이 본문 없는 504 를 냈다).
재시도는 하지 않는다: 한 번에 30~40초라 재시도할 시간이 없고, 성공한 생성이 두 번 과금될 수 있다.

## 오류 대응
공급자 응답은 `ProviderError(status, detail, reason)` 로 바꾼다. `status` 는 화면이 문구를 고르는
상태 코드이고, `reason` 은 로그용 짧은 원인 코드다. ⚠ 공급자 401(키 거부)은 **401 로 내보내지
않는다** — 화면은 401 을 「로그인 만료」로 읽어 사용자의 토큰을 지운다. 서버 설정 문제라 503 이다.
"""
import asyncio
import base64
import binascii
import logging
import time

import httpx

from app.core.config import settings
from app.schemas.interior import InteriorRequest

log = logging.getLogger("placeos.interior")
# 앱에 로깅 설정이 없어(basicConfig 0곳) INFO 가 버려진다 — 성공 소요시간도 Cloud Run 로그(stderr)에 남긴다.
if not log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
    log.propagate = False

NOTE = "AI 생성 참고 이미지 · 실측 도면·시공안 아님. 치수·피난 동선·설비·견적·상권 적합성은 검증하지 않았습니다."
OPENAI_IMAGES = "https://api.openai.com/v1/images/"
# Hosting 60초 한도 안에 응답·전송 여유를 남긴다. 설정값이 이보다 크면 잘라 쓴다.
MAX_TIMEOUT_S = 55.0
_SAFETY_CODES = {"moderation_blocked", "content_policy_violation", "safety_violation"}
_QUOTA_CODES = {"insufficient_quota", "billing_hard_limit_reached", "credit_balance_exhausted"}


class ProviderError(Exception):
    """화면에 보낼 상태 코드·한국어 detail 과, 로그에만 남길 원인 코드."""

    def __init__(self, status: int, detail: str, reason: str, upstream_status: int | None = None,
                 upstream_code: str | None = None, request_id: str | None = None):
        super().__init__(reason)
        self.status = status
        self.detail = detail
        self.reason = reason
        self.upstream_status = upstream_status
        self.upstream_code = upstream_code
        self.request_id = request_id


def prompt_for(req: InteriorRequest) -> str:
    """사용자 조건을 인용한다. 상권·업종만으로 수요나 성과를 지어내지 않는다."""
    return (
        "Create one interior concept visualization, not a measured architectural plan. "
        "Preserve the supplied floor outline, openings and structural elements where visible. "
        "Do not claim exact dimensions, verified code compliance, business performance or local demand. "
        "Do not invent a real street view. Reference links are user notes, not fetched or verified evidence.\n"
        f"User context: district={req.district}; industry={req.industry}; style={req.style}; "
        f"strategy={req.strategy}; user-confirmed area in pyeong={req.area_py}; "
        f"constraints={req.constraints}; reference links={req.links}.\n"
        "Images are labeled by order: " + ", ".join(r.kind for r in req.references)
    )


def decode_reference(data: str, mime: str) -> bytes:
    try:
        raw = base64.b64decode(data, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("참고 이미지 형식이 올바르지 않습니다.") from exc
    valid = ((mime == "image/png" and raw.startswith(b"\x89PNG\r\n\x1a\n"))
             or (mime == "image/jpeg" and raw.startswith(b"\xff\xd8\xff"))
             or (mime == "image/webp" and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"))
    if not valid or len(raw) > 3_000_000:
        raise ValueError("PNG·JPEG·WebP 이미지(각 3MB 이하)만 받습니다.")
    return raw


def reference_files(req: InteriorRequest) -> list:
    """첨부를 공급자 호출 **전에** 검사한다. 실패는 ValueError(→ 422) — 공급자 오류(502)와 섞지 않는다."""
    files = []
    for i, ref in enumerate(req.references):
        raw = decode_reference(ref.data, ref.mime)
        ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[ref.mime]
        files.append(("image[]", (f"{ref.kind}-{i}.{ext}", raw, ref.mime)))
    return files


def timeout_s() -> float:
    return max(5.0, min(float(settings.interior_image_timeout_s), MAX_TIMEOUT_S))


def _error_fields(response: httpx.Response) -> tuple[str | None, str | None, str | None]:
    """OpenAI 오류 본문에서 code·type·param 만 꺼낸다. message 는 사용자 입력을 되풀이할 수 있어 안 쓴다."""
    try:
        err = response.json().get("error") or {}
    except (ValueError, AttributeError):
        return None, None, None
    if not isinstance(err, dict):
        return None, None, None
    pick = lambda k: str(err[k])[:80] if isinstance(err.get(k), (str, int)) else None  # noqa: E731
    return pick("code"), pick("type"), pick("param")


def map_provider_response(response: httpx.Response) -> ProviderError:
    """공급자 HTTP 오류 → 화면 상태 코드 + 한국어 detail."""
    status = response.status_code
    code, etype, param = _error_fields(response)
    marks = {c for c in (code, etype) if c}
    rid = response.headers.get("x-request-id")
    kw = {"upstream_status": status, "upstream_code": code or etype, "request_id": rid}
    if marks & _SAFETY_CODES:
        return ProviderError(422, "이미지 공급자의 안전 정책에 걸려 생성하지 못했습니다. 분위기·제약 문구나 참고 사진을 바꿔 다시 시도하세요.",
                             "provider_safety", **kw)
    if status == 401:
        return ProviderError(503, "서버의 이미지 공급자 키가 거부됐습니다. 운영자가 키 설정을 확인해야 합니다.",
                             "provider_auth", **kw)
    if status == 403:
        return ProviderError(403, "이미지 공급자가 이 모델 사용을 허용하지 않았습니다(조직 인증·권한). 운영자 확인이 필요합니다.",
                             "provider_forbidden", **kw)
    if status == 404:
        return ProviderError(503, "서버에 설정된 이미지 모델을 공급자가 찾지 못했습니다. 운영자 확인이 필요합니다.",
                             "provider_model_not_found", **kw)
    if status == 413:
        return ProviderError(413, "첨부 이미지가 공급자 용량 한도를 넘었습니다. 첨부를 줄이거나 작은 이미지로 다시 시도하세요.",
                             "provider_payload_too_large", **kw)
    if status == 429:
        if marks & _QUOTA_CODES:
            return ProviderError(503, "이미지 공급자 사용 한도(크레딧)가 소진되어 지금은 생성할 수 없습니다. 운영자 확인이 필요합니다.",
                                 "provider_quota", **kw)
        return ProviderError(429, "이미지 공급자 요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요.", "provider_rate_limit", **kw)
    if status == 400:
        if param and param.startswith("image"):
            return ProviderError(422, "공급자가 첨부 이미지를 받지 못했습니다. 다른 PNG·JPEG·WebP 이미지로 다시 시도하세요.",
                                 "provider_bad_image", **kw)
        return ProviderError(502, "이미지 공급자가 요청을 거부했습니다. 잠시 뒤 다시 시도하고, 반복되면 운영자에게 알려 주세요.",
                             "provider_bad_request", **kw)
    if status >= 500:
        return ProviderError(503 if status == 503 else 502,
                             "이미지 공급자에 일시적인 장애가 있습니다. 잠시 뒤 다시 시도하세요.", "provider_unavailable", **kw)
    return ProviderError(502, "이미지 공급자가 예상하지 못한 응답을 보냈습니다. 잠시 뒤 다시 시도하세요.",
                         "provider_unexpected_status", **kw)


def _log(outcome: str, started: float, n_refs: int, err: ProviderError | None = None) -> None:
    """원인 코드·소요시간·첨부 개수만 남긴다. 키·프롬프트·사용자 입력·이미지 내용은 남기지 않는다."""
    elapsed = int((time.perf_counter() - started) * 1000)
    if err is None:
        log.info("interior_preview outcome=%s elapsed_ms=%d refs=%d model=%s",
                 outcome, elapsed, n_refs, settings.interior_image_model)
        return
    log.warning("interior_preview outcome=%s reason=%s status=%d upstream_status=%s upstream_code=%s "
                "request_id=%s elapsed_ms=%d refs=%d model=%s timeout_s=%.0f",
                outcome, err.reason, err.status, err.upstream_status, err.upstream_code,
                err.request_id, elapsed, n_refs, settings.interior_image_model, timeout_s())


async def _call(url: str, body: dict) -> httpx.Response:
    limit = timeout_s()
    timeout = httpx.Timeout(limit, connect=min(10.0, limit))
    async with httpx.AsyncClient(timeout=timeout) as client:
        # httpx 의 timeout 은 단계별(연결·읽기 간격)이라 전체 소요를 묶지 못한다 — 전체 상한을 따로 건다.
        return await asyncio.wait_for(
            client.post(url, headers={"Authorization": f"Bearer {settings.openai_api_key}"}, **body),
            timeout=limit)


async def generate(req: InteriorRequest, files: list | None = None) -> dict:
    """한 장 생성. 실패는 ProviderError 로 던진다(첨부 형식 오류는 ValueError)."""
    if files is None:
        files = reference_files(req)
    params = {"model": settings.interior_image_model, "prompt": prompt_for(req),
              "size": "1024x1024", "quality": "low", "output_format": "png"}
    url = OPENAI_IMAGES + ("edits" if files else "generations")
    body = {"data": params, "files": files} if files else {"json": params}
    started = time.perf_counter()
    try:
        try:
            response = await _call(url, body)
        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            raise ProviderError(504, f"이미지 생성이 {timeout_s():.0f}초 안에 끝나지 않았습니다. 첨부를 줄이거나 잠시 뒤 다시 시도하세요.",
                                "provider_timeout") from exc
        except httpx.TransportError as exc:
            raise ProviderError(502, "이미지 공급자에 연결하지 못했습니다. 잠시 뒤 다시 시도하세요.",
                                f"provider_unreachable:{type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise map_provider_response(response)
        try:
            encoded = response.json()["data"][0]["b64_json"]
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, KeyError, IndexError, TypeError, binascii.Error) as exc:
            raise ProviderError(502, "이미지 공급자 응답 형식이 올바르지 않습니다.", "provider_bad_payload",
                                upstream_status=response.status_code) from exc
        if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) > 12_000_000:
            raise ProviderError(502, "이미지 공급자 응답 형식이 올바르지 않습니다.", "provider_bad_payload",
                                upstream_status=response.status_code)
    except ProviderError as err:
        _log("error", started, len(files), err)
        raise
    _log("ok", started, len(files))
    return {"source": "ai_generated", "image_data_url": f"data:image/png;base64,{encoded}",
            "model": settings.interior_image_model, "note": NOTE}
