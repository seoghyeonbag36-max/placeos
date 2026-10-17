"""전시·공연 업종의 시설 원천 대응 계약 (2026-10-16 결정).

결정: 공연장(문예회관·문화예술회관 포함)·갤러리·미술관은 **모두 하나의 전시·공연 업종**이다.
공연장/갤러리/미술관을 나누는 파생 유형은 만들지 않는다 — 원천 코드가 미술관/갤러리를 못 가르는
문제(이름 규칙으로 97행 분류 불능)가 통합으로 사라진다. 근거와 실측은
docs/finding-exhibit-performance-sources-2026-10-16.md.

원천의 유형 어휘는 **완전 일치**로만 대응한다(industry_details.classify 와 같은 원칙).
시설명 부분문자열로 추측하지 않는다.
"""
from __future__ import annotations

INDUSTRY_KEY = "culture"      # industry_details.DETAILS 의 parent
INDUSTRY_LABEL = "전시·공연"

SOURCE_SEOUL_CULTURE_SPACE = "seoul_culture_space"   # 서울 열린데이터광장 culturalSpaceInfo
SOURCE_MCST_DIRECTORY = "mcst_directory_2025"        # 문체부 전국 문화기반시설 총람

# culturalSpaceInfo.SUBJCODE 원문. 코드 값 그대로 쓴다.
SEOUL_CULTURE_SPACE_INCLUDED = (
    "공연장",
    "문화예술회관",     # 문예회관 — 같은 시설이 원천에 따라 공연장/기타로 갈려 통합으로 정리
    "미술관/갤러리",    # 코엑스전시장 같은 전시장도 이 코드에 들어 있다
)

# 총람 시트명(= 시설 종류). 박물관은 이번 결정 밖이다.
MCST_DIRECTORY_INCLUDED = ("문예회관", "미술관")

# 업종에서 뺀 유형 — 결정에 없어서 넣지 않은 것이지 영구 제외가 아니다.
#   도서관·박물관/기념관·문화원: 전시·공연 시설로 본다는 결정이 없었다.
#   기타: DDP·예술공장 등이 섞여 있어 유형을 알 수 없다(unresolved 로 남긴다).
_INCLUDED = {
    SOURCE_SEOUL_CULTURE_SPACE: frozenset(SEOUL_CULTURE_SPACE_INCLUDED),
    SOURCE_MCST_DIRECTORY: frozenset(MCST_DIRECTORY_INCLUDED),
}


def classify(source: str, raw_type: str) -> str | None:
    """원천과 유형 원문이 전시·공연 시설이면 INDUSTRY_KEY, 아니면 None."""
    included = _INCLUDED.get(source)
    if included is None or not isinstance(raw_type, str):
        return None
    return INDUSTRY_KEY if raw_type.strip() in included else None
