"""테스트 공통 설정.

## 기본 스위트는 외부 API 를 치지 않는다

크레딧 충전(2026-08-01) 전까지 `LLM_API_KEY` 는 사실상 죽은 키였고, LLM 경로는 항상
폴백으로 흘러 테스트가 네트워크를 타지 않았다. 키가 살아나자 `/marketing/{id}` 를
호출하는 테스트들이 **실호출로 바뀌었다** — 매번 12~17초가 걸리고 크레딧이 나가며,
실제로 `test_postings_and_marketing` 이 응답을 기다리다 프로세스째 멎었다.

개별 테스트가 각자 `monkeypatch.setattr(settings, "llm_api_key", "")` 하는 방식은
빠뜨리기 쉽다(실제로 test_districts.py 가 빠뜨려 있었다). 그래서 여기서 전역으로 끈다.

실호출 검증은 `test_llm_live.py` 가 `PLACEOS_LIVE_LLM=1` opt-in 으로만 수행한다 —
그 경우 이 픽스처는 키를 건드리지 않는다.
"""
from __future__ import annotations

import os

import pytest

# SPACEOS_* 는 2026-09-12 PlaceOS 개명 전 이름 — 쓰던 셸을 깨지 않으려 폴백으로 남긴다
_LIVE = (os.getenv("PLACEOS_LIVE_LLM") or os.getenv("SPACEOS_LIVE_LLM")) == "1"


@pytest.fixture(autouse=True)
def _no_network_llm(monkeypatch):
    """LLM 키를 비워 기본 스위트가 외부 API 를 치지 못하게 한다.

    테스트가 본문에서 다시 `llm_api_key` 를 세팅하는 것은 그대로 동작한다
    (autouse 픽스처가 먼저 돌고, 본문의 monkeypatch 가 나중에 덮어쓴다).
    """
    if _LIVE:
        return
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "", raising=False)


@pytest.fixture(autouse=True)
def _no_network_tiles(monkeypatch):
    """트윈 도로 타일(tiles.openfreemap.org)을 기본 스위트에서 치지 않는다 (2026-11-06).

    `/buildings/{id}/twin` 은 응답마다 `services/twin_roads` 로 타일을 받는다. 막지 않으면 트윈을 부르는 테스트가
    네트워크 상태에 따라 느려지거나(타임아웃 5초) 결과가 흔들린다. 타일이 필요한 시험은 tests/fixtures/twin_roads 의
    실제 타일을 `fetch=` 로 넘긴다. 실패 뒤 대기(back-off) 상태도 테스트마다 비운다.
    """
    from app.services import twin_roads

    def _offline(x: int, y: int, z: int = twin_roads.Z) -> bytes:
        raise OSError("tests: tile network disabled")
    monkeypatch.setattr(twin_roads, "fetch_tile", _offline)
    monkeypatch.setattr(twin_roads, "_last_fail", 0.0)


@pytest.fixture(autouse=True)
def _no_network_ledger(monkeypatch):
    """트윈의 건축물대장 실시간 조회(apis.data.go.kr)를 기본 스위트에서 치지 않는다 (2026-11-09).

    키가 있는 환경(로컬 .env)에서 트윈 테스트가 실제 건축HUB 를 부르면 쿼터를 쓰고 결과가 흔들린다.
    대장 응답이 필요한 시험은 `summarise` 에 행을 직접 넘긴다. 캐시 · 실패 대기도 테스트마다 비운다.
    """
    from app.services import building_ledger_live as L

    def _offline(op, jibun, key):
        raise OSError("tests: ledger network disabled")
    monkeypatch.setattr(L, "_fetch", _offline)
    monkeypatch.setattr(L, "_last_fail", 0.0)
    L._cache.clear()


@pytest.fixture(autouse=True)
def _no_network_energy(monkeypatch):
    """건물에너지 실시간 조회도 기본 스위트에서 치지 않는다(2026-11-09)."""
    from app.services import building_energy_live as E

    def _offline(op, params, key, base=None):
        raise OSError("tests: energy network disabled")
    monkeypatch.setattr(E, "_get", _offline)
    monkeypatch.setattr(E, "_last_fail", 0.0)
    E._cache.clear()


@pytest.fixture(autouse=True)
def _no_network_store_units(monkeypatch):
    """트윈의 상가정보 실시간 조회도 기본 스위트에서 치지 않는다(2026-11-09) — Gold(stores_lite)로 내려간다."""
    from app.services import store_units as S

    def _offline(lat, lng, key, radius=60):
        raise OSError("tests: stores network disabled")
    monkeypatch.setattr(S, "_fetch_live", _offline)
    monkeypatch.setattr(S, "_last_fail", 0.0)
    S._cache.clear()


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """요청량 카운터(services/rate_limit)를 테스트마다 비운다.

    카운터는 프로세스 전역이다. 비우지 않으면 앞 테스트들의 가입이 쌓여 뒤 테스트가 가입 한도(429)에
    걸리고, 그 실패는 순서를 바꾸면 사라지는 종류라 원인을 찾기 어렵다(2026-10-06).
    """
    from app.services import rate_limit
    rate_limit.reset()
    yield
    rate_limit.reset()


@pytest.fixture
def signed_in():
    """로그인한 요청의 헤더 — `POST /marketing/generate` 의 LLM 경로는 로그인 호출에만 열린다.

    LLM 경로를 보는 테스트는 이 픽스처를 받아 `headers=signed_in` 으로 부른다. 익명은
    LLM 키가 있어도 스텁이다(test_program_llm_gate.py).

    SQLite 인메모리에 실제로 가입시켜 토큰을 받는다 — 신원 해석(`get_optional_principal`)을
    목으로 바꾸면 "로그인하면 열린다"는 계약 자체를 재지 못한다. `get_db` 오버라이드는
    **이전 값을 복원**한다: test_auth.py 가 모듈 최상단에서 전역으로 걸어 두므로, 여기서
    지워 버리면 뒤에 도는 계정층 테스트가 진짜 DB 를 찾는다.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.db import Base, get_db
    from app.main import app

    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _db
    try:
        resp = TestClient(app).post("/api/v1/auth/signup", json={
            "org_name": "Gate Test Org", "email": "gate@example.com",
            "password": "hunter2hunter"})
        assert resp.status_code == 201, resp.text
        yield {"Authorization": f"Bearer {resp.json()['access_token']}"}
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        Base.metadata.drop_all(bind=engine)


# ── 출력 계약 헬퍼 (2026-08-23 · 2026-09-17 signals 추가) ────────────────────
# 온라인(모객)과 오프라인(자리·연계)은 대칭이 아니라 필요한 속성이 다르고, 검증
# 지표(signals)는 또 다른 모양이다(schemas/marketing.py). 테스트들이 검증하는 것은
# 대개 ha_guard 의 **규칙**이지 계약 자체가 아니므로, 계약이 요구하는 필드는 여기서
# 기본값으로 채워 본문이 규칙에만 집중하게 한다.
# 계약 자체는 test_program_output_split.py 가 본다.

def _perf(channel, content, rationale, target="20~30대 직장인",
          budget_share=100, kpi="저장 수"):
    from app.schemas.marketing import LLMPerformancePlan
    return LLMPerformancePlan(channel=channel, content=content, rationale=rationale,
                              target=target, budget_share=budget_share, kpi=kpi)


def _act(channel, content, rationale, timing="주말 오전",
         actors=None, mode="own"):
    from app.schemas.marketing import LLMActivationPlan
    return LLMActivationPlan(channel=channel, content=content, rationale=rationale,
                             # `or` 를 쓰면 actors=[] 를 기본값이 덮어써서 "주체 없음"을
                             # 검증할 수 없다. None 만 기본값으로 친다.
                             timing=timing,
                             actors=["상인회"] if actors is None else actors, mode=mode)


def _signal(name="일 방문객 수", method="입장 카운터 일별 기록",
            target="일 60명", decision="누적 300명 미만이면 가설을 기각한다"):
    """검증 지표 1건. 기본값은 **검사를 통과하는** 모양이다 — 목표선에 숫자가 있고
    기각 조건이 적혀 있다. 그 둘이 빠진 경우는 본문에서 일부러 비워 검증한다."""
    from app.schemas.marketing import LLMValidationSignal
    return LLMValidationSignal(name=name, method=method, target=target, decision=decision)


# ── 직거래 연결 층(2026-11-18) 공용 환경 ─────────────────────────────────────
# 계정층 테스트와 같은 방식(SQLite 인메모리 + get_db 오버라이드 · 이전 값 복원)에 외래키를 켠다 — 프로덕션(Neon)은
# 외래키를 보므로 삭제 순서가 틀리면 여기서 먼저 운다(test_auth_account_delete.py 와 같은 이유).

DIRECT_ADMIN_TOKEN = "direct-admin-token"
DIRECT_REGISTRY = "1101-2026-012345"


@pytest.fixture
def direct_env(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import app.models.direct  # noqa: F401  — 직거래 표를 메타데이터에 올린다
    from app.core.db import Base, get_db
    from app.main import app

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _db
    monkeypatch.setenv("ADMIN_TOKEN", DIRECT_ADMIN_TOKEN)
    client = TestClient(app)

    class _Env:
        pass

    env = _Env()
    env.client = client
    env.session = factory
    env.admin = {"X-Admin-Token": DIRECT_ADMIN_TOKEN}
    env.base = "/api/v1/direct"

    def signup(email: str) -> dict:
        r = client.post("/api/v1/auth/signup", json={"org_name": "직거래 테스트", "email": email,
                                                     "password": "hunter2hunter"})
        assert r.status_code == 201, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def listing_body(**overrides) -> dict:
        body = dict(district_id="garosugil", address="서울 강남구 신사동 000-0", floor=2, unit_label="201호",
                    area_m2=66.0, use_type="제1종 근린생활시설", ledger_use="", deal_type="lease",
                    deposit_manwon=3000, monthly_rent_manwon=250, maintenance_manwon=20, rent_free_months=2,
                    min_term_months=24, preferred_industries=["education"], excluded_industries=["bar"],
                    description="테스트 전용 합성 매물")
        body.update(overrides)
        return body

    def publish(owner: dict, **overrides) -> str:
        r = client.post(f"{env.base}/listings", headers=owner, json=listing_body(**overrides))
        assert r.status_code == 201, r.text
        lid = r.json()["id"]
        r = client.post(f"{env.base}/listings/{lid}/submit", headers=owner,
                        json={"relation": "owner", "registry_number": DIRECT_REGISTRY, "owner_name": "홍길동"})
        assert r.status_code == 200, r.text
        pending = client.get("/api/v1/admin/direct/verifications", headers=env.admin).json()["items"]
        vid = next(v["id"] for v in pending if v["listing_id"] == lid)
        r = client.post(f"/api/v1/admin/direct/verifications/{vid}", headers=env.admin, json={"decision": "verified"})
        assert r.status_code == 200, r.text
        return lid

    env.signup = signup
    env.listing_body = listing_body
    env.publish = publish
    try:
        yield env
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        Base.metadata.drop_all(bind=engine)
