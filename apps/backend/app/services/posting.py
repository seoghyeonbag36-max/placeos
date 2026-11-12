"""입점 솔루션(Posting) 서비스 — 외부 AI 창업 코파일럿 어댑터.

2026-07-18 개정: 외부에서 만든 AI 창업 코파일럿 프로그램을 연동해 적용한다.
- settings.posting_copilot_url 설정 시 외부 코파일럿 호출 → SimulateResult 로 정규화
- 미설정·호출 실패 시 내부 3-Tier(고급화/가성비/기능중심) 계산으로 폴백

2026-08-01: 코파일럿 명세가 아직 없어 실제로는 항상 폴백이 돈다. 그래서 **폴백의
입력**을 실데이터로 올렸다 — 유닛의 rent 는 R-ONE 임대료, foot 은 서울 상권분석
유동인구에서 온다(services/posting_inputs). area·prem 은 실데이터 소스가 없어
시드 프록시를 유지하며, 응답의 `inputs_source` 가 필드별 출처를 밝힌다.

2026-08-23: **명세를 기다리는 것을 그만두고 우리가 발행했다.** 공급자가 미정이라
기다리는 한 이 자리는 영원히 비어 있었다(07-18 이후 0%). 계약 `spaceos.posting/1` 은
services/posting_copilot 에 있고, 어댑터는 그에 맞춰 오늘 구현·검증됐다. 공급자가
정해지면 `POSTING_COPILOT_URL` 만 채우면 된다.

외부 코파일럿의 연동 형태(REST/패키지)에 대한 가정은 이 모듈 밖으로 내보내지 않는다.
"""
from __future__ import annotations

from app.core.config import settings
from app.services import districts as svc
from app.services import floor_vacancy
from app.services import posting_copilot
from app.services import posting_inputs
from app.services import industry_detail
from app.services import vacant_inventory


def _call_copilot(district_id: str, unit: dict,
                  industry_type: str | None) -> tuple[dict | None, str | None]:
    """외부 AI 창업 코파일럿 호출 → (시나리오, 실패사유).

    반환은 셋 중 하나다. **"안 붙였다"와 "붙였는데 실패했다"를 섞지 않는다** —
    예전에는 둘 다 그냥 폴백이라 화면에서 구분되지 않았고, 코파일럿이 죽어 있어도
    아무도 몰랐다(unviable_note 가 고쳤던 것과 같은 실패 양식이다).

      (None, None)      코파일럿 미설정 — 폴백이 정상 동작이다
      (None, "사유")     설정돼 있는데 실패 — 폴백이되 사유를 화면까지 올린다
      ({...}, None)     정상

    계약은 services/posting_copilot (spaceos.posting/1). 예외를 넓게 받는 이유는
    외부 공급자의 실패로 우리 API 가 5xx 를 내면 안 되기 때문이다 — 어떤 실패든
    폴백으로 같은 스키마를 돌려주는 것이 이 어댑터의 계약이다.
    """
    if not settings.posting_copilot_url:
        return None, None
    try:
        payload = posting_copilot.fetch(district_id, unit, industry_type)
        return posting_copilot.normalize(payload, svc.TIER), None
    except posting_copilot.ContractError as exc:
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001 — 외부 장애가 우리 5xx 가 되면 안 된다
        return None, f"코파일럿 호출 중 예외: {type(exc).__name__}: {exc}"


def _floor_unit_raw(district_id: str, unit_id: str) -> dict | None:
    """층 매물(`vfu-`) → 3-Tier 입력 모양. 그 층의 대장 면적·층 계수로 계산한다."""
    u = next((x for x in (floor_vacancy.load(district_id) or {}).get("units") or [] if x.get("id") == unit_id), None)
    if u is None:
        return None
    # `floor_mix` 를 비우면 임대료 계수가 건물 혼합이 아니라 이 층 라벨의 것이 된다.
    return {"id": u["id"], "n": u.get("n"), "lat": u.get("lat"), "lng": u.get("lng"),
            "area": u.get("area"), "floor": u.get("floor_label") or "1F", "was": u.get("was") or ""}


def _resolve_requested_unit(district_id: str, unit_id: str | None, area_py_override: float | None) -> dict | None:
    """요청이 층 매물이거나 면적을 덮어쓸 때만 입력을 다시 푼다. 그 밖은 종전 경로 그대로다(`vu-` 응답 불변).

    ⚠ 층 매물은 이 한 번의 계산에만 쓴다 — `/postings`·ROI 표본에 넣으면 중앙값 유닛이 상층부로 올라가 프라임
    프리미엄 트립와이어가 부호를 넘는다(`floor_vacancy` 머리말).
    유동 등급은 거점 안 서열이라 건물 유닛과 함께 풀고 그중 이 유닛만 꺼낸다.
    """
    peers = vacant_inventory.units(district_id) if posting_inputs.for_district(district_id) else []
    if unit_id and unit_id.startswith("vfu-"):
        raw = _floor_unit_raw(district_id, unit_id)
        if raw is None:
            return None
        peers = [*peers, raw]
    elif area_py_override is None:
        return None
    if not peers:
        return None
    target = unit_id or peers[0].get("id")
    if not any(p.get("id") == target for p in peers):
        return None
    if area_py_override is not None:
        peers = [{**p, "area": area_py_override} if p.get("id") == target else p for p in peers]
    return next(u for u in posting_inputs.resolve_units(district_id, peers) if u.get("id") == target)


def _apply_fitout(scenarios: dict, prem: float, fitout: int) -> None:
    """코파일럿 답에도 창업자가 넣은 견적을 투자비로 쓴다 — 공급자 계수로 견적을 덮지 않는다(2026-11-12)."""
    for s in scenarios.values():
        net = (s.get("_raw") or {}).get("net", s.get("month_net"))
        if s.get("available") is False or net is None:
            continue
        inv = prem / 100 + fitout / 100
        roi = float("inf") if net <= 0 else inv * 100 / net
        s["invest_mn"] = round(inv)
        s["roi_months"] = 99.0 if net <= 0 else round(roi, 1)
        if s.get("_raw") is not None:
            s["_raw"] = {**s["_raw"], "invest_mn": inv, "roi": roi}


def simulate(district_id: str, unit_id: str | None = None,
             industry_type: str | None = None, strategy: str | None = None,
             prem: int | None = None, industry_detail_key: str | None = None,
             operating_inputs: dict | None = None,
             area_py_override: float | None = None, rent_override: float | None = None,
             fitout_override: int | None = None) -> dict | None:
    """공실 유닛의 입점 시뮬레이션. 코파일럿 우선, 실패 시 3-Tier 폴백.

    strategy(premium/value/factory) 지정 시 해당 전략만, 미지정 시 3전략 비교 반환.
    `prem`(권리금)은 **입력 계약**이다 — 기업이 주면 그 값으로, 안 주면 0 전제로
    계산하고 `inputs_source["prem"]` 이 어느 쪽인지 밝힌다(2026-08-24 결정).
    반환: SimulateResult 스키마 dict. 거점/유닛을 찾지 못하면 None.
    """
    # 임대 표본 부재는 자리 부재가 아니다. Gold에 있는 자리를 404로 숨기거나
    # 임대료 0으로 계산하지 않고, 기존 계산 불가 계약으로 사유를 돌려준다.
    rent_inputs = posting_inputs.for_district(district_id)
    if district_id in svc.PAGES_BY_ID and not (rent_inputs or {}).get("rent_per_m2_krw_thousand"):
        raw_units = vacant_inventory.units(district_id)
        if unit_id and unit_id.startswith("vfu-"):
            raw = _floor_unit_raw(district_id, unit_id)
        elif unit_id:
            raw = next((u for u in raw_units if u["id"] == unit_id), None)
        else:
            raw = next(iter(raw_units), None)
        if raw is not None:
            return {"district_id": district_id, "unit_id": raw["id"], "industry_type": industry_type,
                    "scenarios": {}, "source": "unavailable", "calculation_status": "unavailable",
                    "unavailable_reason": "이 상권은 R-ONE 임대 표본이 없어 계산하지 않습니다. 이웃 값으로 채우지 않습니다."}
    is_floor_unit = bool(unit_id and unit_id.startswith("vfu-"))
    unit = None
    if is_floor_unit or area_py_override is not None:
        unit = _resolve_requested_unit(district_id, unit_id, area_py_override)
    if unit is None:
        if is_floor_unit:
            return None
        units = svc.resolved_units(district_id)
        if not units:
            return None
        unit = next((u for u in units if u["id"] == unit_id), None) if unit_id else units[0]
        if unit is None:
            return None
    if is_floor_unit:
        # 면적은 그 층의 대장 실측이다. `gold-ledger` 를 건물 유닛만 달아 주는 규칙(`_origin_src`)을 여기서 메운다.
        unit = {**unit, "inputs_source": {**(unit.get("inputs_source") or {}), "area": "gold-ledger-floor",
                                          "prem": "absent", "floor": "floor_unit"}}
    if area_py_override is not None:
        unit = {**unit, "area": area_py_override,
                "inputs_source": {**(unit.get("inputs_source") or {}), "area": "user_input"}}
    if rent_override is not None:
        # 계약서 월세(2026-11-12) — R-ONE 추정을 갈아 끼운다. 화면 · 메뉴 손익분기 · Program 인계가 같은 값을 쓰게
        # resolved_inputs 로도 내린다(아래).
        unit = {**unit, "rent": float(rent_override),
                "inputs_source": {**(unit.get("inputs_source") or {}), "rent": "contract"}}
    if operating_inputs is not None and not industry_detail_key:
        raise ValueError("운영 입력에는 세부 업종이 필요합니다")
    # 화면의 BEP·Program 인계도 이 계산과 정확히 같은 면적·임대료를 쓴다.
    resolved_inputs = ({"area_py": unit["area"], "rent_manwon": unit["rent"], "floor": unit["floor"]}
                       if is_floor_unit or area_py_override is not None or rent_override is not None else None)
    if industry_detail_key:
        from app.services import business_fit
        item = industry_detail.get(industry_detail_key)
        if item is None:
            raise ValueError("알 수 없는 세부 업종")
        parent = business_fit.get(item["parent"])
        allowed = {item["label"], item["key"], parent["key"], parent["label"], parent["input"]}
        if industry_type and industry_type.strip() not in allowed:
            raise ValueError("세부 업종과 업종 입력이 일치하지 않습니다")
        economics = industry_detail.calculate(industry_detail_key, operating_inputs or {})
        return {"district_id": district_id, "unit_id": unit["id"],
                "industry_type": economics["label"], "scenarios": {},
                "source": "user_input_scenario", "calculation_status": economics["status"],
                "unavailable_reason": "필수 운영 조건을 모두 입력해 주세요" if economics["status"] == "needs_inputs" else None,
                "economics": economics, "resolved_inputs": resolved_inputs}
    # 외식 평균 3-Tier를 다른 업종의 손익처럼 내보내지 않는다.
    # 업종 미선택은 종전 참고 계산이며 선택된 외식 업종도 세부 업종 예측이 아니다.
    if industry_type and industry_type.strip() not in {"카페", "카페·디저트", "음식점", "cafe", "restaurant"}:
        return {"district_id": district_id, "unit_id": unit["id"], "industry_type": industry_type,
                "scenarios": {}, "source": "unavailable", "calculation_status": "unavailable",
                "unavailable_reason": "선택 업종의 손익에는 세부 업종과 운영 조건이 필요합니다. 아래 세부 업종에서 입력해 주세요.", "resolved_inputs": resolved_inputs}
    if prem is not None:
        # 음수 권리금은 계약 위반이다 — 0 으로 잘라 내리지 않고 거부하면 400 이 필요한데,
        # 이 경로는 어떤 입력에도 같은 스키마를 돌려주는 것이 계약이라 0 으로 눕힌다.
        unit = {**unit, "prem": max(0, prem)}
        unit["inputs_source"] = {**(unit.get("inputs_source") or {}), "prem": "contract"}
    if fitout_override is not None:
        # 인테리어 · 설비 견적(2026-11-12) — 업종 평균 계수 대신 이 값. 출처를 밝혀 「투자비는 계수다」 경고를 거둔다
        unit = {**unit, "fitout": max(0, fitout_override)}
        unit["inputs_source"] = {**(unit.get("inputs_source") or {}), "invest": "user_input"}

    scenarios, fail = _call_copilot(district_id, unit, industry_type)
    source = "copilot"
    source_note = None
    if scenarios is None:
        # 실측으로 계산할 tier 가 하나도 없으면(매출 재료가 없는 고양·파주) 본전 시점을 답하지 않는다
        # (2026-10-27). 코파일럿이 답하면 그 답은 쓴다 — 막는 것은 우리가 지어낼 값뿐이다.
        scenarios = svc.tier_scenarios(unit, district_id)
        reason = svc.payback_unavailable_reason(district_id) or next(
            (s["unavailable_reason"] for s in scenarios.values()
             if not s.get("available", True)), None)
        if not any(s.get("available", True) for s in scenarios.values()):
            return {"district_id": district_id, "unit_id": unit["id"], "industry_type": industry_type,
                    "scenarios": {}, "source": "unavailable", "source_note": fail,
                    "inputs_source": unit.get("inputs_source"), "inputs_quarter": posting_inputs.quarter(),
                    "calculation_status": "unavailable", "unavailable_reason": reason, "resolved_inputs": resolved_inputs}
        # 일부 tier 만 자료 부족이면(가락·불광의 고급화) 선 tier 로 답하고, 빠진 tier 는 시나리오 안에서
        # `available: False` + 사유로 내려간다(2026-10-28 사용자 결정 (b)).
        source = "fallback-3tier"
        source_note = fail
    else:
        if fitout_override is not None:
            _apply_fitout(scenarios, unit.get("prem") or 0, unit["fitout"])
        # 추천은 **우리가** 계산한다 — 기준(회수 최단)이 제품 정의라 공급자가 못 바꾼다.
        # 반올림 전 `_raw` 로 고르고 표시만 반올림하는 것도 폴백과 동일하게 맞춘다.
        best = svc.recommend_tier(scenarios)
        for k, s in scenarios.items():
            s["recommended"] = k == best
            s.pop("_raw", None)
    # 전략 필터 **전에** 판정한다 — 한 전략만 뽑고 나서 보면 "그 전략이 안 된다"와
    # "이 자리가 안 된다"가 뒤섞인다.
    note = svc.unviable_note(scenarios)
    if strategy in scenarios:
        picked = scenarios[strategy]
        if picked.get("available") is False:
            # 고른 전략이 자료 부족이다(가락·불광의 고급화). 「계산했는데 회수가 안 된다」로 읽히지 않게
            # 계산 불가로 답한다 — 계산한 다른 전략은 전략을 비우고 다시 물으면 나온다(2026-10-28 리뷰).
            return {"district_id": district_id, "unit_id": unit["id"], "industry_type": industry_type,
                    "scenarios": {}, "source": "unavailable", "source_note": source_note,
                    "inputs_source": unit.get("inputs_source"), "inputs_quarter": posting_inputs.quarter(),
                    "calculation_status": "unavailable", "unavailable_reason": picked.get("unavailable_reason"), "resolved_inputs": resolved_inputs}
        scenarios = {strategy: picked}
    return {
        "district_id": district_id,
        "unit_id": unit["id"],
        "industry_type": industry_type,
        "scenarios": scenarios,
        "source": source,
        # 폴백으로 떨어진 **이유**. 미설정이면 None, 호출 실패면 사유가 들어간다.
        "source_note": source_note,
        # 시나리오를 만든 입력의 필드별 출처 — 프록시를 실측으로 오독하면 안 된다
        "inputs_source": unit.get("inputs_source"),
        "inputs_quarter": posting_inputs.quarter(),
        "unviable_note": note,
        "resolved_inputs": resolved_inputs,
    }
