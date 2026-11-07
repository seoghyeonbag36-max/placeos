"""[Program] 오프라인 마케팅 솔루션 — 실행 카드(2026-11-07 리뉴얼).

묻는 질문: 「이 상권의 콘텐츠·온라인 데이터로 볼 때, 검증·개업 기간에 언제·어디서·누구와·무엇을 하면 실행할 수 있나?」
대상은 팝업·가오픈·개업 첫 회차다(결정 D2 (a)) — 영업 중 가게의 일반 마케팅은 09-17 결정대로 범위 밖이다.

카드는 **규칙으로** 만든다(LLM 없음 · 로그인 불필요). 근거가 있는 카드만 낸다:
  event     걸어갈 거리(marketing._WALKABLE_M) 안의, 오늘 기준 끝나지 않은 공공 행사 — 가까운 순 최대 3장
  time      유동 대비 매출이 가장 빈 시간대(TRDAR 수요신호 — 서울 거점만 있다)
  neighbor  함께 모이는 업종(관측 lift — 도시 범위) 상위 둘과 교차 쿠폰
  own       매장 자체 접점 — 항상(근거가 없는 거점에서도 할 수 있는 일)

**지어내지 않는 것**: 예산 금액(비율도 — 창업자가 정한다) · 예상 유입·매출 · 주최의 참여 의사.
카드마다 「무엇으로 잴지」(measure)를 붙여 가설 검증 판정표로 넘긴다.
"""
from __future__ import annotations

from datetime import date

from app.services import events, nearby_stores
from app.services import marketing as mkt
from app.services.program_support import region_of

MODES = ("popup", "soft_open", "mvp", "actual_open")
_MAX_EVENT_CARDS = 3

_SIGNAGE_CAVEAT = "입간판·현수막·배너는 옥외광고물 허가·신고 대상일 수 있어요 — 구청(시청)에 먼저 확인하세요."


def _event_card(e: dict) -> dict:
    d = e.get("distance_m")
    when = e.get("when") or "일정 확인 필요"
    if e.get("time"):
        when = f"{when} · {e['time']}"
    src_label = events.SRC_LABEL.get(e.get("src") or "", "공공 행사 자료")
    return {
        "kind": "event", "title": f"「{e.get('n')}」 방문객 연계",
        "when": when,
        "where": f"{e.get('place') or '장소 확인 필요'} · 거점 중심에서 {d}m" if d is not None else (e.get("place") or "장소 확인 필요"),
        "who": f"주최: {e['org']} — 참여·협찬 조건은 원문 확인" if e.get("org") else "주최 확인 필요 — 원문에서 참여 조건 확인",
        "what": "행사 방문객에게 보여 줄 방문 혜택(시식·체험·쿠폰)을 정하고, 행사장에서 자리까지 오는 길을 안내한다",
        "measure": "행사 기간 전용 쿠폰 코드 사용 건수 — 행사 전 같은 요일 결제 건수와 비교",
        "basis": [{"label": "행사 원천", "value": src_label},
                  {"label": "거리", "value": f"{d}m(거점 중심 직선)" if d is not None else "모름"}],
        "caveat": "행사가 열린다는 사실이지 주최가 함께한다는 뜻이 아니에요. 부스·협찬은 주최에 따로 문의하세요.",
        "link": e.get("link"),
    }


def _time_card(rows: list[tuple[str, str, float]], band: str) -> dict:
    d = {k: v for kd, k, v in rows if kd == "demand"}
    f, s = d.get(f"flpop_tmzon_{band}"), d.get(f"selng_tmzon_{band}")
    label = mkt._TMZON_LABEL.get(band, band)
    basis = [{"label": "근거", "value": f"유동 {f:.1f}% / 매출 {s:.1f}% — TRDAR 상권 수요신호(시간대 구성비)"}] \
        if f is not None and s is not None else [{"label": "근거", "value": "TRDAR 상권 수요신호"}]
    return {
        "kind": "time", "title": f"{label} 빈 시간대 체험",
        "when": f"{label} — 유동 대비 매출이 가장 빈 시간대", "where": "자리 앞·매장 안",
        "who": "단독 실행",
        "what": "이 시간대에 맞춘 체험·시식·한정 구성으로 지나가는 사람을 안으로 들인다",
        "measure": "이 시간대 결제 건수 — 같은 기간 다른 시간대와 비교",
        "basis": basis,
        "caveat": "상권(TRDAR) 단위 구성비라 이 자리 앞의 시간대와 다를 수 있어요.",
        "link": None,
    }


def _neighbor_card(top: list[dict]) -> dict:
    names = " · ".join(f"{t['label']}(lift {t['lift']})" for t in top)
    return {
        "kind": "neighbor", "title": f"{' · '.join(t['label'] for t in top)} 이웃과 교차 쿠폰",
        "when": "검증·개업 기간", "where": "같은 거점 안 이웃 가게(네트워킹 탭의 이웃 가게 지도)",
        "who": f"함께 모이는 업종: {names} — 직접 찾아가 제안",
        "what": "서로의 영수증·쿠폰을 상대 가게에서 쓰게 한다 — 조건은 두 가게가 함께 정한다",
        "measure": "가게별 쿠폰 코드 회수 건수",
        "basis": [{"label": "근거", "value": "업종 동반 출현(100m 격자 관측 lift — 도시 범위)"}],
        "caveat": "lift 는 관측일 뿐 인과·매출 효과가 아니에요. PlaceOS 는 이웃 가게에 대신 연락하지 않아요.",
        "link": None,
    }


def _own_card(mode: str, has_events: bool) -> dict:
    mvp = mode == "mvp"
    return {
        "kind": "own", "title": "자리 앞 접점 — QR 사전 예약" if not mvp else "매대·온라인 사전주문 접점",
        "when": "검증 기간 내내", "where": "자리 앞 · 창문" if not mvp else "매대 · 사전주문 페이지",
        "who": "단독 실행",
        "what": ("입간판·창문 사인에 QR 을 달아 사전 예약·알림 신청을 받는다" if not mvp else
                 "매대·사전주문 페이지 QR 로 예약을 받고, 결제까지 이어지는지 본다"),
        "measure": "QR 스캔 수 → 예약·결제 전환 건수",
        "basis": [{"label": "근거", "value": "근거 없이도 할 수 있는 기본 접점" if not has_events
                   else "행사 연계와 함께 쓰는 기본 접점"}],
        "caveat": _SIGNAGE_CAVEAT,
        "link": None,
    }


def plan(district_id: str, industry_key: str | None = None, mode: str = "popup",
         *, today: date | None = None) -> dict | None:
    if region_of(district_id) is None:
        return None
    if mode not in MODES:
        raise ValueError("mode 는 popup · soft_open · mvp · actual_open 중 하나다")
    # 출처 판정은 행사 화면과 같은 규칙을 쓴다(서울 밖인데 전국 Gold 가 없으면 "none" — 「0건」이 아니라 「자료 없음」).
    events_source = (mkt.get_district_events(district_id) or {}).get("events_source", "none")
    no_source = mkt._events_unavailable_note(district_id)
    rows = [] if no_source or events_source == "seed" else (events.for_district(district_id, today=today) or [])
    walkable = [e for e in rows if e.get("distance_m") is not None and e["distance_m"] <= mkt._WALKABLE_M]
    cards = [_event_card(e) for e in walkable[:_MAX_EVENT_CARDS]]
    notes = []
    if no_source:
        notes.append(no_source)
    elif not walkable:
        notes.append(f"걸어갈 거리({mkt._WALKABLE_M}m) 안에 오늘 기준 확인된 공공 행사가 없어요 — 매장 자체 접점부터 시작하세요.")

    ctx = mkt.context_rows(district_id) or []
    band = mkt._gap_band(ctx)
    if band:
        cards.append(_time_card(ctx, band))
    else:
        notes.append("시간대별 유동·매출 자료(TRDAR)가 없는 거점이라 빈 시간대 카드는 만들지 않았어요.")

    top = nearby_stores.colocated_top(district_id, industry_key)[:2] if industry_key else []
    if top:
        cards.append(_neighbor_card(top))
    elif industry_key:
        notes.append("이 도시 범위에서는 이 업종과 함께 모이는 업종을 잴 표본이 부족해요.")

    cards.append(_own_card(mode, bool(walkable)))
    return {
        "district_id": district_id, "mode": mode, "cards": cards,
        "events_source": events_source,
        "notes": notes,
        "note": ("근거가 있는 카드만 냈어요. 예산과 목표치는 창업자가 정합니다 — 예상 유입·매출은 내지 않아요. "
                 "카드의 「측정」은 가설 검증 판정표로 옮겨 시작 전에 고정하세요."),
    }
