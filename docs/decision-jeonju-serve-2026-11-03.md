# 전주 5개 거점 공개

2026-11-03 사용자 지시 「화면에 모두 공개할 것」에 따라 전주동부·전주서부·서부신시가지·한옥마을·송천동을 모두 공개한다.

`ACTIVE_CITIES`와 `SERVED_CITIES`에 전주를 함께 추가한다. Platform 지역 묶음은 전주로 분리하며 Page·Posting·Program은 기존 공개 API와 진입로를 사용한다. 건물 마스터·공실·앵커 산출물은 변경하지 않는다.

수집된 Bronze/Silver에서 전주 층 정보·점포 요약을 만들고 지도 외곽선과 R-ONE 시계열에 전주 항목을 추가한다. 임대료가 없는 서부신시가지는 빈 상태를 보존한다. 리뷰·행사·모델 점수를 만들지 않는다.

통과 조건: `test_city_registry.py`, `test_active_cities_match_serving.py`, `test_jeonju_expansion.py`, `test_renewal_gold.py`, `districtMapModel.test.ts`, 프론트 빌드·린트와 운영 API·브라우저에서 전주 5곳 공개 확인.
