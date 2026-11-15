"""조직 단위 상위 모델 — 설정이 비면 아무것도 바뀌지 않는다 (2026-11-15).

## 여기서 고정하는 계약

  ① **기본은 불변이다.** `LLM_PREMIUM_MODEL` · `LLM_PREMIUM_ORG_IDS` 중 하나라도 비면 모든
     조직이 `settings.llm_model` 로 간다 — 배포만으로 비용이 달라지지 않는다.
  ② **목록에 있는 조직만** 상위 모델로 간다. 목록 밖 조직·익명(org 없음)은 기본 모델이다.
  ③ 라우터가 고른 모델이 **실제 호출까지 전달된다**(`_call_llm` 의 `model` 인자).
     기본 모델일 때는 인자를 넘기지 않는다 — 종전 호출 모양 그대로다.

실호출은 어떤 경우에도 일어나지 않는다(`_call_llm` 을 가짜로 바꾼다).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import marketing as mkt
from tests.test_program_llm_gate import _BRIEF, _fake_plan

client = TestClient(app)
V1 = "/api/v1"

_ORG = "0123456789abcdef0123456789abcdef"
_PREMIUM = "premium-model-for-test"


@pytest.fixture
def base_model(monkeypatch):
    monkeypatch.setattr(settings, "llm_model", "base-model-for-test")
    monkeypatch.setattr(settings, "llm_premium_model", "")
    monkeypatch.setattr(settings, "llm_premium_org_ids", "")
    return "base-model-for-test"


def test_default_settings_keep_every_org_on_base_model(base_model):
    """① 설정이 비어 있으면 어느 조직이든 기본 모델이다."""
    assert mkt.program_model_for_org(_ORG) == base_model
    assert mkt.program_model_for_org(None) == base_model


@pytest.mark.parametrize("model, org_ids", [
    (_PREMIUM, ""),      # 모델만 있고 조직 목록이 없다
    ("", _ORG),          # 조직 목록만 있고 모델이 없다
    ("   ", _ORG),       # 공백뿐인 모델 이름
])
def test_half_configured_stays_on_base_model(base_model, monkeypatch, model, org_ids):
    """① 둘 중 하나만 채우면 켜지지 않는다 — 반쯤 설정된 채로 비용이 새지 않게."""
    monkeypatch.setattr(settings, "llm_premium_model", model)
    monkeypatch.setattr(settings, "llm_premium_org_ids", org_ids)
    assert mkt.program_model_for_org(_ORG) == base_model


def test_only_listed_orgs_get_premium_model(base_model, monkeypatch):
    """② 목록에 있는 조직만 상위 모델 — 하이픈 표기·대문자·공백 구분도 같은 조직으로 읽는다."""
    monkeypatch.setattr(settings, "llm_premium_model", _PREMIUM)
    monkeypatch.setattr(
        settings, "llm_premium_org_ids",
        "01234567-89AB-CDEF-0123-456789ABCDEF,\n ffffffffffffffffffffffffffffffff")
    assert mkt.program_model_for_org(_ORG) == _PREMIUM
    assert mkt.program_model_for_org("f" * 32) == _PREMIUM
    assert mkt.program_model_for_org("a" * 32) == base_model
    assert mkt.program_model_for_org(None) == base_model


@pytest.fixture
def model_spy(monkeypatch):
    """`_call_llm` 이 받은 인자를 그대로 적는다 — `model` 을 넘겼는지까지 본다."""
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    calls: list[dict] = []

    def spy(brief, ctx, site=None, brief_ctx=None, **kwargs):
        calls.append(kwargs)
        return _fake_plan()

    monkeypatch.setattr(mkt, "_call_llm", spy)
    monkeypatch.setattr(mkt, "_district_context", lambda d: None)
    return calls


def test_endpoint_passes_premium_model_for_listed_org(base_model, model_spy, monkeypatch,
                                                      signed_in):
    """③ 목록에 든 조직의 요청은 상위 모델 이름이 호출까지 간다."""
    me = client.get(f"{V1}/auth/me", headers=signed_in)
    assert me.status_code == 200, me.text
    org_id = me.json()["org"]["id"]
    monkeypatch.setattr(settings, "llm_premium_model", _PREMIUM)
    monkeypatch.setattr(settings, "llm_premium_org_ids", org_id)

    r = client.post(f"{V1}/marketing/generate", json=_BRIEF, headers=signed_in)
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "llm"
    assert model_spy == [{"model": _PREMIUM}]


def test_endpoint_keeps_old_call_shape_for_other_orgs(base_model, model_spy, monkeypatch,
                                                      signed_in):
    """③ 목록 밖 조직은 `model` 인자 없이 부른다 — 종전 호출 모양 그대로다."""
    monkeypatch.setattr(settings, "llm_premium_model", _PREMIUM)
    monkeypatch.setattr(settings, "llm_premium_org_ids", _ORG)

    r = client.post(f"{V1}/marketing/generate", json=_BRIEF, headers=signed_in)
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "llm"
    assert model_spy == [{}]
