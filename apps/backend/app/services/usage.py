"""분석 API 사용량 기록 — KPI③ 고객 검증(창업자 파일럿)을 재는 원천 데이터.

번호: 2026-09-16 KPI 재정의 전에는 PMF 가 KPI② 였다. 지금은 ② = 표면 성능 · ③ = 고객 검증이다
(CLAUDE.md §KPI Priorities · 2026-10-19 번호 정리).

## 왜 필요한가

`docs/README.md` §진행률 이 적어 둔 대로 **PMF 를 재는 게이트가 0개**였다(2026-08-27). PPPP
진행률 22게이트는 전부 분석 파이프라인(KPI①)만 센다. 파일럿을 5~10건 받기로 해 놓고
"그 파일럿이 실제로 무엇을 얼마나 썼나"를 셀 자리가 없으면, 유료 전환 의향 30%·NPS 30
같은 목표는 **관측 없이 선언만 남는다** — 이 저장소가 반복해 잡아 온 실패 양식이다.

## 설계 — 익명은 안 센다, 못 세는 게 아니라 세지 않는 것이다

- **익명 요청은 기록하지 않는다.** 공개 데모 트래픽은 파일럿 사용량이 아니고, 익명까지
  세면 DB 를 안 쓰던 분석 API 가 매 요청 DB 를 때린다. `get_optional_principal` 이
  자격증명 없을 때 DB 를 건드리지 않는 것과 짝이다.
- **기록 실패가 요청을 깨뜨리지 않는다.** 사용량 로깅 때문에 분석 API 가 500 을 내면
  주객이 전도된다. 다만 조용히 삼키지 않는다 — `record_access` 는 성공 여부를
  돌려주고, `/admin/usage` 가 "기록이 실제로 쌓이고 있나"를 드러낸다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import Principal
from app.models.auth import AuditLog
from app.services import kpi_scope

logger = logging.getLogger(__name__)

# AuditLog.action 접두사 — 계정 이벤트(signup/login)와 한 표에 살지만 구분은 된다.
ACCESS_PREFIX = "access:"

# 분석 사용이 아닌 경로 — 이용 기록에 남아 있어도 사용량·W4 활성에서 뺀다(2026-10-19).
# 피드백 제출은 분석 요청이 아니다. W4 규칙 ②는 「분석 요청이 1건 이상 있는 주」를 세고
# (docs/pilot-outreach-founders-2026-10.md §W4), 처리방침의 이용 기록도 「분석 경로」다.
# 그런데 /feedback 라우터에 사용량 계측이 걸려 있어, 1주차에 한 번 쓰고 4주차에 설문만 낸
# 조직이 「서로 다른 2주 활성」으로 세졌다(규칙 변경이 아니라 계측 정정 — 그날 파일럿 0건).
# 기록은 api/v1/router.py 에서 끊었고, 이미 쌓인 행은 읽을 때 여기서 거른다 —
# 10-04 이후 관측 전체에 같은 정의가 걸리게.
NON_ANALYSIS_PREFIXES = ("/api/v1/feedback",)


def analysis_access_clauses() -> list:
    """「분석 접근」 행만 고르는 조건. `usage_summary` 와 `pilot_w4` 가 같은 정의를 쓴다."""
    return [AuditLog.action.like(f"{ACCESS_PREFIX}%"),
            *(~AuditLog.detail.like(f"{p}%") for p in NON_ANALYSIS_PREFIXES)]


def record_access(db: Session, principal: Principal | None, path: str) -> bool:
    """접근 1건 기록. 익명이면 아무것도 안 하고 False.

    반환값은 "기록됐나"이지 "요청이 성공했나"가 아니다.
    """
    if principal is None:
        return False
    try:
        db.add(AuditLog(
            org_id=principal.org.id,
            user_id=principal.user.id if principal.user else None,
            action=f"{ACCESS_PREFIX}{principal.via}",
            detail=path[:500],
        ))
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        # 로깅 실패로 분석 응답을 깨뜨리지 않는다. 대신 흔적은 남긴다 —
        # /admin/usage 의 카운트가 0 인 채로 있으면 여기가 계속 실패하는 것이다.
        logger.warning("사용량 기록 실패 (path=%s)", path, exc_info=True)
        return False


def usage_summary(db: Session, days: int = 30) -> dict:
    """조직별 접근 요약 — 파일럿 활성도를 보는 최소 지표.

    `active_orgs` 는 "지금 살아 있나"를 보는 창이다(최근 N일 안에 분석 접근 1건이라도).
    KPI③ 의 창업자 파일럿 **건수**는 이것이 아니라 W4 활성(`services/pilot_w4` — 서로 다른
    2주 이상)으로 센다 — 이 창은 데모 날 한 번 쓴 조직도 센다.
    내부·테스트 조직(`services/kpi_scope`)은 빼고 세며, 뺀 수는 `excluded_orgs` 에 싣는다.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(AuditLog.org_id, func.count(AuditLog.id))
        .where(*analysis_access_clauses())
        .where(AuditLog.created_at >= since)
        .group_by(AuditLog.org_id)
    ).all()
    raw = {org_id: int(n) for org_id, n in rows if org_id}
    # 내부·테스트 조직은 뺀다 — 뺀 사실은 excluded_orgs 로 드러낸다(services/kpi_scope).
    scope = kpi_scope.resolve_scope(db)
    removed = [oid for oid in raw if scope.is_excluded(oid)]
    by_org = {oid: n for oid, n in raw.items() if not scope.is_excluded(oid)}
    names = kpi_scope.org_names(db, by_org)
    return {
        "window_days": days,
        "active_orgs": len(by_org),
        "total_accesses": sum(by_org.values()),
        "by_org": by_org,
        # 화면용 — 이름과 id 앞 8자만. 접근 많은 순.
        "orgs": [
            {"id_prefix": oid[:kpi_scope.ID_PREFIX_LEN], "name": names.get(oid, ""),
             "accesses": n}
            for oid, n in sorted(by_org.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "excluded_accesses": sum(raw[oid] for oid in removed),
        **scope.report(removed),
    }
