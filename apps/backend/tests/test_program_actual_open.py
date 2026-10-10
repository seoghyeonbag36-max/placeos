"""실제 창업 선택은 계획이며, 실적이나 목표 금액을 날조하지 않는다."""
from app.schemas.marketing import ProgramBrief
from app.services import marketing, program_brief


def test_actual_open_request_and_context():
    brief = ProgramBrief(item="테스트 매장", category="카페", mode="actual_open", stage="pre_founder")
    context = program_brief.brief_context(brief.model_dump())
    assert "실제 창업" in context
    assert "실측 비용이 없으면 손익분기 목표 금액을 지어내지 않는다" in context
    assert "고객·후기·매출 실적이 확인되지는 않는다" in context


def test_actual_open_rule_plan_uses_real_cost_measurement():
    brief = ProgramBrief(item="테스트 매장", category="카페", mode="actual_open", stage="pre_founder")
    plan = marketing.generate_program(brief.model_dump(), allow_llm=False)
    assert plan["mode"] == "actual_open"
    assert plan["source"] == "rule-stub"
    assert "정식 개업" in plan["offline"][0]["channel"]
    assert "단기" not in plan["offline"][0]["content"]
    signal = plan["signals"][0]
    assert "POS 실매출" in signal["method"]
    assert "비용 미입력 시 목표 미설정" in signal["target"]
