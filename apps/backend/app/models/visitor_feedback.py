"""방문자의 실제 의견을 파일럿 PMF와 별도 보관한다."""
from datetime import datetime
from sqlalchemy import DateTime, String
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
