"""관리자 전용 API — 운영 지표. 공개 지도에 노출하지 않는 정보만 다룬다.

배경(2026-07-26): Page 공실 레이어는 건축물대장에서 capacity 를 얻은 건물만 그린다.
대장 미확인 건물은 지도에서 빠지는데(연남동 433동), 이 사실이 공개 화면에는 드러나지
않는다. Tier2 근사로 채워 넣으면 근거가 다른 데이터가 한 지도에 섞여 "대장 기반 실측"
논증이 무너지므로, 채우는 대신 **제외 사실을 관리자만 볼 수 있게** 분리한다.

인증: ADMIN_TOKEN 환경변수와 X-Admin-Token 헤더 일치. 미설정이면 라우터 전체가 403 —
토큰을 깜빡한 배포에서 운영 지표가 공개되는 것보다 안 열리는 편이 안전하다(fail-closed).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.districts import PAGES_BY_ID, get_summary
from app.services import latency as latency_service
from app.services import pilot_w4 as pilot_w4_service
from app.services import pmf as pmf_service
from app.services import usage as usage_service

router = APIRouter()

# repo/data/gold  (v1 → api → app → backend → apps → repo)
_GOLD_DIR = Path(__file__).resolve().parents[5] / "data" / "gold"


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """관리자 토큰 검증. 토큰 미설정 시에도 통과시키지 않는다."""
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=403,
                            detail="ADMIN_TOKEN 미설정 — 관리자 API 가 비활성화되어 있습니다")
    if x_admin_token != expected:
        raise HTTPException(status_code=403, detail="관리자 토큰이 올바르지 않습니다")


def _served_vacancy(slug: str | None) -> dict:
    """공개 화면과 **같은 수**를 싣는다 — 거점 전체 공실률(주 지표) · 대조 지표(R-ONE 정렬).

    2026-09-28: 이 표는 `coverage.json` 의 `reference_vacancy_pct` 를 "참고 공실률"로 그렸다.
    그 값은 집합건물 호실(expos_units)을 섞은 옛 대표값이라 공개 화면의 어느 수와도
    다르고(banpo 74.0% — 공개 화면은 대표값을 내렸다), 연남(20.7%)처럼 대조 지표와
    우연히 겹쳐 헷갈렸다. 화면은 아래 두 필드만 읽는다. `reference_vacancy_pct` 는
    coverage.json 을 그대로 옮기는 필드라 응답에는 남는다.
    서빙 보류 거점은 공개 응답이 없으니 None 이다.
    """
    s = get_summary(slug) if slug else None
    return {
        "vacancy_rate": s["vacancy_rate"] if s else None,
        "vacancy_withheld": bool(s and s["vacancy_withheld"]),
        "aligned_vacancy_pct": s["aligned_vacancy_pct"] if s else None,
    }


@router.get("/coverage", dependencies=[Depends(require_admin)])
def coverage() -> dict:
    """거점별 지도 커버리지 — 표시 동수와 제외 동수(대장 미확인/비상업).

    build_page_master 가 남긴 gold/{slug}/coverage.json 을 모아서 돌려준다.

    ⚠ **`coverage.json` 수는 서빙 거점 수가 아니다**(2026-09-28). 산출물은 서빙 보류 도시
    (경기)의 거점에도 서 있어서, 전부 세면 서빙 81 + 보류 7 = 88 이 "거점 88곳"으로
    찍혔다. 거점마다 `served`(= 공개 API 가 내는 거점인가, `districts.PAGES_BY_ID`)를
    붙이고, `totals` 는 **서빙 거점만** 합산한다. 보류 거점은 `held` 에 따로 센다.
    """
    hubs = []
    for path in sorted(_GOLD_DIR.glob("*/coverage.json")):
        try:
            hub = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        slug = hub.get("slug", path.parent.name)
        hub["served"] = slug in PAGES_BY_ID
        hub |= _served_vacancy(slug if hub["served"] else None)
        hubs.append(hub)

    served = [h for h in hubs if h["served"]]
    held = [h for h in hubs if not h["served"]]
    shown = sum(h.get("shown") or 0 for h in served)
    unknown = sum(h.get("excluded_unknown") or 0 for h in served)
    non_comm = sum(h.get("excluded_non_commercial") or 0 for h in served)
    total = shown + unknown + non_comm
    return {
        # 서빙 거점 먼저, 그 안에서 대장 미확인이 많은 순
        "hubs": sorted(hubs, key=lambda h: (not h["served"], -(h.get("excluded_unknown") or 0))),
        "totals": {
            "hubs": len(served),
            "shown": shown,
            "excluded_unknown": unknown,
            "excluded_non_commercial": non_comm,
            "coverage_pct": round(shown / total * 100, 1) if total else None,
        },
        "held": {"hubs": len(held), "slugs": sorted(h.get("slug", "") for h in held)},
    }


@router.get("/latency", dependencies=[Depends(require_admin)])
def latency() -> dict:
    """경로별 응답시간 — KPI② (`API p95 <200ms`) 를 재는 유일한 관측 지점.

    2026-09-16 이전에는 이 목표를 재는 코드가 없어 KPI 가 **선언만** 남아 있었다.

    ⚠ 값은 **프로세스 로컬 표본**이다(응답의 `scope`·`note` 참조) — 재시작하면 0 이고
    인스턴스가 여럿이면 인스턴스마다 다르다. 표본이 `min_samples` 미만인 경로는
    `verdict: "표본부족"` 으로 물러난다. 관리자 전용인 이유는 경로별 지연이 내부
    구조를 드러내기 때문이다.
    """
    return latency_service.summary()


@router.get("/pmf", dependencies=[Depends(require_admin)])
def pmf(db: Session = Depends(get_db)) -> dict:
    """NPS · 유료 전환 의향 — KPI③ 의 나머지 절반을 재는 관측 지점.

    `/usage` 의 `active_orgs` 가 "파일럿이 살아 있나" 라면 여기는 "그래서 돈을 낼
    생각인가 · 남에게 권할 생각인가" 다. 2026-09-16 이전에는 후자를 담을 곳이
    아예 없었다.

    ⚠ 표본이 `min_responses` 미만이면 `verdict: "표본부족"` 이다. 응답 한 건이 NPS 를
    몇 포인트 흔드는지(`one_response_swing_nps`)도 함께 돌려준다 — n 이 작을 때
    "NPS 40 달성" 이 얼마나 약한 말인지 숫자로 보라는 뜻이다.
    """
    return pmf_service.pmf_summary(db)


@router.get("/pilot-w4", dependencies=[Depends(require_admin)])
def pilot_w4(db: Session = Depends(get_db)) -> dict:
    """W4 판정 — 4주 무료가 끝난 조직을 사전등록 규칙대로 센다(2026-09-28).

    `/usage` · `/pmf` 는 "지금" 창이다. 여기는 조직마다 가입일부터 28일을 세고,
    서로 다른 2주 이상 쓴 조직만 분모에 넣고, 응답률 60% 미만이면 판정을 보류한다.
    규칙 원문은 docs/pilot-outreach-founders-2026-10.md §W4 판정 규칙.
    """
    return pilot_w4_service.w4_summary(db)


@router.get("/usage", dependencies=[Depends(require_admin)])
def usage(days: int = 30, db: Session = Depends(get_db)) -> dict:
    """조직별 분석 API 사용량 — KPI② (B2B 파일럿) 를 재는 유일한 관측 지점.

    `active_orgs` 가 목표 5~10건에 대응한다. 값이 0 인데 파일럿이 있다고 알고 있다면
    둘 중 하나다: ① 파일럿이 자격증명 없이(익명으로) 쓰고 있다 ② 기록이 실패하고 있다
    (`services/usage.record_access` 의 경고 로그를 볼 것). **둘 다 조용히 0 으로
    보이므로** 이 엔드포인트가 그 구분을 드러내는 자리다.
    """
    return usage_service.usage_summary(db, days=days)
