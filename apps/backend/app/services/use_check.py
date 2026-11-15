"""입점 점검 — 이 층의 대장 용도 × 필지 용도지역 × 토지이음 행위제한으로 「내 업종이 들어갈 수 있나」를 세 단계로 답한다.

재료: `data/gold/page_use_check_inputs.json`(data.pipelines.build_use_check_inputs) + 호출자가 넘기는 그 층의 대장 행
(`building_ledger_live.summarise` 의 floors[층].parts — purps·code·area_m2).

판정 순서(보수적으로 — 위양성 「가능이라 했는데 막힘」은 설계로 막는다):
  1. 재료가 없으면 `missing_inputs` — 지어내지 않는다.
  2. 필지에 걸린 용도지역이 모두 그 행위를 금지하면 `zoning_prohibited`.
  3. 대장 층 용도의 별표1 호가 이 업종이 속할 수 있는 호와 다르면 `use_change_needed`.
  4. 조건부 가능 · 용도지역 둘 이상 · 다른 지역지구의 금지·조건 · 지구단위계획구역 · 면적 합계에 따라 분류가 갈림 ·
     같은 호 안의 다른 세부용도 — 하나라도 있으면 `needs_check`.
  5. 나머지가 `ledger_ok`(대장상 가능). **허가됨·입점 가능이 아니다.**

⚠ 별표1 호는 대장 용도**코드** 앞 두 자리에서 읽는다. 「휴게음식점」「학원」「체력단련장」은 이름이 같아도
  1종·2종 근생(또는 교육연구·운동시설)으로 갈린다(서울 원본 37종 · 2026-11-15 실측 → docs/finding-eum-landuse-2026-11-15.md).
⚠ 면적 기준은 토지이음 응답의 별표1 정의에서 온다. 그 기준은 「같은 건축물에서 그 용도로 쓰는 바닥면적의 합계」라
  층 하나의 면적으로는 하한만 안다 — 그래서 기준 미만이면 분류를 정하지 않고 확인 필요로 둔다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_INPUTS = Path(__file__).resolve().parents[4] / "data" / "gold" / "page_use_check_inputs.json"
_TTL_SECONDS = 300.0
_cache: dict[str, Any] = {}

# 12업종(services/business_fit.INDUSTRIES 의 key) → 토지이음 행위명 · 대장에서 「같은 세부용도」로 보는 용도코드명.
# 행위명은 DTsearchLunCd 로 표기를 확인한 것만 쓴다(data/collectors/eum_landuse.ACT_NAMES 와 같아야 한다 — 시험이 대조한다).
INDUSTRY_ACTS: dict[str, dict] = {
    "cafe": {"act": "휴게음식점", "same": ("휴게음식점", "제과점")},
    "restaurant": {"act": "일반음식점", "same": ("일반음식점",)},
    "bar": {"act": "일반음식점", "same": ("일반음식점",),
            "note": "주점은 일반음식점 영업으로 본다 — 단란주점·유흥주점은 분류가 달라(별표1 제4호더목·제16호) 이 점검 밖입니다."},
    "beauty": {"act": "미용원", "same": ("미용원", "이(미)용원", "이용원")},
    "clinic": {"act": "의원", "same": ("의원", "치과의원", "한의원")},
    "pharmacy": {"act": "일용품을 판매하는 소매점", "same": ("소매점",),
                 "note": "약국은 별표1 제3호가목(의약품 등 일용품 소매점)으로 봅니다."},
    "convenience": {"act": "일용품을 판매하는 소매점", "same": ("소매점",)},
    "fashion": {"act": "일용품을 판매하는 소매점", "same": ("소매점",)},
    "education": {"act": "학원", "same": ("학원", "교습소")},
    "fitness": {"act": "체력단련장", "same": ("체력단련장",),
                "note": "헬스·필라테스 등 체력단련장 기준입니다 — 노래연습장·PC방·골프연습장은 분류가 달라 따로 확인해야 합니다."},
    # 숙박은 「일반숙박시설」 하나로만 조회했다 — 호텔(관광숙박시설 · 관광진흥법)·생활숙박시설·도시민박은 분류가 달라
    # 토지이음의 「금지」를 이 업종 전체의 금지로 단정하지 않는다(서울 상업지역 대부분이 금지로 온다 · 2026-11-15).
    "lodging": {"act": "일반숙박시설", "same": ("일반숙박시설",), "prohibit_as_check": True,
                "note": "숙박은 일반숙박시설(여관·모텔) 기준입니다 — 호텔(관광숙박시설)·생활숙박시설·도시민박은 분류와 규정이 달라 "
                        "따로 확인해야 하고, 그래서 토지이음의 「금지」도 확인 필요로 둡니다."},
    "culture": {"act": "미술관", "same": ("미술관", "전시장", "기타전시장"),
                "note": "전시(미술관·전시장) 기준입니다 — 공연장은 토지이음 행위 조회가 비어 이 점검 밖입니다."},
}

# 건축법 시행령 별표1 호 이름(대장 용도코드 앞 두 자리와 같은 번호).
HO_NAMES = {1: "단독주택", 2: "공동주택", 3: "제1종 근린생활시설", 4: "제2종 근린생활시설", 5: "문화 및 집회시설",
            6: "종교시설", 7: "판매시설", 8: "운수시설", 9: "의료시설", 10: "교육연구시설", 11: "노유자시설",
            12: "수련시설", 13: "운동시설", 14: "업무시설", 15: "숙박시설", 16: "위락시설", 17: "공장"}

SRC_EUM = "토지이음 토지이용규제 행위제한정보(국토교통부 · data.go.kr 15058410)"
SRC_VWORLD = "V-World 토지이용계획속성(국토교통부)"
SRC_LEDGER = "건축물대장 층별개요(건축HUB)"
NOTE = ("허가 판정이 아닙니다. 건축물대장·토지이음 기재 기준이며, 영업신고·용도변경이 되는지는 관할 구청(건축과·위생과 등)에서 "
        "정해집니다. 지구단위계획 결정도서·개별 법령(식품위생법 등)·건물 상태(정화조·주차·피난)는 이 점검에 들어 있지 않습니다.")
SOURCES = [
    {"name": "토지이음 토지이용계획 열람", "url": "https://www.eum.go.kr/web/ar/lu/luLandDet.jsp"},
    {"name": "국토교통부 토지이용규제정보서비스(행위제한)", "url": "https://www.data.go.kr/data/15058410/openapi.do"},
    {"name": "건축법 시행령 별표1(용도별 건축물의 종류)", "url": "https://www.law.go.kr/법령/건축법시행령"},
]


def clear_cache() -> None:
    _cache.clear()


def _load() -> dict | None:
    now = time.monotonic()
    if _cache.get("data") is not None and now - _cache.get("at", 0.0) < _TTL_SECONDS:
        return _cache["data"]
    if not _INPUTS.exists():
        return None
    try:
        _cache["data"] = json.loads(_INPUTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    _cache["at"] = now
    return _cache["data"]


def ho_of(code: str | None) -> int | None:
    """대장 용도코드 → 별표1 호. 코드가 없거나 숫자가 아니면 None."""
    if not code or len(code) < 2 or not code[:2].isdigit():
        return None
    return int(code[:2])


def ho_name(ho: int | None) -> str:
    return HO_NAMES.get(ho, f"별표1 제{ho}호") if ho else "분류 미상"


def _law_label(law: dict) -> str:
    if not law.get("ho"):
        return law.get("ref", "")
    return f"제{law['ho']}호" + (f"{law['mok']}목" if law.get("mok") else "")


def _area_txt(v: float) -> str:
    return f"{v:,.0f}㎡"


def _verdict(rows: list[dict], refs: set[str]) -> tuple[str, list[dict]]:
    """한 지역지구의 행 중 관련 별표1 조문에 걸린 것 → ok | check | blocked | missing."""
    hit = [r for r in rows if any(l["ref"] in refs for l in r["laws"])]
    if not hit:
        return "missing", hit
    regs = {r["reg"] for r in hit}
    if regs == {"금지"}:
        return "blocked", hit
    if regs == {"가능"} and not any(r["c"] for r in hit):
        return "ok", hit
    return "check", hit


def _rows_text(hit: list[dict], data: dict) -> str:
    parts = []
    for r in hit:
        laws = "·".join(_law_label(l) for l in r["laws"])
        conds = [data["conds"][i] for i in r["c"] if i < len(data["conds"])]
        parts.append(f"{r['reg']}({laws})" + (f" — 조건: {' / '.join(conds)}" if conds else ""))
    return "; ".join(parts)


def check(pnu: str, industry: str, *, parts: list[dict] | None = None, area_m2: float | None = None,
          ledger_date: str | None = None) -> dict | None:
    """한 층의 입점 점검. 모르는 업종이면 None(호출자가 400). 재료가 없으면 missing_inputs 로 답한다."""
    spec = INDUSTRY_ACTS.get(industry)
    if spec is None:
        return None
    from app.services.business_fit import _BY_KEY  # 업종 이름의 단일 출처

    label = (_BY_KEY.get(industry) or {}).get("label", industry)
    act = spec["act"]
    data = _load()
    checks: list[dict] = []
    basis = (data or {}).get("basis") or {}
    vw_date, eum_date = basis.get("vworld_updated_max"), basis.get("eum_fetched")

    def add(item: str, status: str, reason: str, source: str, date: str | None, estimated: bool = False) -> None:
        checks.append({"item": item, "status": status, "reason": reason, "source": source,
                       "source_date": date, "estimated": estimated})

    zones = (data or {}).get("parcels", {}).get(pnu)
    names = (data or {}).get("zone_names", {})
    rules = (((data or {}).get("acts") or {}).get(pnu[:5]) or {}).get(act)

    # ① 필지 용도지역
    use_zones = [(c, rel) for c, rel in (zones or []) if c.startswith("UQA") and not c.startswith("UQA0")]
    if not zones or not use_zones:
        add("필지 용도지역", "missing",
            "이 필지의 지역지구를 아직 받지 않았습니다(지금은 서울 서빙 거점 빈 층 필지만 수집)." if not zones
            else "이 필지에 걸린 용도지역 코드가 응답에 없습니다.", SRC_VWORLD, vw_date)
    elif len(use_zones) > 1:
        add("필지 용도지역", "check",
            "대지가 용도지역 둘 이상에 걸립니다: " + ", ".join(f"{names.get(c, c)}({r})" for c, r in use_zones)
            + " — 어느 지역 규정을 따르는지는 국토의 계획 및 이용에 관한 법률 제84조(걸친 면적 등)로 정해집니다.",
            SRC_VWORLD, vw_date)
    else:
        c, r = use_zones[0]
        add("필지 용도지역", "ok", f"{names.get(c, c)}({r})", SRC_VWORLD, vw_date)

    # 이 행위가 속할 수 있는 별표1 조문 — 용도지역 행에서 모은다
    laws: dict[str, dict] = {}
    for c, _ in use_zones:
        for r in (rules or {}).get(c) or []:
            for l in r["laws"]:
                laws.setdefault(l["ref"], l)
    feasible = {ref: l for ref, l in laws.items() if not (area_m2 and l.get("max") and area_m2 >= l["max"])} or laws
    target_hos = {l["ho"] for l in feasible.values() if l.get("ho")}

    # ② 대장 층 용도
    ledger_state = "missing"
    floor_ho: int | None = None
    if not parts:
        add("대장 층 용도", "missing", "이 층의 건축물대장 용도를 받지 못했습니다.", SRC_LEDGER, ledger_date)
    else:
        main = max(parts, key=lambda p: p.get("area_m2") or 0)
        purps, floor_ho = main.get("purps") or "용도 미기재", ho_of(main.get("code"))
        others = [p.get("purps") for p in parts if p is not main and p.get("purps") and p.get("purps") != purps]
        tail = f" (같은 층 다른 기재: {', '.join(dict.fromkeys(others))})" if others else ""
        need = ", ".join(f"{ho_name(l['ho'])}(별표1 {_law_label(l)})" for l in feasible.values()) or "토지이음 응답 없음"
        if floor_ho is None:
            ledger_state = "check"
            add("대장 층 용도", "check", f"대장 용도 「{purps}」의 용도코드가 없어 별표1 분류를 정하지 못했습니다{tail}.",
                SRC_LEDGER, ledger_date)
        elif not target_hos:
            ledger_state = "check"
            add("대장 층 용도", "check", f"대장 용도 「{purps}」({ho_name(floor_ho)}) — 이 업종의 별표1 분류를 토지이음에서 받지 못해 "
                f"대조하지 못했습니다{tail}.", SRC_LEDGER, ledger_date)
        elif floor_ho in target_hos:
            if purps in spec["same"]:
                ledger_state = "ok"
                add("대장 층 용도", "ok", f"대장 용도 「{purps}」({ho_name(floor_ho)}) — 이 업종과 같은 세부용도입니다{tail}.",
                    SRC_LEDGER, ledger_date)
            else:
                ledger_state = "check"
                add("대장 층 용도", "check",
                    f"대장 용도 「{purps}」({ho_name(floor_ho)}) — 같은 {ho_name(floor_ho)} 안의 다른 세부용도입니다. "
                    f"건축물대장 기재내용 변경 대상인지 관할 구청에 확인하세요{tail}.", SRC_LEDGER, ledger_date)
        else:
            ledger_state = "blocked"
            add("대장 층 용도", "blocked",
                f"대장 용도 「{purps}」({ho_name(floor_ho)}) — 이 업종은 {need}로 분류돼 용도변경(신고·허가) 또는 대장 기재변경이 "
                f"필요합니다. 정화조·주차장 기준이 함께 바뀔 수 있어 관할 구청에 확인하세요{tail}.", SRC_LEDGER, ledger_date)

    # 용도지역 판정에 쓸 조문 — 대장 호가 맞으면 그 호의 조문, 아니면 가능한 조문 전부
    relevant = {ref for ref, l in feasible.items() if l.get("ho") == floor_ho} or set(feasible)

    # ③ 용도지역 행위제한
    zone_states = []
    zoning_state = "missing"
    if use_zones:
        texts = []
        for c, _ in use_zones:
            rows = (rules or {}).get(c)
            if rows is None:
                zone_states.append("missing")
                texts.append(f"{names.get(c, c)}: 미조회")
                continue
            st, hit = _verdict(rows, relevant)
            zone_states.append(st)
            texts.append(f"{names.get(c, c)} · {act}: " + (_rows_text(hit, data) if hit else "응답에 해당 행 없음"))
        if all(s == "missing" for s in zone_states) or any(t.endswith(": 미조회") for t in texts):
            z = "missing"   # 걸린 용도지역 중 하나라도 미조회면 판정하지 않는다
        elif all(s == "blocked" for s in zone_states):
            z = "blocked"
        elif all(s == "ok" for s in zone_states):
            z = "ok"
        else:
            z = "check"
        if z == "blocked" and spec.get("prohibit_as_check"):
            z = "check"
            texts.append("이 업종은 조회한 행위 하나로 대표되지 않아 금지를 단정하지 않습니다")
        add("용도지역 행위제한", z, " | ".join(texts), SRC_EUM, eum_date)
        zoning_state = z

    # ④ 다른 지역지구(용도지구·보호구역·지구단위계획 등)
    if zones:
        flagged, unfetched = [], []
        for c, _ in zones:
            if c in dict(use_zones) or c.startswith("UQA0"):
                continue
            nm = names.get(c, c)
            if "지구단위계획" in nm:
                flagged.append(f"{nm} — 결정도서의 허용·불허 용도는 토지이음 행위제한 응답에 없습니다. 토지이음 열람이나 구청에서 확인하세요")
                continue
            # 받지 않은 지역지구를 「규정 없음」으로 세지 않는다 — 키가 없으면 미조회다(빈 목록 [] 만이 「규정 없음」).
            # 2026-11-15 리뷰: 한도로 못 받은 강남·송파·강동과 서초 일부 콜이 「맞음」·「대장상 가능」으로 새고 있었다.
            if rules is None or c not in rules:
                unfetched.append(nm)
                continue
            hit = [r for r in rules[c] if r["reg"] == "금지" or r["c"]]
            if hit:
                flagged.append(f"{nm} · {act}: {_rows_text(hit, data)}")
        if unfetched:
            add("다른 지역지구", "missing",
                f"토지이음 행위제한을 아직 받지 않은 지역지구가 있습니다: {', '.join(dict.fromkeys(unfetched))}"
                + (f" | {' | '.join(flagged)}" if flagged else ""), SRC_EUM, eum_date)
        else:
            add("다른 지역지구", "check" if flagged else "ok",
                " | ".join(flagged) if flagged else f"용도지역 밖 지역지구 {len(zones) - len(use_zones)}개에서 이 행위를 막거나 조건을 다는 행이 없습니다.",
                SRC_EUM, eum_date)

    # ⑤ 면적 기준 — 같은 건물의 같은 용도 합계에 따라 별표1 분류가 갈리는가
    split = [l for l in feasible.values() if l.get("max") or l.get("min")]
    if len({l["ho"] for l in feasible.values()}) > 1 and split:
        bounds = sorted({v for l in split for v in (l.get("max"), l.get("min")) if v})
        add("면적 기준", "check",
            f"같은 건물에서 이 용도로 쓰는 바닥면적 합계가 {', '.join(_area_txt(b) for b in bounds)} 기준 어느 쪽이냐에 따라 "
            + " / ".join(f"{ho_name(l['ho'])}({_law_label(l)})" for l in feasible.values())
            + (f"로 갈립니다. 이 층 대장 면적은 {_area_txt(area_m2)}입니다." if area_m2 else "로 갈립니다."),
            SRC_EUM, eum_date)

    # 종합
    # 자료 없음 항목이 하나라도 있으면 판정하지 않는다 — 받지 않은 것을 「맞음」으로 세지 않는다
    if zoning_state == "missing" or ledger_state == "missing" or any(c["status"] == "missing" for c in checks):
        status = "missing_inputs"
        lacking = [c["item"] for c in checks if c["status"] == "missing"]
        # 「다른 지역지구이(가) 없어」는 「지역지구가 없다」로 읽힌다(11-15 프로덕션 확인) — 없는 것은 항목이 아니라 그 자료다
        headline = f"자료 부족 — {', '.join(lacking)} 자료를 아직 받지 못해 점검하지 않았습니다."
    elif zoning_state == "blocked":
        status = "zoning_prohibited"
        headline = f"용도지역상 금지 — 토지이음 행위제한에 이 필지의 용도지역에서 {act}이(가) 금지로 나옵니다."
    elif ledger_state == "blocked":
        status = "use_change_needed"
        headline = "대장상 용도 변경 필요 — 지금 대장 용도로는 이 업종의 건축법 분류와 다릅니다."
    elif any(c["status"] == "check" for c in checks):
        status = "needs_check"
        n = sum(c["status"] == "check" for c in checks)
        headline = f"확인 필요 — {n}가지를 관할 구청에 확인해야 합니다."
    else:
        status = "ledger_ok"
        headline = "대장상 가능 — 대장 용도와 용도지역 행위제한이 이 업종과 맞습니다(허가 판정 아님)."
    note = NOTE + (f" {spec['note']}" if spec.get("note") else "")
    return {"pnu": pnu, "industry": industry, "industry_label": label, "act": act, "regulation_status": status,
            "headline": headline, "checks": checks, "note": note, "sources": SOURCES, "permission": None}
