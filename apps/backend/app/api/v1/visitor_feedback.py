"""방문자 의견 접수. 조회와 변경은 관리자 전용이다."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.admin import require_admin
from app.core.db import get_db
from app.models.visitor_feedback import VisitorFeedback
from app.schemas.visitor_feedback import VisitorFeedbackIn, VisitorFeedbackSaved, VisitorFeedbackOut, VisitorFeedbackStatus
from app.services import visitor_feedback as service

router = APIRouter()

@router.post("", response_model=VisitorFeedbackSaved, status_code=201)
def submit(body: VisitorFeedbackIn, tasks: BackgroundTasks, db: Session = Depends(get_db)) -> VisitorFeedbackSaved:
    if not service.reserve_submission():
        raise HTTPException(429, "의견 접수가 많습니다. 잠시 후 다시 시도해 주세요.", headers={"Retry-After": "3600"})
    row = service.save_feedback(db, body)
    result = VisitorFeedbackSaved.model_validate(row)
    tasks.add_task(service.notify_feedback, row.id)
    return result

@router.get("", response_model=list[VisitorFeedbackOut], dependencies=[Depends(require_admin)])
def listing(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db)) -> list[VisitorFeedback]:
    return list(db.scalars(select(VisitorFeedback).order_by(VisitorFeedback.created_at.desc(), VisitorFeedback.id).offset(offset).limit(limit)))

@router.patch("/{feedback_id}", response_model=VisitorFeedbackOut, dependencies=[Depends(require_admin)])
def update(feedback_id: str, body: VisitorFeedbackStatus, db: Session = Depends(get_db)) -> VisitorFeedback:
    row = db.get(VisitorFeedback, feedback_id)
    if row is None:
        raise HTTPException(404, "의견을 찾을 수 없습니다")
    row.status = body.status
    db.commit()
    db.refresh(row)
    return row

@router.delete("/{feedback_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete(feedback_id: str, db: Session = Depends(get_db)) -> None:
    """삭제 요청 확인 후 운영자가 의견과 연락처를 삭제한다."""
    row = db.get(VisitorFeedback, feedback_id)
    if row is None:
        raise HTTPException(404, "의견을 찾을 수 없습니다")
    db.delete(row)
    db.commit()
