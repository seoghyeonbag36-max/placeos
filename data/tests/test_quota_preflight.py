"""쿼터 프리플라이트의 서빙 보류 제외 판정.

실행: (레포 루트에서) python -m pytest -q data/tests/test_quota_preflight.py

이 스크립트가 찍는 실행줄은 그대로 복사돼 돌아간다. 그래서 **대상을 고르는 판정**이
곧 하루치 쿼터의 행선지다 — 쿼터는 하루가 지나면 회수되지 않으므로, 서빙하지 않기로
한 도시가 그 줄에 섞이면 그날의 수집이 통째로 화면에 닿지 않는다(2026-09-05 결정).
"""
from __future__ import annotations

import sys
from pathlib import Path

from scripts import quota_preflight as qp

# `app.data.measured_pages` 를 직접 import 하는 테스트가 있다 — 이 파일만 돌려도 찾도록 백엔드
# 경로를 넣는다(전체 묶음에서는 앞선 테스트가 넣어 줘서 순서에 따라 통과·실패가 갈렸다).
_BACKEND = str(Path(__file__).resolve().parents[2] / "apps" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def test_paused_excludes_exactly_the_unserved_cities(monkeypatch):
    """`SERVED_CITIES` 한 곳이 단일 출처다 — 슬러그를 손으로 적지 않는다."""
    import app.data.measured_pages as mp

    monkeypatch.setattr(mp, "SERVED_CITIES", frozenset({"seoul"}))
    paused = qp._paused()

    expected = {slug for slug, hub in qp.ALL_HUBS.items()
                if getattr(hub, "city", "seoul") != "seoul"}
    assert paused == expected
    assert paused, "경기 거점이 등재돼 있으므로 비면 판정이 안 돈 것이다"
    # 서울 거점은 한 곳도 빠지지 않는다 — 빠지면 있는 일이 없는 것처럼 보인다.
    assert not any(getattr(qp.ALL_HUBS[s], "city", "seoul") == "seoul" for s in paused)


def test_resuming_a_city_puts_its_hubs_back(monkeypatch):
    """도시 재개는 `SERVED_CITIES` 에 도시 id 를 되넣는 것으로 그 도시 거점을 되살린다.

    2026-10-26 부터 예외가 하나 있다 — 추후 확장 과제(`PageHub.deferred`: 계획상가·단일시설)는
    도시가 서빙돼도 계속 빠진다(거점 단위 판단). 그 밖의 거점은 전부 돌아와야 한다.
    """
    import app.data.measured_pages as mp

    monkeypatch.setattr(mp, "SERVED_CITIES", frozenset({"seoul", "paju"}))
    paused = qp._paused()

    paju_paused = {s for s in paused if getattr(qp.ALL_HUBS[s], "city", "") == "paju"}
    assert all(getattr(qp.ALL_HUBS[s], "deferred", "") for s in paju_paused), paju_paused
    assert any(not getattr(qp.ALL_HUBS[s], "deferred", "")
               for s in qp.ALL_HUBS if getattr(qp.ALL_HUBS[s], "city", "") == "paju"
               and s not in paused)
    assert any(getattr(qp.ALL_HUBS[s], "city", "") == "goyang" for s in paused)


def test_deferred_hubs_stay_paused_even_in_a_served_city():
    """추후 확장 과제 거점은 서빙 도시 안에서도 쿼터 대상에서 빠진다(2026-10-26 결정)."""
    paused = qp._paused()
    deferred = {s for s, h in qp.ALL_HUBS.items() if getattr(h, "deferred", "")}
    assert deferred, "보류 표기가 사라졌다 — 결정이 바뀌었는지 확인할 것"
    assert deferred <= paused


def test_unreadable_decision_excludes_nothing(monkeypatch):
    """판단을 못 읽으면 아무것도 빼지 않는다 — 서울 잔여까지 조용히 사라지면 안 된다."""
    monkeypatch.setitem(sys.modules, "app.data.measured_pages", None)

    assert qp._paused() == set()


def test_unseen_buildings_counts_new_storefront_buildings_only():
    """점포 스냅샷의 건물 중 대장 행이 없는 것만 센다 — 사무실형 업종·429 강등 규칙은 수집기와 같다."""
    import importlib
    qp = importlib.import_module("scripts.quota_preflight")
    stores = [
        {"bldMngNo": "A", "indsLclsNm": "음식"},
        {"bldMngNo": "B", "indsLclsNm": "소매"},
        {"bldMngNo": "C", "indsLclsNm": "부동산"},      # 사무실형 — 수집기도 그룹에서 뺀다
        {"bldMngNo": "", "indsLclsNm": "음식"},          # 건물관리번호 없음
        {"bldMngNo": "D", "indsLclsNm": "음식"},
    ]
    rows = [{"bdMgtSn": "A", "capacity_method": "floor_ouln"},
            {"bdMgtSn": "D", "capacity_method": "rate_limited"}]   # 강등은 완료가 아니다
    assert qp.unseen_buildings(stores, rows) == 2       # B · D
    assert qp.unseen_buildings([], rows) == 0
