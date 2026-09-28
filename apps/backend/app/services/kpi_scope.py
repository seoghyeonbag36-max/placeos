"""KPI③ 표본에서 내부·테스트 조직을 뺀다 — `usage` · `pmf` 가 함께 쓰는 단 한 곳.

## 왜 필요한가 (2026-09-28)

`usage.usage_summary` 와 `pmf.pmf_summary` 는 **모든 조직**을 셌다. 창업자 본인의 시험
가입, 08-28 계정층 검증 때 만든 조직이 `active_orgs` 와 NPS 표본에 그대로 섞인다.
파일럿 목표가 5~10곳이라 한두 곳이 판정을 바꾼다(n=5 에서 한 조직 = NPS 40포인트).

## 두 규칙의 합집합 — 결정 (a)+(b)

| 규칙 | 대상 | 어디서 바꾸나 |
|---|---|---|
| (a) 이름 접두사 `[내부]` | **앞으로** 만드는 시험 조직 | 가입할 때 조직 이름만 그렇게 쓴다(폰에서 끝난다) |
| (b) 환경변수 `KPI_EXCLUDE_ORG_IDS` | **이미 있는** 조직(이름을 바꿀 API 가 없다) | Cloud Run 환경변수(노트북) |

`orgs.is_internal` 컬럼(c)은 쓰지 않았다 — Neon 수동 upgrade 가 배포보다 늦으면 `orgs`
를 읽는 모든 쿼리(로그인 포함)가 깨진다. 파일럿이 붙어 조직 관리 화면이 필요해질 때 간다.

## 숨기지 않고 뺀다

뺀 조직은 응답의 `excluded_orgs`(수) · `excluded`(이름·id 앞 8자·사유)로 드러난다.
"파일럿 3곳"이 원래 5곳에서 2곳을 뺀 값인지 읽는 사람이 알아야 한다.
환경변수에 적혔는데 DB 에 없는 id 는 `exclusion_rules.env_ids_unmatched` 로 센다 —
오타가 난 id 는 아무것도 안 빼면서 **조용히** 통과하기 때문이다.

⚠ 판정 기준(`pmf.MIN_RESPONSES` 등)은 여기서 건드리지 않는다. 표본에서 무엇을 빼는가만 정한다.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.auth import Org

# (a) 조직 이름이 이것으로 시작하면(앞 공백 무시) 내부 조직이다. 반각 대괄호만 인정한다 —
# 전각 `［내부］` 까지 받으면 규칙이 흐려진다. 가입 화면 안내 문구와 같은 표기를 쓴다.
INTERNAL_NAME_PREFIX = "[내부]"
# (b) 쉼표·공백으로 구분한 org id 목록. id 는 uuid4().hex(32자 소문자)다.
EXCLUDE_ENV = "KPI_EXCLUDE_ORG_IDS"

REASON_NAME = "name_prefix"
REASON_ENV = "env"

# 화면·응답에 싣는 id 길이 — 전체 id 는 내지 않는다(조직 식별은 이름 + 앞 8자로 충분하다).
ID_PREFIX_LEN = 8


def env_excluded_ids() -> set[str]:
    """`KPI_EXCLUDE_ORG_IDS` 를 읽는다. 요청마다 읽는다(`ADMIN_TOKEN` 과 같은 방식).

    하이픈이 섞인 UUID 표기로 붙여 넣어도 저장 형식(hex 32자)으로 맞춘다.
    """
    raw = os.getenv(EXCLUDE_ENV, "")
    return {tok.replace("-", "").lower() for tok in re.split(r"[,\s]+", raw) if tok.strip()}


def is_internal_name(name: str | None) -> bool:
    return bool(name) and name.lstrip().startswith(INTERNAL_NAME_PREFIX)


@dataclass(frozen=True)
class KpiScope:
    """이번 요청에서 KPI③ 표본에서 뺄 조직과 그 사유."""

    reasons: dict[str, tuple[str, ...]] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)
    env_ids_configured: int = 0
    env_ids_unmatched: tuple[str, ...] = ()

    def is_excluded(self, org_id: str | None) -> bool:
        return org_id is not None and org_id in self.reasons

    def report(self, removed_org_ids: Iterable[str]) -> dict:
        """실제로 표본에서 빠진 조직만 싣는다(제외 대상이어도 이 표본에 없었으면 안 싣는다)."""
        removed = sorted(set(removed_org_ids))
        return {
            "excluded_orgs": len(removed),
            "excluded": [
                {"id_prefix": oid[:ID_PREFIX_LEN], "name": self.names.get(oid, ""),
                 "reasons": list(self.reasons[oid])}
                for oid in removed
            ],
            "exclusion_rules": {
                "name_prefix": INTERNAL_NAME_PREFIX,
                "env_var": EXCLUDE_ENV,
                "env_ids_configured": self.env_ids_configured,
                "env_ids_unmatched": [i[:ID_PREFIX_LEN] for i in self.env_ids_unmatched],
            },
        }


def resolve_scope(db: Session) -> KpiScope:
    """(a) 이름 접두사 ∪ (b) 환경변수 id — 제외 조직 집합을 한 번에 읽는다."""
    env_ids = env_excluded_ids()
    # SQL LIKE 에서 `[` 는 Postgres·SQLite 모두 일반 문자다. `%`·`_` 는 접두사에 없다.
    cond = func.ltrim(Org.name).like(f"{INTERNAL_NAME_PREFIX}%")
    if env_ids:
        cond = or_(cond, Org.id.in_(env_ids))
    rows = db.execute(select(Org.id, Org.name).where(cond)).all()

    reasons: dict[str, tuple[str, ...]] = {}
    names: dict[str, str] = {}
    for org_id, name in rows:
        r = tuple(tag for tag, hit in ((REASON_NAME, is_internal_name(name)),
                                       (REASON_ENV, org_id in env_ids)) if hit)
        if r:
            reasons[org_id] = r
            names[org_id] = name
    return KpiScope(
        reasons=reasons,
        names=names,
        env_ids_configured=len(env_ids),
        env_ids_unmatched=tuple(sorted(env_ids - {oid for oid, _ in rows})),
    )


def org_names(db: Session, org_ids: Iterable[str]) -> dict[str, str]:
    """표본 조직의 이름 — 화면이 id 앞 8자와 함께 보여 준다."""
    ids = list(set(org_ids))
    if not ids:
        return {}
    return dict(db.execute(select(Org.id, Org.name).where(Org.id.in_(ids))).all())
