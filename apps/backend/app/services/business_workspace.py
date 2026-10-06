"""개인 사업 정보 저장 — 소유자는 인증 컨텍스트로 결정한다.

2026-10-06: 같은 행(`business_workspaces.data`, JSON)에 **저장한 결과**(`results`)를 함께 둔다.
새 표를 만들지 않은 이유: 계정층 마이그레이션은 배포에 묶여 있지 않아 운영 DB 에 따로 적용해야 하고
(docs/deploy-cloud-run.md §2026-10-04), 이 데이터는 이미 "사용자가 직접 남긴 개인 사업 정보"라는
같은 성격이다. 그래서 탈퇴(auth_service.delete_account)가 이 행을 지울 때 결과도 함께 지워진다.

⚠ 사업 정보(status·profile)와 결과는 **따로 쓴다.** `save` 가 행 전체를 갈아끼우면 결과가 사라지고,
결과를 쓸 때 사업 정보를 건드리면 화면이 보낸 적 없는 값이 바뀐다 — 두 함수가 서로의 키를 보존한다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_api_key
from app.models.auth import BusinessWorkspace, RevokedToken
from app.schemas.auth import BusinessWorkspaceData, SavedResultIn, SavedResultOut

RESULTS_KEY = "results"
# 사용자당 보관 상한(종류 합산). 넘으면 가장 오래된 것부터 지운다 — 무한히 쌓이지 않게.
MAX_RESULTS = 30


class SavedResultNotFound(Exception):
    pass


def _profile_part(data: dict | None) -> dict:
    return {k: v for k, v in (data or {}).items() if k != RESULTS_KEY}


def _results_part(data: dict | None) -> list[dict]:
    return list((data or {}).get(RESULTS_KEY) or [])


def load(db: Session, user_id: str) -> BusinessWorkspaceData:
    row = db.get(BusinessWorkspace, user_id)
    if row is None or not _profile_part(row.data):
        return BusinessWorkspaceData(status="unset")
    return BusinessWorkspaceData.model_validate(_profile_part(row.data))


def save(db: Session, user_id: str, data: BusinessWorkspaceData) -> BusinessWorkspaceData:
    row = db.get(BusinessWorkspace, user_id)
    if row is None:
        row = BusinessWorkspace(user_id=user_id, data=data.model_dump())
        db.add(row)
    else:
        # 저장한 결과는 그대로 둔다 — 사업 정보만 갈아끼운다. 새 dict 를 대입해야 JSON 열의 변경이 잡힌다.
        results = _results_part(row.data)
        row.data = {**data.model_dump(), **({RESULTS_KEY: results} if results else {})}
    db.commit()
    return data


# ── 저장한 결과 ────────────────────────────────────────────────────────────────


def list_results(db: Session, user_id: str) -> list[SavedResultOut]:
    """최신 것이 앞에 온다."""
    row = db.get(BusinessWorkspace, user_id)
    items = [SavedResultOut.model_validate(r) for r in _results_part(row.data if row else None)]
    return sorted(items, key=lambda r: r.createdAt, reverse=True)


def add_result(db: Session, user_id: str, item: SavedResultIn) -> SavedResultOut:
    saved = SavedResultOut(**item.model_dump(), id=uuid.uuid4().hex,
                           createdAt=datetime.now(timezone.utc))
    row = db.get(BusinessWorkspace, user_id)
    record = saved.model_dump(mode="json")
    if row is None:
        # 사업 정보를 아직 안 정한 사용자도 결과는 남길 수 있다 — 사업 정보 부분은 "unset" 으로 둔다.
        row = BusinessWorkspace(user_id=user_id,
                                data={**BusinessWorkspaceData(status="unset").model_dump(), RESULTS_KEY: [record]})
        db.add(row)
    else:
        results = (_results_part(row.data) + [record])[-MAX_RESULTS:]
        row.data = {**_profile_part(row.data), RESULTS_KEY: results}
    db.commit()
    return saved


def delete_result(db: Session, user_id: str, result_id: str) -> None:
    row = db.get(BusinessWorkspace, user_id)
    results = _results_part(row.data if row else None)
    kept = [r for r in results if r.get("id") != result_id]
    if row is None or len(kept) == len(results):
        raise SavedResultNotFound(result_id)     # 남의 결과도 여기로 떨어진다(존재 여부를 안 흘린다)
    row.data = {**_profile_part(row.data), **({RESULTS_KEY: kept} if kept else {})}
    db.commit()


def logout(db: Session, token: str) -> None:
    token_hash = hash_api_key(token)
    if db.get(RevokedToken, token_hash) is None:
        db.add(RevokedToken(token_hash=token_hash))
        db.commit()
