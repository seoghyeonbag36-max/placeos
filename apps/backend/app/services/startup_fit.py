"""[Page] 빈 층마다 「창업 가능 등급」과 「건물주 등록 여부」 — 요청 때 계산한다(2026-11-25 사용자 요청).

## 무엇을 답하나
Page 의 빈 층(`floor_vacancy` · 확인 · 추정)마다 두 가지를 붙인다.

1. **창업 가능 등급** — 창업 여력 있음(A1) · 창업 가능 · 여력 얇음(A2) · 조건부 · 확인 필요(B) · 창업 어려움(C)
   - 법·용도: `use_check.check` 를 일반 창업 6업종(`FOUNDER`)으로 돌린다 — 흐름 R4 입점 점검과 같은 규칙이다.
     Gold 층 대장에는 용도코드가 없어 대장 용도명으로 별표1 호를 근사한다(`ho_approx`). 같은 규칙을 실시간 용도코드로
     돌린 집계(docs/finding-eum-landuse-2026-11-15.md §4)와 업종·판정별 비율 차이는 최대 1.5%p 였다(2026-11-23 대조).
   - 수지: Posting 3-Tier(`districts.tier_scenarios`)를 그 층에 **1층 기준**으로 돌린다 — 매출에 층 보정이 없어서,
     상층을 층 계수 임대료로만 보면 매출은 1층 그대로라 낙관으로 기운다. 상층은 「이 층 임대료」로도 따로 계산해 둘 다 적는다.
     기준선은 서울 같은 가격대 평균 영업이익률(KOSIS `profit_rate`)이다 — 새 임계값을 만들지 않는다(KPI 규칙 ①과 같은 원칙).
   - 자리: 추정 빈 층 · 300㎡ 이상 · 건물 상업층 전체 공실은 「조건부」, 3층 이상은 참고만(등급 불변).
2. **건물주 등록** — 같은 건물 ID + 층에 게시 중 · 소유자 확인 매물(L3)이 있는가. 앱의 3D 트윈 · 자리 상세가 쓰는 키와 같다.
   직거래 표가 없으면 「not_ready」, DB 를 못 읽으면 「unavailable」 — 둘 다 0 건이 아니다(모르는 것을 없다고 세지 않는다).

## 무엇이 아닌가
- 허가 판정이 아니다. 대장 · 토지이음 기재와 PlaceOS 계산으로 본 1차 분류이고, 화면도 그렇게 적는다.
- 임대료는 R-ONE 1층 임대료 × 층 계수(실측 아님) — 「이 층 월세」가 아니다. 건물주 매물이 붙으면 그 월세로 다시 봐야 한다.
- 매물을 고르거나 순위를 매기지 않는다(직거래 규칙: PlaceOS 는 조건을 조율 · 권고하지 않는다).

등급 부분은 Gold 와 규칙으로만 정해지므로 상권별로 잠시 기억한다(`_TTL_SECONDS`). 건물주 등록은 요청마다 DB 를 읽는다.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services import business_fit, direct_listings, floor_vacancy, posting_inputs, posting_revenue, use_check, \
    vacant_inventory
from app.services import districts as district_svc

_TTL_SECONDS = 600.0
_cache: dict[str, tuple[float, list[dict]]] = {}

TIERS = ("premium", "value", "factory")
TIER_LABEL = {"premium": "고급화", "value": "가성비", "factory": "공장제"}
# 일반 창업 6업종 — use_check.INDUSTRY_ACTS 의 키. 의원 · 약국(면허 업종) · 숙박 · 전시는 뺀다.
FOUNDER = ("cafe", "restaurant", "convenience", "beauty", "education", "fitness")
GRADES = ("A1", "A2", "B", "C")
GRADE_LABEL = {"A1": "창업 여력 있음", "A2": "창업 가능 · 여력 얇음", "B": "조건부 · 확인 필요", "C": "창업 어려움"}
LARGE_M2 = 300          # 별표1 휴게음식점 · 제과점이 1·2종 근생으로 갈리는 면적(같은 건물 합계 — 여기선 층 면적으로 본다)

# ── 대장 용도명 → 건축법 시행령 별표1 호(근사) ───────────────────────────────────────────
# 별표1 의 면적 기준은 「같은 건축물에서 그 용도로 쓰는 바닥면적 합계」인데 여기서는 그 층 면적으로 본다.
HO_BY_NAME: dict[str, int] = {
    # 제3호 제1종 근린생활시설
    "소매점": 3, "상점(소매점)": 3, "의약품판매소": 3, "의료기기판매소": 3,
    "이(미)용원": 3, "미용원": 3, "이용원": 3, "목욕장": 3, "일반목욕장": 3, "세탁소": 3,
    "의원": 3, "치과의원": 3, "한의원": 3, "침술원": 3, "조산원": 3, "조산소": 3, "안마원": 3, "산후조리원": 3,
    "기타제1종근린생활시설": 3, "탁구장": 3, "체육도장": 3,
    "공중화장실": 3, "마을공동시설": 3, "지역아동센터": 3, "파출소": 3, "지역자치센터": 3, "우체국": 3,
    "공공도서관": 3, "변전소": 3, "통신용시설": 3,
    # 제4호 제2종 근린생활시설
    "일반음식점": 4, "주점영업": 4, "기타제2종근린생활시설": 4, "기원": 4, "당구장": 4, "체력단련장": 4,
    "노래연습장": 4, "사진관": 4, "표구점": 4, "안마시술소": 4, "수리점": 4, "총포판매사": 4, "총포판매소": 4,
    "서점(1종근.생미해당)": 4, "자동차영업소": 4, "비디오물감상실": 4, "멀티미디어문화컨텐츠설비제공업소": 4,
    "인터넷컴퓨터게임시설제공업소": 4, "게임제공업소": 4, "청소년게임제공업소": 4, "복합유통게임제공업소": 4,
    "복합유통.제공업소": 4, "놀이형시설": 4,
    # 제5호 문화 및 집회시설 · 제6호 종교시설
    "기타전시장": 5, "미술관": 5, "박물관": 5, "기념관": 5, "과학관": 5, "문화관": 5, "체험관": 5, "산업전시장": 5,
    "기타문화및집회시설": 5, "예식장": 5, "기타집회장": 5, "수도원": 6,
    # 제7호 판매시설
    "기타판매시설": 7, "기타소매시장": 7, "의약품도매점": 7, "일반게임제공업의시설": 7,
    "인터넷컴퓨터게임시설제공업의시설": 7, "청소년게임제공업의시설": 7, "복합유통게임제공업의시설": 7,
    # 제9호 의료시설 · 제10호 교육연구시설 · 제11호 노유자시설
    "병원": 9, "요양병원": 9, "한방병원": 9, "치과병원": 9, "기타병원": 9, "기타의료시설": 9,
    "연구소": 10, "기타연구소": 10, "기타교육연구시설": 10, "교육원": 10, "교육(연수)원": 10, "연수원": 10,
    "도서관": 10, "초등학교": 10, "유치원": 10,
    "노인복지시설": 11, "기타노유자시설": 11, "어린이집": 11, "영유아보육시설": 11, "사회복지시설": 11,
    "아동복지시설": 11, "기타아동관련시설": 11,
    # 제13호 운동 · 제14호 업무 · 제1호 단독(공관) · 제15호 숙박 · 제16호 위락
    "기타운동시설": 13, "기타 운동시설": 13, "체육관": 13, "체육장": 13,
    "자치단체청사": 14, "공관": 1, "여인숙": 15,
    "유흥주점": 16, "기타위락시설": 16, "무도장(학원)": 16, "투전기업소": 16, "유기장": 16,
    # 제19호 위험물 · 제20호 자동차 · 제21호 동식물 · 제24호 방송통신 · 제27호 관광휴게
    "주유소": 19, "액화가스판매소": 19, "석유판매소": 19, "고압가스충전소": 19, "위험물취급소": 19,
    "유독물보관저장시설": 19, "도료류판매소": 19,
    "세차장": 20, "기타자동차관련시설": 20, "온실": 21, "전신전화국": 24, "공원에 부수되는 시설": 27,
}
# 면적으로 갈리는 것 — (기준㎡, 미만일 때 호, 이상일 때 호)
HO_BY_AREA: dict[str, tuple[int, int, int]] = {
    "휴게음식점": (300, 3, 4), "제과점": (300, 3, 4),
    "동물병원": (300, 3, 4), "동물미용실": (300, 3, 4), "동물위탁시설": (300, 3, 4),
    "부동산중개업소": (30, 3, 4), "결혼상담소": (30, 3, 4), "출판사": (30, 3, 4),
    "학원": (500, 4, 10), "교습소": (500, 4, 10), "직업훈련소": (500, 4, 10),
    "골프연습장": (500, 4, 13),
    "기타공연장": (500, 4, 5), "극장": (500, 4, 5), "극장(영화관)": (500, 4, 5), "영화관": (500, 4, 5), "음악당": (500, 4, 5),
    "단란주점": (150, 4, 16), "방송국": (1000, 3, 24),
}
# 대장상 근생이지만 공공 · 기반 시설 — 상가정보 · 인허가에 안 잡혀 「빈 층」으로 남았을 가능성이 크다
PUBLIC_USES = frozenset({"공중화장실", "파출소", "지역자치센터", "우체국", "공공도서관", "변전소", "통신용시설",
                         "마을공동시설", "방송국"})
HO_NAMES = {**use_check.HO_NAMES, 19: "위험물 저장 및 처리 시설", 20: "자동차 관련 시설", 21: "동물 및 식물 관련 시설",
            24: "방송통신시설", 27: "관광 휴게시설"}


def ho_approx(purps: str | None, area_m2: float) -> int | None:
    """대장 용도명 → 별표1 호. 이름으로 못 정하면(「기타근린생활시설」 · 처음 보는 이름) None — 점검이 「확인 필요」로 간다."""
    p = (purps or "").strip()
    if p in HO_BY_NAME:
        return HO_BY_NAME[p]
    if p in HO_BY_AREA:
        lim, lo, hi = HO_BY_AREA[p]
        return lo if area_m2 < lim else hi
    return None


def clear_cache() -> None:
    _cache.clear()


def _labels(keys: list[str]) -> str:
    by = {i["key"]: i["label"] for i in business_fit.industries()}
    return " · ".join(by.get(k, k) for k in keys)


def _legal(unit: dict) -> tuple[int | None, dict[str, dict[str, str | None]]]:
    purps = (unit.get("purps") or "").strip()
    area = float(unit.get("area_m2") or 0)
    ho = ho_approx(purps, area)
    parts = [{"purps": purps, "area_m2": area, "code": f"{ho:02d}000" if ho else None}]
    pnu = unit.get("pnu") or (unit.get("building_id") or "").split("-")[0]
    out: dict[str, dict[str, str | None]] = {}
    for key in FOUNDER:
        res = use_check.check(pnu, key, parts=parts, area_m2=area) or {}
        items = {c["item"]: c["status"] for c in res.get("checks") or []}
        out[key] = {"status": res.get("regulation_status"), "ledger": items.get("대장 층 용도"),
                    "zone": items.get("용도지역 행위제한"), "parcel": items.get("필지 용도지역"),
                    "other": items.get("다른 지역지구"), "area": items.get("면적 기준")}
    return ho, out


def _margins(district_id: str, peers: list[dict], unit: dict, floor_label: str) -> dict[str, dict[str, Any]]:
    """그 층을 `floor_label` 로 놓고 3-Tier 를 돌린 결과(실측으로 계산한 tier 만). `posting._resolve_requested_unit` 과 같은 경로다."""
    raw = {"id": unit["id"], "n": unit.get("n"), "lat": unit.get("lat"), "lng": unit.get("lng"),
           "area": unit.get("area"), "floor": floor_label, "was": unit.get("was") or ""}
    resolved = next((u for u in posting_inputs.resolve_units(district_id, [*peers, raw]) if u.get("id") == unit["id"]), None)
    if resolved is None:
        return {}
    sc = district_svc.tier_scenarios(resolved, district_id)
    out = {}
    for t in TIERS:
        s = sc.get(t) or {}
        if s.get("available") and s.get("month_rev"):
            out[t] = {"viable": bool(s.get("viable")), "margin": s["month_net"] / s["month_rev"]}
    return out


def _pct(x: float) -> str:
    a = abs(x * 100)
    return f"{'+' if x > 0 else ''}{x * 100:.{2 if 0 < a < 0.1 else 1}f}%"


def _grade(unit: dict, ho: int | None, legal: dict, f1: dict, here: dict) -> dict:
    """등급과 이유. 어려움(hard) 사유가 하나라도 있으면 C, 없고 확인 조건(soft)이 있으면 B, 둘 다 없으면 수지로 A1/A2."""
    purps = (unit.get("purps") or "").strip() or "용도 미기재"
    ho_txt = HO_NAMES.get(ho, f"별표1 제{ho}호") if ho else "1·2종 미상"
    reasons: list[dict[str, str]] = []

    def add(code: str, tone: str, text: str) -> None:
        reasons.append({"code": code, "tone": tone, "text": text})

    ledger_open = [k for k in FOUNDER if legal[k]["ledger"] in ("ok", "check")]
    full_open = [k for k in ledger_open if legal[k]["zone"] in ("ok", "check") and legal[k]["other"] != "missing"]
    zone_blocked = [k for k in ledger_open if legal[k]["zone"] == "blocked"]
    zone_missing = [k for k in ledger_open if legal[k]["zone"] in (None, "missing")]
    same_use = [k for k in full_open if legal[k]["ledger"] == "ok"]

    # ① 법·용도
    if purps in PUBLIC_USES:
        add("L_PUBLIC", "hard", f"대장 용도 「{purps}」 — 공공 · 기반 시설이라 임대 매물로 보기 어려워요"
                                f"(상가정보 · 인허가에 안 잡혀 빈 층으로 남았을 수 있어요).")
    elif not ledger_open:
        if ho == 7:
            add("L_SALES", "soft", f"대장 용도 「{purps}」(판매시설) — 점검 규칙은 소매점(1종 근생)과 분류가 달라 용도변경으로 "
                                   f"보지만, 판매시설 안 상점이면 그대로 쓰는 경우가 있어 구청 확인이 필요해요.")
        else:
            add("L_USE_CHANGE", "hard", f"대장 용도 「{purps}」({ho_txt}) — 일반 창업 6업종 모두 건축법 분류가 달라 "
                                        f"용도변경(신고 · 허가)이 필요해요. 주차 · 정화조 · 피난 기준이 같이 바뀔 수 있어요.")
    elif not full_open and zone_blocked and not zone_missing:
        add("L_ZONE_BLOCK", "hard", f"대장상 들어갈 수 있는 {_labels(zone_blocked)}의 행위가 이 필지 용도지역에서 "
                                    f"「금지」로 나와요(토지이음 행위제한).")
    elif not full_open:
        if all(legal[k]["parcel"] in (None, "missing") for k in ledger_open):
            add("L_PARCEL_MISSING", "soft", "이 필지의 용도지역 자료가 없어 법 · 용도 판정을 미뤘어요.")
        elif zone_missing:
            add("L_ZONE_MISSING", "soft", f"이 필지의 토지이음 행위제한을 아직 받지 않았어요. 대장 용도 「{purps}」({ho_txt})로는 "
                                          f"{_labels(ledger_open)} 분류라, 행위제한을 받으면 다시 판정해요.")
        else:
            add("L_OTHER_MISSING", "soft", "용도지역 밖 지역지구의 행위제한을 아직 받지 않아 법 · 용도 판정을 미뤘어요.")
    else:
        text = f"대장 용도 「{purps}」({ho_txt}) — {_labels(full_open)}이(가) 같은 건축법 분류로 들어갈 수 있어요"
        if same_use:
            text += f"(세부용도까지 같은 업종: {_labels(same_use)})"
        checks = []
        if any(legal[k]["other"] == "check" for k in full_open):
            checks.append("지구단위계획 등 다른 지역지구")
        if any(legal[k]["zone"] == "check" for k in full_open):
            checks.append("용도지역 조례 조건")
        add("L_OPEN", "ok", text + (f". 구청 확인: {' · '.join(checks)}." if checks else "."))

    # ② 수지 — 1층 기준으로 가른다
    kp = {t: posting_revenue.profit_rate(t) for t in TIERS}
    measured = [t for t in TIERS if t in f1]
    plus = [t for t in measured if f1[t]["viable"] and kp.get(t) is not None and f1[t]["margin"] >= kp[t]]
    ok = [t for t in measured if f1[t]["viable"]]
    here_ok = [t for t in TIERS if t in here and here[t]["viable"]]
    best = max(measured, key=lambda t: f1[t]["margin"]) if measured else None
    base = " · ".join(f"{TIER_LABEL[t]} {kp[t] * 100:.1f}%" for t in TIERS if kp.get(t) is not None)
    if not measured:
        add("E_NA", "soft", "이 상권은 실측으로 계산할 수 있는 가격대가 없어 수지를 계산하지 않았어요.")
    elif plus:
        t = max(plus, key=lambda x: f1[x]["margin"] - kp[x])
        add("E_PLUS", "ok", f"1층 기준 순익률 {TIER_LABEL[t]} {_pct(f1[t]['margin'])} — 서울 같은 가격대 평균({base}) 이상이에요"
                            f"(서울 평균 가게보다 임대료 부담이 가볍다는 뜻).")
    elif ok:
        top = max(ok, key=lambda t: f1[t]["margin"])
        top_txt = f"{TIER_LABEL[top]} {_pct(f1[top]['margin'])}" if f1[top]["margin"] > 0 else f"{TIER_LABEL[top]} 본전 근처"
        add("E_THIN", "info", f"1층 기준 흑자(최고 {top_txt})지만 서울 같은 가격대 평균({base})보다 "
                              f"얇아요 — 임대료 부담이 서울 평균보다 커요.")
    elif here_ok:
        add("E_UPPER_ONLY", "soft", f"1층 임대료로는 세 가격대 모두 적자예요(최고 {TIER_LABEL[best]} {_pct(f1[best]['margin'])}). "
                                    f"이 층 임대료(층 계수)로는 {' · '.join(TIER_LABEL[t] for t in here_ok)} 흑자지만 매출은 1층 기준이라 "
                                    f"상층 매출이 버텨 줘야 해요.")
    else:
        need = min((-f1[t]["margin"] / (1 - (posting_revenue.opex_rate(t) or 0)), t) for t in measured)
        tail = (f" 가장 가까운 {TIER_LABEL[need[1]]}는 사실상 본전이에요." if need[0] < 0.0005
                else f" 본전이려면 가장 가까운 {TIER_LABEL[need[1]]} 기준으로 추정 매출보다 {need[0] * 100:.1f}% 더 팔아야 해요.")
        add("E_NO", "hard", f"1층 기준 세 가격대 모두 월 순익이 0 이하예요(최고 {TIER_LABEL[best]} {_pct(f1[best]['margin'])})." + tail)

    # ③ 자리
    area = float(unit.get("area_m2") or 0)
    if unit.get("certainty") == "probable":
        add("P_PROBABLE", "soft", "추정 빈 층이에요 — 층을 모르는 점포가 다른 층에 있어야 비는 층이라, 비었는지부터 확인하세요.")
    if area >= LARGE_M2:
        sizes = [a * 3.3058 for a in (posting_revenue.avg_store_pyeong() or {}).values()]
        span = f"{min(sizes):.0f}~{max(sizes):.0f}㎡" if sizes else "가맹점 중앙"
        add("P_LARGE", "soft", f"{area:,.0f}㎡ — {LARGE_M2}㎡ 이상이에요(휴게음식점이 1·2종 근생으로 갈리는 기준 · 가맹점 중앙 면적 "
                               f"{span}의 몇 배). 층 전체 면적이라 호실로 나뉘어 임대되는지 확인하세요.")
    if unit.get("bld_status") == "empty":
        add("P_EMPTY_BLD", "soft", f"이 건물 상업층 {len(unit.get('com_floors') or [])}개가 모두 비어 있어요 — 신축 입주 전인지, "
                                   f"리모델링 · 재건축 · 매각 중인지부터 확인하세요.")
    if (unit.get("floor") or 1) >= 3:
        add("P_UPPER", "info", f"{unit.get('floor')}층 — 찾아오는 업종(학원 · 미용 · 운동)이 주로 맞아요. 음식점 · 카페 · 소매는 "
                               f"엘리베이터 · 간판 노출을 확인하세요(등급에는 반영하지 않아요).")

    # 화면에 보일 가격대 — 「여력 있음」이면 서울 평균을 넘긴 그 가격대, 아니면 순익률이 가장 나은 가격대
    shown = max(plus, key=lambda x: f1[x]["margin"] - kp[x]) if plus else best
    tones = {r["tone"] for r in reasons}
    grade = "C" if "hard" in tones else ("B" if "soft" in tones else ("A1" if any(r["code"] == "E_PLUS" for r in reasons) else "A2"))
    return {"grade": grade, "grade_label": GRADE_LABEL[grade], "reasons": reasons,
            "open_industries": [{"key": k, "label": _labels([k])} for k in full_open],
            "best_tier": shown, "best_margin_1f": round(f1[shown]["margin"], 4) if shown else None,
            "seoul_avg": round(kp[shown], 4) if shown and kp.get(shown) is not None else None}


def _graded(district_id: str) -> list[dict] | None:
    """상권의 빈 층 전부에 등급을 붙인다(상권별로 잠시 기억). 층 산출물이 없으면 None."""
    hit = _cache.get(district_id)
    if hit and time.monotonic() - hit[0] < _TTL_SECONDS:
        return hit[1]
    d = floor_vacancy.load(district_id)
    if d is None:
        return None
    peers = vacant_inventory.units(district_id) if posting_inputs.for_district(district_id) else []
    out = []
    for u in d.get("units") or []:
        ho, legal = _legal(u)
        label = u.get("floor_label") or "1F"
        f1 = _margins(district_id, peers, u, "1F")
        here = f1 if label == "1F" else _margins(district_id, peers, u, label)
        g = _grade(u, ho, legal, f1, here)
        out.append({"id": u.get("id"), "building_id": u.get("building_id"), "pnu": u.get("pnu"),
                    "n": u.get("n") or "", "floor": u.get("floor"), "floor_label": label,
                    "certainty": u.get("certainty"), "area_m2": u.get("area_m2"), "purps": u.get("purps") or "", **g})
    _cache[district_id] = (time.monotonic(), out)
    return out


def owner_index(db: Session | None, district_id: str) -> tuple[str, dict[tuple[str, int], list[dict]]]:
    """(건물 ID, 층) → 그 층의 건물주 확인 매물. 표가 없으면 not_ready, DB 를 못 읽으면 unavailable — 둘 다 「없음」이 아니다."""
    if db is None:
        return "unavailable", {}
    try:
        if not direct_listings.schema_ready(db):
            return "not_ready", {}
        rows = direct_listings.public_listings(db, district_id)
    except Exception:  # noqa: BLE001 — DB 가 없거나(드라이버 · 연결) 깨져도 등급 화면은 서야 한다. 모르는 것은 「unavailable」
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return "unavailable", {}
    idx: dict[tuple[str, int], list[dict]] = {}
    for r in rows:
        if not r.building_id:
            continue
        idx.setdefault((r.building_id, r.floor), []).append({
            "id": r.id, "title": direct_listings.title(r), "unit_label": r.unit_label or "", "area_m2": r.area_m2,
            "deal_type": r.deal_type, "deposit_manwon": r.deposit_manwon, "monthly_rent_manwon": r.monthly_rent_manwon})
    return "ready", idx


OWNER_NOTE = {
    "ready": "게시 중이고 소유자 확인을 마친 건물주 매물만 셉니다.",
    "not_ready": "건물주 직거래 기능을 준비하고 있어요 — 매물을 담을 데이터베이스 표가 아직 없어 등록 여부를 확인할 수 없어요(0 건이 아닙니다).",
    "unavailable": "건물주 매물을 지금 읽지 못했어요 — 등록 여부를 모릅니다(0 건이 아닙니다).",
}
NOTE = ("허가 판정이 아니에요. 법·용도는 건축물대장 · 토지이음 기재(대장 용도코드는 용도명으로 근사), 수지는 Posting 3-Tier 의 "
        "1층 기준 추정(R-ONE 임대료 × 층 계수 · 실제 호가 아님)이고, 기준선은 서울 같은 가격대 평균 영업이익률(KOSIS 2024)이에요.")


def for_district(district_id: str, db: Session | None = None, *, building_id: str | None = None,
                 certainty: str | None = None, detail: bool = True) -> dict | None:
    """상권(또는 그 안 건물 하나)의 빈 층별 창업 가능 등급 + 건물주 등록. 층 산출물이 없으면 None."""
    graded = _graded(district_id)
    if graded is None:
        return None
    status, owners = owner_index(db, district_id)
    rows = [g for g in graded if (not building_id or g["building_id"] == building_id)
            and (not certainty or g["certainty"] == certainty)]
    units = []
    for g in rows:
        own = owners.get((g["building_id"], g["floor"]), [])
        item = {**g, "owner": own}
        if not detail:
            item = {k: item[k] for k in ("id", "building_id", "pnu", "floor", "floor_label", "certainty", "grade")}
            item["owner"] = [{"id": o["id"]} for o in own]
        units.append(item)
    return {
        "district_id": district_id,
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "owner_status": status,
        "owner_note": OWNER_NOTE[status],
        "counts": {g: sum(1 for u in units if u["grade"] == g) for g in GRADES},
        "owner_floors": sum(1 for u in units if u["owner"]),
        "note": NOTE,
        "units": units,
    }
