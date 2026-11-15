"""후보의 공적 자료 조회. 자료가 없어도 입점 가능 여부를 만들어내지 않는다."""
from datetime import datetime, timezone

from app.schemas.candidate_review import CandidateReview, ReviewFact, ReviewSource
from app.services import building_floors, building_ledger_live, building_twin


def review(district: str, building_id: str, unit_id: str | None = None) -> CandidateReview | None:
    """등록된 건물·층만 조회한다. 대장 원천 기준일과 조회 시각은 별개다."""
    twin = building_twin.twin(district, building_id)
    if twin is None:
        return None
    floor = None
    if unit_id:
        floor = next((f for f in twin.get("floors", []) if f.get("unit_id") == unit_id), None)
        if floor is None:
            return None
    pnu = building_floors.pnu_of(building_id)
    ledger = building_ledger_live.ledger(pnu)
    status = str(ledger.get("status", "error"))
    title = ledger.get("title") or {}
    facts: list[ReviewFact] = []
    note = "대장 조회 결과를 받지 못했습니다. 공식 자료 또는 관할 기관에서 확인해 주세요."
    if status == "ok":
        if title.get("n_titles") != 1:
            note = "이 지번의 대장을 선택한 동에 확실히 연결할 수 없습니다. 대표 동의 수치를 이 후보에 적용하지 않습니다."
        else:
            note = "건축물대장 기록입니다. 현장 상태·입점 허가를 확인한 결과가 아닙니다."
            for key, label in (("strct", "건물 구조"), ("grnd", "지상 층수"), ("ugrnd", "지하 층수")):
                value = title.get(key)
                if value is not None:
                    facts.append(ReviewFact(label=label, value=str(value), scope="건물"))
            # 층은 동일한 후보의 unit_id로 연결된 번호만 사용한다.
            rows = ledger.get("floors") or {}
            level = floor.get("lv") if floor else None
            if level is not None:
                parts = (rows.get(str(level)) or {}).get("parts") or []
                for part in parts:
                    if part.get("purps"):
                        facts.append(ReviewFact(label="대장 용도", value=part["purps"] + (f" ({part['etc']})" if part.get("etc") else ""), scope=f"{level}층"))
    return CandidateReview(
        building_id=building_id, unit_id=unit_id, pnu=pnu,
        queried_at=datetime.now(timezone.utc).isoformat(), ledger_status=status, ledger_note=note,
        facts=facts,
        regulation_note="후보에 공적 지역지구 코드와 검토할 토지이용행위가 연결되지 않아 규제를 자동 조회·판정하지 않았습니다. 토지이음에서 주소를 조회하고 관할 기관에 확인해 주세요.",
        sources=[
            ReviewSource(name="건축HUB 건축물대장 원천 안내", url="https://www.data.go.kr/data/15134735/openapi.do"),
            ReviewSource(name="토지이음 토지이용계획 열람", url="https://www.eum.go.kr/web/ar/lu/luLandDet.jsp"),
        ],
    )
