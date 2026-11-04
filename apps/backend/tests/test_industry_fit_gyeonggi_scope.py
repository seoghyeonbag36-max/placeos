"""경기 순위의 비교 범위와 모델 미수록 지역을 실제 공개 목록과 대조한다."""
from app.services import business_fit, districts, industry_recommend


def test_gyeonggi_scope_includes_every_public_city_without_inventing_scores():
    business_fit._cache.clear()
    response = business_fit.fit_by_district("restaurant")
    expected = {p["id"] for p in districts.PAGES if districts.page_city(p).sido == "경기도"}
    rows = {r["district_id"]: r for r in response["districts"] if r["district_id"] in expected}
    assert set(rows) == expected
    scope = next(s for s in response["ranking_scopes"] if s["region"] == "경기도")
    assert scope["scope"] == "served_hubs" and scope["region_census"] is False
    assert scope["public_n"] == len(expected)
    assert scope["ranked_n"] + scope["unranked_n"] == len(expected)
    assert set(scope["unranked_ids"]) == {did for did, r in rows.items() if r["fit_rank"] is None}
    assert len(scope["public_cities"]) > 2
    assert {"고양", "파주", "수원", "성남", "용인"} <= set(scope["public_cities"])
    means = business_fit._all_means()
    for did in expected - means.keys():
        assert rows[did]["fit"] is None and rows[did]["fit_rank"] is None


def test_gyeonggi_rank_is_one_model_and_descending_over_the_actual_covered_population():
    business_fit._cache.clear()
    response = business_fit.fit_by_district("restaurant")
    page_by = {p["id"]: p for p in districts.PAGES}
    groups = [g for g in response["rank_groups"] if g.get("key", "").endswith("/경기도")]
    assert len(groups) == 1
    members = [r for r in response["districts"] if r["rank_group"] == groups[0]["key"]]
    assert all(districts.page_city(page_by[r["district_id"]]).sido == "경기도" for r in members)
    assert len({r["fit_model"] for r in members}) == 1
    assert [r["fit_rank"] for r in members] == list(range(1, len(members) + 1))
    assert [r["fit"] for r in members] == sorted((r["fit"] for r in members), reverse=True)
    assert industry_recommend._load() is not None


def test_validated_gyeonggi_model_ranks_every_public_hub():
    business_fit._cache.clear()
    response = business_fit.fit_by_district("restaurant")
    expected = {p["id"] for p in districts.PAGES if districts.page_city(p).sido == "경기도"}
    rows = [r for r in response["districts"] if r["district_id"] in expected]
    assert all(r["fit_rank"] is not None and r["fit_model"] == "industry-gnn-gyeonggi" for r in rows)
    assert {r["fit_rank"] for r in rows} == set(range(1, len(expected) + 1))
