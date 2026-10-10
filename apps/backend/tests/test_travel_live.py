"""교통 실호출 계약. PLACEOS_LIVE_TRAVEL=1일 때 외부 조회 2회를 수행한다."""
import asyncio
import os

import pytest

from app.core.config import settings
from app.schemas.travel import TravelRequest
from app.services.travel import get_travel_times


@pytest.mark.skipif(os.getenv("PLACEOS_LIVE_TRAVEL") != "1", reason="교통 실호출은 opt-in입니다.")
def test_travel_live_both_providers_return_estimates():
    assert settings.kakao_mobility_api_key.strip(), "KAKAO_MOBILITY_API_KEY가 필요합니다."
    assert settings.odsay_api_key.strip(), "ODSAY_API_KEY가 필요합니다."
    # 서울역 → 강남역 좌표 질의. 예상 수치 자체는 고정하지 않는다.
    request = TravelRequest(origin={"lat": 37.5547, "lng": 126.9707},
                            destination={"lat": 37.4979, "lng": 127.0276})
    result = asyncio.run(get_travel_times(request))
    assert len(result.results) == 2
    for item in result.results:
        assert item.status == "ok", f"{item.provider}: {item.status}"
        assert item.duration_seconds is not None and item.duration_seconds > 0
        assert item.source == "provider_estimate"
