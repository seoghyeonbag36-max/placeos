"""고양·파주 도시 전체 6곳(2026-11-23 등록) — 등록만 되고 서빙·기본 순회에 오르지 않으며, 이웃과 점포 반경이 겹치지 않는다."""
from __future__ import annotations

import math

from data.config import page_hubs as ph
from data.config.rone_districts import DISTRICT_RONE, SHARED_RONE


def _m(a: ph.PageHub, b: ph.PageHub) -> float:
    return math.hypot((a.cx - b.cx) * 111320 * math.cos(math.radians(37.7)), (a.cy - b.cy) * 111000)


def test_registered_but_not_served_until_gate_passes():
    new = set(ph.GOYANG_PAJU_CITYWIDE_HUBS)
    assert len(new) == 6 and new <= set(ph.ALL_HUBS)
    assert new & set(ph.ACTIVE_HUBS) == set(ph.GOYANG_PAJU_CITYWIDE_SERVED_HUBS)
    assert set(ph.GOYANG_PAJU_CITYWIDE_SERVED_HUBS) <= new
    # 등록만으로 기본 순회·거점 수 분모가 흔들리지 않는다
    assert not (new & set(ph.HUBS))


def test_caution_hubs_are_registered_not_served_until_judged():
    """「주의」 17곳 — 대장 뒤 판정 전에는 서빙·기본 순회에 오르지 않고, 계획상가·단일시설로 미리 단정하지도 않는다."""
    caution = set(ph.GOYANG_PAJU_CAUTION_HUBS)
    assert len(caution) == 17 and caution <= set(ph.ALL_HUBS)
    assert caution & set(ph.ACTIVE_HUBS) == set(ph.GOYANG_PAJU_CAUTION_SERVED_HUBS)
    for slug, hub in ph.GOYANG_PAJU_CAUTION_HUBS.items():
        assert not hub.deferred and not hub.caveat and hub.city in {"goyang", "paju"}, slug


def test_ceiling_hubs_are_deferred_and_never_served():
    """계획상가 밀집 보류 6곳 — 수집만 하고 서빙·기본 순회에는 오르지 않는다(deferred)."""
    ceiling = set(ph.GOYANG_PAJU_CEILING_HUBS)
    assert len(ceiling) == 6 and ceiling <= set(ph.DEFERRED_HUBS)
    assert not (ceiling & set(ph.ACTIVE_HUBS))
    for slug, hub in ph.GOYANG_PAJU_CEILING_HUBS.items():
        assert hub.deferred == "계획상가" and hub.caveat and hub.city in {"goyang", "paju"}, slug


def test_every_new_hub_has_a_shared_rone_anchor():
    for slug in {*ph.GOYANG_PAJU_CITYWIDE_HUBS, *ph.GOYANG_PAJU_CEILING_HUBS, *ph.GOYANG_PAJU_CAUTION_HUBS}:
        assert DISTRICT_RONE[slug] in {"경기>고양시청", "경기>탄현역", "경기>파주시청"}, slug
        # 표본이 고양 2 · 파주 1 뿐이라 신규 거점은 전부 공유다 — 화면이 「*」·rone-shared 로 밝힌다
        assert slug in SHARED_RONE, slug


def test_new_hubs_use_observed_separation_and_do_not_overlap_store_radius():
    """이격 ≥1.0km + 점포 반경이 이웃의 점포 반경과 겹치지 않는다(이중 계수 방지 · hub-chain 규칙)."""
    for slug, hub in {**ph.GOYANG_PAJU_CITYWIDE_HUBS, **ph.GOYANG_PAJU_CEILING_HUBS, **ph.GOYANG_PAJU_CAUTION_HUBS}.items():
        assert hub.city in {"goyang", "paju"} and (hub.deferred == "계획상가") == (slug in ph.GOYANG_PAJU_CEILING_HUBS), slug
        assert 200 <= hub.radius_m <= hub.stores_radius_m <= 700, slug
        for other_slug, other in ph.ALL_HUBS.items():
            if other_slug == slug:
                continue
            d = _m(hub, other)
            assert d >= 1000, (slug, other_slug, round(d))
            if other_slug in hub.partition_with and slug in other.partition_with:
                continue  # 가까운 쪽 귀속을 서로 선언한 짝은 겹쳐도 점포가 이중 계수되지 않는다(2026-11-23 마두동 동측 ↔ 마두역)
            assert d + 1 >= hub.stores_radius_m + other.stores_radius_m, (slug, other_slug, round(d))


def test_janghang_partition_group_is_symmetric_and_does_not_touch_served_hubs():
    """장항2동(2026-11-23) — 라페스타 · 웨스턴돔 · 마두역 반경 확대의 가까운 쪽 귀속 짝은 서로 선언하고, 서빙 거점과는 겹치지 않는다."""
    group = ("ilsan", "westerndom", "madu", "juyeop", "madu-east")
    for slug in group:
        for partner in ph.ALL_HUBS[slug].partition_with:
            assert slug in ph.ALL_HUBS[partner].partition_with, (slug, partner)
    for slug in ("ilsan", "westerndom", "madu"):
        hub = ph.ALL_HUBS[slug]
        assert (hub.radius_m, hub.stores_radius_m) in {(500, 700), (470, 670)} and hub.deferred == "계획상가"
        for other_slug, other in ph.ACTIVE_HUBS.items():  # 서빙 중인 거점의 점포 반경과는 닿지 않는다
            assert _m(hub, other) + 1 >= hub.stores_radius_m + other.stores_radius_m, (slug, other_slug)
