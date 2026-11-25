"""Platform 인스타그램 Gold (2026-11-22) — 공식 Graph API 해시태그 집계만 · 연결 전에도 대표 해시태그를 싣는다 · 유료 상품에 싣지 않는다.

아래 거점 값은 테스트 전용 합성값이다(실제 인스타 수치 아님).
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services import instagram_context, platform_profile

ROOT = Path(__file__).resolve().parents[3]


def _write(tmp_path: Path, monkeypatch, hubs: dict, connected: bool = True) -> None:
    path = tmp_path / "platform_instagram.json"
    path.write_text(json.dumps({"built_at": "2026-11-22T00:00:00+00:00", "source": "합성 출처", "connected": connected,
                                "api_version": "v27.0", "window": "최근 24시간", "stale_after_days": 30,
                                "target_n": len(hubs), "collected_n": 0, "hubs": hubs}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(instagram_context, "_PATH", path)
    instagram_context._cache.clear()


def test_committed_gold_lists_every_seoul_hub_with_a_hashtag():
    from tests.test_districts import SEOUL_DISTRICT_IDS
    gold = json.loads(instagram_context._PATH.read_text(encoding="utf-8"))
    assert set(SEOUL_DISTRICT_IDS) <= set(gold["hubs"]), "서울 서빙 거점은 모두 대표 해시태그를 가진다"
    for slug, hub in gold["hubs"].items():
        assert hub["hashtag"] and not hub["hashtag"].startswith("#"), slug
        assert hub["status"] in {"collected", "pending", "no_hashtag", "error"}, slug
        if hub["status"] != "collected":
            assert "recent_24h" not in hub, slug          # 수집 전에 수치를 지어 싣지 않는다
    for key in ("caption", "permalink", "username", "media_url"):
        assert key not in json.dumps(gold, ensure_ascii=False), key   # 계정·본문·링크는 싣지 않는다


def test_for_district_merges_hub_values_with_global_meta(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, {"garosugil": {"hashtag": "가로수길", "status": "collected", "recent_24h": 42,
                                                 "collected_at": "2026-11-22T00:00:00+00:00", "shared_with": []}})
    got = instagram_context.for_district("garosugil")
    assert got["recent_24h"] == 42 and got["connected"] is True and got["window"] == "최근 24시간"
    assert got["source"] == "합성 출처" and got["api_version"] == "v27.0"
    assert instagram_context.for_district("nowhere") is None


def test_missing_gold_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(instagram_context, "_PATH", tmp_path / "missing.json")
    instagram_context._cache.clear()
    assert instagram_context.for_district("garosugil") is None


def test_platform_profile_carries_instagram_and_cites_it_only_when_collected(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, {"garosugil": {"hashtag": "가로수길", "status": "pending", "shared_with": []}}, connected=False)
    ident = TestClient(app).get("/api/v1/commercial-districts/garosugil/platform").json()["identity"]
    assert ident["instagram"]["hashtag"] == "가로수길" and ident["instagram"]["status"] == "pending"
    assert ident["instagram"]["connected"] is False
    assert "인스타그램" not in ident["source"]                     # 수집 전에는 출처로 적지 않는다
    _write(tmp_path, monkeypatch, {"garosugil": {"hashtag": "가로수길", "status": "collected", "recent_24h": 3,
                                                 "collected_at": "2026-11-22T00:00:00+00:00", "shared_with": []}})
    assert "인스타그램 공식 API" in platform_profile.identity("garosugil")["source"]


def test_paid_products_do_not_read_instagram():
    """Meta 플랫폼 약관 §3.a.iv — 플랫폼 데이터(집계·가공 포함 §12.l)를 팔지 않는다. 유료 리포트·광고·가격 경로는 인스타 모듈을 읽지 않는다."""
    services = ROOT / "apps/backend/app/services"
    for name in ("owner_diagnosis.py", "direct_purchases.py", "direct_pricing.py", "direct_admin.py"):
        text = (services / name).read_text(encoding="utf-8")
        assert "instagram" not in text.lower(), name
