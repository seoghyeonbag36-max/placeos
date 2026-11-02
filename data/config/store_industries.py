"""상가정보 소분류 코드 → 사업자가 고르는 12업종 사상.

빌더(`build_stores_lite`)와 서빙(`services/nearby_stores`)이 같은 표를 쓴다 — 서빙 이미지에는
`data/pipelines` 가 없고 `data/config` 만 실린다. 표준 라이브러리 밖을 import 하지 않는다.
"""
from __future__ import annotations

# 사업자가 고르는 12업종(`business_fit.INDUSTRIES`)으로의 사상. 그쪽 needles 는 카카오 라벨용이라 상가정보
# 소분류에 그대로 못 쓴다 — 코드로 고정한다. 여기 없는 소분류는 12업종 밖이다(부동산·사무 서비스 등).
INDUSTRY_LABELS: dict[str, str] = {
    "cafe": "카페·디저트", "restaurant": "음식점", "bar": "술집", "beauty": "미용·네일",
    "clinic": "병·의원", "pharmacy": "약국", "convenience": "편의점·생활", "fashion": "옷·잡화",
    "education": "학원·교육", "fitness": "운동·여가", "lodging": "숙박", "culture": "전시·공연",
}
_INDUSTRY_EXACT = {
    "I21201": "cafe", "I21001": "cafe", "I21008": "cafe", "G20507": "cafe",
    "G21501": "pharmacy",
    "G20405": "convenience", "G20404": "convenience", "S20901": "convenience", "S20902": "convenience",
    "S20701": "beauty", "S20702": "beauty", "S20703": "beauty",
    "G20901": "fashion", "G20902": "fashion", "G20903": "fashion", "G20905": "fashion", "G20907": "fashion",
    "G20910": "fashion", "G20911": "fashion", "G21503": "fashion", "G21602": "fashion", "G21701": "fashion",
    "P10603": "fitness", "R10406": "fitness", "R10407": "fitness", "R10202": "education",
    "G21301": "culture", "G21801": "culture",
    "I20701": "",      # 구내식당 — 창업 업종이 아니다
}


def industry_of(scls_code: str | None) -> str | None:
    """상가정보 소분류 코드 → 12업종 key. 12업종 밖이면 None."""
    code = str(scls_code or "")
    if code in _INDUSTRY_EXACT:
        return _INDUSTRY_EXACT[code] or None
    if code.startswith("I211"):
        return "bar"
    if code.startswith("I2"):
        return "restaurant"
    if code.startswith("I1"):
        return "lodging"
    if code.startswith("Q1"):
        return "clinic"
    if code.startswith("P1"):
        return "education"
    if code.startswith("R103"):
        return "fitness"
    return None
