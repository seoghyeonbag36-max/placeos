"""인테리어 참고 이미지 — 사용자당 **하루 5회** 생성 한도 (2026-11-07 사용자 요청).

## 왜 DB 로 세는가

`services/rate_limit` 의 LLM 한도는 프로세스 메모리에서 센다. 그래서 실효 상한이 「설정값 × Cloud Run 인스턴스 수」이고
재시작하면 0 으로 돌아간다(그 파일 머리말 §한계). 이미지 한 장은 공급자 과금이 LLM 한 번보다 크고, 사용자가 받은 약속이
「하루 5회」라 인스턴스마다 5회씩 새면 약속이 거짓이 된다. 그래서 계정층 DB 의 기존 `audit_log` 표에 한 줄씩 남겨 센다
— 새 표·마이그레이션이 없다(decision-lightweight-first). 사용량 집계(`services/usage`)는 `access:` 접두사만 세므로
이 행(`interior:image`)은 KPI③ 표본에 섞이지 않는다.

## 「하루」의 경계

한국 시간(KST) 0시에 초기화한다. 「오늘 5회」를 사용자가 읽는 달력과 맞춘다(24시간 이동 창이 아니다).

## 세는 것과 안 세는 것

- **센다**: 공급자가 이미지를 돌려준 생성. 호출 직전에 한 칸을 잡고(`reserve`), 실패하면 돌려준다(`release`).
  먼저 잡는 이유는 동시에 여러 번 눌러도 한도를 넘겨 공급자를 부르지 않게 하기 위해서다.
- **안 센다**: 서버 미설정(503) · 입력·첨부 오류(422) · 공급자 실패(4xx/5xx/시간 초과). 사용자 잘못이 아닌 실패로
  하루 몫을 깎지 않는다.

## 한계

잡기 전에 세는 조회와 잡는 쓰기 사이에 잠금이 없다 — 같은 사용자가 같은 순간에 두 번 보내면 한 번 더 지나갈 수 있다.
화면은 생성 중 버튼을 잠근다(InteriorPlanner). 정확히 막아야 하면 사용자 행 잠금(SELECT … FOR UPDATE)을 더한다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import AuditLog

log = logging.getLogger("placeos.interior")

ACTION = "interior:image"
KST = timezone(timedelta(hours=9), "KST")


class QuotaExceeded(Exception):
    """오늘 한도를 다 썼다. `detail` 은 화면에 그대로 싣는 한국어 문구다."""

    def __init__(self, limit: int, resets_at: datetime):
        self.limit = limit
        self.resets_at = resets_at
        self.detail = (f"오늘 이미지 생성 한도({limit}회)를 모두 사용했습니다. "
                       "내일 0시(한국 시간)에 다시 만들 수 있습니다.")
        super().__init__(self.detail)


def daily_limit() -> int:
    return max(0, int(settings.interior_images_daily_limit_per_user))


def _window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """오늘(KST)의 시작과 내일 0시 — 둘 다 UTC 로 돌려준다(저장값 `created_at` 이 UTC 다)."""
    now = (now or datetime.now(timezone.utc)).astimezone(KST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def used_today(db: Session, user_id: str, now: datetime | None = None) -> int:
    start, _ = _window(now)
    return int(db.execute(
        select(func.count(AuditLog.id))
        .where(AuditLog.action == ACTION, AuditLog.user_id == user_id, AuditLog.created_at >= start)
    ).scalar_one())


def status(db: Session, user_id: str, now: datetime | None = None) -> dict:
    """화면이 「오늘 남은 생성 n/5회」를 그리는 값."""
    limit = daily_limit()
    used = used_today(db, user_id, now)
    _, resets = _window(now)
    return {"limit": limit, "used": min(used, limit), "remaining": max(0, limit - used),
            "resets_at": resets.astimezone(KST).isoformat()}


def reserve(db: Session, user_id: str, org_id: str | None, now: datetime | None = None) -> str:
    """한 칸을 잡고 그 행 id 를 돌려준다. 한도면 `QuotaExceeded`."""
    limit = daily_limit()
    _, resets = _window(now)
    if used_today(db, user_id, now) >= limit:
        raise QuotaExceeded(limit, resets)
    row = AuditLog(org_id=org_id, user_id=user_id, action=ACTION, detail="ai/interior-preview")
    if now is not None:
        # UTC 로 맞춰 쓴다 — SQLite 는 시간대를 버리고 벽시계 값만 남겨, KST 값을 그대로 쓰면 9시간 어긋나 센다.
        row.created_at = now.astimezone(timezone.utc)
    db.add(row)
    db.commit()
    return row.id


def release(db: Session, row_id: str) -> None:
    """실패한 생성의 칸을 돌려준다. 돌려주지 못해도 요청 실패 사유를 덮지 않는다 — 흔적만 남긴다."""
    try:
        row = db.get(AuditLog, row_id)
        if row is not None:
            db.delete(row)
            db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.warning("interior_quota release_failed row=%s", row_id, exc_info=True)
