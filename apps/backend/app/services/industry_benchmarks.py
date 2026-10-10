"""공식 통계의 운영 참고값. 원문에 없는 가정·비용은 만들지 않는다."""
from __future__ import annotations

from typing import Any

SOURCE_URL = "https://www.mafra.go.kr/bbs/home/798/595247/download.do"
SOURCE_TITLE = "2025 외식업체 경영실태 조사 통계보고서"

# 표 25(p.49), 표 29(p.57), 표 67(p.133)의 전국·전체 운영형태 평균.
# 요리 주점은 단독 집계가 없으므로 기타 주점업의 참고값임을 별도로 밝힌다.
ROWS = {
    "bar_cooking": ("기타 주점업", 166, 29.7, 27.7, 21166.0, "broader_category"),
    "bar_beer": ("생맥주 전문점", 76, 37.0, 27.9, 20029.7, "exact_category"),
}


def benchmark(detail_key: str, input_fields: list[dict]) -> dict[str, Any]:
    """정의가 맞는 세 항목만 반환하고 모든 결측의 사유를 공개한다."""
    row = ROWS.get(detail_key)
    values: dict[str, dict[str, Any]] = {}
    if row:
        category, sample_n, seats, days, price_won, match = row
        for key, raw, value, table, page, conversion in (
            ("capacity", seats, round(seats), "표 29", 57, "정수 입력을 위해 좌석 수 평균을 반올림"),
            ("days", days, round(days), "표 25", 49, "30일 기준 월 영업일 평균을 정수로 반올림"),
            ("price", price_won, price_won / 10000, "표 67", 133, "원 → 만원 환산"),
        ):
            values[key] = dict(value=value, original_value=raw, table=table, page=page, conversion=conversion)
        source = dict(title=SOURCE_TITLE, url=SOURCE_URL, survey_year=2025,
                      published_on="2026-02-28", geography="전국", category=category,
                      sample_n=sample_n, category_match=match)
    else:
        source = None
    return dict(values=values, source=source,
                note=("요리 주점 단독 평균은 없습니다. 기타 주점업의 참고 평균이며 해당 점포의 실측값이 아닙니다."
                      if detail_key == "bar_cooking" else "전국 업종 평균 참고값이며 해당 점포의 실측값이 아닙니다."),
                unavailable={f["key"]: ("이 세부 업종에 대응하는 검증된 평균 자료가 없습니다." if not row else
                             "입력 정의에 맞는 평균을 확인하지 못했습니다. 실제 운영·계약 조건을 직접 입력하세요.")
                             for f in input_fields if f["key"] not in values})
