"""Proposal 「메뉴 설정」 업종 기준값(2026-11-26) — 출처가 있는 값만 · 원천 값을 그대로 환산 · 개인/가맹 구분을 지어내지 않는다."""
import json

from fastapi.testclient import TestClient

from app.main import app
from app.services import industry_benchmarks, menu_benchmarks as mb


def _by_key(key: str) -> dict:
    return next(c for c in mb.categories() if c["key"] == key)


def _value(cat: dict, key: str) -> dict | None:
    return next((v for v in cat["values"] if v["key"] == key), None)


def test_every_value_names_a_known_source_and_unit():
    src = mb.sources()
    for cat in mb.categories():
        for v in cat["values"]:
            assert v["source"] in src, (cat["key"], v)
            assert v["unit"] in {"만원", "원", "일", "%"}
            assert v["detail"]


def test_kosis_per_store_numbers_are_the_gold_totals_divided_by_stores_and_months():
    gold = json.loads(mb.KOSIS_GOLD.read_text(encoding="utf-8"))["industries"]
    for key, spec in mb.CATEGORIES.items():
        if not spec["kosis"]:
            continue
        row = gold[spec["kosis"]]
        cat = _by_key(key)
        expect = row["labor_mn"] * 100 / row["estab"] / 12
        assert _value(cat, "labor")["value"] == round(expect)
        assert _value(cat, "sales")["value"] == round(row["sales_mn"] * 100 / row["estab"] / 12)
        assert _value(cat, "labor_rate")["value"] == round(row["labor_mn"] / row["sales_mn"] * 100, 1)
        assert _value(cat, "profit_rate")["value"] == round((1 - row["opex_rate"]) * 100, 1)


def test_mafra_days_and_ticket_come_from_the_existing_transcription():
    korean = _by_key("restaurant_korean")
    _, _, _, days, price, _ = industry_benchmarks.ROWS["restaurant_korean"]
    assert _value(korean, "open_days")["raw"] == days and _value(korean, "open_days")["value"] == round(days)
    assert _value(korean, "avg_ticket")["value"] == round(price)
    assert "표 25" in _value(korean, "open_days")["detail"]
    cooking = _by_key("bar_cooking")
    assert any("기타 주점업" in n for n in cooking["notes"])           # 더 넓은 업종의 참고값이라고 밝힌다


def test_no_fabricated_ownership_split_or_missing_sources():
    out = mb.payload()
    assert out["ownership_split"]["available"] is False
    assert "전체 평균" in out["ownership_split"]["reason"]
    for cat in out["categories"]:
        assert not any(k in v for v in cat["values"] for k in ("independent", "franchise"))
        assert {m["key"] for m in cat["missing"]} >= {"menus", "food_cost_rate", "open_hours", "equipment"}
    snack = _by_key("restaurant_snack")                                  # 대응하는 원천 행이 없으면 값을 비워 두고 그렇다고 말한다
    assert snack["values"] == []
    assert any(m["key"] == "all" for m in snack["missing"])
    coffee = _by_key("cafe_coffee")
    assert _value(coffee, "open_days") is None                          # 원천에 없는 칸을 다른 업종 값으로 채우지 않는다
    assert any(m["key"] == "open_days" for m in coffee["missing"])


def test_endpoint_serves_the_payload():
    r = TestClient(app).get("/api/v1/ai/menu-benchmarks")
    assert r.status_code == 200
    body = r.json()
    assert [c["key"] for c in body["categories"]] == list(mb.CATEGORIES)
    assert set(body["sources"]) == {mb.KOSIS_ID, mb.MAFRA_ID}
