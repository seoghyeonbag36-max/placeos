"""마케팅 엔드포인트 — 상권 행사 · 상권 단위 마케팅(Program · Page).

⚠ 라우트 등록 순서 주의: 아래 `/{district_id}` 가 아무 문자열이나 삼키므로,
정적 경로(`/events`)는 **반드시 그보다 먼저** 선언한다.

2026-11-22 사용자 정의 「Program = 개업 후 계약을 맺은 공실에 대한 네트워킹·오프라인 마케팅」으로 `POST /generate`(검증 프로그램 생성)와
`GET /sites`(공실 유닛 목록)를 **지웠다** — 부르는 화면이 없었다 → docs/decision-program-post-opening-2026-11-22.md.
(2026-09-17 에는 `/places`·`/reviews`·`/onboarding/generate` 가 삭제됐다 → docs/feature-program.md §0-V.)
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import Principal, get_optional_principal
from app.schemas.district import DistrictEvents, Marketing
from app.services import marketing as mkt

router = APIRouter()


@router.get("/events", response_model=DistrictEvents)
async def list_district_events(
    district_id: str = Query(..., min_length=1, max_length=40, description="거점 id"),
) -> dict:
    """상권 행사만 — 온라인 콘텐츠 LLM 생성을 **돌리지 않는다**.

    Program 지도가 오프라인 홍보 장소를 찍는 데 쓴다. `/{district_id}` 는 행사와 함께
    온라인 콘텐츠를 LLM 으로 만들어 오므로, 지도를 볼 때마다 부르면 크레딧을 쓴다.
    ⚠ `/{district_id}` 보다 먼저 선언해야 한다(모듈 머리말).
    """
    out = mkt.get_district_events(district_id)
    if out is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return out


@router.get("/{district_id}", response_model=Marketing)
async def get_marketing(
    district_id: str,
    principal: Principal | None = Depends(get_optional_principal),
) -> dict:
    """상권 단위 마케팅(행사 + 온라인 콘텐츠).

    온라인 콘텐츠는 Platform 수집 정보(gold/program_content_context) 기반 생성이며
    **LLM 은 로그인한 호출에만 열린다** — 익명은 시드로 응답한다(공개 데모가 익명을 통과시키므로
    막지 않으면 반복 호출이 그대로 크레딧이 된다). LLM 키 미설정·Gold 미적재·호출 실패도 시드로 폴백한다(source 필드로 구분).
    행사(events)는 서울열린데이터광장 문화행사 실데이터 — events_source 로 출처를 밝힌다.
    행사는 LLM 과 무관해서 익명에게도 그대로 나간다.
    """
    m = mkt.get_district_marketing(district_id, allow_llm=principal is not None)
    if m is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return m
