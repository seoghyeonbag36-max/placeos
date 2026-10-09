"""테스트 데이터는 합성이다. 실측 소분류 대응과 중복/결손 처리만 검증한다."""
from data.config.industry_details import classify
from data.pipelines.build_industry_detail import normalize, aggregate


def test_specific_industries_do_not_leak_to_parent_word_matches():
    assert classify("요가/필라테스 학원") == "fitness_studio"
    assert classify("미술학원") == "education_art"
    assert classify("독서실/스터디 카페") == "education_study"
    assert classify("요리 주점") == "bar_cooking"
    assert classify("주류 소매업") is None
    assert classify("예술품 소매업") is None  # 갤러리라고 단정할 수 없다


def test_store_ids_deduplicate_but_colocated_stores_remain():
    row = dict(bizesId="a", lat=37.5, lon=127, indsSclsNm="네일숍")
    result = aggregate(normalize([row, row, {**row, "bizesId": "b"}]))
    assert result["sample_n"] == 2
    assert result["counts"]["beauty_nail"] == 2
    assert result["duplicate_n"] == 1


def test_conflicting_ids_invalid_coordinates_and_unknown_sources_are_not_filled():
    row = dict(bizesId="a", lat=37.5, lon=127, indsSclsNm="네일숍")
    result = aggregate(normalize([row, {**row, "indsSclsNm": "미용실"},
                                 {**row, "bizesId": "b", "lat": float("nan")},
                                 {**row, "bizesId": ""}]))
    assert result["sample_n"] == 0
    assert result["conflicting_ids_n"] == 1
    assert result["invalid_n"] == 2
    assert result["counts"]["culture_performance"] is None
