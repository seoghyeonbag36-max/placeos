"""카카오 Local 후보 탐색. 기존 Gold 측정 셀만 사용하며 상권 경계를 지어내지 않는다."""
from __future__ import annotations
import math
from datetime import datetime, timezone
import httpx
from app.core.config import settings
from app.services import districts, gold_vacancy

# 검색어·카카오 분류의 명시적 대응. 미등록 업종을 다른 업종으로 대체하지 않는다.
# 값은 검색 규칙이며, 관측 데이터·추천 점수가 아니다.
MAPPINGS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "cafe": ("카페", "카페", ("카페",)),
    "restaurant": ("음식점", "음식점", ("음식점",)),
    "bar": ("술집", "술집", ("술집",)),
    "bar_cooking": ("요리 주점", "요리주점", ("요리주점", "일본식주점")),
    "bar_beer": ("생맥주 전문점", "맥주", ("호프", "맥주")),
    # 실제 Local 응답에서 확인한 분류명: 음식점 > 술집 > 일본식주점.
    "izakaya": ("이자카야", "이자카야", ("일본식주점",)),
    "beauty_hair": ("미용실", "미용실", ("미용실",)),
    "beauty_nail": ("네일숍", "네일", ("네일",)),
    "beauty_skin": ("피부 관리실", "피부관리", ("피부관리",)),
    "fashion_clothes": ("의류", "의류", ("의류",)),
    "fashion_shoes": ("신발", "신발", ("신발",)),
    "fashion_bags": ("가방", "가방", ("가방",)),
    "education_language": ("외국어학원", "외국어학원", ("외국어학원",)),
    "education_art": ("미술학원", "미술학원", ("미술학원",)),
    "education_music": ("음악학원", "음악학원", ("음악학원",)),
    "education_study": ("독서실·스터디 카페", "스터디카페", ("스터디카페", "독서실")),
    "fitness_gym": ("헬스장", "헬스", ("헬스",)),
    "fitness_studio": ("요가·필라테스", "필라테스", ("필라테스", "요가")),
    "leisure_pc": ("PC방", "PC방", ("PC방",)),
    "leisure_karaoke": ("노래방", "노래방", ("노래방",)),
    "lodging_hotel": ("호텔·리조트", "호텔", ("호텔", "리조트")),
    "lodging_motel": ("여관·모텔", "모텔", ("모텔", "여관")),
    "culture_gallery": ("갤러리·작품 판매", "갤러리", ("갤러리", "화랑")),
}


class SearchError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status, self.message = status, message
        super().__init__(message)


def options() -> list[dict[str, str]]:
    return [{"key": key, "label": item[0]} for key, item in MAPPINGS.items()]


def normalize(rows: list[dict], cells: list[dict], center: list[float],
              allowed: tuple[str, ...]) -> list[dict]:
    """측정 범위·분류·좌표를 확인하고 장소 ID로 중복 제거한다."""
    found: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            lat, lng = float(row["y"]), float(row["x"])
            ident, name, category = str(row["id"]), row["place_name"], row["category_name"]
        except (KeyError, ValueError, TypeError):
            continue
        if not ident.isdigit() or not isinstance(name, str) or not name or not isinstance(category, str):
            continue
        if not math.isfinite(lat) or not math.isfinite(lng):
            continue
        if not any(word in category for word in allowed):
            continue
        if not any(c["lat"] <= lat <= c["lat"] + c["dlat"] and
                   c["lng"] <= lng <= c["lng"] + c["dlng"] for c in cells):
            continue
        # 장소 ID로 공식 상세 URL을 만든다. 제공사 응답의 임의 URL을 전달하지 않는다.
        found.setdefault(ident, dict(id=ident, name=name, category=category,
            address=row.get("road_address_name") or row.get("address_name") or "",
            phone=row.get("phone") or None, lat=lat, lng=lng,
            place_url=f"https://place.map.kakao.com/{ident}",
            distance_m=round(districts._dist_m(lat, lng, center[0], center[1]))))
    return sorted(found.values(), key=lambda p: (p["distance_m"], p["id"]))


async def search(district_id: str, industry_key: str) -> dict:
    district = districts.PAGES_BY_ID.get(district_id)
    if district is None:
        raise SearchError(404, "알 수 없는 Platform입니다.")
    mapping = MAPPINGS.get(industry_key)
    if mapping is None:
        raise SearchError(422, "현재 검색 미지원 업종입니다.")
    if not settings.kakao_rest_api_key.strip():
        raise SearchError(503, "점포 검색 API 키가 설정되지 않았습니다.")
    measured = gold_vacancy.build_cells(district_id, district["grid"])
    cells = measured.get("cells", []) if measured else []
    if not cells:
        raise SearchError(422, "이 Platform의 측정 범위가 없어 검색할 수 없습니다.")
    rect = ",".join(str(v) for v in (min(c["lng"] for c in cells), min(c["lat"] for c in cells),
        max(c["lng"] + c["dlng"] for c in cells), max(c["lat"] + c["dlat"] for c in cells)))
    rows: list[dict] = []
    truncated = False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 클릭 한 번에 최대 3페이지. 제공사 검색 제한을 전수 조사로 표현하지 않는다.
            for page in range(1, 4):
                response = await client.get("https://dapi.kakao.com/v2/local/search/keyword.json",
                    headers={"Authorization": f"KakaoAK {settings.kakao_rest_api_key}"},
                    params={"query": mapping[1], "rect": rect, "x": district["center"][1],
                            "y": district["center"][0], "sort": "distance", "size": 15, "page": page})
                if response.status_code == 429:
                    raise SearchError(429, "카카오 검색 호출 한도를 초과했습니다.")
                if response.status_code in (401, 403):
                    raise SearchError(503, "카카오 검색 키 또는 API 권한을 확인해야 합니다.")
                response.raise_for_status()
                payload = response.json()
                rows.extend(payload["documents"])
                meta = payload["meta"]
                truncated = not meta["is_end"] or meta["total_count"] > meta["pageable_count"]
                if meta["is_end"]:
                    break
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise SearchError(502, "점포 검색 제공사 응답을 받지 못했습니다. 다시 시도해 주세요.") from exc
    return dict(district_id=district_id, industry_key=industry_key, source="kakao_local",
        scope="measured_cells", queried_at=datetime.now(timezone.utc).isoformat(), truncated=truncated,
        note=f"검색어: {mapping[1]} · 기존 공실 측정 범위 안에서 검색된 후보입니다. 공식 상권 경계·전체 점포 목록이 아니며 현재 영업과 성공 여부는 확인하지 않았습니다.",
        places=normalize(rows, cells, district["center"], mapping[2]))
