"""인증한 개인의 캠페인만 읽고 쓴다. 공개 분석 응답과 분리한다."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user
from app.schemas.campaign import Command, Conditions
from app.services import campaigns

router = APIRouter()


@router.get("")
def list_campaigns(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return campaigns.list_campaigns(db, current.user.id)


@router.post("", status_code=201)
def create_campaign(body: Conditions, current: CurrentUser = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> dict:
    return campaigns.create(db, current.user.id, body)


@router.post("/{campaign_id}/commands")
def command_campaign(campaign_id: str, body: Command, current: CurrentUser = Depends(get_current_user),
                     db: Session = Depends(get_db)) -> dict:
    try:
        return campaigns.mutate(db, current.user.id, campaign_id, body)
    except campaigns.CampaignError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(422, "입력과 증빙을 확인하세요: " + "; ".join(e["msg"] for e in exc.errors())) from exc
