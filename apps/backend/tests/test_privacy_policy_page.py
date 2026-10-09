"""개인정보 처리방침 정적 페이지 = 코드가 하는 일과 같아야 한다 (2026-10-08).

처리방침(`apps/frontend/public/privacy.html`)은 사람이 쓴 글이라 코드가 바뀌어도 혼자 낡는다. 그런데
이 문서는 법정 공개 의무(개인정보 보호법 제30조)이고, 구글 OAuth 앱 게시의 필수 링크이기도 하다.
그래서 **어긋남이 생기면 여기서 먼저 운다**.

잠그는 것
1. **표가 늘면 운다** — 계정층 ORM 표 집합이 바뀌면(새 개인정보 칸이 생겼을 수 있다) 처리방침을 고치라고 알려 준다.
2. 표마다 처리방침이 그 항목을 말하고 있다.
3. 외부로 정보가 나가는 곳(호스팅·DB·LLM·지도·로그인)이 국외 이전 표와 §5 에 적혀 있다.
4. 법이 요구하는 절(보관·파기·제3자 제공·국외 이전·보호책임자·시행일)이 빠지지 않았다.
5. **미완성 표시가 남은 채로 나가지 않는다.**
6. 정적 서빙이 실제로 되고, 옛 빌드를 붙잡지 않도록 no-cache 로 나간다(FrontendFiles).

못 잡는 것: 문장이 사실인지(예: Neon 리전). 그건 사람이 콘솔에서 확인한 값이다 —
docs/runbook-custom-domain-placeos-kr-2026-10-08.md §5.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.db import Base
import app.models.auth  # noqa: F401  — 표를 Base.metadata 에 올린다
import app.models.feedback  # noqa: F401
from app.main import FrontendFiles

POLICY = Path(__file__).resolve().parents[2] / "frontend" / "public" / "privacy.html"

# 표 → 처리방침이 그 항목을 가리키는 말. 표가 늘면 이 사전도 같이 늘려야 하고, 늘리려면 처리방침을 먼저 읽게 된다.
TABLE_TO_POLICY_WORD = {
    "users": "이메일 주소",
    "orgs": "조직(사업) 이름",
    "memberships": "멤버십",
    "api_keys": "API 키",
    "audit_log": "이용 기록",
    "business_workspaces": "사업 정보",
    "revoked_tokens": "로그아웃",
    "pilot_feedback": "피드백",
    "social_identities": "고유 사용자 ID",
}


def _text() -> str:
    html = POLICY.read_text(encoding="utf-8")
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)       # 주석(작성자 메모)은 본문이 아니다
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_policy_file_exists():
    assert POLICY.is_file(), f"처리방침이 없다: {POLICY}"


def test_new_table_means_policy_review():
    """새 표가 생기면 개인정보 항목이 늘었을 수 있다 — 처리방침의 §1·§4 를 고치고 이 사전에 추가한다."""
    tables = set(Base.metadata.tables)
    assert tables == set(TABLE_TO_POLICY_WORD), (
        f"계정층 표가 바뀌었다. 새로 생긴 표: {sorted(tables - set(TABLE_TO_POLICY_WORD))} · "
        f"사라진 표: {sorted(set(TABLE_TO_POLICY_WORD) - tables)}. "
        "apps/frontend/public/privacy.html 의 §1(받는 항목)·§2(파기)·§4(국외 이전)를 고친 뒤 TABLE_TO_POLICY_WORD 를 갱신할 것."
    )


def test_every_table_is_described():
    text = _text()
    missing = {t: w for t, w in TABLE_TO_POLICY_WORD.items() if w not in text}
    assert not missing, f"처리방침이 말하지 않는 표: {missing}"


def test_outbound_services_are_disclosed():
    text = _text()
    for name in ("Google LLC", "Neon, Inc.", "Anthropic, PBC", "네이버 지도", "카카오맵", "구글 로그인"):
        assert name in text, f"외부로 정보가 나가는 곳이 처리방침에 없다: {name}"


def test_required_sections_present():
    text = _text()
    for heading in ("받는 개인정보와 쓰는 목적", "보관 기간과 파기", "제3자 제공", "처리 위탁과 국외 이전",
                    "이용자의 권리", "안전성 확보 조치", "개인정보 보호책임자", "시행일"):
        assert heading in text, f"법정 절이 빠졌다: {heading}"


def test_withdrawal_is_promised_and_contact_is_public():
    text = _text()
    assert "탈퇴하면 바로 지웁니다" in text
    html = POLICY.read_text(encoding="utf-8")
    assert re.search(r'href="mailto:[^"@\s]+@[^"@\s]+\.[a-z]+"', html), "보호책임자 연락처(mailto)가 없다"


def test_no_unfinished_markers_ship():
    """작성 중 표시가 남은 처리방침은 공개하지 않는다(구글 심사 봇도, 이용자도 그대로 읽는다)."""
    text = _text()
    for marker in ("TODO", "TBD", "XXX", "{{", "}}", "[[", "]]", "확인 필요", "확인필요", "미정", "추후 기재", "○○"):
        assert marker not in text, f"미완성 표시가 남았다: {marker!r}"


def test_served_statically_and_never_cached(tmp_path):
    """FrontendFiles 가 /privacy.html 을 200 으로 내고, 옛 문구를 붙잡지 않게 no-cache 로 낸다."""
    (tmp_path / "privacy.html").write_text(POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    mini = FastAPI()
    mini.mount("/", FrontendFiles(directory=str(tmp_path), html=True), name="frontend")
    r = TestClient(mini).get("/privacy.html")
    assert r.status_code == 200
    assert "개인정보 처리방침" in r.text
    assert r.headers["cache-control"] == "no-cache"
