"""저장한 결과 (2026-10-06 · /auth/results) — Posting 계산·Program 생성 결과를 사용자가 고른 것만 남긴다.

종전에는 결과가 화면 상태에만 있어 새로고침·탭 종료에 사라졌다(docs/finding-project-review-4roles-2026-10-06.md §2-4).

## 여기서 고정하는 계약

  ① 저장 → 목록(최신 먼저) → 삭제가 왕복한다. 없는 id 삭제는 404.
  ② **본인 것만** 보인다 — 다른 사용자의 결과는 목록에 없고 지우려 해도 404(존재를 안 흘린다).
  ③ JWT 사용자만 쓴다. 자격증명 없음·조직 API 키는 401.
  ④ 사업 정보 저장과 결과 저장이 **서로를 지우지 않는다**(같은 JSON 행에 산다).
  ⑤ 보관 상한을 넘으면 오래된 것부터 지운다. 한 건이 너무 크면 422. 종류는 posting·program 뿐.
  ⑥ 탈퇴하면 결과도 함께 지워진다(사업 정보 행 삭제와 같은 경로).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.models.auth import BusinessWorkspace
from app.services import business_workspace

client = TestClient(app)
V1 = "/api/v1"
PASSWORD = "hunter2hunter"

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
_Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _override():
    s = _Session()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _db():
    Base.metadata.create_all(bind=_engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    Base.metadata.drop_all(bind=_engine)


def _auth(email: str = "founder@example.com") -> dict[str, str]:
    r = client.post(f"{V1}/auth/signup", json={"org_name": "결과 저장 시험", "email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


POSTING = {"kind": "posting", "title": "가로수길 1F · 카페", "districtId": "garosugil",
           "payload": {"input": {"unit_id": "vu-1", "industry_type": "카페"},
                       "result": {"scenarios": {"value": {"payback_months": 31}}}}}
PROGRAM = {"kind": "program", "title": "제철 오마카세 가오픈", "districtId": "yeonnam",
           "payload": {"plan": {"item": "제철 오마카세", "signals": [{"name": "일 방문객 수"}]}}}


def test_save_list_delete_round_trip():
    h = _auth()
    first = client.post(f"{V1}/auth/results", json=POSTING, headers=h)
    assert first.status_code == 201, first.text
    second = client.post(f"{V1}/auth/results", json=PROGRAM, headers=h).json()
    assert {"id", "createdAt"} <= second.keys() and second["payload"] == PROGRAM["payload"]

    listed = client.get(f"{V1}/auth/results", headers=h).json()
    assert [r["title"] for r in listed] == [PROGRAM["title"], POSTING["title"]], "최신 것이 앞에 와야 한다"

    assert client.delete(f"{V1}/auth/results/{first.json()['id']}", headers=h).json() == {"ok": True}
    assert [r["title"] for r in client.get(f"{V1}/auth/results", headers=h).json()] == [PROGRAM["title"]]
    assert client.delete(f"{V1}/auth/results/{first.json()['id']}", headers=h).status_code == 404


def test_results_are_private_per_user():
    a, b = _auth("a@example.com"), _auth("b@example.com")
    saved = client.post(f"{V1}/auth/results", json=POSTING, headers=a).json()
    assert client.get(f"{V1}/auth/results", headers=b).json() == []
    assert client.delete(f"{V1}/auth/results/{saved['id']}", headers=b).status_code == 404
    assert len(client.get(f"{V1}/auth/results", headers=a).json()) == 1


def test_requires_a_signed_in_user_not_an_org_api_key():
    h = _auth()
    assert client.get(f"{V1}/auth/results").status_code == 401
    assert client.post(f"{V1}/auth/results", json=POSTING).status_code == 401
    key = client.post(f"{V1}/auth/api-keys", json={"name": "연동"}, headers=h).json()["key"]
    assert client.get(f"{V1}/auth/results", headers={"X-API-Key": key}).status_code == 401


def test_profile_and_results_do_not_erase_each_other():
    h = _auth()
    # 사업 정보 없이도 결과를 남길 수 있고, 그때 사업 정보는 "unset" 이다.
    client.post(f"{V1}/auth/results", json=POSTING, headers=h)
    assert client.get(f"{V1}/auth/workspace", headers=h).json()["status"] == "unset"

    profile = {"status": "set", "profile": {"goal": "start", "industryKey": "cafe", "homeDistrictId": None}}
    assert client.post(f"{V1}/auth/workspace", headers=h, json=profile).status_code == 200
    assert len(client.get(f"{V1}/auth/results", headers=h).json()) == 1, "사업 정보 저장이 결과를 지웠다"

    client.post(f"{V1}/auth/results", json=PROGRAM, headers=h)
    ws = client.get(f"{V1}/auth/workspace", headers=h).json()
    assert ws["status"] == "set" and ws["profile"]["industryKey"] == "cafe", "결과 저장이 사업 정보를 바꿨다"
    assert "results" not in ws, "사업 정보 응답에 결과가 섞여 나간다"


def test_cap_drops_the_oldest(monkeypatch):
    monkeypatch.setattr(business_workspace, "MAX_RESULTS", 3)
    h = _auth()
    for i in range(5):
        assert client.post(f"{V1}/auth/results", json={**POSTING, "title": f"계산 {i}"}, headers=h).status_code == 201
    assert [r["title"] for r in client.get(f"{V1}/auth/results", headers=h).json()] == ["계산 4", "계산 3", "계산 2"]


@pytest.mark.parametrize("bad", [
    {**POSTING, "kind": "memo"},                                   # 종류는 posting·program 뿐
    {**POSTING, "title": ""},
    {**POSTING, "payload": {"blob": "가" * 30_000}},              # 한글 3바이트 × 3만 ≈ 88KB > 64KB
    {**POSTING, "owner": "someone-else"},                          # 모르는 필드
])
def test_invalid_results_are_rejected(bad):
    assert client.post(f"{V1}/auth/results", json=bad, headers=_auth()).status_code == 422


def test_account_deletion_removes_saved_results():
    h = _auth()
    client.post(f"{V1}/auth/results", json=POSTING, headers=h)
    uid = client.get(f"{V1}/auth/me", headers=h).json()["user_id"]
    assert client.delete(f"{V1}/auth/me", headers=h).status_code == 200
    with _Session() as db:
        assert db.execute(select(BusinessWorkspace).filter_by(user_id=uid)).scalar_one_or_none() is None
    again = _auth()                                   # 같은 이메일로 다시 가입해도 이전 결과는 없다
    assert client.get(f"{V1}/auth/results", headers=again).json() == []
