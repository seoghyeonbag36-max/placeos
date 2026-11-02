"""건물 공실 3분류 + 자료 없음 — `/heatmap/buildings` · `/buildings/{id}/twin` 이 함께 쓰는 한 규칙.

| 값 | 뜻 |
|---|---|
| `confirmed` | 층 매물 중 `certainty=confirmed` 가 있다 — 자료 대조 결과 영업 흔적이 없는 층이 있음(현장 미확인) |
| `probable`  | `probable` 층만 있거나 건물 status 가 partial·high·empty |
| `full`      | status full |
| `unknown`   | `polygon_only` — 대장·점포 근거가 없다. 「공실」로 칠하지 않는다 |

층 매물은 지번당 대표 1동에만 붙는다(`build_vacant_floor_units`). 층 근거 자체가 지번 단위라 같은 지번의 다른
폴리곤도 같은 층 집합을 들고 있다 — 그래서 **지번으로** 잇는다. 대표 동 하나만 「확정」이고 옆 폴리곤이 「의심」이면
한 지번이 두 말을 하게 된다.
"""
from __future__ import annotations

from app.services import floor_vacancy


def floors_by_pnu(district_id: str | None) -> dict[str, dict[int, dict]]:
    """지번 → {층: 층 매물}. `/floor-vacancies` 와 같은 파일에서 읽는다."""
    out: dict[str, dict[int, dict]] = {}
    for u in (floor_vacancy.load(district_id) or {}).get("units") or []:
        pnu, floor = str(u.get("pnu") or ""), u.get("floor")
        if pnu and isinstance(floor, int):
            out.setdefault(pnu, {})[floor] = u
    return out


def classify(props: dict, listed: dict[int, dict] | None) -> str:
    """건물 속성 + 그 지번의 층 매물 → 3분류. 근거 없는 건물이 먼저 빠진다."""
    if props.get("source") == "polygon_only":
        return "unknown"
    certainties = {u.get("certainty") for u in (listed or {}).values()}
    if "confirmed" in certainties:
        return "confirmed"
    if "probable" in certainties:
        return "probable"
    status = props.get("status")
    if status == "full":
        return "full"
    if status in ("partial", "high", "empty"):
        return "probable"
    return "unknown"
