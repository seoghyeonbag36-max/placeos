"""상권 흐름(파주-고양-서울) 계약 — 출발→도착 **집계**와 그 위에서 고른 짝.

값의 출처는 서울시×KT 수도권 생활이동(OA-22300)이고 `gold/platform_corridor.json` 이 단일
출처다. 한 사람의 동선이 아니다 — 필드 이름에 동선(route·path·trajectory)을 쓰지 않는다.
서울 마디는 거점(행정동), 경기 마디는 시군구다(`kind`). 같은 시군구 마디의 경기 거점은 같은
흐름 값을 공유한다 — `hubs` 가 그 소속을 밝힌다.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SegmentKey = Literal["paju", "goyang", "seoul"]
SynergyKind = Literal["visit_link", "commute", "inbound", "local_belt"]


class _Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class CorridorSegment(_Model):
    key: SegmentKey
    name: str


class CorridorPeriod(_Model):
    days: list[str]
    n_days: int = Field(ge=1)
    weekday: int = Field(ge=0)
    weekend: int = Field(ge=0)


class CorridorLink(_Model):
    """구간 → 구간 하루 이동(같은 구간 안 포함)."""
    from_: SegmentKey = Field(alias="from")
    to: SegmentKey
    per_day: float = Field(ge=0)
    avg_min: float | None = None
    avg_km: float | None = None
    purpose_group_share: dict[str, float]
    arr_hour_share: list[float]
    peak_hours: list[int]


class CorridorPair(_Model):
    """마디 → 마디 하루 이동. 방문 = 기타·쇼핑·관광·병원 · 출근 = 출근·등교 · 귀가."""
    from_: str = Field(alias="from")
    to: str
    per_day: float = Field(ge=0)
    visit_per_day: float = Field(ge=0)
    work_per_day: float = Field(ge=0)
    home_per_day: float = Field(ge=0)
    purpose_group_share: dict[str, float]
    peak_hours: list[int]
    avg_min: float | None = None


class CorridorHub(_Model):
    """마디에 속한 서빙 거점. 공실률은 싣지 않는다 — 화면이 거점 목록에서 합친다."""
    id: str
    name: str
    rent_1f_per_pyeong: float | None = None
    rent_shared: bool = False
    fit: float | None = None
    fit_rank: int | None = None
    rank_group_name: str | None = None   # 순위 묶음(서울 · 고양·파주) — 묶음이 다르면 견주지 않는다
    rank_n: int | None = None


class CorridorRole(_Model):
    kind: Literal["출근형", "주거형", "방문형", "혼합"]
    deviation_pp: dict[str, float] | None = None
    median_share: dict[str, float] | None = None
    margin_pp: float | None = None


class CorridorNode(_Model):
    id: str
    kind: Literal["hub", "sgg"]
    segment: SegmentKey
    name: str
    hubs: list[CorridorHub]
    arrivals_per_day: float = Field(ge=0)
    from_gyeonggi_per_day: float = Field(ge=0)
    corridor_rank: int | None = None
    on_corridor: bool
    role: CorridorRole
    # 흐름에 붙은 마디만 아래를 싣는다(붙지 않은 서울 거점은 순위 재료만 남는다)
    inflow_share: dict[str, float] | None = None
    purpose_group_share: dict[str, float] | None = None
    purpose_share: dict[str, float] | None = None
    arr_hour_share: list[float] | None = None
    peak_hours: list[int] | None = None
    external_share: float | None = None
    from_segment_per_day: dict[str, float] | None = None
    top_destinations: list[CorridorPair] | None = None
    top_origins: list[CorridorPair] | None = None


class CorridorSynergy(CorridorPair):
    """측정으로 고른 짝 — 경기 마디마다 종류별 하나. 결과를 약속하지 않는다."""
    kind: SynergyKind
    node: str
    basis: str
    value: float = Field(ge=0)
    back_per_day: float | None = None
    per_day_both: float | None = None


class CorridorSummary(_Model):
    id: str
    name: str
    segments: list[CorridorSegment]
    period: CorridorPeriod


class CorridorResponse(_Model):
    id: str
    name: str
    note: str
    segments: list[CorridorSegment]
    period: CorridorPeriod
    source: str
    dataset: str
    resolution: dict[str, str]
    caveats: list[str]
    links: list[CorridorLink]
    outer: dict[str, dict[str, dict[str, float]]]
    nodes: list[CorridorNode]
    hub_nodes: dict[str, str]
    pairs: list[CorridorPair]
    synergies: list[CorridorSynergy]
    params: dict[str, float]
    # 업종을 골라 물었을 때만 — 순위 묶음(잣대별 · business_fit.rank_groups 그대로)
    industry: dict | None = None
    rank_groups: list[dict] | None = None
