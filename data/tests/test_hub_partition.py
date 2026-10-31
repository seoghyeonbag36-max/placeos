"""PageHub.partition_with — 겹친 수집 범위를 가까운 쪽 거점에만 담는다 (2026-10-31 용봉동·전남대).

반경을 줄여 겹침을 피하던 자리(중심 416m → 반경 207m)가 상가를 잘랐다. 반경은 각자 정하고, 겹친 점포의 이중 계수만 막는다.
"""
from data.config import page_hubs as ph
from data.config.page_hubs import PageHub, owns_point


def test_no_partner_means_every_point_is_owned():
    hub = ph.ALL_HUBS["garosugil"]
    assert not hub.partition_with and owns_point(hub, 37.5205, 127.0230) and owns_point(hub, 0.0, 0.0)


def test_each_point_belongs_to_exactly_one_of_the_pair():
    a, b = ph.GWANGJU_HUBS["gj-yongbong"], ph.GWANGJU_HUBS["gj-chonnam"]
    assert a.partition_with == ("gj-chonnam",) and b.partition_with == ("gj-yongbong",)
    n = 0
    for i in range(-30, 31):
        for j in range(-30, 31):
            lat, lon = (a.cy + b.cy) / 2 + i * 0.0001, (a.cx + b.cx) / 2 + j * 0.0001
            assert owns_point(a, lat, lon) != owns_point(b, lat, lon), (lat, lon)   # 정확히 한 쪽
            n += 1
    assert n == 61 * 61


def test_a_point_at_each_center_belongs_to_its_own_hub():
    a, b = ph.GWANGJU_HUBS["gj-yongbong"], ph.GWANGJU_HUBS["gj-chonnam"]
    assert owns_point(a, a.cy, a.cx) and not owns_point(b, a.cy, a.cx)
    assert owns_point(b, b.cy, b.cx) and not owns_point(a, b.cy, b.cx)


def test_partners_reference_each_other():
    """짝이 한쪽만 선언돼 있으면 두 거점이 같은 점포를 다 가져간다."""
    for slug, hub in ph.ALL_HUBS.items():
        for other in hub.partition_with:
            assert other in ph.ALL_HUBS, (slug, other)
            assert slug in ph.ALL_HUBS[other].partition_with, f"{slug} → {other} 짝이 한쪽뿐이다"


def test_checklist_import_applies_the_same_partition(monkeypatch):
    """체크리스트 가져오기(`import_acquisition.import_stores`)도 수집기와 같은 가까운 쪽 귀속을 건다 — 빠지면
    다음 가져오기가 겹친 점포 전량을 최신 stores_raw 로 만든다(2026-10-31 리뷰)."""
    from data.collectors import import_acquisition as ia
    a, b = ph.GWANGJU_HUBS["gj-yongbong"], ph.GWANGJU_HUBS["gj-chonnam"]
    mine = {"bizesId": "near-a", "lat": a.cy, "lon": a.cx}
    theirs = {"bizesId": "near-b", "lat": b.cy, "lon": b.cx}
    monkeypatch.setattr(ia, "ACTIVE_HUBS", {"gj-yongbong": a})
    monkeypatch.setattr(ia, "_store_status", lambda run: {"gj-yongbong": "complete"})
    monkeypatch.setattr(ia, "_read_stores", lambda run, slug, how: ([mine, theirs], {}))
    seen = {}
    monkeypatch.setattr(ia, "_decide", lambda slug, name, date, rows, force: (seen.setdefault("rows", rows), None) and ("unchanged(x)", None))
    out, snap = ia.import_stores(None, "2026-10-31", apply=False, force=False)
    assert [r["bizesId"] for r in seen["rows"]] == ["near-a"], seen
    assert "partition" in out["gj-yongbong"]
