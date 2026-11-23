"""고양·파주 전용 진입로(2026-11-23) — `/goyang-paju` 는 프론트의 범위 쿼리로 보낸다. 프론트 정적 마운트(`/`)에 가려지면 404 가 된다."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_goyang_paju_path_redirects_to_scope_query():
    for path in ("/goyang-paju", "/goyang-paju/"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 307, path
        assert r.headers["location"] == "/?region=goyang-paju", path


def test_scope_entry_is_not_part_of_the_api_schema_and_health_still_works():
    assert "/goyang-paju" not in client.get("/openapi.json").json()["paths"]
    assert client.get("/health").json()["status"] == "ok"
