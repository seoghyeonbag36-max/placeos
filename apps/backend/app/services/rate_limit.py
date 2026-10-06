"""요청량 제어 — 비용이 새는 경로와 무차별 대입을 막는 카운터 (2026-10-06).

## 왜 필요한가

2026-10-06 점검(docs/finding-project-review-4roles-2026-10-06.md §6 ①)에서 `app/` 에 요청량
제한이 **0줄**이었다. 그 결과 둘이 열려 있었다.

- **LLM 비용.** `POST /marketing/generate` 는 호출 1회가 곧 LLM 1회이고 캐시가 없다. 익명은
  막아 두었지만(2026-10-03) 가입이 무료이고 무제한이라, 계정을 만들어 반복 호출하면 막은 의미가
  없었다.
- **무차별 대입.** 로그인 비밀번호와 관리자 토큰을 몇 번 틀려도 아무 일이 없었다.

## 키에 클라이언트 IP 를 쓰지 않는다

요청은 Firebase Hosting → Cloud Run 을 거쳐 온다. `X-Forwarded-For` 의 어느 홉을 믿어야 하는지
실측하지 않았고, 맨 앞 값은 클라이언트가 마음대로 적을 수 있다. IP 로 묶으면 헤더만 바꿔 가며
우회한다. 그래서 **요청자가 바꿀 수 없는 키**만 쓴다.

| 대상 | 키 | 창 | 넘으면 |
|---|---|---|---|
| 로그인 실패 | 이메일(계정 단위) | 15분 | 그 이메일의 비밀번호 로그인 429 (구글 로그인은 그대로) |
| 새 계정 생성 | 전역 | 1시간 | 가입 429 (기존 계정 로그인은 그대로) |
| LLM 생성 | 조직 + 전역 | 24시간 | 같은 200 에 규칙 스텁(`stub_reason: "llm_quota"`) |
| 관리자 토큰 실패 | 전역 | 15분 | 관리자 API 429 — **맞는 토큰도** 창이 끝날 때까지 막힌다 |

관리자 쪽이 전역인 것은 의도다. 계정마다 나눌 키가 없고(토큰 하나), 막지 않으면 대입 속도에
상한이 없다. 대신 공격자가 관리자 화면을 15분씩 막아 둘 수 있는데, 그 화면은 운영자 한 명이
가끔 보는 화면이라 대입을 허용하는 쪽보다 싸다.

## 읽을 때 반드시 아는 것 (한계)

1. **프로세스 로컬이다** — `services/latency` 와 같다. Cloud Run 인스턴스마다 따로 세므로
   **실효 상한 = 설정값 × 인스턴스 수**다(최대 3대 · 2026-10-06 `gcloud run services describe` 확인).
   재시작하면 0 이다. 새 의존성(Redis 등) 없이 시작한다는 선택이다(decision-lightweight-first).
2. **고정 창이다.** 창의 경계에서는 최대 두 배가 몰릴 수 있다. 막는 것은 "무제한"이지 "정확한 분당 N회"가 아니다.
3. 키가 많은 표(로그인 실패·조직)는 `MAX_KEYS` 를 넘으면 가장 오래 손대지 않은 키부터 버린다 —
   메모리는 유한하고, 버리려면 그만큼 요청을 더 보내야 하므로 우회 비용이 커진다.
"""
from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict

from app.core.config import settings

GLOBAL = "*"
MAX_KEYS = 10_000

LOGIN_WINDOW_S = 15 * 60
ADMIN_WINDOW_S = 15 * 60
SIGNUP_WINDOW_S = 60 * 60
LLM_WINDOW_S = 24 * 60 * 60

# 테스트가 시계를 바꿔 끼운다(창이 끝난 뒤를 기다리지 않고 재기 위해).
_clock = time.monotonic
_lock = threading.Lock()


class _Window:
    """키별 고정 창 카운터. 호출부가 `_lock` 을 잡은 채로 쓴다."""

    def __init__(self, window_s: float, max_keys: int = MAX_KEYS) -> None:
        self.window_s = window_s
        self.max_keys = max_keys
        self._hits: OrderedDict[str, tuple[float, int]] = OrderedDict()

    def _live(self, key: str, now: float) -> tuple[float, int]:
        hit = self._hits.get(key)
        if hit is None or now - hit[0] >= self.window_s:
            return now, 0
        return hit

    def count(self, key: str, now: float) -> int:
        return self._live(key, now)[1]

    def retry_after(self, key: str, now: float) -> int:
        """창이 끝날 때까지 남은 초(올림, 최소 1)."""
        start, _ = self._live(key, now)
        return max(1, math.ceil(start + self.window_s - now))

    def add(self, key: str, now: float) -> None:
        start, n = self._live(key, now)
        self._hits[key] = (start, n + 1)
        self._hits.move_to_end(key)
        while len(self._hits) > self.max_keys:
            self._hits.popitem(last=False)

    def clear(self, key: str) -> None:
        self._hits.pop(key, None)

    def reset(self) -> None:
        self._hits.clear()


_login_failures = _Window(LOGIN_WINDOW_S)
_admin_failures = _Window(ADMIN_WINDOW_S, max_keys=1)
_signups = _Window(SIGNUP_WINDOW_S, max_keys=1)
_llm_by_org = _Window(LLM_WINDOW_S)
_llm_global = _Window(LLM_WINDOW_S, max_keys=1)


def _blocked(window: _Window, key: str, limit: int, now: float) -> int:
    """한도에 닿았으면 남은 초, 아니면 0."""
    return window.retry_after(key, now) if window.count(key, now) >= limit else 0


# ── 로그인 실패 (이메일 단위) ─────────────────────────────────────────────────

def login_retry_after(email: str) -> int:
    """이 이메일의 비밀번호 로그인이 막혀 있으면 남은 초, 아니면 0."""
    with _lock:
        return _blocked(_login_failures, email.lower(), settings.login_failures_per_email, _clock())


def record_login_failure(email: str) -> None:
    with _lock:
        _login_failures.add(email.lower(), _clock())


def clear_login_failures(email: str) -> None:
    """로그인에 성공하면 그 이메일의 실패를 지운다 — 몇 번 틀린 진짜 주인이 계속 막히지 않게."""
    with _lock:
        _login_failures.clear(email.lower())


# ── 관리자 토큰 실패 (전역) ───────────────────────────────────────────────────

def admin_retry_after() -> int:
    with _lock:
        return _blocked(_admin_failures, GLOBAL, settings.admin_failures_per_instance, _clock())


def record_admin_failure() -> None:
    with _lock:
        _admin_failures.add(GLOBAL, _clock())


# ── 새 계정 생성 (전역) ───────────────────────────────────────────────────────

def try_signup() -> int:
    """새 계정 하나를 만들어도 되면 세고 0, 한도면 세지 않고 남은 초를 준다."""
    with _lock:
        now = _clock()
        retry = _blocked(_signups, GLOBAL, settings.signup_hourly_cap_per_instance, now)
        if not retry:
            _signups.add(GLOBAL, now)
        return retry


# ── LLM 생성 (조직 + 전역) ────────────────────────────────────────────────────

def try_llm(org_id: str) -> bool:
    """LLM 1회를 써도 되면 조직·전역 양쪽에 세고 True. 어느 한쪽이라도 한도면 세지 않고 False."""
    with _lock:
        now = _clock()
        if (_llm_by_org.count(org_id, now) >= settings.llm_daily_quota_per_org
                or _llm_global.count(GLOBAL, now) >= settings.llm_daily_cap_per_instance):
            return False
        _llm_by_org.add(org_id, now)
        _llm_global.add(GLOBAL, now)
        return True


def reset() -> None:
    """테스트용. 운영 경로에서는 부르지 않는다."""
    with _lock:
        for w in (_login_failures, _admin_failures, _signups, _llm_by_org, _llm_global):
            w.reset()
