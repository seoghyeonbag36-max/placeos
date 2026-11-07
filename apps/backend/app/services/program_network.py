"""[Program] 네트워킹 — 이 상권에서 계약 전에 누구에게 묻고, 개업 뒤 누구와 함께할 수 있나(2026-11-07 리뉴얼).

1단계 · 공식 네트워크(개인정보 0)
  - K-Startup 공고 중 지원분야 「행사ㆍ네트워크」(모집 중 · 지역 · 끝나지 않은 것)
  - 기업마당 행사정보 — 중소기업 대상 교육·세미나·전시회·사업설명회(좌표가 없어 지역 해시태그로 고른다)
  - 지원기관 안내 — 공식 누리집만. 주소는 2026-11-07 에 열어 누리집 제목까지 확인한 것만 싣는다
2단계 · 이웃 가게(방문형)
  - 함께 모이는 업종(관측 lift — 도시 범위 Gold) + 「방문해서 물어볼 질문」. 가게 목록은 화면이 기존
    nearby-stores 로 그린다(공개 상가정보 — 상호·업종·위치만)

**하지 않는 것**(정보통신망법 제50조 — 영리 목적 광고성 정보는 수신자의 명시적 사전 동의가 필요하다):
  기존 가게의 연락처를 모으거나 PlaceOS 가 대신 연락하지 않는다. 응답에 개인 연락처 칸이 없다
  (tests/test_program_network.py 가 잠근다). 기관은 대표 누리집만 싣는다.
3단계(사용자끼리 옵트인 연결)는 결정 D3 에 따라 파일럿이 붙은 뒤에 만든다 — 지금은 상대가 없다.
"""
from __future__ import annotations

from datetime import date

from app.services import events, nearby_stores
from app.services import program_sources as src
from app.services.program_support import (STAGES, Region, area_scope, clean, industry_terms,
                                          is_network_category, kstartup_item, parse_range, region_of, region_rank)

_MAX_EVENTS = 40
_SUMMARY_MAX = 160

# 공식 누리집 — 2026-11-07 에 열어 HTTP 200 과 누리집 제목을 확인했다(전북신용보증재단은 연결 실패로 뺐다).
_DIRECTORY_NATIONAL = [
    {"name": "소상공인24", "url": "https://www.sbiz24.kr", "role": "소상공인 지원사업 신청·정책자금"},
    {"name": "소상공인시장진흥공단", "url": "https://www.semas.or.kr", "role": "지역센터 상담·교육·컨설팅"},
    {"name": "창조경제혁신센터", "url": "https://ccei.creativekorea.or.kr", "role": "지역 창업 보육·네트워킹"},
    {"name": "K-Startup", "url": "https://www.k-startup.go.kr", "role": "창업지원사업 통합 공고"},
    {"name": "기업마당", "url": "https://www.bizinfo.go.kr", "role": "부처·지자체 지원사업·행사 공고"},
]
_DIRECTORY_REGIONAL = {
    "서울특별시": [{"name": "서울시 소상공인 종합지원 포털(서울신용보증재단)", "url": "https://www.seoulsbdc.or.kr",
                    "role": "서울 자영업 상담·교육"}],
    "경기도": [{"name": "경기도시장상권진흥원", "url": "https://www.gmr.or.kr", "role": "경기 상권·전통시장 지원"}],
    "전남광주통합특별시": [{"name": "광주신용보증재단", "url": "https://www.gjsinbo.or.kr", "role": "광주 소상공인 보증·지원"}],
}

# 계약 전에 이웃 가게·상인 조직에 물어볼 것 — 숫자를 지어내지 않는 질문만.
QUESTIONS = [
    "이 골목의 권리금은 보통 어떻게 정해지나요? 최근에 바뀐 적이 있나요?",
    "임대인(건물주)은 수리·원상복구·업종 변경 요청에 어떻게 응하는 편인가요?",
    "상인회나 상점가 모임이 있나요? 가입 조건과 공동 행사(축제·쿠폰)는 어떻게 하나요?",
    "평일과 주말, 하루 중 언제 손님이 가장 많고 언제가 비나요?",
    "배달·포장 비중은 어느 정도인가요? 주변에서 함께 하는 플랫폼이 있나요?",
    "최근 1~2년 사이 문을 닫거나 바뀐 가게가 있다면, 이유가 무엇이었나요?",
    "이 상권에서 함께 행사하거나 교차 쿠폰을 해 본 이웃 가게가 있나요?",
]


def bizinfo_event_item(r: dict, region: Region, terms: list[str], today: date) -> dict | None:
    # 실제 응답의 기간 필드는 eventBeginEndDe 다(11-08 실측 '20261203 ~ 20261203') — 예전에는 명세의 다른 이름만 읽어
    # 일정이 전부 비었고, 그래서 끝난 행사도 거르지 못했다. 옛 이름은 폴백으로 남긴다.
    start, end = parse_range(r.get("eventBeginEndDe") or r.get("eventPeriod") or r.get("BeginEndDe"))
    if end and end < today:
        return None
    area = clean(r.get("areaNm"))
    scope = area_scope(area, region)
    if scope is None:
        return None          # 다른 시도에서 열리는 행사 — 해시태그 검색이 섞어 보낸다(11-08 #서울 97건 중 31건)
    title = clean(r.get("nttNm") or r.get("title")) or "(행사명 없음)"
    summary = clean(r.get("nttCn") or r.get("description"), _SUMMARY_MAX)
    text = " ".join(filter(None, [title, summary]))
    matched = [f"지역: {area}" if scope == "local" else "전국 행사(개최지 " + (area or "미상") + ")"]
    if (hits := [t for t in terms if t in text]):
        matched.append("업종 언급: " + "·".join(hits))
    eid = clean(r.get("eventInfoId") or r.get("seq"))
    return {
        "source": "bizinfo_event", "source_label": src.SOURCE_LABEL["bizinfo_event"], "id": f"bev-{eid}",
        "title": title, "kind": clean(r.get("eventInfoTyNm") or r.get("eventType")),
        "org": clean(r.get("originEngnNm") or r.get("originOrg")), "area": clean(r.get("areaNm")),
        "start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
        "period_text": None if end else clean(r.get("eventBeginEndDe") or r.get("eventPeriod") or r.get("BeginEndDe"), 60),
        "apply_period": clean(r.get("rceptPd"), 60),
        "url": clean(r.get("bizinfoUrl") or r.get("originUrlAdres") or r.get("originUrl")),
        "summary": summary, "matched": matched,
    }


def network(district_id: str, industry_key: str | None = None, industry_label: str | None = None,
            stage: str | None = None, *, today: date | None = None) -> dict | None:
    region = region_of(district_id)
    if region is None:
        return None
    if stage not in (None, *STAGES):
        raise ValueError("stage 는 pre_founder · founder 중 하나다")
    today = today or events.today_kst()
    terms = industry_terms(industry_label)
    items: list[dict] = []
    statuses: list[dict] = []

    ks = src.kstartup_open()
    got = []
    for r in ks.rows:
        if not is_network_category(clean(r.get("supt_biz_clsfc"))):
            continue
        it = kstartup_item(r, region, stage, terms, today)
        if it:
            got.append({"source": it["source"], "source_label": it["source_label"], "id": it["id"],
                        "title": it["title"], "kind": it["category"], "org": it["org"], "area": it["region"],
                        "start": it["start"], "end": it["end"], "period_text": None,
                        "apply_period": None, "url": it["url"], "summary": it["summary"], "matched": it["matched"]})
    items += got
    statuses.append(src.status_of("kstartup", ks, len(got)))

    bz = src.bizinfo("event", region.bizinfo_tag)
    got = [it for r in bz.rows if (it := bizinfo_event_item(r, region, terms, today))]
    items += got
    statuses.append(src.status_of("bizinfo_event", bz, len(got)))

    # 이 지역 공고 먼저(전국은 뒤) → 업종 언급 → 마감이 가까운 순. 예전(시작일 순)에는 3월부터 모집 중인 다른 지역
    # 기관의 전국 공고가 맨 위에 섰다(11-08 실측) — program_support.region_rank 와 같은 규칙이다.
    items.sort(key=lambda it: (region_rank(it, region), not any(m.startswith("업종 언급") for m in it["matched"]),
                               it["end"] is None, it["end"] or "", it["title"]))
    complements = nearby_stores.colocated_top(district_id, industry_key) if industry_key else []
    return {
        "district_id": district_id, "region": region.as_dict(), "industry": industry_label,
        "events": items[:_MAX_EVENTS], "total_events": len(items), "sources": statuses,
        "complements": complements,
        "complements_note": (nearby_stores.colocation_note() if complements else
                             ("업종을 고르면 이 도시에서 함께 모이는 업종을 보여 드려요." if not industry_key else
                              "이 도시 범위에서는 이 업종과 함께 모이는 업종을 잴 표본이 부족해요.")),
        "questions": QUESTIONS,
        "directory": _DIRECTORY_REGIONAL.get(region.sido, []) + _DIRECTORY_NATIONAL,
        "note": ("공식 행사·지원기관과, 직접 찾아가 물어볼 이웃 가게를 안내합니다. PlaceOS 는 가게 연락처를 모으거나 "
                 "대신 연락하지 않아요. 행사 일정·참가 조건은 원문에서 다시 확인하세요."),
    }
