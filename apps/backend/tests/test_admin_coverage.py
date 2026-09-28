"""관리자 커버리지(`GET /admin/coverage`) — 서빙 거점과 보류 거점을 가른다.

2026-09-28 `#admin` 브라우저 실측에서 요약이 "거점 88곳"이었다. `coverage.json` 은 서빙
보류 도시(경기)의 거점에도 서 있어서, 파일을 전부 세면 서빙 81 + 보류 7 이 한 숫자로
합쳐졌다. 잠그는 성질:

1. 거점마다 `served` 가 붙고, 그 기준은 공개 API 가 내는 거점(`districts.PAGES_BY_ID`)이다.
2. `totals` 는 **서빙 거점만** 합산한다(보류 거점의 동수가 커버리지에 섞이지 않는다).
3. 보류 거점은 `held` 로 따로 센다 — 숨기지 않는다.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import admin as admin_api
from app.main import app
from app.services.districts import PAGES_BY_ID

client = TestClient(app)
URL = "/api/v1/admin/coverage"


@pytest.fixture()
def headers(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "t")
    return {"X-Admin-Token": "t"}


def _write(root, slug, shown, unknown, non_comm):
    d = root / slug
    d.mkdir()
    (d / "coverage.json").write_text(json.dumps({
        "slug": slug, "hub_name": slug, "tier": "Tier1", "built_at": "2026-09-28",
        "shown": shown, "excluded_unknown": unknown, "excluded_non_commercial": non_comm,
        "coverage_pct": None, "reference_vacancy_pct": None,
    }), encoding="utf-8")


def test_totals_count_only_served_hubs(tmp_path, monkeypatch, headers):
    served = sorted(PAGES_BY_ID)[:2]
    _write(tmp_path, served[0], 100, 10, 5)
    _write(tmp_path, served[1], 50, 30, 0)
    _write(tmp_path, "zz-held-hub", 999, 999, 999)          # 서빙 목록에 없는 거점
    assert "zz-held-hub" not in PAGES_BY_ID
    monkeypatch.setattr(admin_api, "_GOLD_DIR", tmp_path)

    body = client.get(URL, headers=headers).json()

    assert body["totals"] == {
        "hubs": 2, "shown": 150, "excluded_unknown": 40, "excluded_non_commercial": 5,
        "coverage_pct": round(150 / 195 * 100, 1),
    }
    assert body["held"] == {"hubs": 1, "slugs": ["zz-held-hub"]}
    by_slug = {h["slug"]: h for h in body["hubs"]}
    assert by_slug["zz-held-hub"]["served"] is False
    assert by_slug[served[0]]["served"] is True and by_slug[served[1]]["served"] is True
    # 서빙 거점이 먼저, 그 안에서는 대장 미확인이 많은 순
    assert [h["slug"] for h in body["hubs"]] == [served[1], served[0], "zz-held-hub"]


def test_real_gold_hub_count_matches_the_served_list(headers):
    """저장소 Gold 로 — 요약의 거점 수가 서빙 목록(공개 API)과 같은 집합에서 나온다."""
    body = client.get(URL, headers=headers).json()
    served = {h["slug"] for h in body["hubs"] if h["served"]}
    held = {h["slug"] for h in body["hubs"] if not h["served"]}
    assert served <= set(PAGES_BY_ID)
    assert not held & set(PAGES_BY_ID)
    assert body["totals"]["hubs"] == len(served)
    assert body["held"]["hubs"] == len(held)
    assert body["totals"]["hubs"] + body["held"]["hubs"] == len(body["hubs"])


def test_still_requires_the_admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "t")
    assert client.get(URL).status_code == 403
    assert client.get(URL, headers={"X-Admin-Token": "wrong"}).status_code == 403
