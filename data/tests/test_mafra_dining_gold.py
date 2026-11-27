"""gold/mafra_dining_2025.json(농식품부 2025 외식업체 경영실태 조사 · build_mafra_dining_2025.py) — 원문 표를 옮긴 값이
회계 항등식을 지키고, 메뉴 표가 응답 수 순이며, 업종 × 운영형태 교차 값을 담지 않는지 본다."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLD = json.loads((ROOT / "data" / "gold" / "mafra_dining_2025.json").read_text(encoding="utf-8"))
T = GOLD["tables"]
PARTS = ["food_cost", "labor", "rent", "tax", "family_labor", "owner_pay", "other_cost"]


def test_source_is_pinned_to_the_report_file():
    s = GOLD["source"]
    assert s["title"] == "2025 외식업체 경영실태 조사 통계보고서" and s["org"] == "농림축산식품부"
    assert len(s["pdf_sha256"]) == 64 and s["pdf_pages"] == 323
    assert s["sample_n"] == 3138


def test_every_row_keeps_the_accounting_identity():
    for row in T["sales"]["rows"]:
        g = lambda k: T[k]["rows"][row]["mean"]  # noqa: E731
        assert abs(g("sales") - g("opex") - g("profit")) <= 0.5, row
        assert abs(sum(g(k) for k in PARTS) - g("opex")) <= 0.5, row


def test_ownership_rows_split_the_whole_sample_and_no_cross_tab_exists():
    rows = T["open_days"]["rows"]
    assert rows["프랜차이즈"]["n"] + rows["비프랜차이즈"]["n"] == rows["■ 전체 ■"]["n"]
    for table in T.values():                                    # 행 이름은 업종 · 운영형태 · 전체 중 하나 — 「한식 프랜차이즈」 같은 교차 행은 없다
        assert not any("프랜차이즈" in r and r not in ("프랜차이즈", "비프랜차이즈") for r in table["rows"])


def test_plausible_ranges_and_units():
    for row, v in T["open_days"]["rows"].items():
        assert 20 <= v["mean"] <= 31, row
    for row, v in T["open_hours"]["rows"].items():
        assert 5 <= v["mean"] <= 16, row
    for row in T["sales"]["rows"]:
        rate = T["food_cost"]["rows"][row]["mean"] / T["sales"]["rows"][row]["mean"]
        assert 0.25 <= rate <= 0.6, row
    assert T["sales"]["unit"] == "만원/년" and T["avg_ticket"]["unit"] == "원"


def test_menu_tables_are_sorted_by_answers_and_carry_their_table_numbers():
    assert set(GOLD["menus"]) >= {"한식", "커피 전문점", "치킨 전문점", "김밥 및 기타 간이음식점업", "제과"}
    for name, m in GOLD["menus"].items():
        ns = [i["n"] for i in m["items"]]
        assert ns == sorted(ns, reverse=True), name
        assert 68 < m["table"] <= 86 and m["page"] > 0
        assert all(i["price"] > 0 for i in m["items"])
    assert GOLD["menus"]["커피 전문점"]["items"][0]["name"] == "커피"


def test_food_mix_rows_cover_every_row_and_sum_to_about_100():
    fm = GOLD["food_mix"]
    assert fm["table"] == 105 and len(fm["columns"]) == 9
    assert set(fm["rows"]) == set(T["open_days"]["rows"])
    for row, r in fm["rows"].items():
        assert len(r["values"]) == 9 and all(0 <= x <= 100 for x in r["values"]), row
        assert abs(sum(r["values"]) - 100) <= 1.5, row
    assert fm["rows"]["한식"]["n"] == T["open_days"]["rows"]["한식"]["n"]
