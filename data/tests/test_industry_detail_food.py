"""추가 선택 업종은 원천 대응 전 실측 경쟁점으로 취급하지 않는다."""
from data.config.industry_details import BY_KEY


def test_restaurant_and_daily_business_options_have_no_invented_sources() -> None:
    for key in ("restaurant_korean", "restaurant_japanese", "restaurant_chinese", "restaurant_western",
                "cafe_coffee", "cafe_bakery", "retail_grocery", "service_laundry"):
        item = BY_KEY[key]
        assert item["label"]
        assert item["family"] in {"seats", "retail", "appointments"}
        assert item["source_names"] == []
