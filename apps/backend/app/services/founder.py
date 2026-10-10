"""직접 확인한 계약 조건만 합산한다. 시세·매출 추정은 섞지 않는다."""
from app.schemas.founder import CandidateCosts, CostAssessment

INITIAL = ("deposit", "premium", "fitout", "equipment")
MONTHLY = ("rent", "maintenance", "other_monthly")


def assess_costs(costs: CandidateCosts) -> CostAssessment:
    """일부 합계는 명시하되 미확인 항목이 있으면 총 필요자금을 판정하지 않는다."""
    missing = [key for key in (*INITIAL, *MONTHLY) if getattr(costs, key) is None]
    initial = sum(getattr(costs, key) or 0 for key in INITIAL)
    monthly = sum(getattr(costs, key) or 0 for key in MONTHLY)
    required = None if missing else initial + monthly * costs.reserve_months
    remaining = None if required is None or costs.budget is None else costs.budget - required
    status = ("incomplete" if missing else "budget_unknown" if remaining is None
              else "over_budget" if remaining < 0 else "within_budget")
    return CostAssessment(known_initial=initial, known_monthly=monthly,
        required_cash=required, budget_remaining=remaining, missing_fields=missing, status=status,
        note="직접 입력한 금액만 합산했습니다. 보증금 포함 초기 비용과 선택한 개월의 월 고정비이며, 매출·세금·변동비·회수기간을 예측하지 않습니다.")
