"""가입/로그인/API 키 비즈니스 로직. 가입 = 조직 생성 + 관리자 멤버십 1건(트랜잭션 단위).

감사로그(`audit_log.detail`)에 **이메일을 적지 않는다**(2026-10-05). 행마다 user_id 가 이미 있어
누가 했는지는 그것으로 충분하고, 사본을 남기면 탈퇴 때 지울 곳이 하나 더 는다. detail 에는
로그인 수단("password" | "google")만 적는다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.security import (
    UNUSABLE_PASSWORD, generate_api_key, has_usable_password, hash_api_key, hash_password,
    issue_access_token, verify_password,
)
from app.models.auth import ApiKey, AuditLog, BusinessWorkspace, Membership, Org, User
from app.models.feedback import PilotFeedback

# 구글로 처음 들어온 사람의 조직 이름. 구글 화면은 사업 이름을 묻지 않으므로, 가입 화면에서
# 적지 않았으면 이 이름으로 시작한다(「내 사업」 카드에서 사업 이름을 따로 적는다).
DEFAULT_ORG_NAME = "내 작업 공간"


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class ApiKeyNotFound(Exception):
    pass


def signup(db: Session, org_name: str, email: str, password: str) -> tuple[User, Org]:
    email = email.lower()
    if db.execute(select(User).filter_by(email=email)).scalar_one_or_none():
        raise EmailAlreadyRegistered(email)

    org = Org(name=org_name)
    user = User(email=email, hashed_password=hash_password(password))
    db.add_all([org, user])
    db.flush()  # id 채번 — Membership 이 org.id/user.id 를 참조하기 전에 필요

    membership = Membership(org_id=org.id, user_id=user.id, role="admin")
    db.add(membership)
    db.add(AuditLog(org_id=org.id, user_id=user.id, action="signup", detail="password"))
    db.commit()
    db.refresh(user)
    db.refresh(org)
    return user, org


def login(db: Session, email: str, password: str) -> tuple[str, User, Org, str]:
    """반환: (access_token, user, org, role). 조직이 여럿이면 첫 멤버십을 쓴다."""
    email = email.lower()
    user = db.execute(select(User).filter_by(email=email)).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentials(email)

    membership = db.execute(
        select(Membership).filter_by(user_id=user.id)
    ).scalars().first()
    if membership is None:
        raise InvalidCredentials(email)  # 조직 없는 사용자 — 정상 가입 경로로는 안 생긴다

    org = db.get(Org, membership.org_id)
    token = issue_access_token(user, org)
    db.add(AuditLog(org_id=org.id, user_id=user.id, action="login", detail="password"))
    db.commit()
    return token, user, org, membership.role


def login_with_google(db: Session, email: str, org_name: str | None = None) -> tuple[str, bool]:
    """구글이 확인한 이메일로 로그인한다. 처음이면 가입(조직 생성)까지 한 트랜잭션으로.

    반환: (access_token, 새로 만들었나). `email` 은 services/google_auth 가 검증한 값이어야 한다.

    ⚠ 같은 이메일의 **비밀번호 계정**이 이미 있으면 그 계정으로 들어가되 비밀번호를 끊는다.
    비밀번호 가입은 이메일 소유를 확인하지 않았다 — 남이 먼저 이 주소로 가입해 두었다면
    (선점) 구글로 들어온 진짜 주인과 계정을 나눠 쓰게 된다. 비밀번호를 끊으면 선점자의
    로그인이 막히고, 해시가 바뀌므로 그가 이미 들고 있던 토큰도 `cv` 검사로 함께 무효가 된다
    (core/security.credential_version). 진짜 주인이 비밀번호로 가입했던 경우라면 이후로는
    구글로만 들어오면 된다.
    """
    email = email.lower()
    user = db.execute(select(User).filter_by(email=email)).scalar_one_or_none()
    if user is None:
        org = Org(name=(org_name or "").strip() or DEFAULT_ORG_NAME)
        user = User(email=email, hashed_password=UNUSABLE_PASSWORD)
        db.add_all([org, user])
        db.flush()
        db.add(Membership(org_id=org.id, user_id=user.id, role="admin"))
        db.add(AuditLog(org_id=org.id, user_id=user.id, action="signup", detail="google"))
        db.commit()
        db.refresh(user)
        db.refresh(org)
        return issue_access_token(user, org), True

    membership = db.execute(select(Membership).filter_by(user_id=user.id)).scalars().first()
    if membership is None:
        raise InvalidCredentials(email)
    org = db.get(Org, membership.org_id)
    if has_usable_password(user.hashed_password):
        user.hashed_password = UNUSABLE_PASSWORD
        db.add(AuditLog(org_id=org.id, user_id=user.id, action="auth.google_link",
                        detail="password_disabled"))
    db.add(AuditLog(org_id=org.id, user_id=user.id, action="login", detail="google"))
    db.commit()
    db.refresh(user)
    return issue_access_token(user, org), False


def delete_account(db: Session, user: User) -> None:
    """회원 탈퇴 = 개인정보 파기 (2026-10-05). 한 트랜잭션으로 지운다.

    지우는 것
    - 사용자(이메일·비밀번호 해시) · 개인 사업 정보(business_workspaces) · 그가 낸 피드백
    - **혼자 쓰던 조직**: 조직 · API 키 · 그 조직의 피드백 · 이용 기록까지 통째로

    남기는 것 — 다른 멤버가 있는 조직
    - 조직과 남은 멤버의 기록. 떠난 사람의 감사 행은 user_id 를 비워 익명 집계로만 남긴다 —
      조직 사용량(`/admin/usage` active_orgs)이 과거로 거슬러 줄면 안 되기 때문이다. 가입·로그인
      행의 detail 은 2026-10-05 전까지 이메일 사본이었으므로 함께 비운다.

    순서는 외래키 방향(자식 → 부모)이다. SQLite 는 외래키를 기본으로 안 보지만 Postgres(Neon)는
    본다 — 테스트가 `PRAGMA foreign_keys=ON` 으로 같은 순서를 강제한다(test_auth_account_delete.py).
    """
    uid = user.id
    org_ids = list(db.execute(select(Membership.org_id).filter_by(user_id=uid)).scalars())
    solo = [oid for oid in org_ids
            if db.execute(select(func.count()).select_from(Membership)
                          .where(Membership.org_id == oid)).scalar_one() == 1]

    db.execute(delete(BusinessWorkspace).where(BusinessWorkspace.user_id == uid))
    db.execute(delete(PilotFeedback).where(PilotFeedback.user_id == uid))
    if solo:
        db.execute(delete(PilotFeedback).where(PilotFeedback.org_id.in_(solo)))
        db.execute(delete(ApiKey).where(ApiKey.org_id.in_(solo)))
        db.execute(delete(AuditLog).where(AuditLog.org_id.in_(solo)))
        db.execute(delete(Membership).where(Membership.org_id.in_(solo)))
        db.execute(delete(Org).where(Org.id.in_(solo)))
    db.execute(update(AuditLog).where(AuditLog.user_id == uid,
                                      AuditLog.action.in_(("signup", "login")))
               .values(detail=""))
    db.execute(update(AuditLog).where(AuditLog.user_id == uid).values(user_id=None))
    db.execute(delete(Membership).where(Membership.user_id == uid))
    db.execute(delete(User).where(User.id == uid))
    db.commit()


# ── API 키 ─────────────────────────────────────────────────────────────────────
# B2B 파일럿은 사람이 브라우저로 들어오는 경로(JWT)와 상대 시스템이 서버에서 부르는
# 경로(API 키) 둘 다 쓴다. 키는 **조직 단위**다 — 담당자가 퇴사해도 연동이 안 끊긴다.


def issue_api_key(db: Session, org_id: str, user_id: str, name: str) -> tuple[ApiKey, str]:
    """반환: (레코드, **원문**). 원문은 이 순간 이후 어디에도 없다."""
    raw, key_hash = generate_api_key()
    rec = ApiKey(org_id=org_id, name=name, key_hash=key_hash)
    db.add(rec)
    db.add(AuditLog(org_id=org_id, user_id=user_id,
                    action="api_key.issue", detail=name))
    db.commit()
    db.refresh(rec)
    return rec, raw


def list_api_keys(db: Session, org_id: str) -> list[ApiKey]:
    return list(db.execute(
        select(ApiKey).filter_by(org_id=org_id).order_by(ApiKey.created_at.desc())
    ).scalars())


def revoke_api_key(db: Session, org_id: str, user_id: str, key_id: str) -> ApiKey:
    """폐기는 삭제가 아니라 `revoked_at` 기록이다 — 감사추적에서 키가 사라지면
    '언제까지 유효했나'를 답할 수 없다(실사 항목 2)."""
    rec = db.execute(
        select(ApiKey).filter_by(id=key_id, org_id=org_id)
    ).scalar_one_or_none()
    if rec is None:
        raise ApiKeyNotFound(key_id)     # 다른 조직의 키도 여기로 떨어진다(존재 여부를 안 흘린다)
    if rec.revoked_at is None:
        rec.revoked_at = datetime.now(timezone.utc)
        db.add(AuditLog(org_id=org_id, user_id=user_id,
                        action="api_key.revoke", detail=rec.name))
        db.commit()
        db.refresh(rec)
    return rec


def resolve_api_key(db: Session, raw: str) -> tuple[Org, ApiKey] | None:
    """원문 키 → (조직, 키). 없거나 폐기됐으면 None.

    해시 컬럼은 unique 인덱스라 동등검색 한 번이다.
    """
    rec = db.execute(
        select(ApiKey).filter_by(key_hash=hash_api_key(raw))
    ).scalar_one_or_none()
    if rec is None or rec.revoked_at is not None:
        return None
    org = db.get(Org, rec.org_id)
    return (org, rec) if org is not None else None
