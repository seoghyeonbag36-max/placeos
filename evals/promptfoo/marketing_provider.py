"""promptfoo Python provider — services/marketing.py 의 LLM 호출 두 곳을 프로덕션 그대로 부른다.

- target=district → `_call_district_llm` + `ha_guard.check_district`   (get_district_marketing 과 같은 순서)
- target=program  → `_call_llm`         + `ha_guard.check_program`    (generate_program 과 같은 순서)

프로덕션이 호출 뒤에 돌리는 HA 후처리 검증기를 **같은 입력으로** 다시 돌려, 위반(violation)이
나오면 "이 프롬프트·모델 조합은 프로덕션에서 폐기될 출력을 낸다"로 읽는다.
키는 앱 설정(settings.llm_api_key)에서만 읽는다 — 이 파일은 키를 읽거나 출력하지 않는다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2] / "apps" / "backend"
sys.path.insert(0, str(_BACKEND))


def _result(contents: list[str], findings: list, extra: dict | None = None) -> dict:
    from app.services import ha_guard

    return {
        "output": json.dumps(
            {
                "contents": contents,
                "has_violation": ha_guard.has_violation(findings),
                "findings": [f.model_dump() for f in findings],
                **(extra or {}),
            },
            ensure_ascii=False,
        )
    }


def call_api(prompt: str, options: dict, context: dict) -> dict:
    try:
        from app.core.config import settings
        from app.services import ha_guard, marketing as mkt
        from app.services import program_brief
    except Exception as exc:  # 서비스가 옮겨졌거나 삭제됐다면 평가가 아니라 설정 문제다
        return {"error": f"marketing 서비스 import 실패: {exc!r}"}

    if not settings.llm_api_key:
        return {"error": "settings.llm_api_key 미설정 — 라이브 호출을 하지 않는다 (크레딧 보호)"}

    v = context["vars"]
    try:
        if v["target"] == "district":
            did = v["district_id"]
            ctx = mkt._district_context(did)
            if not ctx:
                return {"error": f"{did}: Gold 상권 컨텍스트 없음"}
            d = mkt.DISTRICTS_BY_ID.get(did, {})
            parsed = mkt._call_district_llm(d.get("name", did), d.get("sub", ""), ctx)
            findings = ha_guard.check_district(parsed, ctx)
            return _result(list(parsed.online_contents), findings,
                           {"ha_check": parsed.ha_check})

        brief = json.loads(v["brief"]) if isinstance(v["brief"], str) else v["brief"]
        ctx = mkt._district_context(brief.get("district_id"))
        site_ctx = mkt._site_context(brief)
        brief_ctx = program_brief.brief_context(brief)
        parsed = mkt._call_llm(brief, ctx, site_ctx, brief_ctx)
        findings = ha_guard.check_program(
            parsed, brief, "\n".join(c for c in (ctx, site_ctx) if c) or None)
        contents = [p.content for p in (*parsed.online, *parsed.offline)]
        return _result(contents, findings, {"ha_check": parsed.ha_check})
    except Exception as exc:
        # 파싱·호출 실패도 결과다 — 프로덕션에서는 이때 규칙 기반 스텁으로 내려간다.
        return {"error": f"LLM 호출 실패(프로덕션이면 스텁 폴백): {exc!r}"}
