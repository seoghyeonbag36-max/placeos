"""AI 오케스트라 수용 테스트 — 구현 전 계약 제안(TDD red).

운영 인터페이스가 이미 있다는 뜻이 아니다. 이 파일은 다음 최소 인터페이스를
제안하며, 구현이 없으면 skip/xfail 대신 명시적으로 실패한다.

Orchestrator(store_path, tools, provider): 파일 경로는 테스트 임시 저장소.
create(org_id, inputs, budget_units) / advance(org_id, run_id, until=None)
get(org_id, run_id) / cancel(org_id, run_id): 상태는 dict로 반환.
상태: status, completed_steps, results, missing_inputs, spent_units, reason.
도구는 platform/page/posting/program 순서로 호출하며 입력 dict를 받는다.
provider.generate(context)는 payload와 cost_units를 반환한다.

모든 입력·공급자 응답·비용 단위는 합성 테스트 fixture다. 실측·실제 가격이 아니다.
TODO: 운영 구현에서 기존 서비스·HA 검증·인증 컨텍스트에 연결한다.
외부 모델과 실제 Gold는 호출하지 않는다. 실행 관리자 자체는 목킹하지 않는다.
"""
from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from typing import Any

import pytest


EVIDENCE = {
    "vacancy_source": "synthetic",
    "inputs_source": {"rent": "seed", "foot": "seed"},
    "inputs_quarter": "2026Q2",
    "assumptions": ["합성 테스트 입력"],
    "claims": [{"text": "저녁 수요를 검증한다", "source": "user_input"}],
}
INPUTS = {"item": "테스트 카페", "category": "카페", "operating_inputs":
          {"monthly_rent": 100, "opening_days": 20}, "evidence": EVIDENCE}


def implementation() -> Any:
    """미구현 상태를 수집 오류나 건너뛰기가 아닌 테스트 실패로 보고한다."""
    try:
        return import_module("app.services.ai_orchestration")
    except ModuleNotFoundError as exc:
        if exc.name != "app.services.ai_orchestration":
            raise
        pytest.fail("미구현: app.services.ai_orchestration — 오케스트라 계약을 충족해야 합니다")


class Provider:
    """공급자 경계만 대체한다. payload도 합성값이다."""

    def __init__(self, payload: Any = None, cost: int = 1) -> None:
        self.payload = payload if payload is not None else {"unexpected": "schema violation"}
        self.cost = cost
        self.calls: list[dict] = []

    def generate(self, context: dict) -> dict:
        self.calls.append(deepcopy(context))
        return {"payload": deepcopy(self.payload), "cost_units": self.cost}


class Tools:
    """합성 데이터 도구. 받은 입력을 기록해 단계 전달을 검사한다."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def bindings(self) -> dict:
        def bind(step: str) -> Any:
            def invoke(context: dict) -> dict:
                self.calls.append((step, deepcopy(context)))
                return {"evidence": deepcopy(context["evidence"]), "fixture": step}
            return invoke
        return {step: bind(step) for step in ("platform", "page", "posting")}


def manager(module: Any, path: Any, tools: Tools, provider: Provider) -> Any:
    return module.Orchestrator(store_path=path, tools=tools.bindings(), provider=provider)


def test_pppp_preserves_provenance(tmp_path: Any) -> None:
    module, tools, provider = implementation(), Tools(), Provider()
    engine = manager(module, tmp_path / "runs.sqlite", tools, provider)
    run = engine.create(org_id="org-a", inputs=deepcopy(INPUTS), budget_units=10)
    state = engine.advance(org_id="org-a", run_id=run["id"], until="posting")
    assert [step for step, _ in tools.calls] == ["platform", "page", "posting"]
    for _, context in tools.calls:
        assert context["evidence"] == EVIDENCE
    for step in ("platform", "page", "posting"):
        assert state["results"][step]["evidence"] == EVIDENCE
    restored = manager(module, tmp_path / "runs.sqlite", Tools(), Provider())
    assert restored.get(org_id="org-a", run_id=run["id"])["results"] == state["results"]


def test_missing_inputs_pause_without_invention(tmp_path: Any) -> None:
    module, tools, provider = implementation(), Tools(), Provider()
    engine = manager(module, tmp_path / "runs.sqlite", tools, provider)
    inputs = deepcopy(INPUTS)
    del inputs["operating_inputs"]
    run = engine.create(org_id="org-a", inputs=inputs, budget_units=10)
    state = engine.advance(org_id="org-a", run_id=run["id"])
    assert state["status"] == "waiting_inputs"
    assert "operating_inputs" in state["missing_inputs"]
    assert "operating_inputs" not in state["inputs"]
    assert not any(step == "posting" for step, _ in tools.calls)
    assert provider.calls == []


def test_run_is_isolated_by_org(tmp_path: Any) -> None:
    module, tools, provider = implementation(), Tools(), Provider()
    engine = manager(module, tmp_path / "runs.sqlite", tools, provider)
    run = engine.create(org_id="org-a", inputs=deepcopy(INPUTS), budget_units=10)
    before = deepcopy(engine.get(org_id="org-a", run_id=run["id"]))
    for action in (engine.get, engine.advance, engine.cancel):
        with pytest.raises(module.RunNotFound):
            action(org_id="org-b", run_id=run["id"])
    assert engine.get(org_id="org-a", run_id=run["id"]) == before
    assert tools.calls == []
    assert provider.calls == []


def test_resume_skips_completed_steps(tmp_path: Any) -> None:
    module, tools = implementation(), Tools()
    path = tmp_path / "runs.sqlite"
    engine = manager(module, path, tools, Provider())
    run = engine.create(org_id="org-a", inputs=deepcopy(INPUTS), budget_units=10)
    before = engine.advance(org_id="org-a", run_id=run["id"], until="page")
    assert before["completed_steps"] == ["platform", "page"]
    resumed_tools = Tools()
    resumed = manager(module, path, resumed_tools, Provider())
    after = resumed.advance(org_id="org-a", run_id=run["id"], until="posting")
    assert [step for step, _ in resumed_tools.calls] == ["posting"]
    for step in ("platform", "page"):
        assert after["results"][step] == before["results"][step]


def test_model_switch_keeps_validation(tmp_path: Any) -> None:
    from tests.conftest import _act, _perf, _signal
    from app.schemas.marketing import LLMProgramPlan

    module = implementation()
    valid = LLMProgramPlan(
        online=[_perf(channel="테스트 채널", content="방문 의향 설문", rationale="가설 검증")],
        offline=[_act(channel="팝업", content="방문객 기록", rationale="가설 검증")],
        signals=[_signal()],
                           ha_check="합성 테스트 입력 점검").model_dump()
    bad_price = deepcopy(valid)
    bad_price["online"][0]["content"] = "입장료 123456원을 받는다"
    for supplier in ("supplier-a", "supplier-b"):
        for label, payload, accepted in (("valid", valid, True),
                                         ("schema", {"unexpected": True}, False),
                                         ("ha", bad_price, False)):
            provider = Provider(payload)
            engine = manager(module, tmp_path / f"{supplier}-{label}.sqlite", Tools(), provider)
            run = engine.create(org_id="org-a", inputs=deepcopy(INPUTS), budget_units=10)
            state = engine.advance(org_id="org-a", run_id=run["id"])
            assert len(provider.calls) == 1
            assert (state["status"] == "completed") is accepted
            if not accepted:
                assert "program" not in state["results"]
                assert state["reason"] in {"schema_violation", "ha_violation"}


def test_run_budget_stops_further_calls(tmp_path: Any) -> None:
    module, tools, provider = implementation(), Tools(), Provider()
    path = tmp_path / "runs.sqlite"
    engine = manager(module, path, tools, provider)
    run = engine.create(org_id="org-a", inputs=deepcopy(INPUTS), budget_units=0)
    state = engine.advance(org_id="org-a", run_id=run["id"])
    assert state["status"] == "budget_exhausted"
    assert state["reason"] == "run_budget"
    assert state["spent_units"] == 0
    assert provider.calls == []
    replacement = Provider()
    resumed = manager(module, path, Tools(), replacement)
    again = resumed.advance(org_id="org-a", run_id=run["id"])
    assert again["status"] == "budget_exhausted"
    assert replacement.calls == []
