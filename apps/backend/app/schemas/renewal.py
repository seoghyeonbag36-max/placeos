"""2026-11 리뉴얼 새 경로의 응답 계약. 값이 없으면 null 이고 0 으로 채우지 않는다."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class HubOutline(BaseModel):
    id: str
    rings: list[list[list[float]]]      # 조각마다 바깥 고리 [[lat, lng], …]
    holes: list[list[list[float]]] = []  # 재지 않은 안쪽 구멍
    type_code: str | None = None
    type_name: str | None = None
    type_is_manual: bool = False        # 사람이 붙인 라벨인가(False 는 원본의 데이터 분류이거나 유형 없음)


class HubOutlines(BaseModel):
    note: str | None = None
    hubs: list[HubOutline]


class RentHistory(BaseModel):
    district_id: str
    quarters: list[str]
    rent_per_pyeong_manwon: list[float | None]  # 1층 기준 · 만원/평·월
    rent_available: bool
    floor_factor: dict[str, float]
    vacancy_mid_pct: list[float | None]
    vacancy_small_pct: list[float | None]
    source: str                         # rone | rone-shared | none
    source_name: str | None = None
    shared_from: str | None = None
    note: str | None = None


class SelectedScore(BaseModel):
    industry: str
    label: str | None = None
    score: float | None = None
    rank_note: str | None = None
    district_mean: float | None = None
    delta_pp: float | None = None


class RankedFloorUnit(BaseModel):
    id: str
    floor_label: str | None = None
    certainty: str | None = None
    area: float | None = None
    area_m2: float | None = None
    purps: str | None = None


class RankedSite(BaseModel):
    unit_id: str | None = None
    name: str | None = None
    lat: float | None = None
    lng: float | None = None
    area_py: float | None = None
    floor: str | None = None
    capacity: float | None = None
    vacancy_rate: float | None = None
    was: str | None = None              # ⚠ 직전 업종이 아니다 — 건물 현재 대표 업종
    recommendations: list[dict[str, Any]] = []
    matched_distance_m: float | None = None
    distinct: dict[str, Any] | None = None
    selected: SelectedScore | None = None
    floor_units: list[RankedFloorUnit] = []


class SiteRanking(BaseModel):
    model_config = {"protected_namespaces": ()}

    district_id: str
    industry: str | None = None
    model_covered: bool
    unavailable_reason: str | None = None
    sites: list[RankedSite]
    unit_count: int
    matched_count: int
    match_radius_m: float
    note: str


class HourPoint(BaseModel):
    hour: int
    value: float | None = None
    share: float | None = None


class HourlyProfile(BaseModel):
    district: str
    daytype: Literal["weekday", "weekend"]
    hours: list[HourPoint]
    peak: HourPoint
    source: str
    unit: str
    sample_days: int | None = None
    as_of: str | None = None
    note: str | None = None


class TwinStoreRef(BaseModel):
    name: str
    ind: str | None = None
    ho: str | None = None


class TwinUnit(BaseModel):
    ho: str | None = None
    area_m2: float | None = None      # 전용면적(전유부 전유 행)
    purps: str | None = None
    pub_m2: float | None = None       # 그 호의 공용면적 합(전유공용면적 공용 행) — 계약면적 = area_m2 + pub_m2
    # 상가정보 대조(2026-11-09) — 같은 층 · 같은 호 점포. store_checked=False 면 호수가 없어 대조하지 않은 것
    store: TwinStoreRef | None = None
    store_checked: bool = False


class TwinLedgerPart(BaseModel):
    purps: str | None = None
    etc: str | None = None
    area_m2: float


class TwinLedgerFloor(BaseModel):
    parts: list[TwinLedgerPart]          # 층별개요 용도별 행(넓은 순)
    stair_m2: float | None = None        # 계단실 행 넓이 합(있을 때만 · 실측)
    ev_m2: float | None = None           # 승강기 관련 행 넓이 합(있을 때만 · 실측)


class TwinLedgerLive(BaseModel):
    """건축물대장 실시간 조회(services/building_ledger_live) — 승강기 수 · 층별개요 용도별 행."""
    status: str                           # ok · no_key · no_pnu · refused · error · backoff
    source: str
    error: str | None = None
    elevators: dict[str, int] | None = None   # {passenger, emergency} — 개수만 실측, 위치는 모른다
    fields_missing: bool = False
    title: dict | None = None
    floors: dict[str, TwinLedgerFloor] | None = None   # 키 = 층 번호(지하 음수) 문자열


class TwinExclEstimate(BaseModel):
    """일반건축물 층 전용면적 추정 — 층 바닥면적 × 상업층 전용률. 실측 아님(services/exclusive_estimate)."""
    m2: float
    low: float
    high: float
    ratio: float
    basis: str


class TwinFloor(BaseModel):
    lv: int                             # 지하 음수
    label: str
    status: Literal["vacant_confirmed", "vacant_probable", "occupied", "uncertain", "noncom", "unknown"]
    rule_kind: str | None = None        # placeFloors 규칙값(occupied·uncertain·vacant·noncom)
    area_m2: float | None = None
    area_source: str | None = None
    purps: str | None = None
    rent_est_manwon: int | None = None
    rent_per_pyeong: float | None = None
    unit_id: str | None = None          # 층 매물 vfu-
    units: list[TwinUnit] | None = None
    excl_est: TwinExclEstimate | None = None   # 전유부가 없는 층만 · 추정
    stores: list[TwinStoreRef] | None = None   # 상가정보 이 층 점포(2026-11-09)


class TwinNeighbor(BaseModel):
    id: str | None = None
    ring: list[list[float]]
    floors: int
    height_m: float | None = None
    height_source: str | None = None
    vac_class: str


class VacancyStat(BaseModel):
    basis: str
    label: str
    vacant: float
    total: float
    rate_pct: float | None = None
    note: str


class TwinRange(BaseModel):
    min: float | None = None
    max: float | None = None


class TwinHistoryItem(BaseModel):
    start: str | None = None
    end: str | None = None
    industry: str | None = None
    name: str | None = None


class TwinHistory(BaseModel):
    source: str
    lot_buildings: int | None = None
    items: list[TwinHistoryItem]
    items_total: int = 0
    summary: dict[str, Any] | None = None


class TwinRoad(BaseModel):
    """도로 중심선 한 구간(OSM). 폭은 등급 추정이다 — services/twin_roads.py."""
    n: str                       # 도로 이름(없으면 "")
    c: str                       # OSM 등급(primary · minor · service …)
    w: float                     # 보도 포함 전체 폭(m) · 추정
    sw: float                    # 한쪽 보도 폭(m) · 추정
    ow: int                      # 일방통행 1
    line: list[list[float]]      # [[위도, 경도], …]


class TwinRoadCheck(BaseModel):
    """도로명주소의 도로가 건물 바로 앞인지 — 외곽선에서 그 도로 가장자리까지 거리."""
    name: str | None = None
    gap_m: float | None = None
    ok: bool
    found: bool


class TwinRoadsSource(BaseModel):
    by: str
    license: str
    license_url: str
    via: str
    radius_m: float


class BuildingTwin(BaseModel):
    id: str | None = None
    name: str | None = None
    road_addr: str | None = None
    lat: float
    lng: float
    ring: list[list[float]]
    floors_above: int
    floors_below: int
    floors_conflict: bool
    height_m: float | None = None
    height_source: Literal["vworld", "estimated"]
    approval_date: str | None = None
    built_at: str | None = None
    vac_class: str
    representative_industry: str | None = None
    lot_buildings: int | None = None
    sources: list[str]
    floors: list[TwinFloor]
    neighbors: list[TwinNeighbor]
    vacancy_stats: list[VacancyStat]
    range: TwinRange
    history: TwinHistory
    notes: list[str]
    # 주변 실제 도로(2026-11-06) — 타일을 못 받으면 roads=[] · roads_error 에 사유. 트윈 본체와 무관하게 빈다.
    roads: list[TwinRoad] = []
    roads_source: TwinRoadsSource | None = None
    road_check: TwinRoadCheck | None = None
    roads_error: str | None = None
    ledger_live: TwinLedgerLive | None = None   # 2026-11-09 — 대장 실시간(승강기 · 층별 용도) · 실패해도 트윈은 그대로
    stores_live: dict | None = None             # 2026-11-09 — 상가정보 대조 요약(원천 · 호실 대조 수)


class RelationCounts(BaseModel):
    same: int
    same_chain: int
    similar: int
    colocated: int
    other: int
    total: int


class FloorSplit(BaseModel):
    basement: int
    f1: int
    f2: int
    f3p: int
    unknown: int


class NearbyStore(BaseModel):
    name: str | None = None
    brand: str | None = None
    is_chain: bool
    cat: str | None = None
    relation: Literal["same", "similar", "colocated", "other"]
    lat: float
    lng: float
    floor: int | None = None
    floor_label: str | None = None
    distance_m: float
    same_building: bool


class NearestSame(BaseModel):
    name: str | None = None
    distance_m: float
    floor: int | None = None


class ChainCount(BaseModel):
    brand: str
    n: int


class RelativeRank(BaseModel):
    percentile: float | None = None
    band: str | None = None             # 여유 쪽 · 중간 · 붐비는 쪽
    index: float | None = None          # 참고 지수
    compared_sites: int
    note: str


class ColocatedName(BaseModel):
    name: str | None = None
    lift: float | None = None


class NearbyRelations(BaseModel):
    same: list[str]
    similar: list[str]
    colocated: list[ColocatedName]


class NearbyStores(BaseModel):
    center: dict[str, float]
    radius: int
    basis: Literal["직선"]
    floor_weighted: bool
    edge_truncated: bool
    store_as_of: str | None = None
    counts: RelationCounts
    floor_split: FloorSplit
    by_radius: dict[str, RelationCounts]
    nearest_same: NearestSame | None = None
    chains: list[ChainCount]
    relative: RelativeRank
    stores: list[NearbyStore]
    relations: NearbyRelations
    notes: list[str]


class ReportSection(BaseModel):
    status: Literal["ok", "unavailable"]
    source: str | None = None
    as_of: str | None = None
    note: str | None = None
    data: dict[str, Any] | None = None


class DistrictReport(BaseModel):
    district_id: str
    selected_industry: str | None = None
    unit_id: str | None = None
    building_id: str | None = None
    overview: ReportSection
    industry: ReportSection
    population: ReportSection
    sales: ReportSection
    openclose: ReportSection
    vacancy: ReportSection
    rent: ReportSection
    site: ReportSection
    competition: ReportSection
    posting: ReportSection
    events: ReportSection
