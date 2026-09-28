"""KPI③ 표본의 내부·테스트 조직 제외 — `services/kpi_scope` (2026-09-28, 결정 (a)+(b)).

잠그는 성질:
1. 이름이 `[내부]` 로 시작하는 조직(a)과 `KPI_EXCLUDE_ORG_IDS` 에 적힌 조직(b)은
   `active_orgs` 와 PMF 표본에서 **둘 다** 빠진다 — 두 규칙은 합집합이다.
2. 빠진 조직은 숨지 않는다: `excluded_orgs` 에 수로, `excluded` 에 이름·id 앞 8자·사유로 잡힌다.
3. 응답에 전체 org id·이메일이 새로 실리지 않는다(화면용 필드는 id 앞 8자뿐).
4. 환경변수에 적혔는데 DB 에 없는 id 는 조용히 지나가지 않는다(`env_ids_unmatched`).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.services import kpi_scope, pmf

V1 = "/api/v1"
_ANALYSIS_PATH = f"{V1}/commercial-districts"

_engine = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _fresh_schema(monkeypatch):
    monkeypatch.delenv(kpi_scope.EXCLUDE_ENV, raising=False)
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=_engine)


client = TestClient(app)


@pytest.fixture()
def admin(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "t")
    return {"X-Admin-Token": "t"}


def _org(email: str, org_name: str) -> tuple[dict, str]:
    """가입 → (인증 헤더, org id)."""
    token = client.post(f"{V1}/auth/signup", json={
        "org_name": org_name, "email": email, "password": "hunter2hunter"}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    return h, client.get(f"{V1}/auth/me", headers=h).json()["org"]["id"]


def _use_and_answer(h: dict, score: int = 10, pay: str = "yes") -> None:
    """분석 1회 + 피드백 1건. 피드백 POST 도 추적 라우터라 접근은 조직당 2건이 쌓인다."""
    assert client.get(_ANALYSIS_PATH, headers=h).status_code == 200
    assert client.post(f"{V1}/feedback", json={"nps_score": score, "would_pay": pay},
                       headers=h).status_code == 201


# ── 규칙 (a) 이름 접두사 ────────────────────────────────────────────────────────

def test_name_prefixed_org_leaves_usage_and_pmf_and_is_reported(admin) -> None:
    pilot, _ = _org("p@acme.com", "Acme 프랜차이즈")
    internal, internal_id = _org("me@placeos.kr", "[내부] 창업자 시험")
    _use_and_answer(pilot, score=10)
    _use_and_answer(internal, score=0)

    u = client.get(f"{V1}/admin/usage", headers=admin).json()
    assert u["active_orgs"] == 1, "내부 조직이 파일럿 수에 섞였다"
    assert internal_id not in u["by_org"]
    assert u["total_accesses"] == 2 and u["excluded_accesses"] == 2
    assert u["excluded_orgs"] == 1
    assert u["excluded"] == [{"id_prefix": internal_id[:8], "name": "[내부] 창업자 시험",
                              "reasons": ["name_prefix"]}]

    p = client.get(f"{V1}/admin/pmf", headers=admin).json()
    assert p["n_orgs"] == 1 and p["detractors"] == 0, "내부 조직의 0점이 NPS 에 섞였다"
    assert p["excluded_orgs"] == 1
    assert p["excluded"][0]["id_prefix"] == internal_id[:8]


def test_prefix_must_lead_the_name() -> None:
    """이름 중간의 `[내부]` 나 전각 괄호는 규칙이 아니다 — 규칙이 흐려지면 실고객이 빠진다."""
    assert kpi_scope.is_internal_name("[내부] 시험")
    assert kpi_scope.is_internal_name("  [내부]시험")
    assert not kpi_scope.is_internal_name("Acme [내부]")
    assert not kpi_scope.is_internal_name("［내부］ 시험")
    assert not kpi_scope.is_internal_name("내부 시험")


# ── 규칙 (b) 환경변수 ──────────────────────────────────────────────────────────

def test_env_listed_org_is_excluded_even_with_a_normal_name(admin, monkeypatch) -> None:
    """이미 있는 조직은 이름을 바꿀 길이 없다 — id 로 뺀다."""
    pilot, _ = _org("p@acme.com", "Acme")
    legacy, legacy_id = _org("verify@acme.com", "계정층 검증 08-28")
    _use_and_answer(pilot)
    _use_and_answer(legacy)

    dashed = f"{legacy_id[:8]}-{legacy_id[8:12]}-{legacy_id[12:16]}-{legacy_id[16:20]}-{legacy_id[20:]}"
    monkeypatch.setenv(kpi_scope.EXCLUDE_ENV, f" {dashed.upper()} , ")

    u = client.get(f"{V1}/admin/usage", headers=admin).json()
    assert u["active_orgs"] == 1 and u["excluded_orgs"] == 1
    assert u["excluded"][0]["reasons"] == ["env"]
    p = client.get(f"{V1}/admin/pmf", headers=admin).json()
    assert p["n_orgs"] == 1 and p["excluded_orgs"] == 1


def test_both_rules_union_and_one_org_counts_once(admin, monkeypatch) -> None:
    a, a_id = _org("a@x.com", "[내부] A")
    b, b_id = _org("b@x.com", "B 검증용")
    c, _ = _org("c@x.com", "C 파일럿")
    for h in (a, b, c):
        _use_and_answer(h)
    monkeypatch.setenv(kpi_scope.EXCLUDE_ENV, f"{a_id},{b_id}")

    u = client.get(f"{V1}/admin/usage", headers=admin).json()
    assert u["active_orgs"] == 1
    assert u["excluded_orgs"] == 2, "두 규칙에 모두 걸린 조직이 두 번 세어졌다"
    reasons = {e["id_prefix"]: e["reasons"] for e in u["excluded"]}
    assert reasons[a_id[:8]] == ["name_prefix", "env"]
    assert reasons[b_id[:8]] == ["env"]


def test_unknown_env_id_is_surfaced_not_silently_ignored(admin, monkeypatch) -> None:
    pilot, _ = _org("p@acme.com", "Acme")
    _use_and_answer(pilot)
    monkeypatch.setenv(kpi_scope.EXCLUDE_ENV, "deadbeef" * 4)

    u = client.get(f"{V1}/admin/usage", headers=admin).json()
    assert u["active_orgs"] == 1 and u["excluded_orgs"] == 0
    assert u["exclusion_rules"]["env_ids_configured"] == 1
    assert u["exclusion_rules"]["env_ids_unmatched"] == ["deadbeef"]


# ── 보고 형식 ──────────────────────────────────────────────────────────────────

def test_excluded_counts_only_orgs_present_in_that_sample(admin) -> None:
    """피드백 없이 접근만 한 내부 조직은 usage 에서만 빠진 것으로 센다."""
    pilot, _ = _org("p@acme.com", "Acme")
    internal, _ = _org("me@x.com", "[내부] 접근만")
    _use_and_answer(pilot)
    assert client.get(_ANALYSIS_PATH, headers=internal).status_code == 200

    assert client.get(f"{V1}/admin/usage", headers=admin).json()["excluded_orgs"] == 1
    assert client.get(f"{V1}/admin/pmf", headers=admin).json()["excluded_orgs"] == 0


def test_all_excluded_pmf_stays_insufficient_and_says_why(admin) -> None:
    internal, _ = _org("me@x.com", "[내부] 혼자")
    _use_and_answer(internal)
    p = client.get(f"{V1}/admin/pmf", headers=admin).json()
    assert p["n_orgs"] == 0 and p["verdict"] == "표본부족"
    assert p["excluded_orgs"] == 1 and "내부·테스트 조직 1곳" in p["note"]


def test_pmf_threshold_is_untouched() -> None:
    """이 변경은 표본에서 무엇을 빼는가만 정한다 — 판정 기준은 그대로."""
    assert pmf.MIN_RESPONSES == 5 and pmf.NPS_TARGET == 30.0 and pmf.PAY_TARGET_PCT == 30.0


def test_usage_rows_for_screen_carry_name_and_id_prefix_only(admin) -> None:
    pilot, pilot_id = _org("secret-person@acme.com", "Acme")
    _use_and_answer(pilot)
    u = client.get(f"{V1}/admin/usage", headers=admin).json()
    assert u["orgs"] == [{"id_prefix": pilot_id[:8], "name": "Acme", "accesses": 2}]
    assert "secret-person" not in str(u) and "secret-person" not in str(
        client.get(f"{V1}/admin/pmf", headers=admin).json()), "이메일이 관리자 응답에 실렸다"
