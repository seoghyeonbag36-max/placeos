"""거점 체인 상태의 계획상가 예외 판정 테스트.

실행: (레포 루트에서) python -m pytest -q data/tests/test_chain_status.py
"""
from __future__ import annotations

import json

from data.config.page_hubs import PageHub
from scripts import chain_status as chain


def _store_ratio_report(tmp_path, monkeypatch, *, caveat: str) -> dict:
    """건물당 점포 11개인 가상 거점의 체인 보고서를 만든다."""
    slug = "store-ratio-probe"
    hub = PageHub(slug, "점포 비율 검증 거점", 127.0, 37.5, caveat=caveat)
    stores = [{"bldMngNo": "same-building", "store_id": i} for i in range(11)]
    store_path = tmp_path / "bronze" / slug / "2026-08-30" / "stores_raw.json"
    store_path.parent.mkdir(parents=True)
    store_path.write_text(json.dumps(stores), encoding="utf-8")

    monkeypatch.setattr(chain, "BRONZE", tmp_path / "bronze")
    monkeypatch.setattr(chain, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(chain, "_hubs", lambda: {slug: hub})
    monkeypatch.setattr(chain, "_city_of", lambda _hub: ("seoul", "seoul"))
    monkeypatch.setattr(chain, "_served_ids", lambda: {slug})
    return chain.summarize(slug)


def _store_stage(report: dict) -> dict:
    return next(stage for stage in report["stages"] if stage["stage"] == "점포")


def test_caveat_hub_is_not_blocked_on_store_ratio(tmp_path, monkeypatch):
    report = _store_ratio_report(tmp_path, monkeypatch, caveat="제품 판단으로 서빙 승인")
    store = _store_stage(report)

    assert store["status"] != chain.BLOCKED
    assert "예외" in store["evidence"]
    assert "점포" not in report["blocked"]


def test_caveat_absent_hub_still_blocks_on_store_ratio(tmp_path, monkeypatch):
    report = _store_ratio_report(tmp_path, monkeypatch, caveat="")
    store = _store_stage(report)

    assert store["status"] == chain.BLOCKED
    assert "점포" in report["blocked"]


# ── 서빙등재: 제품 판단(SERVED_CITIES)과 배선 결손을 가른다 ────────────────────────
#
# 2026-09-05 에 geumchon·tanhyeon·yadang 셋이 "Gold 가 섰는데 목록에 없다 —
# `_is_measured` 조건 확인" 으로 보고됐다. 그런데 `_is_measured` 는 통과하고 있었고,
# 실제로 거르는 것은 그 다음 줄의 `SERVED_CITIES={"seoul"}` 였다. 즉 프로버가 **멀쩡한
# 배선을 디버깅하라고** 시킨 것이다. 아래 둘이 그 갈림을 고정한다.

def _serving_report(tmp_path, monkeypatch, *, city: str, served: frozenset) -> dict:
    """Gold(건물마스터)까지 선 거점이 서빙 목록에 없을 때의 보고서."""
    slug = "serving-probe"
    hub = PageHub(slug, "서빙 판정 검증 거점", 127.0, 37.5, city=city)
    gold = tmp_path / "gold" / slug
    gold.mkdir(parents=True)
    # Gold 가 **선** 상태를 만든다 — 서빙등재의 `ready` 는 Page마스터·앵커를 보므로,
    # 건물마스터만 두면 "Gold 가 서기 전" 가지로 빠져 이 테스트가 다른 것을 재게 된다.
    gold.joinpath("page_building_master.geojson").write_text("{}", encoding="utf-8")
    gold.joinpath("coverage.json").write_text(
        json.dumps({"tier": "Tier1", "shown": 120, "reference_coverage_pct": 95.0}),
        encoding="utf-8")

    monkeypatch.setattr(chain, "BRONZE", tmp_path / "bronze")
    monkeypatch.setattr(chain, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(chain, "_hubs", lambda: {slug: hub})
    monkeypatch.setattr(chain, "_city_of", lambda _hub: (city, city))
    monkeypatch.setattr(chain, "_served_ids", lambda: set())     # 목록에 없다
    monkeypatch.setattr(chain, "_served_cities", lambda: served)
    return chain.summarize(slug)


def _serving_stage(report: dict) -> dict:
    return next(s for s in report["stages"] if s["stage"] == "서빙등재")


def test_unserved_city_is_paused_not_a_wiring_defect(tmp_path, monkeypatch):
    report = _serving_report(tmp_path, monkeypatch, city="paju", served=frozenset({"seoul"}))
    stage = _serving_stage(report)

    assert stage["status"] == chain.PAUSED
    assert "제품 판단" in stage["evidence"]
    # 다음 한 수로 뽑히면 안 된다 — 고칠 코드가 없기 때문이다.
    assert stage["next"] == ""
    assert report["next_stage"] != "서빙등재"
    assert report["serving_paused"] is True


def test_served_city_still_reports_missing_listing(tmp_path, monkeypatch):
    """서빙 대상 도시인데 목록에 없으면 그것은 진짜 결손이다 — 보류로 삼키지 않는다."""
    report = _serving_report(tmp_path, monkeypatch, city="seoul", served=frozenset({"seoul"}))
    stage = _serving_stage(report)

    assert stage["status"] == chain.TODO
    assert "_is_measured" in stage["next"]
    assert report["serving_paused"] is False


def test_unreadable_decision_does_not_become_paused(tmp_path, monkeypatch):
    """판단을 못 읽었을 때(None) '보류'라고 단정하면 진짜 결손이 조용히 묻힌다."""
    report = _serving_report(tmp_path, monkeypatch, city="paju", served=None)
    stage = _serving_stage(report)

    assert stage["status"] == chain.TODO
    assert report["serving_paused"] is False


# ── 보류 도시는 수집 명령도 내지 않는다 (2026-09-05 결정) ──────────────────────────
#
# 서빙을 09-03 에 껐는데 프로버는 경기 17거점의 대장·공실유닛을 계속 "다음 한 수"로
# 냈다. 그걸 집으면 화면에 닿지 않을 데이터에 하루치 쿼터가 사라진다(쿼터는 회수되지
# 않는다). 명령은 **지우는 것이 아니라 가린다** — 재개할 때 다시 찾아야 하므로.

def _uncollected_paused_report(monkeypatch, tmp_path, *, include_paused: bool) -> dict:
    slug = "paused-collect-probe"
    hub = PageHub(slug, "보류 도시 미수집 거점", 126.8, 37.7, city="paju")
    monkeypatch.setattr(chain, "BRONZE", tmp_path / "bronze")   # 아무것도 수집 안 됨
    monkeypatch.setattr(chain, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(chain, "_hubs", lambda: {slug: hub})
    monkeypatch.setattr(chain, "_city_of", lambda _hub: ("paju", "paju"))
    monkeypatch.setattr(chain, "_served_ids", lambda: set())
    monkeypatch.setattr(chain, "_served_cities", lambda: frozenset({"seoul"}))
    return chain.summarize(slug, include_paused=include_paused)


def test_paused_city_yields_no_next_move(tmp_path, monkeypatch):
    report = _uncollected_paused_report(monkeypatch, tmp_path, include_paused=False)

    assert report["serving_paused"] is True
    assert report["next"] == ""          # 쿼터를 태우라고 시키지 않는다
    assert report["next_stage"] == ""


def test_include_paused_restores_the_next_move(tmp_path, monkeypatch):
    """재개할 때 명령을 다시 찾을 수 있어야 한다 — 가린 것이지 지운 것이 아니다."""
    report = _uncollected_paused_report(monkeypatch, tmp_path, include_paused=True)

    assert report["serving_paused"] is True
    assert report["next"] != ""
    # 단계 목록에는 보류 여부와 무관하게 늘 남아 있다.
    assert any(s["next"] for s in report["stages"])


# ── 대장 잘림: 파일이 있다고 대장이 끝난 게 아니다 (2026-10-28) ─────────────────────────
# 수집기는 쿼터가 끝나도 받은 데까지 저장한다. 존재만 보면 대장이 239동 잘린 평택역이 Tier1·앵커 OK 로 보였다.

def _ledger_report(tmp_path, monkeypatch, *, rows: list[str]) -> dict:
    slug = "ledger-probe"
    hub = PageHub(slug, "대장 잘림 검증 거점", 127.0, 37.5)
    stores = [{"bldMngNo": f"b{i}", "lat": "37.5", "lon": "127.0", "indsMclsNm": "커피점"} for i in range(3)]
    p = tmp_path / "bronze" / slug / "2026-10-28" / "stores_raw.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(stores), encoding="utf-8")
    (p.parent / "bldg_polygons.geojson").write_text(json.dumps({"features": [{}] * 3}), encoding="utf-8")
    g = tmp_path / "gold" / slug / "building_vacancy.json"
    g.parent.mkdir(parents=True)
    g.write_text(json.dumps([{"capacity_method": m} for m in rows]), encoding="utf-8")
    monkeypatch.setattr(chain, "BRONZE", tmp_path / "bronze")
    monkeypatch.setattr(chain, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(chain, "_hubs", lambda: {slug: hub})
    monkeypatch.setattr(chain, "_city_of", lambda _hub: ("seoul", "seoul"))
    monkeypatch.setattr(chain, "_served_ids", lambda: {slug})
    return chain.summarize(slug)


def _ledger(report: dict) -> dict:
    return next(s for s in report["stages"] if s["stage"] == "대장")


def test_truncated_ledger_is_todo_and_becomes_the_next_move(tmp_path, monkeypatch):
    """잘린 대장은 할 일이다 — PARTIAL 로 두면 「다음 한 수」로 안 뽑혀 「모두 통과」로 읽혔다(리뷰)."""
    report = _ledger_report(tmp_path, monkeypatch, rows=["floor_ouln"])
    stage = _ledger(report)
    assert stage["status"] == chain.TODO and "2동 남음" in stage["evidence"], stage
    assert report["next_stage"] == "대장", (report["next_stage"], report["next"])


def test_rate_limited_rows_are_not_received(tmp_path, monkeypatch):
    """429 로 못 받은 행은 수집기가 재개 때 다시 받는다 — 받은 것으로 세면 잘린 대장이 완주로 보인다."""
    stage = _ledger(_ledger_report(tmp_path, monkeypatch, rows=["floor_ouln", "rate_limited", "rate_limited"]))
    assert stage["status"] == chain.TODO and "1/3동 받음" in stage["evidence"], stage


def test_complete_ledger_is_ok(tmp_path, monkeypatch):
    stage = _ledger(_ledger_report(tmp_path, monkeypatch, rows=["floor_ouln"] * 3))
    assert stage["status"] == chain.OK, stage


def test_probe_does_not_print_into_machine_output(tmp_path, monkeypatch, capsys):
    """--json·--next 를 읽는 쪽이 있다 — 판정 중의 「[group] …」 이 표준출력에 새면 json.loads 가 깨진다(리뷰)."""
    _ledger_report(tmp_path, monkeypatch, rows=["floor_ouln"])
    assert capsys.readouterr().out == ""


# ── 앵커 폴백: 값이 폴백 10.0 인데 「R-ONE 대조 통과」로 보이면 안 된다 (2026-10-31) ─────────────────────
# 경기 3차 50거점·광주 13거점은 R-ONE 값을 받기 전에 calibrate 를 돌려, 라벨은 「R-ONE … 경기>수원역」인데 값은 폴백 10.0 이었다.

def test_fallback_anchor_is_todo_not_ok(tmp_path, monkeypatch):
    slug = "anchor-probe"
    hub = PageHub(slug, "앵커 폴백 검증 거점", 127.0, 37.5)
    g = tmp_path / "gold" / slug
    g.mkdir(parents=True)
    (g / "calibration.json").write_text(json.dumps({"anchor_pct": 10.0, "anchor_is_fallback": True}), encoding="utf-8")
    (g / "coverage.json").write_text(json.dumps({"tier": "Tier1", "reference_coverage_pct": 100, "shown": 3,
                                                 "representative_vacancy_pct": 12.0}), encoding="utf-8")
    (g / "page_building_master.geojson").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(chain, "BRONZE", tmp_path / "bronze")
    monkeypatch.setattr(chain, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(chain, "_hubs", lambda: {slug: hub})
    monkeypatch.setattr(chain, "_city_of", lambda _hub: ("seoul", "seoul"))
    monkeypatch.setattr(chain, "_served_ids", lambda: {slug})
    summary = chain.summarize(slug)
    stage = next(s for s in summary["stages"] if s["stage"] == "앵커")
    # PARTIAL 이면 「다음 한 수」로 안 뽑혀 「모두 통과」로 읽힌다 — TODO 여야 다음 명령이 나온다(리뷰)
    assert stage["status"] == chain.TODO and "폴백" in stage["evidence"], stage
    assert "rone_rent" in stage["next"]
    # 앞 단계가 다 통과한 거점이면 이 TODO 가 「다음 한 수」로 뽑혀야 한다(PARTIAL 이면 「모두 통과」로 끝났다)
    real = summary["stages"]
    i = next(k for k, s in enumerate(real) if s["stage"] == "앵커")
    passed = [{**s, "status": chain.OK, "next": ""} for s in real[:i]] + real[i:]
    monkeypatch.setattr(chain, "stages", lambda _slug: passed)
    assert "rone_rent" in chain.summarize(slug)["next"]


# ── 경기 3차 거점 단위 서빙 판단 (2026-10-31 리뷰) ───────────────────────────────
# 화성을 서빙 도시로 넣자(병점역 1곳) 같은 도시의 봉담이 「_is_measured 확인」으로 보고됐다 — 배선 결손이 아니라 제품 판단이다.

def test_unserved_batch_hub_in_served_city_is_paused(tmp_path, monkeypatch):
    monkeypatch.setattr(chain, "_batch_unserved", lambda s: True)
    report = _serving_report(tmp_path, monkeypatch, city="hwaseong", served=frozenset({"hwaseong"}))
    stage = _serving_stage(report)
    assert stage["status"] == chain.PAUSED and not stage["next"], stage
    assert "GYEONGGI_BATCH3_SERVED_HUBS" in stage["evidence"]


def test_batch_unserved_reads_the_real_lists():
    assert chain._batch_unserved("bongdam") is True          # 화성 — 서빙 목록 밖
    assert chain._batch_unserved("byeongjeom") is False      # 화성 — 10-31 재판정 뒤 서빙
    assert chain._batch_unserved("garosugil") is False       # 배치 밖 — 판단 대상이 아니다

