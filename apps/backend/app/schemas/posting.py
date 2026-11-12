"""입점 시뮬레이션(Posting) 요청/결과 스키마.

외부 AI 창업 코파일럿(services/posting.py 어댑터)과 내부 3-Tier 폴백이
모두 이 스키마로 정규화되어 FE·리포트가 공급자에 독립적으로 동작한다.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.district import TierScenario


class SimulateRequest(BaseModel):
    district_id: str
    unit_id: str | None = None       # 거점 내 공실 유닛 (없으면 대표 유닛)
    industry_type: str | None = None  # GNN 업종 추천(Platform) 결과를 전달 가능
    strategy: str | None = None       # premium | value | factory (없으면 3전략 비교)
    # 권리금(만원) — **기업이 넣는다**. 공개 통계가 없어(bronze 전수 확인) 수집으로는
    # 못 채우고, 실제로도 임대인·기존 임차인과의 협상값이라 그 기업만 안다.
    # Program 입력 계약 ③층(창업계획)과 같은 성격이다: 수집 과제가 아니라 계약 과제.
    # 안 주면 0 을 전제로 계산하고 `inputs_source["prem"]="absent"` 로 밝힌다.
    # 실측 감도(270유닛 전수): 추천 5.2% 뒤집힘 · roi 중앙 1.6개월(p90 15.5) ·
    # 회수가부 판정은 0건 변화. → docs/feature-posting.md §0-K
    prem: int | None = None
    industry_detail_key: str | None = Field(default=None, max_length=100)
    operating_inputs: dict[str, Any] | None = None
    # 사용자가 계약서·도면으로 넣은 내부면적(평). 주면 `inputs_source["area"]="user_input"`.
    area_py_override: float | None = Field(default=None, gt=0, le=3000, allow_inf_nan=False)
    # 계약서의 월 임대료(만원). 주면 R-ONE 추정 대신 이 값으로 계산하고 `inputs_source["rent"]="contract"`(2026-11-12).
    rent_override: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    # 받은 인테리어 · 설비 견적(만원). 주면 업종 평균 계수(면적 × 평당 계수 + 고정분) 대신 세 가격대 모두 이 값을 투자비로
    # 쓰고 `inputs_source["invest"]="user_input"`(2026-11-12 — 계수로는 회수 1개월 미만이 836곳 중 296곳이었다).
    # 권리금(prem)은 따로 더한다.
    fitout_override: int | None = Field(default=None, ge=0, le=1_000_000)


class ResolvedPostingInputs(BaseModel):
    area_py: float
    rent_manwon: float
    floor: str


class SimulateResult(BaseModel):
    district_id: str
    unit_id: str
    industry_type: str | None
    scenarios: dict[str, TierScenario]
    source: str  # "copilot" | "fallback-3tier"
    # 폴백으로 떨어진 **이유**. 코파일럿 미설정이면 None(폴백이 정상 동작이다),
    # 설정돼 있는데 실패했으면 계약 위반·연결 실패 사유가 들어간다.
    # 이 둘을 구분하지 않으면 코파일럿이 죽어 있어도 화면이 똑같아 아무도 모른다.
    source_note: str | None = None
    # 시나리오를 만든 입력의 **필드별** 출처: area/rent/prem/foot →
    #   "rone"(R-ONE 임대료) | "flpop"(서울 상권분석 유동인구) | "seed"(손으로 적은 프록시)
    # source 가 코파일럿이냐 폴백이냐와 별개로, 입력이 실측인지 프록시인지를 밝힌다.
    inputs_source: dict[str, str] | None = None
    inputs_quarter: str | None = None   # 실데이터 기준 분기 (예: "20261")
    # 세 전략 모두 회수 불가일 때만 채워진다 — "추천이 없다"와 "이 자리는 회수가
    # 안 된다"를 구분한다. 예전에는 둘 다 빈 값으로 조용히 같아 보였다.
    unviable_note: str | None = None
    calculation_status: str = "calculated"
    unavailable_reason: str | None = None
    economics: dict[str, Any] | None = None


class SimulateResultWithInputs(SimulateResult):
    """층 매물·내부면적 계산에서만 돌려주는 입력값. 기존 건물 응답의 키 집합은 보존한다."""
    resolved_inputs: ResolvedPostingInputs
