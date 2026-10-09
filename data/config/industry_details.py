"""사업자 세부 업종 계약. 원천 소분류의 완전 일치만 집계·실험 라벨로 쓴다.

source_names는 로컬 상가정보 Gold의 inds_scls 실측 어휘다. 전시·공연은
그 모집단에 없어 빈 목록으로 남긴다. UI 선택 가능과 추천 가능은 별개다.
"""
from __future__ import annotations


def _item(key: str, parent: str, label: str, family: str,
          names: tuple[str, ...], needs: str) -> dict:
    return dict(key=key, parent=parent, label=label, family=family,
                source_names=list(names), evidence_needed=needs)


DETAILS = [
    _item("bar_cooking", "bar", "요리 주점", "seats", ("요리 주점",), "야간·주말 소비, 좌석 회전율, 주류·식재료 원가"),
    _item("bar_beer", "bar", "생맥주 전문점", "seats", ("생맥주 전문",), "야간 소비, 좌석 회전율, 객단가"),
    _item("bar_entertainment", "bar", "유흥 주점", "seats", ("일반 유흥 주점", "무도 유흥 주점"), "영업 형태·입점 가능 여부, 인력·시설 비용"),
    _item("beauty_hair", "beauty", "미용실", "appointments", ("미용실",), "시술 시간, 작업대·직원 수, 예약률·재방문"),
    _item("beauty_nail", "beauty", "네일숍", "appointments", ("네일숍",), "시술 시간, 예약률, 재료비·인건비"),
    _item("beauty_skin", "beauty", "피부 관리실", "appointments", ("피부 관리실",), "시술 시간, 예약률, 장비·인건비"),
    _item("fashion_clothes", "fashion", "의류", "retail", ("기타 의류 소매업", "여성 의류 소매업", "남성 의류 소매업", "유아용 의류 소매업", "한복 소매업"), "고객층, 할인·반품, 매입원가·재고 회전"),
    _item("fashion_shoes", "fashion", "신발", "retail", ("신발 소매업",), "구매 건수, 객단가, 할인·반품·재고"),
    _item("fashion_bags", "fashion", "가방", "retail", ("가방 소매업",), "구매 건수, 객단가, 매입원가·재고"),
    _item("fashion_accessories", "fashion", "액세서리·잡화", "retail", ("액세서리/잡화 소매업", "시계/귀금속 소매업"), "구매 건수, 객단가, 상품별 원가"),
    _item("education_subject", "education", "입시·교과학원", "tuition", ("입시·교과학원",), "과목·학령인구, 정원·재원생, 교습비·강사비"),
    _item("education_language", "education", "외국어학원", "tuition", ("외국어학원",), "대상 연령, 정원·재원생, 수강료·강사비"),
    _item("education_art", "education", "미술학원", "tuition", ("미술학원",), "학령인구, 정원·재원생, 재료비·강사비"),
    _item("education_music", "education", "음악학원", "tuition", ("음악학원",), "강의실·시간표, 정원·재원생, 장비·강사비"),
    _item("education_vocational", "education", "직업·자격 교육", "tuition", ("기타 기술/직업 훈련학원", "컴퓨터 학원", "전문자격/고시학원"), "과정 기간, 월 환산 수강료, 충원율·강사비"),
    _item("education_study", "education", "독서실·스터디 카페", "membership", ("독서실/스터디 카페",), "좌석 수, 월 환산 이용료·이용률"),
    _item("fitness_gym", "fitness", "헬스장", "membership", ("헬스장",), "유효 회원 수·재등록, 월 귀속 회비, 장비·환불"),
    _item("fitness_studio", "fitness", "요가·필라테스", "tuition", ("요가/필라테스 학원",), "수업 정원·시간표, 월 귀속 수강료, 강사비·환불"),
    _item("fitness_golf", "fitness", "골프 연습장", "appointments", ("골프 연습장",), "타석 수·이용 시간, 이용률, 장비 유지비"),
    _item("fitness_sports", "fitness", "라켓·구기 시설", "appointments", ("테니스장", "당구장", "볼링장", "탁구장", "스쿼시/라켓볼장"), "시설별 예약 시간, 수용량, 장비·시설 비용"),
    _item("leisure_pc", "fitness", "PC방", "appointments", ("PC방",), "좌석·시간당 이용료, 이용률·장비·전기료"),
    _item("leisure_karaoke", "fitness", "노래방", "appointments", ("노래방",), "방 수·시간당 이용료, 이용률·시설 비용"),
    _item("lodging_hotel", "lodging", "호텔·리조트", "rooms", ("호텔/리조트",), "객실 점유율·판매단가, 계절성·예약 수수료·청소비"),
    _item("lodging_motel", "lodging", "여관·모텔", "rooms", ("여관/모텔",), "숙박 판매 기준 객실 수·점유율·단가, 대실은 별도 분석"),
    _item("lodging_pension", "lodging", "펜션", "rooms", ("펜션",), "객실 수·점유율·단가, 성수기·비수기"),
    _item("lodging_monthly", "lodging", "기숙사·고시원", "membership", ("기숙사/고시원",), "방 수·월 이용료·입주율, 관리 비용"),
    _item("lodging_other", "lodging", "기타 숙박", "rooms", ("그 외 기타 숙박업", "캠핑/글램핑"), "숙박 유형·판매 단위, 점유율·단가·운영비"),
    _item("culture_performance", "culture", "공연장", "tickets", (), "KOPIS 시설·공연 연결, 좌석·회차·유료 관객·제작비"),
    _item("culture_exhibition", "culture", "전시장·팝업 대관", "rental", (), "시설 목록, 대관 가능일·계약 단가, 설치·운영비"),
    _item("culture_gallery", "culture", "갤러리·작품 판매", "commission", (), "갤러리 목록, 작품 판매액·판매 수수료·전시 비용"),
]
BY_KEY = {i["key"]: i for i in DETAILS}
BY_SOURCE = {name: i["key"] for i in DETAILS for name in i["source_names"]}
assert len(BY_SOURCE) == sum(len(i["source_names"]) for i in DETAILS), "중복 업종 사상"


def classify(source_name: str) -> str | None:
    """상호·부분문자열로 추측하지 않고 실측 소분류를 대응한다."""
    return BY_SOURCE.get(source_name.strip())
