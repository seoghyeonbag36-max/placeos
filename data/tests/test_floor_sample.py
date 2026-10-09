"""[Page 검증] 층 단위 무작위 층화 표본 생성기(`make_roadview_sample --floors`)의 성질을 고정한다.

이 표본은 "화면에 걸린 빈 층이 맞는가"를 재는 정답지의 **틀**이다. 틀이 조용히 틀어지면
(모집단이 화면 목록과 갈라지거나, 라벨러가 예측을 보거나, 채운 라벨이 덮이면) 그 위에서
잰 정확도는 숫자만 그럴듯하고 의미가 없다. 그래서 고정하는 것 여덟:

  1. 모집단 = 상업층 전부를 네 계층으로 **빠짐없이·겹치지 않게** 나눈다
  2. 빈 층 계층은 화면 목록(`build_vacant_floor_units._units_for`)과 **정확히 같다**
  3. 서빙 목록이 마스터보다 낡았으면 **멈춘다**(화면과 다른 목록을 검증하지 않는다)
  4. 인접 거점이 같은 (지번, 층)을 들면 한 번만 센다
  5. 같은 틀 + 같은 시드 = 같은 표본, 시드가 다르면 다른 표본
  6. 가중치 = N_h / n_h, 계층 크기가 목표보다 작으면 전수
  7. `labels.csv` 에는 모델이 아는 것이 **한 칸도** 없다(블라인드)
  8. 라벨이 채워진 시트는 `--force` 로도 덮이지 않는다

실행: (레포 루트에서) python -m pytest data/tests/test_floor_sample.py -q
"""
from __future__ import annotations

import csv
import json
from types import SimpleNamespace

import pytest

from data.pipelines import build_vacant_floor_units as bvfu
from data.validation import make_roadview_sample as msr


# ── 합성 마스터 ───────────────────────────────────────────────────────────────

def _feat(pnu: str, *, com: list[int], occ: list[int], unknown: int = 0,
          status: str = "partial", floors: int = 6, bid: str | None = None,
          x: float = 127.0) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon",
                     "coordinates": [[[x, 37.5], [x + 0.001, 37.5], [x + 0.001, 37.501], [x, 37.5]]]},
        "properties": {
            "id": bid or f"{pnu}-1", "pnu": pnu, "name": "빌딩", "capacity_method": "floor_ouln",
            "source": "stores+ledger", "status": status, "floors": floors, "vacancy_rate": 50.0,
            "com_floors": com, "occ_floors": occ, "unknown_n": unknown, "industry": "소매",
        },
    }


def _flr_rows(pnu: str, floors: list[int]) -> dict[str, list[dict]]:
    return {pnu: [{"flrGbCdNm": "지상", "flrNo": n, "area": 200.0, "mainPurpsCdNm": "소매점"}
                  for n in floors]}


# 합성 PNU(19자리). 실제 지번과 무관하다.
PNU_A = "1168010700100010000"
PNU_B = "1168010700100020000"
PNU_FULL = "1168010700100030000"


def _hub_feats() -> list[dict]:
    return [
        # A: 상업 1~5, 영업 {2,3}, 후보 {1,4,5}, 층 미상 1 → 낮은 층부터 → 1 probable / 4·5 confirmed
        _feat(PNU_A, com=[1, 2, 3, 4, 5], occ=[2, 3], unknown=1),
        # B: 상업 1~2, 영업 {1}, 후보 {2}, 층 미상 0 → 2 confirmed
        _feat(PNU_B, com=[1, 2], occ=[1], unknown=0),
        # 만실 건물 — 화면 목록에서 빠진다 → 후보가 있어도 unlisted
        _feat(PNU_FULL, com=[1, 2, 3], occ=[1, 2], unknown=0, status="full"),
    ]


@pytest.fixture
def world(tmp_path, monkeypatch):
    """임시 gold 위의 거점 `hub1` — 마스터와, 실제 생성기로 만든 서빙 목록을 갖춘다."""
    slug = "hub1"
    gold = tmp_path / "gold"
    (gold / slug).mkdir(parents=True)
    feats = _hub_feats()
    (gold / slug / "page_building_master.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")

    flr = {}
    for pnu in (PNU_A, PNU_B, PNU_FULL):
        flr.update(_flr_rows(pnu, [1, 2, 3, 4, 5]))
    monkeypatch.setattr(bvfu, "GOLD", gold)
    monkeypatch.setattr(bvfu, "_load_floor_rows", lambda _s: flr)
    units = bvfu._units_for(slug)
    (gold / slug / "vacant_floor_units.json").write_text(
        json.dumps({"built_at": "2026-10-08T00:00:00+00:00", "units": units}), encoding="utf-8")

    monkeypatch.setattr(msr, "GOLD", gold)
    monkeypatch.setattr(msr, "_OUT", tmp_path / "out")
    monkeypatch.setattr(msr, "ACTIVE_HUBS", {slug: SimpleNamespace(name="테스트거점")})
    monkeypatch.setattr(msr, "load_latest", lambda *_a, **_k: [])     # 주소 폴백 경로
    (tmp_path / "out").mkdir()
    return SimpleNamespace(slug=slug, gold=gold, units=units, tmp=tmp_path)


def _by_key(rows):
    return {(r["pnu"], r["floor"]): r["cls"] for r in rows}


# ── 1·2. 모집단 ───────────────────────────────────────────────────────────────

def test_population_partitions_every_commercial_floor(world):
    rows, _ = msr.floor_population(world.slug)
    got = _by_key(rows)
    # 상업층 5 + 2 + 3 = 10 — 겹치지도 빠지지도 않는다
    assert len(rows) == len(got) == 10
    assert got[(PNU_A, 1)] == "vacant_probable"     # 층 미상 점포가 낮은 층부터 앉는다
    assert got[(PNU_A, 4)] == got[(PNU_A, 5)] == "vacant_confirmed"
    assert got[(PNU_A, 2)] == got[(PNU_A, 3)] == "occupied"
    assert got[(PNU_B, 2)] == "vacant_confirmed" and got[(PNU_B, 1)] == "occupied"
    # 만실 건물의 후보 층(3)은 목록에서 빠졌으므로 occupied 도 vacant 도 아닌 unlisted
    assert got[(PNU_FULL, 3)] == "unlisted"


def test_vacant_strata_equal_the_serving_list_exactly(world):
    """빈 층 계층은 생성기가 낸 목록과 (지번, 층, 확실도) 까지 같다 — 단일 출처 고정."""
    rows, _ = msr.floor_population(world.slug)
    mine = {(r["pnu"], r["floor"], r["certainty"]) for r in rows if r["cls"].startswith("vacant_")}
    theirs = {(u["pnu"], u["floor"], u["certainty"]) for u in world.units}
    assert mine == theirs and mine


def test_stale_serving_list_fails_closed(world):
    """서빙 목록이 마스터와 어긋나면(영업 확인 층을 빈 층으로 싣고 있다) 표본을 만들지 않는다."""
    path = world.gold / world.slug / "vacant_floor_units.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["units"].append({**doc["units"][0], "floor": 2, "pnu": PNU_A, "certainty": "confirmed"})
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(msr.StaleInventory):
        msr.floor_population(world.slug)


def test_listed_unit_missing_from_master_fails_closed(world):
    path = world.gold / world.slug / "vacant_floor_units.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["units"].append({**doc["units"][0], "pnu": "9999999999999999999"})
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(msr.StaleInventory):
        msr.floor_population(world.slug)


# ── 4. 거점 간 중복 ────────────────────────────────────────────────────────────

def test_cross_hub_duplicate_is_counted_once_first_hub_wins(world, monkeypatch):
    # 인접 거점 hub2 는 PNU_B 를 똑같이 들고 있고, 한 층(1)의 판정이 다르다(영업 확인 없음).
    gold2 = world.gold / "hub2"
    gold2.mkdir()
    (gold2 / "page_building_master.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [_feat(PNU_B, com=[1, 2], occ=[], unknown=0)]}), encoding="utf-8")
    flr = _flr_rows(PNU_B, [1, 2])
    monkeypatch.setattr(bvfu, "_load_floor_rows", lambda _s: flr)
    (gold2 / "vacant_floor_units.json").write_text(
        json.dumps({"units": bvfu._units_for("hub2")}), encoding="utf-8")

    frame, meta = msr.build_frame([world.slug, "hub2"])
    keys = [(r["pnu"], r["floor"]) for r in frame]
    assert len(keys) == len(set(keys)) == 10                      # 10 + 2 - 겹침 2
    assert meta["rows_with_duplicates"] == 12
    assert meta["cross_hub_duplicates"] == 2
    assert meta["cross_hub_class_conflicts"] == 1                 # B 의 1층: occupied ↔ vacant
    owner = {(r["pnu"], r["floor"]): r["slug"] for r in frame}
    assert owner[(PNU_B, 1)] == world.slug                        # 첫 거점이 갖는다


# ── 5·6. 추출 ─────────────────────────────────────────────────────────────────

def _big_frame(n_per: int = 40) -> list[dict]:
    frame = []
    for i, key in enumerate(msr._STRATA):
        cls, band = key.split("|")
        for j in range(n_per + i):                                 # 계층마다 크기가 다르다
            frame.append({"slug": "hub1", "pnu": f"{i:03d}{j:016d}", "floor": 1 if band == "1F" else 2 + j % 4,
                          "band": band, "cls": cls, "stratum": key, "also_in": [], "conflict": False})
    return frame


def test_same_frame_and_seed_give_same_sample_and_other_seed_differs():
    frame, quota = _big_frame(), {k: 7 for k in msr._STRATA}
    a, _ = msr.draw_floor_sample(frame, quota, 42)
    b, _ = msr.draw_floor_sample(list(reversed(frame)), quota, 42)   # 입력 순서가 달라도
    c, _ = msr.draw_floor_sample(frame, quota, 43)
    ids = lambda s: [(r["pnu"], r["floor"]) for r in s]              # noqa: E731
    assert ids(a) == ids(b)
    assert ids(a) != ids(c)


def test_quota_census_and_weights():
    frame = _big_frame()
    quota = {k: 10 for k in msr._STRATA}
    small = next(k for k in msr._STRATA)                              # 첫 계층을 일부러 작게
    frame = [r for r in frame if r["stratum"] != small] + [
        r for r in frame if r["stratum"] == small][:4]                # N=4 < 목표 10 → 전수
    sample, design = msr.draw_floor_sample(frame, quota, 1)
    assert design[small] == {"N": 4, "target": 10, "n": 4, "weight": 1.0, "census": True}
    for key, d in design.items():
        got = [r for r in sample if r["stratum"] == key]
        assert len(got) == d["n"] == min(10, d["N"])
        assert len({(r["pnu"], r["floor"]) for r in got}) == len(got)         # 중복 추출 없음
        if got:
            # 가중치 합 = 계층 크기 — 표본이 틀을 복원한다
            assert sum(r["weight"] for r in got) == pytest.approx(d["N"])


def test_scaled_quota_never_zeroes_a_stratum():
    q = msr.scaled_quota(0.01)
    assert all(v >= 1 for v in q.values())
    assert sum(msr.scaled_quota(1.0).values()) == 365


# ── 7. 블라인드 ───────────────────────────────────────────────────────────────

_MODEL_WORDS = ("vacant_", "confirmed", "probable", "occupied", "unlisted", "stratum")
_MODEL_COLS = {"cls", "certainty", "weight", "N_h", "n_h", "stratum", "status", "vacancy_rate",
               "area_m2", "purps", "was", "band", "bldg_id", "pnu"}


def test_labels_sheet_is_blind_and_key_holds_the_model(world):
    msr.run_floors([world.slug], tag="t1")
    out = world.tmp / "out" / "floor_sample_t1"
    with (out / "labels.csv").open(encoding="utf-8-sig", newline="") as fp:
        rows = list(csv.DictReader(fp))
    assert rows
    assert not (_MODEL_COLS & set(rows[0])), "labels.csv 에 모델이 아는 열이 있다"
    blob = (out / "labels.csv").read_text(encoding="utf-8-sig") + (out / "GUIDE.md").read_text(encoding="utf-8")
    for w in _MODEL_WORDS:
        assert w not in blob, f"블라인드 시트에 '{w}' 가 샜다"
    # 라벨러가 채울 열은 비어 있다
    assert all(not r[c] for r in rows for c in msr._LABEL_COLS)
    # 모델 쪽은 key.csv 에 있고, id 로 1:1 조인된다
    with (out / "key.csv").open(encoding="utf-8-sig", newline="") as fp:
        keys = {r["id"]: r for r in csv.DictReader(fp)}
    assert {r["id"] for r in rows} == set(keys)
    assert {"cls", "stratum", "weight", "certainty"} <= set(next(iter(keys.values())))


def test_design_json_records_provenance(world):
    d = msr.run_floors([world.slug], tag="t2", seed=7)
    assert d["seed"] == 7 and d["n_total"] == 10                   # 작은 틀이라 전수
    snap = d["snapshots"][world.slug]
    assert len(snap["master_sha12"]) == 12 and len(snap["units_sha12"]) == 12
    saved = json.loads((world.tmp / "out" / "floor_sample_t2" / "design.json").read_text(encoding="utf-8"))
    assert saved["strata"].keys() == set(msr._STRATA)
    assert "군집 부트스트랩" in saved["inference"]


# ── 8. 덮어쓰기 가드 ──────────────────────────────────────────────────────────

def test_filled_labels_are_never_overwritten_even_with_force(world):
    msr.run_floors([world.slug], tag="t3")
    labels = world.tmp / "out" / "floor_sample_t3" / "labels.csv"
    rows = list(csv.DictReader(labels.open(encoding="utf-8-sig", newline="")))
    rows[0]["label_actual"] = "공실"
    with labels.open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    before = labels.read_bytes()
    for force in (False, True):
        with pytest.raises(SystemExit):
            msr.run_floors([world.slug], tag="t3", force=force)
    assert labels.read_bytes() == before


def test_empty_sheet_needs_force_to_regenerate(world):
    msr.run_floors([world.slug], tag="t4")
    with pytest.raises(SystemExit):
        msr.run_floors([world.slug], tag="t4")                     # 라벨 0행이어도 말없이 덮지 않는다
    msr.run_floors([world.slug], tag="t4", force=True)


def test_dry_run_writes_nothing(world):
    msr.run_floors([world.slug], tag="t5", dry_run=True)
    assert not (world.tmp / "out" / "floor_sample_t5").exists()


@pytest.mark.parametrize("tag", ["../evil", "a/b", "x" * 40, "a b"])
def test_tag_cannot_escape_the_output_dir(world, tag):
    with pytest.raises(SystemExit):
        msr.run_floors([world.slug], tag=tag)


# ── 기존 모드 보존 ────────────────────────────────────────────────────────────

def test_legacy_building_mode_is_still_the_default(monkeypatch):
    calls = []
    monkeypatch.setattr(msr, "run", lambda: calls.append("legacy"))
    msr.main([])
    assert calls == ["legacy"]


def test_floor_only_flags_are_rejected_without_floors(monkeypatch):
    monkeypatch.setattr(msr, "run", lambda: pytest.fail("건물 모드가 돌면 안 된다"))
    with pytest.raises(SystemExit):
        msr.main(["--dry-run"])


# ── 실데이터 정합 (gold 가 추적되므로 CI 에서도 돈다) ──────────────────────────────

@pytest.mark.parametrize("slugs", [["garosugil", "sharosugil"]])
def test_real_hubs_frame_matches_serving_list(slugs):
    """인접한 실거점 둘: 서빙 목록과 틀이 어긋나지 않고(StaleInventory 없음), 겹침이 한 번만 세어진다."""
    frame, meta = msr.build_frame(slugs)
    if not meta["snapshots"]:
        pytest.skip("gold 산출물 없음")
    by_key = {(r["pnu"], r["floor"]): r for r in frame}
    served: dict[tuple[str, int], str] = {}
    for s in slugs:
        p = msr.GOLD / s / "vacant_floor_units.json"
        for u in json.loads(p.read_text(encoding="utf-8"))["units"]:
            served.setdefault((u["pnu"], u["floor"]), u["certainty"])

    # 틀의 빈 층 계층은 전부 어느 거점의 서빙 목록에 실제로 있고,
    for key, r in by_key.items():
        if r["cls"].startswith("vacant_"):
            assert key in served
    # 서빙 목록의 모든 (지번, 층)은 틀에 있다. 빈 층 계층이 아니라면 그 이유는 오직 하나 —
    # 첫 거점은 영업으로 보는데 다른 거점이 빈 층으로 싣는 거점 간 판정 불일치뿐이다.
    for key in served:
        r = by_key[key]
        assert r["cls"].startswith("vacant_") or r["conflict"]
    assert len(by_key) == len(frame) == meta["unique"] <= meta["rows_with_duplicates"]
