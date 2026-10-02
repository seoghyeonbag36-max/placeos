"""개인 사업 정보 저장 — 소유자는 인증 컨텍스트로 결정한다."""
from sqlalchemy.orm import Session
from app.models.auth import BusinessWorkspace, RevokedToken
from app.schemas.auth import BusinessWorkspaceData
from app.core.security import hash_api_key


def load(db: Session, user_id: str) -> BusinessWorkspaceData:
    row = db.get(BusinessWorkspace, user_id)
    return BusinessWorkspaceData.model_validate(row.data) if row else BusinessWorkspaceData(status="unset")


def save(db: Session, user_id: str, data: BusinessWorkspaceData) -> BusinessWorkspaceData:
    row = db.get(BusinessWorkspace, user_id)
    if row is None:
        row = BusinessWorkspace(user_id=user_id, data=data.model_dump())
        db.add(row)
    else:
        row.data = data.model_dump()
    db.commit()
    return data


def logout(db: Session, token: str) -> None:
    token_hash = hash_api_key(token)
    if db.get(RevokedToken, token_hash) is None:
        db.add(RevokedToken(token_hash=token_hash))
        db.commit()
