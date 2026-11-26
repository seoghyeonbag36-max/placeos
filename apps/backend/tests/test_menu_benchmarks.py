"""Proposal 「메뉴 설정」 업종 기준값(2026-11-26) — 값은 Gold 를 그대로 환산 · 업종 × 운영형태 교차를 지어내지 않는다 ·
대표메뉴는 응답 수 순(판매 비중이 아님) · 원천 행이 없는 업종은 비워 두고 그렇다고 말한다."""
import json

from fastapi.testclient import TestClient

from app.main import app
from app.services import industry_benchmarks, menu_benchmarks as mb

GOLD = json.loads(mb.MAFRA_GOLD.read_text(encoding="utf-8"))
KOSIS = json.loads(mb.KOSIS_GOLD.read_text(encoding="utf-8"))["industries"]


def _cat(key: str) -> dict:
    return next(c for c in mb.categories() if c["key"] == key)


def _v(values: list[dict], key: str) -> dict | None:
    return next((v for v in values if v["key"] == key), None)


def _mean(table: str, row: str) -> float:
    return GOLD["tables"][table]["rows"][row]["mean"]


def test_every_value_names_a_known_source_and_unit():
    src = mb.sources()
    for cat in mb.categories():
        for v in cat["values"]:
            assert v["source"] in src, (cat["key"], v)
            assert v["unit"] in {"만원", "원", "일", "시간", "%"}
            assert v["detail"]


def test_report_values_are_the_gold_means_converted_without_new_numbers():
    for key, spec in mb.CATEGORIES.items():
        row = spec["mafra"]
        if not row:
            continue
        values = _cat(key)["values"]
        assert _v(values, "open_days")["raw"] == _mean("open_days", row)
        assert _v(values, "open_hours")["value"] == mb._r(_mean("open_hours", row), 1)
        assert _v(values, "food_cost_rate")["value"] == mb._r(_mean("food_cost", row) / _mean("sales", row) * 100, 1)
        assert _v(values, "labor_month")["value"] == mb._r(_mean("labor", row) / 12)          # 매출 · 비용 표는 연간 금액
        assert _v(values, "invest_kitchen")["value"] == mb._r(_mean("invest_kitchen", row))
        assert f"표 {GOLD['tables']['open_hours']['table']}" in _v(values, "open_hours")["detail"]


def test_report_agrees_with_the_earlier_hand_transcription():
    # services/industry_benchmarks.ROWS(표 25 · 67)는 이 보고서에서 먼저 손으로 옮긴 값이다 — PDF 에서 뽑은 값과 같아야 한다
    for detail_key, row in (("restaurant_korean", "한식"), ("bar_beer", "생맥주 전문점"), ("bar_cooking", "기타 주점업")):
        _cat_name, _n, _seats, days, price, _match = industry_benchmarks.ROWS[detail_key]
        assert _mean("open_days", row) == days
        assert _mean("avg_ticket", row) == price


def test_kosis_seoul_values_stay_separate_and_match_the_gold():
    for key, spec in mb.CATEGORIES.items():
        if not spec["kosis"]:
            continue
        row = KOSIS[spec["kosis"]]
        values = _cat(key)["values"]
        assert _v(values, "seoul_labor_month")["value"] == mb._r(row["labor_mn"] * 100 / row["estab"] / 12)
        assert _v(values, "seoul_sales_month")["value"] == mb._r(row["sales_mn"] * 100 / row["estab"] / 12)


def test_menus_are_top_answers_with_an_estimated_cost_rate_and_no_sales_share():
    coffee = _cat("cafe_coffee")["menus"]
    gold_items = GOLD["menus"]["커피 전문점"]["items"]
    assert [i["name"] for i in coffee["items"]] == [i["name"] for i in gold_items if i["n"] >= 2][:mb.MENU_TOP]
    assert coffee["items"][0] == {"name": gold_items[0]["name"], "n": gold_items[0]["n"], "price": gold_items[0]["price"]}
    assert all(a["n"] >= b["n"] for a, b in zip(coffee["items"], coffee["items"][1:]))
    assert coffee["cost_rate"]["value"] == mb._r(_mean("food_cost", "커피 전문점") / _mean("sales", "커피 전문점") * 100, 1)
    assert "판매 비중이 아니에요" in coffee["note"]
    assert not any("share" in i for i in coffee["items"])                                    # 판매 비중을 만들지 않는다
    assert _cat("restaurant_snack")["menus"]["table"] == GOLD["menus"]["김밥 및 기타 간이음식점업"]["table"]


def test_ownership_is_whole_industry_only_and_never_crossed_with_a_category():
    own = mb.ownership()
    assert own["available"] is True and own["scope"].startswith("외식업 전체")
    assert "업종 안에서" in own["note"]
    by = {g["key"]: g for g in own["groups"]}
    assert _v(by["franchise"]["values"], "open_days")["raw"] == _mean("open_days", "프랜차이즈")
    assert _v(by["independent"]["values"], "open_days")["raw"] == _mean("open_days", "비프랜차이즈")
    assert by["independent"]["n"] + by["franchise"]["n"] == GOLD["tables"]["open_days"]["rows"]["■ 전체 ■"]["n"]
    for cat in mb.categories():                                                                # 업종 값에 개인/가맹을 섞지 않는다
        assert not any(k in v["key"] for v in cat["values"] for k in ("franchise", "independent"))


def test_categories_without_a_source_row_stay_empty():
    other = _cat("restaurant_other")
    assert other["values"] == [] and other["menus"] is None
    assert any(m["key"] == "all" for m in other["missing"])
    assert any("기타 주점업" in n for n in _cat("bar_cooking")["notes"])
    assert any("김밥 및 기타 간이음식점업" in n for n in _cat("restaurant_snack")["notes"])


def test_endpoint_serves_the_payload():
    r = TestClient(app).get("/api/v1/ai/menu-benchmarks")
    assert r.status_code == 200
    body = r.json()
    assert [c["key"] for c in body["categories"]] == list(mb.CATEGORIES)
    assert set(body["sources"]) == {mb.KOSIS_ID, mb.MAFRA_ID}
    assert [g["key"] for g in body["ownership"]["groups"]] == ["independent", "franchise"]


def test_half_up_rounding_matches_the_report_reading():
    assert mb._r(28.5) == 29 and mb._r(27.4) == 27 and mb._r(10.65, 1) == 10.7
    franchise = next(g for g in mb.ownership()["groups"] if g["key"] == "franchise")
    days = _v(franchise["values"], "open_days")
    assert days["raw"] == 28.5 and days["value"] == 29                     # 가맹점 월 영업일 28.5일 → 29일
