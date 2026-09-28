"""W4 판정 — 4주 무료 파일럿이 끝난 조직을 사전등록 규칙대로 센다(2026-09-28).

규칙의 단일 출처는 docs/pilot-outreach-founders-2026-10.md 「W4 판정 규칙」 절이다.
여기 상수를 바꾸면 그 절도 같이 바꾼다 — 결과를 본 뒤 기준을 바꾸지 않는다.

## `usage` · `pmf` 와 무엇이 다른가

| | `usage_summary` / `pmf_summary` | 여기 |
|---|---|---|
| 시계 | "오늘부터 N일 전" 고정 창 / 기간 없음 | **조직마다 가입일부터 28일** |
| 활성 | 창 안에 접근 1건이라도 | 가입일 기준 **서로 다른 2주 이상** 접근 |
| 분모 | 답한 조직 전부 | **W4 가 끝난 활성 조직**만. 무응답은 빼되 응답률로 드러낸다 |

두 계측기는 그대로 둔다 — "지금 살아 있나"를 보는 창으로는 여전히 맞다.

## 판정 순서

1. W4 가 끝난 활성 조직 < `MIN_RESPONSES` → `표본부족` (모집 문제 — 응답률을 따질 모수가 없다)
2. 응답률 < 60% → `판정보류` (만족한 조직만 답해도 좋아 보이는 것을 막는다)
3. 답한 활성 조직 < `MIN_RESPONSES` → `표본부족`
4. NPS ≥ 30 **그리고** "예" ≥ 30% → `충족`, 아니면 `미달`

`충족` 도 "PMF 달성"이 아니라 **방향 신호**다(n=5 에서 한 조직이 NPS 를 40점 움직인다).
"아마"는 합격선에 넣지 않고 `would_pay_maybe_pct` 로 따로 낸다.

## 피드백 시점

피드백은 **기간을 자르지 않는다.** 규칙상 종료 때 링크를 보내고 3일 뒤 한 번 더 요청하므로
응답은 28일 뒤에 들어오는 게 정상이다. 조직당 최신 1건(`pmf` 와 같은 규칙).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog, Org
from app.models.feedback import PilotFeedback
from app.services import kpi_scope
from app.services.pmf import (
    DETRACTOR_MAX, MIN_RESPONSES, NPS_TARGET, PAY_TARGET_PCT, PROMOTER_MIN,
)
from app.services.usage import ACCESS_PREFIX

# 무료 기간. 파일럿 제안(4주 무료)과 같이 바꾼다.
PILOT_DAYS = 28
WEEK_DAYS = 7
# 가입일 기준 주(1~7 · 8~14 · 15~21 · 22~28일) 중 접근이 있는 주가 이 수 이상이면 활성.
MIN_ACTIVE_WEEKS = 2
# 응답률(답한 활성 ÷ 활성)이 이 미만이면 판정을 보류한다.
MIN_RESPONSE_RATE_PCT = 60.0


def _utc(dt: datetime) -> datetime:
    """SQLite 는 tz 를 버리고 돌려준다 — 저장은 늘 UTC 이므로 UTC 로 붙인다."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _week_index(signup: datetime, at: datetime) -> int | None:
    """가입일 기준 0~3 주차. 가입 전이거나 28일 뒤면 None."""
    delta = _utc(at) - _utc(signup)
    if delta < timedelta(0) or delta >= timedelta(days=PILOT_DAYS):
        return None
    return delta.days // WEEK_DAYS


def w4_summary(db: Session, now: datetime | None = None) -> dict:
    """W4 판정. 읽기만 한다. 내부·테스트 조직은 `kpi_scope` 로 뺀다."""
    now = _utc(now or datetime.now(timezone.utc))
    scope = kpi_scope.resolve_scope(db)

    orgs = db.execute(select(Org.id, Org.name, Org.created_at)).all()
    removed = [oid for oid, _, _ in orgs if scope.is_excluded(oid)]
    signup = {oid: _utc(c) for oid, _, c in orgs if not scope.is_excluded(oid)}
    names = {oid: n for oid, n, _ in orgs}

    weeks: dict[str, set[int]] = {oid: set() for oid in signup}
    for org_id, at in db.execute(
        select(AuditLog.org_id, AuditLog.created_at)
        .where(AuditLog.action.like(f"{ACCESS_PREFIX}%"))
    ).all():
        if org_id in signup:
            w = _week_index(signup[org_id], at)
            if w is not None:
                weeks[org_id].add(w)

    latest: dict[str, PilotFeedback] = {}
    for row in db.execute(
        select(PilotFeedback).order_by(PilotFeedback.created_at.desc())
    ).scalars():
        if row.org_id in signup and row.org_id not in latest:
            latest[row.org_id] = row

    per_org = []
    ended_active: list[str] = []
    in_progress = ended_inactive = 0
    for oid, t0 in sorted(signup.items(), key=lambda kv: kv[1]):
        w4_end = t0 + timedelta(days=PILOT_DAYS)
        ended = now >= w4_end
        active = len(weeks[oid]) >= MIN_ACTIVE_WEEKS
        if not ended:
            status = "진행중"
            in_progress += 1
        elif active:
            status = "활성"
            ended_active.append(oid)
        else:
            status = "비활성"
            ended_inactive += 1
        fb = latest.get(oid)
        per_org.append({
            "id_prefix": oid[:kpi_scope.ID_PREFIX_LEN],
            "name": names.get(oid, ""),
            "signup_at": t0.isoformat(),
            "w4_end": w4_end.isoformat(),
            "status": status,
            "active_weeks": sorted(w + 1 for w in weeks[oid]),
            "responded": fb is not None,
        })

    n_active = len(ended_active)
    answered = [latest[oid] for oid in ended_active if oid in latest]
    n = len(answered)
    rate = round(n / n_active * 100.0, 1) if n_active else None

    base = {
        **scope.report(removed),
        "rules": {
            "pilot_days": PILOT_DAYS,
            "min_active_weeks": MIN_ACTIVE_WEEKS,
            "min_response_rate_pct": MIN_RESPONSE_RATE_PCT,
            "min_responses": MIN_RESPONSES,
            "nps_target": NPS_TARGET,
            "pay_target_pct": PAY_TARGET_PCT,
            "source": "docs/pilot-outreach-founders-2026-10.md §W4 판정 규칙",
        },
        "orgs_in_progress": in_progress,
        "orgs_ended_inactive": ended_inactive,
        "orgs_ended_active": n_active,
        "responded": n,
        "response_rate_pct": rate,
        "orgs": per_org,
    }

    if n_active < MIN_RESPONSES:
        return {**base, "verdict": "표본부족", "nps": None,
                "note": (f"W4 가 끝난 활성 조직 {n_active}곳 < {MIN_RESPONSES}. "
                         "규칙: W8 까지 한 번만 늘리고, 그래도 부족하면 채널·대상을 바꾼다.")}
    if rate < MIN_RESPONSE_RATE_PCT:
        return {**base, "verdict": "판정보류", "nps": None,
                "note": (f"응답률 {rate}% < {MIN_RESPONSE_RATE_PCT:g}%. "
                         "무응답 조직에 한 번 더 요청하고 1주 뒤 다시 판정한다.")}
    if n < MIN_RESPONSES:
        return {**base, "verdict": "표본부족", "nps": None,
                "note": f"답한 활성 조직 {n}곳 < {MIN_RESPONSES}."}

    promoters = sum(1 for r in answered if r.nps_score >= PROMOTER_MIN)
    detractors = sum(1 for r in answered if r.nps_score <= DETRACTOR_MAX)
    nps = (promoters - detractors) / n * 100.0
    pay = {k: sum(1 for r in answered if r.would_pay == k) for k in ("yes", "maybe", "no")}
    pay_pct = pay["yes"] / n * 100.0
    verdict = "충족" if nps >= NPS_TARGET and pay_pct >= PAY_TARGET_PCT else "미달"
    return {
        **base,
        "verdict": verdict,
        "nps": round(nps, 1),
        "promoters": promoters,
        "passives": n - promoters - detractors,
        "detractors": detractors,
        "would_pay_pct": round(pay_pct, 1),
        "would_pay_maybe_pct": round(pay["maybe"] / n * 100.0, 1),
        "would_pay_counts": pay,
        "one_response_swing_nps": round(200.0 / n, 1),
        "note": ("방향 신호이지 'PMF 달성'이 아니다. "
                 f"n={n} 에서 한 조직이 NPS 를 {round(200.0 / n, 1)}포인트 움직인다."),
    }
