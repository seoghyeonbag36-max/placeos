"""방문자의 실제 의견을 파일럿 PMF와 별도 보관한다."""
from datetime import datetime
from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base
from app.models.auth import _now, _uuid

class VisitorFeedback(Base):
    __tablename__ = "visitor_feedback"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    category: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(2000))
    page: Mapped[str] = mapped_column(String(500))
    contact: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="received")
    notification_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # 2026-10-25 — 스스로 고른 입장과 그 입장의 선택형 응답(키만). 그 전 의견은 둘 다 NULL.
    # none_as_null — 기본값이면 None 이 SQL NULL 이 아니라 JSON 'null' 로 저장돼 옛 의견(SQL NULL)과 섞인다(실측).
    role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    answers: Mapped[dict[str, str] | None] = mapped_column(JSON(none_as_null=True), nullable=True)
