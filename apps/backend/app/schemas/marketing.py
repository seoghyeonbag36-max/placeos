"""상권 마케팅 스키마 — 후처리 검증 결과(HAFinding) · 상권 온라인 콘텐츠의 LLM 구조화 출력.

2026-11-22 사용자 정의 「Program = 개업 후 계약을 맺은 공실에 대한 네트워킹·오프라인 마케팅」으로 **검증 프로그램 생성**의 입력/출력 계약
(`ProgramBrief` · `ProgramPlan` · `ChannelPlan` · `ValidationSignal` · `LLMProgramPlan` · 공실 유닛 `VacantSite`)을 지웠다
→ docs/decision-program-post-opening-2026-11-22.md. (그전 2026-09-17 에는 영업 중인 가게의 리뷰·사진·메뉴 계약이 삭제됐다 → docs/feature-program.md §0-V.)
"""
from __future__ import annotations

from pydantic import BaseModel


class HAFinding(BaseModel):
    """Humanistic Authority 후처리 검증 결과 1건 (services/ha_guard.py).

    `ha_check` 가 **LLM 의 자기신고**인 것과 달리 이건 서버가 입력과 대조해 낸 판정이다.

    - `severity == "violation"`: 입력 대조로 거짓이 확정된 것(지어낸 금액, 확정된 트렌드
      방향 역행, 아직 없는 경험을 근거로 삼는 것). 이 findings 가 붙어 있고 `source` 가
      `"llm"` 이 아니면 **LLM 응답이 폐기되고 폴백으로 내려간 것**이다 — 키 미설정·호출
      실패와 구분되는 상태다.
    - `severity == "warning"`: 사전 매칭이라 오탐이 섞인다. 응답은 살리고 밝히기만 한다.
    """
    severity: str                     # "violation" | "warning"
    code: str                         # fabricated_price | trend_contradiction | ...
    message: str                      # 사람이 읽을 판정 문장
    evidence: str | None = None       # 걸린 실제 문자열 (사람이 오탐인지 보게 한다)


# 상권 단위 응답 모델(GET /marketing/{id})은 여기가 아니라 `schemas/district.py::Marketing`
# 이다. 예전에 이 파일에도 같은 뜻의 `DistrictMarketing` 이 있었지만 라우터가 쓰지 않는
# 죽은 사본이었고, 2026-08-06 실제로 이걸 고치고 응답이 안 바뀌어 한 번 헛짚었다. 지웠다.


class LLMDistrictContents(BaseModel):
    """LLM 구조화 출력 계약 — 상권 단위 온라인 콘텐츠(Program 2단계).

    online_contents 는 프론트가 그대로 노출하는 한 줄 카피(해시태그 포함) 목록이다.
    """
    online_contents: list[str]
    ha_check: str

