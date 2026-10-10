"""창업 후보 비용 검토 API."""
from fastapi import APIRouter
from app.schemas.founder import CandidateCosts, CostAssessment
from app.services.founder import assess_costs

router = APIRouter()


@router.post("/costs", response_model=CostAssessment)
def costs(body: CandidateCosts) -> CostAssessment:
    return assess_costs(body)
