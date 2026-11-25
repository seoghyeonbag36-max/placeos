"""Page 빈 층 「창업 가능 등급 · 건물주 등록」(2026-11-25) — GET /commercial-districts/{id}/startup-fit.

고정하는 것:
- 모든 빈 층이 네 등급 중 하나를 받고, 이유가 비지 않는다. 추정 빈 층은 「여력 있음 · 가능」이 되지 않는다.
- 「여력 있음」은 기준선(서울 같은 가격대 평균 영업이익률) 이상이다 — 손으로 정한 임계값이 아니다.
- 건물주 등록은 게시 중 · 소유자 확인 매물(L3)만, 같은 건물 ID + 층에만 붙는다. 표가 없으면 「not_ready」(0 건이 아니다).
- 허가 판정이 아니라는 문구가 응답에 실린다.
아래 매물 주소 · 이름 · 번호는 테스트 전용 합성값이다(conftest.direct_env).
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import get_db
from app.main import app
from app.services import floor_vacancy, startup_fit

client = TestClient(app)
URL = "/api/v1/commercial-districts/{}/startup-fit"


def _empty_db():
    """직거래 표가 하나도 없는 DB — 프로덕션에 마이그레이션이 아직 안 들어간 상태와 같다."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _db():
        db = session()
        try:
            yield db
        finally:
            db.close()
    return _db


def _get(district: str, **params):
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _empty_db()
    try:
        return client.get(URL.format(district), params=params)
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous


def test_every_vacant_floor_gets_one_grade_with_reasons():
    r = _get("garosugil")
    assert r.status_code == 200, r.text
    body = r.json()
    units = body["units"]
    inventory = floor_vacancy.load("garosugil")["units"]
    assert len(units) == len(inventory) > 0
    assert sum(body["counts"].values()) == len(units)
    for u in units:
        assert u["grade"] in startup_fit.GRADES and u["grade_label"] == startup_fit.GRADE_LABEL[u["grade"]]
        assert u["reasons"], u["id"]
        if u["certainty"] == "probable":
            assert u["grade"] in ("B", "C"), "추정 빈 층을 「여력 있음 · 가능」으로 그리면 추정이 실측처럼 읽힌다"
        if u["grade"] == "C":
            assert any(x["tone"] == "hard" for x in u["reasons"])
        if u["grade"] == "B":
            assert any(x["tone"] == "soft" for x in u["reasons"]) and not any(x["tone"] == "hard" for x in u["reasons"])


def test_capacity_grade_is_measured_against_seoul_average_not_a_hand_threshold():
    units = _get("garosugil").json()["units"]
    plus = [u for u in units if any(x["code"] == "E_PLUS" for x in u["reasons"])]
    thin = [u for u in units if any(x["code"] == "E_THIN" for x in u["reasons"])]
    assert plus or thin
    for u in plus:   # 보이는 가격대가 실제로 서울 평균 이상이다
        assert u["best_margin_1f"] is not None and u["seoul_avg"] is not None
        assert u["best_margin_1f"] >= u["seoul_avg"] - 1e-4
    for u in units:
        if u["grade"] == "A1":
            assert any(x["code"] == "E_PLUS" for x in u["reasons"])
        if u["grade"] == "A2":
            assert any(x["code"] == "E_THIN" for x in u["reasons"])


def test_says_it_is_not_a_permit_decision():
    body = _get("garosugil").json()
    assert "허가 판정이 아니" in body["note"]
    assert "실제 호가 아님" in body["note"]


def test_owner_check_without_tables_is_not_ready_not_zero():
    body = _get("garosugil").json()
    assert body["owner_status"] == "not_ready"
    assert "0 건이 아닙니다" in body["owner_note"]
    assert body["owner_floors"] == 0


def test_building_filter_and_summary_mode():
    full = _get("garosugil").json()["units"]
    bid = next(u["building_id"] for u in full if u["building_id"])
    one = _get("garosugil", building_id=bid).json()["units"]
    assert one and all(u["building_id"] == bid for u in one)
    lean = _get("garosugil", detail="false").json()["units"]
    assert len(lean) == len(full) and all(u["reasons"] == [] for u in lean)


def test_unknown_district_is_404():
    assert _get("no-such-hub").status_code == 404


def test_ho_approximation_by_ledger_use_name():
    assert startup_fit.ho_approx("소매점", 50) == 3
    assert startup_fit.ho_approx("일반음식점", 50) == 4
    assert startup_fit.ho_approx("휴게음식점", 120) == 3 and startup_fit.ho_approx("휴게음식점", 320) == 4
    assert startup_fit.ho_approx("학원", 600) == 10
    # 1·2종을 이름으로 못 정하거나 처음 보는 이름이면 None — 점검이 「확인 필요」로 간다(지어내지 않는다)
    assert startup_fit.ho_approx("기타근린생활시설", 50) is None
    assert startup_fit.ho_approx("처음 보는 용도", 50) is None


def _vacant_floor(grade_in: tuple[str, ...]) -> dict:
    startup_fit.clear_cache()
    units = startup_fit.for_district("garosugil", None)["units"]
    return next(u for u in units if u["grade"] in grade_in and u["building_id"] and u["certainty"] == "confirmed")


def test_owner_listing_attaches_only_to_same_building_and_floor(direct_env):
    env = direct_env
    target = _vacant_floor(("A1", "A2", "B"))
    owner = env.signup("owner@example.com")
    lid = env.publish(owner, building_id=target["building_id"], floor=target["floor"], unit_label="101호")
    # 같은 건물 다른 층 · 확인 전 매물은 붙지 않는다
    env.publish(owner, building_id=target["building_id"], floor=target["floor"] + 40, address="서울 강남구 신사동 000-9")
    draft = env.client.post(f"{env.base}/listings", headers=owner,
                            json=env.listing_body(building_id=target["building_id"], floor=target["floor"])).json()["id"]

    body = env.client.get(URL.format("garosugil"), params={"building_id": target["building_id"]}).json()
    assert body["owner_status"] == "ready"
    hit = [u for u in body["units"] if u["floor"] == target["floor"]]
    assert hit and all([o["id"] for o in u["owner"]] == [lid] for u in hit)
    assert all(not u["owner"] for u in body["units"] if u["floor"] != target["floor"])
    assert draft not in str(body)
    assert "홍길동" not in str(body)                      # 소유자 정보는 싣지 않는다(L5)
    assert body["owner_floors"] == len(hit)
