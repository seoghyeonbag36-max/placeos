"""공식 통계 전사·환산·결측 계약. 통계 원문 표의 수치를 검증한다."""
from app.services import industry_detail


def test_cooking_reference_discloses_category_and_rounding():
    row = next(i for i in industry_detail.options() if i["key"] == "bar_cooking")["benchmark"]
    assert row["source"]["category"] == "기타 주점업"
    assert row["source"]["category_match"] == "broader_category"
    assert row["source"]["sample_n"] == 166
    assert row["source"]["survey_year"] == 2025
    assert row["values"]["capacity"]["original_value"] == 29.7
    assert row["values"]["capacity"]["value"] == 30
    assert row["values"]["days"]["original_value"] == 27.7
    assert row["values"]["days"]["value"] == 28
    assert row["values"]["price"]["value"] == 2.1166
    assert row["values"]["price"]["page"] == 133
    assert "단독 평균은 없습니다" in row["note"]


def test_beer_uses_its_own_statistics_without_cost_fallback():
    row = next(i for i in industry_detail.options() if i["key"] == "bar_beer")["benchmark"]
    assert row["source"]["category_match"] == "exact_category"
    assert row["source"]["sample_n"] == 76
    assert row["values"]["capacity"]["value"] == 37
    assert row["values"]["price"]["value"] == 2.00297
    assert set(row["unavailable"]) == {"cycles", "utilization", "variable_cost_rate", "rent", "fixed_cost", "investment"}
    out = industry_detail.calculate("bar_beer", {k: v["value"] for k, v in row["values"].items()})
    assert out["status"] == "needs_inputs"
    assert out["monthly_revenue"] is None


def test_unsupported_industries_do_not_receive_bar_averages():
    for option in industry_detail.options():
        row = option["benchmark"]
        assert set(row["values"]) | set(row["unavailable"]) == {f["key"] for f in option["fields"]}
        if option["key"] not in ("bar_cooking", "bar_beer"):
            assert row["source"] is None
            assert row["values"] == {}
