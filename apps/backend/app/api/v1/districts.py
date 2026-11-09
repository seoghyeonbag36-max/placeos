"""상권(commercial district) 엔드포인트 — 요약/상세/감성/입점.

거점별 데이터를 백엔드 단일 소스(app/data + app/services/districts)로 제공한다.
프론트엔드는 이 엔드포인트로 정적 임베드를 대체할 수 있다.
"""
from fastapi import APIRouter, HTTPException, Query

from app.schemas.district import DistrictSummary, Posting, Zone
from app.schemas.floor_vacancy import FloorVacancyList
from app.schemas.renewal import (DistrictReport, HubOutlines, NearbyStores, RentHistory, ResearchLocations,
                                 SiteRanking)
from app.services import districts as svc
from app.services import (district_report, floor_vacancy, hub_outlines, nearby_stores, platform_profile,
                          research_locations, rone_history)

router = APIRouter()


@router.get("", response_model=list[DistrictSummary])
async def list_districts() -> list[dict]:
    """서울 13 Page 거점 요약(감성·공실·리뷰·Tier 구성) — City Dashboard 용."""
    return svc.list_summaries()


@router.get("/outlines", response_model=HubOutlines)
async def get_outlines() -> dict:
    """전 거점 실측 범위 외곽선 + 유형. ⚠ `/{district_id}` 보다 먼저 선언해야 한다."""
    out = hub_outlines.outlines()
    if out is None:
        raise HTTPException(status_code=404, detail="hub outlines not built")
    return out


@router.get("/research-locations", response_model=ResearchLocations)
async def get_research_locations(
    group: str | None = Query(None, pattern="^(gwangju|jeonju)$", description="지도 묶음 — 비우면 광주·전주 전부"),
) -> dict:
    """광주·전주 조사 위치(대장 관측). 서빙 거점이 아니다. ⚠ `/{district_id}` 보다 먼저 선언해야 한다."""
    out = research_locations.research_locations(group)
    if out is None:
        raise HTTPException(status_code=404, detail="research locations not built")
    return out


@router.get("/{district_id}/summary", response_model=DistrictSummary)
async def get_district_summary(district_id: str) -> dict:
    s = svc.get_summary(district_id)
    if s is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return s


@router.get("/{district_id}")
async def get_district(district_id: str) -> dict:
    """거점 전체 원천 데이터(zones/units/events/poi/grid)."""
    d = svc.get_district(district_id)
    if d is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return d


@router.get("/{district_id}/sentiment", response_model=list[Zone])
async def get_sentiment(district_id: str) -> list[dict]:
    """상권 감성 구역(Platform) — **전 필드가 추정치다**.

    점수(s)·표본수(r)·증감(d)·키워드(f) 모두 app/data/seoul_pages.py 의 시드값이며
    실제로 리뷰를 센 적이 없다. 구역 단위 감성을 만들려면 리뷰 원문 수집이 먼저다:
      - 플레이스 리뷰 크롤러 골격(data/crawlers/review_crawler.py)은 수집 0건인 채로
        2026-09-17 에 삭제됐다(Program 대상 재정의 — 영업 중인 가게 리뷰를 쓰지 않는다)
      - 네이버 블로그 코퍼스(17,653건)는 **거점 단위 광고성 스니펫**이라
        324개 구역으로 내릴 수 없고, 감성분석을 돌리면 광고 톤을 재게 된다
    자세한 판단 근거는 docs/placeos-vibe-build-sequence.md 의 5번 항목 참조.
    """
    zones = svc.get_sentiment(district_id)
    if zones is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return zones


@router.get("/{district_id}/platform")
async def get_platform_profile(district_id: str) -> dict:
    """Platform — "이 상권은 어떤 플랫폼인가" + "어느 자리에 어떤 업소가 들어와야 하나".

    정체성(업종 구성·블로그 키워드·검색 트렌드·수요신호)과 자리 제안(실측 공실 유닛 ×
    GNN 최근접 노드 추천)을 한 응답으로 낸다. 둘 다 없는 거점은 404 —
    "이 거점을 모른다"가 아니라 "이 거점에 Platform 산출물이 없다"는 뜻이며,
    `identity: null` 로 오는 경우(자리는 있는데 컨텍스트만 없다)와 구분된다.

    감성은 여기 없다 — 전부 시드라 정체성의 근거로 쓸 수 없다(`/{거점}/sentiment` 참조).
    """
    p = platform_profile.profile(district_id)
    if p is None:
        raise HTTPException(status_code=404,
                            detail=f"no platform profile for district: {district_id}")
    return p


@router.get("/{district_id}/postings", response_model=list[Posting])
async def get_postings(district_id: str) -> list[dict]:
    """공실 유닛 + 3-Tier 비용-효용 시나리오(Posting)."""
    p = svc.get_postings(district_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return p


@router.get("/{district_id}/rent-history", response_model=RentHistory)
async def get_rent_history(district_id: str) -> dict:
    """R-ONE 22분기 임대·공실 시계열. 표본 상권의 통계이고 거점 실측이 아니다."""
    out = rone_history.history(district_id)
    if out is None:
        raise HTTPException(status_code=404, detail=f"no rent history for district: {district_id}")
    return out


@router.get("/{district_id}/site-ranking", response_model=SiteRanking)
async def get_site_ranking(
    district_id: str,
    industry: str | None = Query(None, min_length=1, max_length=40),
) -> dict:
    """빈 자리를 선택 업종 기준으로 — 점수 내림차순(값 없는 자리는 뒤로) + 같은 지번의 층 매물."""
    try:
        out = platform_profile.site_ranking(district_id, industry)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if out is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return out


@router.get("/{district_id}/nearby-stores", response_model=NearbyStores)
async def get_nearby_stores(
    district_id: str,
    lat: float = Query(..., ge=33, le=39, allow_inf_nan=False),
    lng: float = Query(..., ge=124, le=132, allow_inf_nan=False),
    radius: int = Query(100, ge=nearby_stores.MIN_RADIUS_M, le=nearby_stores.MAX_RADIUS_M),
    industry: str | None = Query(None, min_length=1, max_length=40),
    detail_key: str | None = Query(None, min_length=1, max_length=100),
    floor: bool = Query(False, description="층 반영 — 경쟁 점포 자체의 층으로 참고 가중치를 곱한다"),
    building_id: str | None = Query(None, min_length=1, max_length=60),
) -> dict:
    """이 자리 반경 안 점포 — 직선거리. 경쟁 강도는 이 상권 빈 자리들과 비교한 상대 위치다."""
    try:
        out = nearby_stores.nearby(district_id, lat, lng, radius, industry, detail_key,
                                   floor_weighted=floor, building_id=building_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if out is None:
        raise HTTPException(status_code=404, detail=f"no store data for district: {district_id}")
    return out


@router.get("/{district_id}/report", response_model=DistrictReport)
async def get_report(
    district_id: str,
    industry: str | None = Query(None, min_length=1, max_length=40),
    unit_id: str | None = Query(None, min_length=1, max_length=60),
    building_id: str | None = Query(None, min_length=1, max_length=60),
) -> dict:
    """검증 리포트 — 칸마다 status·source·as_of·note·data. 비는 칸도 칸째 나간다."""
    try:
        out = district_report.report(district_id, industry, unit_id, building_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if out is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return out


@router.get("/{district_id}/floor-vacancies", response_model=FloorVacancyList)
async def get_floor_vacancies(
    district_id: str,
    certainty: str | None = Query(None, pattern="^(confirmed|probable)$"),
    floor: int | None = Query(None, ge=-5, le=100),
    min_area: int | None = Query(None, ge=0),
    max_area: int | None = Query(None, ge=0),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> dict:
    """층 단위 공실 매물 목록 — "이 건물 **몇 층**이 비었고 몇 평인가".

    `/postings` 와 **다른 것을 센다.** 저쪽은 통째로 빈 건물 1동 = 유닛 1개이고
    3-Tier 시나리오가 붙는 ROI 표본이다. 여기는 (지번, 층) = 유닛 1개이고
    `partial` 건물이 들어오며 시나리오가 붙지 않는다 — 층으로 쪼갠 표본을 ROI 에
    쓰면 프라임 프리미엄 트립와이어가 부호를 넘는다(docs/feature-posting.md §0-Q·§0-T).

    `certainty` 로 확정만 좁힐 수 있다. 기본은 둘 다 주되 유닛마다 표시되므로,
    화면이 추정을 확정처럼 그리지 않는 것은 호출부 책임이다.

    404 는 "이 거점을 모른다"가 아니라 **"이 거점에 층 단위 산출물이 없다"** 는 뜻이다.
    """
    out = floor_vacancy.listing(district_id, certainty=certainty, floor=floor,
                                min_area=min_area, max_area=max_area,
                                limit=limit, offset=offset)
    if out is None:
        raise HTTPException(
            status_code=404,
            detail=f"no floor-level vacancy inventory for district: {district_id}")
    return out
