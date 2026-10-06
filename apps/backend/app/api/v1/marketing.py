"""마케팅 엔드포인트 — 검증 프로그램 생성 + 자리·행사·상권 조회(Program).

⚠ 라우트 등록 순서 주의: 아래 `/{district_id}` 가 아무 문자열이나 삼키므로,
정적 경로(`/generate`·`/sites`·`/events`)는 **반드시 그보다 먼저** 선언한다.

2026-09-17 에 `/places`·`/reviews`(영업 중인 가게 상호 검색과 블로그 스니펫)와
`/onboarding/generate`(점주 제공 원문의 상용 동의 경계)가 **삭제됐다**. 대상이 아직
그 자리에서 장사한 적 없는 창업자로 바뀌면서 그 입력 자체가 사라졌다
→ docs/feature-program.md §0-V.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import settings
from app.core.security import Principal, get_optional_principal
from app.schemas.district import DistrictEvents, Marketing
from app.schemas.marketing import ProgramBrief, ProgramPlan, VacantSiteList
from app.services import marketing as mkt
from app.services import program_site, rate_limit

router = APIRouter()


@router.post("/generate", response_model=ProgramPlan)
async def generate_program(
    brief: ProgramBrief,
    principal: Principal | None = Depends(get_optional_principal),
) -> dict:
    """검증 프로그램 생성 — 모객(online) · 자리·연계(offline) · **검증 지표(signals)**.

    입력(ProgramBrief)은 팝업스토어·가오픈·MVP 로 아이템을 확인하려는 창업자의 브리프다.

    **LLM 은 로그인한 호출(JWT·조직 API 키)에만 열린다.** 익명은 규칙 기반 스텁으로
    응답한다 — 같은 200 이고 `source` 만 `"rule-stub"` 이다. 이 호출은 1회가 곧 LLM 1회이고
    캐시가 없는데 공개 데모는 익명을 통과시키므로, 막지 않으면 반복 호출이 그대로 크레딧이
    된다. 잘못된 자격증명은 라우터 공통 의존성에서 이미 401 이다(조용히 익명으로 강등하지 않는다).
    LLM 키 미설정·호출 실패·HA 검증 위반 폐기도 같은 스텁이다 (source 필드로 구분).

    **로그인해도 한도가 있다(2026-10-06).** 가입이 무료라 "로그인한 호출에만"만으로는 계정을
    찍어 내면 다시 열린다. 조직당·인스턴스당 24시간 횟수(services/rate_limit.try_llm)를 넘으면
    같은 200 에 스텁을 주고 `stub_reason: "llm_quota"` 로 이유를 밝힌다 — 화면이 "실패"가
    아니라 "한도"라고 말할 수 있게. 키가 없으면 어차피 LLM 을 안 부르므로 세지 않는다.
    """
    allow_llm = principal is not None
    stub_reason: str | None = None
    if allow_llm and settings.llm_api_key and not rate_limit.try_llm(principal.org.id):
        allow_llm, stub_reason = False, "llm_quota"
    plan = mkt.generate_program(brief.model_dump(), allow_llm=allow_llm)
    return {**plan, "stub_reason": stub_reason} if stub_reason else plan


@router.get("/sites", response_model=VacantSiteList)
async def list_vacant_sites(
    district_id: str = Query(..., min_length=1, max_length=40, description="거점 id"),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """거점의 공실 유닛 목록 — Program 입력 계약 ①층(자리)의 후보다.

    팝업·가오픈은 **아직 아무도 없는 자리**를 짧게 빌려 도는 것이라, 이 목록이 검증의
    무대 후보가 된다.

    Gold 미적재면 `site_source == "unavailable"` 로 빈 목록을 준다 — 404 가 아니다.
    "이 거점을 모른다"와 "이 거점에 공실 산출물이 없다"는 다른 상태다.
    """
    sites = program_site.units(district_id)[:limit]
    return {"district_id": district_id, "sites": sites,
            **program_site.provenance(district_id)}


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
    **LLM 은 로그인한 호출에만 열린다** — 익명은 시드로 응답한다(`/generate` 와 같은 문, 같은
    이유). LLM 키 미설정·Gold 미적재·호출 실패도 시드로 폴백한다(source 필드로 구분).
    행사(events)는 서울열린데이터광장 문화행사 실데이터 — events_source 로 출처를 밝힌다.
    행사는 LLM 과 무관해서 익명에게도 그대로 나간다.
    """
    m = mkt.get_district_marketing(district_id, allow_llm=principal is not None)
    if m is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return m
