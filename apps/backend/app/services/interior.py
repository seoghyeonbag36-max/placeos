"""OpenAI Image API 어댑터. 가짜 이미지 폴백·외부 링크 자동 수집·원문 저장은 하지 않는다."""
import base64
import binascii

import httpx

from app.core.config import settings
from app.schemas.interior import InteriorRequest

NOTE = "AI 생성 참고 이미지 · 실측 도면·시공안 아님. 치수·피난 동선·설비·견적·상권 적합성은 검증하지 않았습니다."


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


async def generate(req: InteriorRequest) -> dict:
    files = []
    for i, ref in enumerate(req.references):
        raw = decode_reference(ref.data, ref.mime)
        ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[ref.mime]
        files.append(("image[]", (f"{ref.kind}-{i}.{ext}", raw, ref.mime)))
    params = {"model": settings.interior_image_model, "prompt": prompt_for(req),
              "size": "1024x1024", "quality": "low", "output_format": "png"}
    async with httpx.AsyncClient(timeout=180) as client:
        url = "https://api.openai.com/v1/images/" + ("edits" if files else "generations")
        body = {"data": params, "files": files} if files else {"json": params}
        response = await client.post(url, headers={"Authorization": f"Bearer {settings.openai_api_key}"}, **body)
        response.raise_for_status()
        encoded = response.json()["data"][0]["b64_json"]
        raw = base64.b64decode(encoded, validate=True)
        if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) > 12_000_000:
            raise ValueError("이미지 공급자 응답 형식이 올바르지 않습니다.")
    return {"source": "ai_generated", "image_data_url": f"data:image/png;base64,{encoded}",
            "model": settings.interior_image_model, "note": NOTE}
