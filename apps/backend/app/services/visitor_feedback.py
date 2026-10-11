"""의견 저장과 TLS SMTP 알림. 메일 실패 상태를 명시한다."""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from threading import Lock
from time import monotonic
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.visitor_feedback import VisitorFeedback
from app.schemas.visitor_feedback import VisitorFeedbackIn

logger = logging.getLogger(__name__)
_lock = Lock()
_started = 0.0
_count = 0

def reserve_submission() -> bool:
    """인스턴스당 시간당 접수 상한을 예약한다. 재시작하면 초기화된다."""
    global _started, _count
    with _lock:
        now = monotonic()
        if now - _started >= 3600:
            _started, _count = now, 0
        if _count >= settings.visitor_feedback_hourly_cap:
            return False
        _count += 1
        return True

def save_feedback(db: Session, body: VisitorFeedbackIn) -> VisitorFeedback:
    row = VisitorFeedback(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def send_notification(row: VisitorFeedback) -> str:
    """SMTP 미설정은 disabled, 발송 실패는 failed로 반환한다."""
    if not (settings.feedback_smtp_host and settings.feedback_mail_from):
        return "disabled"
    msg = EmailMessage()
    msg["Subject"] = f"[PlaceOS 의견] {row.category} · {row.id}"
    msg["From"] = settings.feedback_mail_from
    msg["To"] = settings.feedback_mail_to
    msg.set_content(f"유형: {row.category}\n페이지: {row.page}\n연락처: {row.contact or chr(45)}\n\n{row.message}")
    try:
        with smtplib.SMTP(settings.feedback_smtp_host, settings.feedback_smtp_port, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if settings.feedback_smtp_user:
                smtp.login(settings.feedback_smtp_user, settings.feedback_smtp_password)
            smtp.send_message(msg)
        return "sent"
    except (OSError, smtplib.SMTPException):
        logger.warning("방문자 의견 메일 발송 실패: %s", row.id)
        return "failed"

def notify_feedback(feedback_id: str) -> None:
    """응답 후 별도 DB 세션으로 메일 알림 상태를 기록한다."""
    with SessionLocal() as db:
        row = db.get(VisitorFeedback, feedback_id)
        if row is not None:
            row.notification_status = send_notification(row)
            db.commit()
