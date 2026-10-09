"""AI 추론 엔드포인트 — LSTM 공실 예측 / GNN 업종 추천 / 매출 시뮬레이션."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.posting import SimulateRequest, SimulateResult
from app.services import business_fit as fit_svc
from app.services import industry_recommend as industry_svc
from app.services import posting as posting_svc
from app.services import industry_detail as detail_svc
from app.services import vacancy_forecast as vacancy_svc

router = APIRouter()


class VacancyRequest(BaseModel):
    district_id: str
    horizon_months: int = 1


class IndustryRequest(BaseModel):
    """업종 추천 요청 — 거점(+좌표)이 기본 키.

    building_id 는 초기 스텁의 계약이라 남겨 뒀다(호출부가 아직 없어 깨질 소비자는 없다).
    GNN 그래프의 노드는 카카오 점포 자리라 건물 대장 키와 join 되지 않는다 — 건물로
    물으려면 좌표를 함께 준다.
    """
    district_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    building_id: str | None = None


@router.post("/predict-vacancy")
async def predict_vacancy(req: VacancyRequest) -> dict[str, object]:
    """LSTM 공실 예측 — gold/platform_vacancy_forecast.json 서빙.

    성능 숫자를 여기 적지 않는다 — 적어 둔 값은 재학습마다 낡는다(09-28 에 07-25 값이
    남아 있었다). 응답의 `metrics`(산출물 그대로)와 `skill`(베이스라인 대비 판정:
    축마다 두 무정보 규칙 중 강한 쪽 — 어느 쪽이었는지는 `baseline_label`,
    `scripts/kpi_baseline.py` 와 같은 코드)을 읽을 것. `metrics` 에서는 종전 기준(상수·
    지속성)에 댄 실력 값(`direction_skill_pp`·`mae_skill` 과 그 개명본)을 **뺀다** —
    판정 값으로 오인되기 때문이다(`vacancy_forecast._LEGACY_SKILL_KEYS`).

    horizon_months(1~12)는 분기로 환산(올림, 최대 4분기)해 재귀 예측 horizon 을 고른다.
    forecast json 부재 시(신규 클론 등) 스텁 응답으로 폴백, 미지원 거점은 404.
    """
    if not vacancy_svc.is_available():
        return {"district_id": req.district_id, "predicted_vacancy_rate": None, "model": "lstm-stub"}
    quarters = max(1, min(-(-req.horizon_months // 3), 4))  # ceil(months/3), 1~4 클램프
    out = vacancy_svc.get_forecast(req.district_id, quarters=quarters)
    if out is None:
        raise HTTPException(status_code=404, detail=f"no forecast for district: {req.district_id}")
    return out


@router.get("/forecast-skill")
async def get_forecast_skill() -> dict[str, object]:
    """LSTM 공실 예측의 베이스라인 대비 판정만 — 거점 보드처럼 예측 본문 없이
    판정 문구만 필요한 화면용. 산출물이 없으면 `skill: null`(화면은 문구를 숨긴다)."""
    return {"skill": vacancy_svc.skill_summary()}


@router.post("/recommend-industry")
async def recommend_industry(req: IndustryRequest) -> dict[str, object]:
    """GNN 업종 추천 — gold/platform_industry_recommend.json 서빙.

    좌표를 주면 최근접 그래프 노드의 Top-3, 없으면 거점 단위 평균 Top-3.
    추천 json 부재 시(신규 클론·미학습) 스텁 응답으로 폴백, 미지원 거점은 404.
    """
    if not req.district_id or not industry_svc.is_available():
        return {"district_id": req.district_id, "building_id": req.building_id,
                "recommendations": [], "model": "gnn-stub"}
    out = industry_svc.recommend(req.district_id, req.lat, req.lon)
    if out is None:
        raise HTTPException(
            status_code=404,
            detail=f"no recommendation for district/좌표: {req.district_id}")
    return {**out, "building_id": req.building_id}


@router.get("/industries")
async def list_industries() -> dict[str, object]:
    """「내 사업」이 고르는 업종 12종(화면설계서 3판 주요 고객 절). 순서가 화면 칩 순서다."""
    return {"industries": fit_svc.industries()}


@router.get("/industry-fit")
async def industry_fit_by_district(industry: str) -> dict[str, object]:
    """내 업종으로 서빙 상권 전체를 견준다 — 창업자·상권 옮기기 사업자용.

    모델 라벨이 없거나 서빙 어휘(산출물이 정한다)에 없는 업종은 `model_covered=False` 이고
    순위(fit_rank)가 전부 None 이다. 사유는 `fit_unavailable_reason`.
    """
    out = fit_svc.fit_by_district(industry)
    if out is None:
        raise HTTPException(status_code=404, detail=f"unknown industry: {industry}")
    return out


@router.get("/industry-details")
async def industry_details() -> dict[str, object]:
    """세부 업종 선택과 운영 입력 계약. 추천 가능 여부와 분리한다."""
    return {"details": detail_svc.options()}


@router.get("/industry-competition")
async def industry_competition(district_id: str, detail_key: str) -> dict:
    """수집 범위·기준일·누락을 동반한 세부 업종 경쟁점 관측."""
    if district_id not in {r["id"] for r in fit_svc._served()}:
        raise HTTPException(status_code=404, detail="서빙 대상 상권이 아닙니다")
    try:
        return detail_svc.competition(district_id, detail_key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/district-industries/{district_id}")
async def district_industries(district_id: str) -> dict[str, object]:
    """한 상권 안에서 업종 12종을 견준다 — 업종 바꾸기 사업자용."""
    out = fit_svc.industries_in_district(district_id)
    if out is None:
        raise HTTPException(status_code=404, detail=f"no industry data for district: {district_id}")
    return out


@router.post("/simulate-revenue", response_model=SimulateResult)
async def simulate_revenue(req: SimulateRequest) -> dict:
    """입점 시뮬레이션(Posting) — 외부 AI 창업 코파일럿 어댑터 경유.

    코파일럿(settings.posting_copilot_url) 미설정 시 내부 3-Tier 폴백으로 응답한다.
    """
    try:
        result = posting_svc.simulate(req.district_id, req.unit_id,
                                      req.industry_type, req.strategy, req.prem,
                                      req.industry_detail_key, req.operating_inputs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {req.district_id}")
    return result
