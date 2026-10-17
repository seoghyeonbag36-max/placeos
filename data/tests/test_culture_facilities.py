"""시설 유형 원문 → 전시·공연 업종 대응. 합성 입력이며 원천 응답을 호출하지 않는다."""
from data.config import culture_facilities as cf
from data.config.industry_details import BY_KEY


def test_performance_gallery_and_art_museum_are_one_industry():
    s = cf.SOURCE_SEOUL_CULTURE_SPACE
    assert cf.classify(s, "공연장") == cf.INDUSTRY_KEY
    assert cf.classify(s, "미술관/갤러리") == cf.INDUSTRY_KEY
    m = cf.SOURCE_MCST_DIRECTORY
    assert cf.classify(m, "미술관") == cf.INDUSTRY_KEY


def test_arts_centers_are_included_under_both_source_vocabularies():
    # 같은 문예회관이 서울 문화공간에서는 문화예술회관, 총람에서는 문예회관 시트다
    assert cf.classify(cf.SOURCE_SEOUL_CULTURE_SPACE, "문화예술회관") == cf.INDUSTRY_KEY
    assert cf.classify(cf.SOURCE_MCST_DIRECTORY, "문예회관") == cf.INDUSTRY_KEY


def test_types_outside_the_decision_are_not_filled():
    s = cf.SOURCE_SEOUL_CULTURE_SPACE
    for raw in ("도서관", "박물관/기념관", "문화원", "기타"):
        assert cf.classify(s, raw) is None
    assert cf.classify(cf.SOURCE_MCST_DIRECTORY, "박물관") is None


def test_exact_match_only_no_substring_or_unknown_source_guess():
    s = cf.SOURCE_SEOUL_CULTURE_SPACE
    assert cf.classify(s, "공연장 ") == cf.INDUSTRY_KEY      # 공백만 정리
    assert cf.classify(s, "소극장") is None                  # 이름·부분일치로 추측하지 않는다
    assert cf.classify(s, "미술관") is None                  # 서울 어휘는 '미술관/갤러리' 한 덩어리
    assert cf.classify("kakao_local", "공연장") is None      # 저장 불가·미등록 원천
    assert cf.classify(s, None) is None  # type: ignore[arg-type]


def test_industry_key_is_the_culture_parent_in_the_detail_contract():
    assert BY_KEY["culture_performance"]["parent"] == cf.INDUSTRY_KEY
    assert BY_KEY["culture_gallery"]["parent"] == cf.INDUSTRY_KEY
