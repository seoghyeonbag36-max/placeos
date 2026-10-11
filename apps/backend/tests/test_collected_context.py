"""새 Gold의 출처·공간 단위·결측·안전한 링크 계약을 검증한다."""
import json
from pathlib import Path
from datetime import date
from app.services import collected_context, platform_profile, events

ROOT = Path(__file__).resolve().parents[3]


def test_collected_context_all_served_hubs_have_safe_evidence():
    from tests.test_districts import SEOUL_DISTRICT_IDS
    for slug in SEOUL_DISTRICT_IDS:
        data = collected_context.for_district(slug)
        assert data is not None, slug
        for item in data["online"]["items"]:
            assert item["link"].startswith(("https://", "http://"))
            assert item["query"].startswith("서울 ")
            assert "?" not in item["query"]
            assert "description" not in item
        assert "소득이 아닙니다" in data["consumption"]["note"]


def test_consumption_matches_official_administrative_rows_without_aggregation():
    folder = ROOT / "data/bronze/pppp_api_followup/2026-10-11/133957/seoul_consumption"
    if not folder.exists():
        import pytest
        pytest.skip("로컬 Bronze 원본은 배포하지 않는다")
    rows = {}
    for path in folder.glob("*.json"):
        for row in json.loads(path.read_text(encoding="utf-8"))["VwsmAdstrdNcmCnsmpW"]["row"]:
            rows[(row["ADSTRD_CD"], str(row["STDR_YYQU_CD"]))] = row
    data = collected_context.for_district("garosugil")
    assert data["consumption"]["districts"]
    for district in data["consumption"]["districts"]:
        source = rows[(district["code"], district["quarter"])]
        assert district["total_won"] == source["EXPNDTR_TOTAMT"]
        assert district["name"] == source["ADSTRD_CD_NM"]


def test_missing_collected_gold_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(collected_context, "_PATH", tmp_path / "missing.json")
    assert collected_context.for_district("garosugil") is None


def test_profile_serves_evidence_and_tour_zero_does_not_erase_cultural_events():
    assert platform_profile.identity("garosugil")["collected"] is not None
    gold = json.loads(collected_context._PATH.read_text(encoding="utf-8"))
    assert gold["tourapi"]["rows"] == 0
    source = json.loads(events._EVENTS_JSON.read_text(encoding="utf-8"))
    assert source["as_of"] == date(2026, 10, 11).isoformat()
    assert sum(map(len, source["districts"].values())) > 0
