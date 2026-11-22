"""Program 리뉴얼(2026-11-07) — 지원 프로그램 · 네트워킹 · 실행 카드. 원천 호출은 전부 가짜다(네트워크 없음).

못 박는 것:
  - 지역·단계 규칙(K-Startup supt_regin·biz_enyy · 정부24 소관기관 · 기업마당 해시태그) — 「경기도 광주시」가 광주 거점에
    섞이지 않는다 · 끝난 공고는 빠진다 · 「행사ㆍ네트워크」 공고는 지원 목록이 아니라 네트워킹에 간다
  - 키가 없거나 원천이 실패하면 그 원천만 상태로 밝힌다(지난 목록을 최신처럼 보이지 않는다) · 키 값은 어디에도 없다
  - 네트워킹 응답에 개인 연락처 칸이 없다(정보통신망법 제50조 — 대신 연락하지 않는다)
  - 실행 카드는 근거가 있는 것만, 카드마다 측정 방법이 있고, 금액·예상 성과를 싣지 않는다
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import events, nearby_stores, program_network, program_plan, program_sources, program_support
from app.services import marketing as mkt

client = TestClient(app)
API = "/api/v1/program"
TODAY = date(2026, 11, 8)
SECRET = "sk-test-secret-key-value"


def ks(sn, title, regin="서울", enyy="예비창업자,1년미만", clsfc="사업화", end="20261130", **kw):
    return {"pbanc_sn": sn, "id": sn, "biz_pbanc_nm": title, "supt_regin": regin, "biz_enyy": enyy,
            "supt_biz_clsfc": clsfc, "pbanc_rcpt_bgng_dt": "20261101", "pbanc_rcpt_end_dt": end,
            "pbanc_ntrp_nm": "창업진흥원", "aply_trgt": "일반인", "pbanc_ctnt": "공고 내용", "detl_pg_url":
            "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view", "prch_cnpl_no": "02-000-0000",
            "rcrt_prgs_yn": "Y", **kw}


KS_ROWS = [
    ks("1001", "서울 예비창업 사업화 지원"),
    ks("1002", "부산 창업 지원", regin="부산"),
    ks("1003", "기창업자 스케일업", regin="전국", enyy="1년미만,3년미만"),
    ks("1004", "서울 창업 네트워킹 데이", clsfc="행사ㆍ네트워크", end="20261120"),
    ks("1005", "이미 마감된 공고", end="20261101"),
    ks("1006", "카페 창업 아카데미", regin="전국"),
    ks("1007", "광주 청년 창업", regin="광주"),
]
BIZ_EVENTS = {"jsonArray": [
    {"eventInfoId": "EVEN_1", "nttNm": "서울 창업 세미나", "eventInfoTyNm": "세미나", "eventBeginEndDe": "20261120 ~ 20261120",
     "areaNm": "서울", "originEngnNm": "서울창업허브", "bizinfoUrl": "https://www.bizinfo.go.kr/e?eventInfoId=EVEN_1",
     "nttCn": "카페 창업자 대상 세미나"},
    {"eventInfoId": "EVEN_2", "nttNm": "끝난 박람회", "eventBeginEndDe": "20261001 ~ 20261003", "areaNm": "서울"},
    {"eventInfoId": "EVEN_3", "nttNm": "대전 기술 교육", "eventBeginEndDe": "20261125 ~ 20261125", "areaNm": "대전"},
    {"eventInfoId": "EVEN_4", "nttNm": "전국 온라인 창업 설명회", "eventBeginEndDe": "20261112 ~ 20261112", "areaNm": "전국"},
]}


@pytest.fixture
def sources(monkeypatch):
    """원천 둘(K-Startup · 기업마당 행사)을 가짜로 — 부른 URL 을 센다."""
    calls: list[str] = []

    def fake(url, params):
        calls.append(url)
        assert "serviceKey" in params or "crtfcKey" in params
        if url == program_sources.KSTARTUP_URL:
            return {"data": KS_ROWS if params["page"] == 1 else [], "matchCount": len(KS_ROWS)}
        if url == program_sources.BIZINFO_EVENT_URL:
            return BIZ_EVENTS
        raise AssertionError(url)

    s = program_sources.settings
    monkeypatch.setattr(s, "data_go_kr_service_key", SECRET, raising=False)
    monkeypatch.setattr(s, "bizinfo_event_api_key", SECRET, raising=False)
    monkeypatch.setattr(program_sources, "_fetch_json", fake)
    program_sources.clear_cache()
    yield calls
    program_sources.clear_cache()


# ── 지역 ──────────────────────────────────────────────────────────────────
def test_region_of_seoul_uses_gu_and_outside_uses_city():
    r = program_support.region_of("garosugil")
    assert (r.sido, r.local, r.tags, r.bizinfo_tag) == ("서울특별시", "강남구", ("서울",), "서울")
    s = program_support.region_of("suwonst")
    assert (s.sido, s.local) == ("경기도", "수원시"), "특례시는 정부24 표기(○○시)로 맞춘다"
    g = program_support.region_of("gj-chungjang")
    assert g.local == "광주광역시" and g.bizinfo_tag == "전남광주" and "광주" in g.tags
    assert program_support.region_of("no-such-hub") is None


# ── 지원 프로그램 ──────────────────────────────────────────────────────────
def test_region_rank_reads_each_source_region_chip():
    seoul = program_support.region_of("garosugil")
    rank = lambda **it: program_support.region_rank({"matched": [], **it}, seoul)  # noqa: E731
    assert rank(matched=["지역: 서울특별시 강남구"]) == 0
    assert rank(matched=["지역: 서울"], region="서울") == 1
    assert rank(matched=["지역 해시태그: 서울"], area="서울") == 1
    assert rank(matched=["지역 해시태그: 서울"], area="전국") == 2, "기업마당 행사의 지역 칸이 전국이면 전국"
    assert rank(matched=["전국(중앙·공공기관)"]) == 2
    assert rank(matched=["지역: 전국"], region="전국") == 2
    assert rank() == 2, "지역을 모르면 전국으로 본다"
    assert rank(matched=["지역: 서울특별시"], title="[서울] 강남구 청년 창업 지원") == 0, "제목 머리가 내 구"
    assert rank(matched=["지역: 서울특별시"], title="[서울] 성동구 소상공인 지원") == 3, "같은 시도의 다른 구는 전국 뒤"
    suwon = program_support.region_of("suwonst")
    assert program_support.region_rank({"matched": ["지역: 경기도"], "title": "[경기] 안성시 도시재생 창업지원"}, suwon) == 3
    assert program_support.region_rank({"matched": ["지역: 경기도"], "title": "[경기] 수원시 창업 아카데미"}, suwon) == 0
    assert program_support.region_rank({"matched": ["지역: 경기도"], "title": "[경기] 2026 판교 투자교류회"}, suwon) == 1


def test_missing_keys_are_reported_per_source_without_calls(monkeypatch):
    s = program_sources.settings
    for k in ("data_go_kr_service_key", "bizinfo_event_api_key"):
        monkeypatch.setattr(s, k, "", raising=False)
    monkeypatch.setattr(program_sources, "_fetch_json", lambda *a, **k: pytest.fail("키 없이 원천을 불렀다"))
    program_sources.clear_cache()
    out = program_network.network("garosugil", None, None, None, today=TODAY)
    assert out["events"] == [] and {s["status"] for s in out["sources"]} == {"no_key"}
    assert all(s["note"] for s in out["sources"])


def test_bizinfo_reqerr_is_error_with_reason_and_no_secret(monkeypatch, sources):
    real = program_sources._fetch_json

    def ip_block(url, params):
        if url == program_sources.BIZINFO_EVENT_URL:
            return {"reqErr": "등록되지 않은 IP 입니다."}
        return real(url, params)

    monkeypatch.setattr(program_sources, "_fetch_json", ip_block)
    program_sources.clear_cache()
    out = program_network.network("garosugil", None, None, None, today=TODAY)
    biz = next(s for s in out["sources"] if s["id"] == "bizinfo_event")
    assert biz["status"] == "error" and "등록되지 않은 IP" in biz["note"]
    assert SECRET not in json.dumps(out, ensure_ascii=False)


def test_http_error_is_error_and_cached_briefly(monkeypatch):
    import urllib.error

    n = {"calls": 0}

    def boom(url, params):
        n["calls"] += 1
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(program_sources.settings, "data_go_kr_service_key", SECRET, raising=False)
    monkeypatch.setattr(program_sources, "_fetch_json", boom)
    program_sources.clear_cache()
    got = program_sources.kstartup_open()
    assert got.status == "error" and "HTTP 403" in got.note and SECRET not in got.note
    program_sources.kstartup_open()
    assert n["calls"] == 1, "실패는 TTL_FAIL_S 동안 다시 치지 않는다"
    program_sources.clear_cache()


def test_success_is_cached(sources):
    program_sources.kstartup_open()
    program_sources.kstartup_open()
    assert sources.count(program_sources.KSTARTUP_URL) == 1


# ── 네트워킹 ───────────────────────────────────────────────────────────────
def _keys(node, acc=None):
    acc = set() if acc is None else acc
    if isinstance(node, dict):
        for k, v in node.items():
            acc.add(k)
            _keys(v, acc)
    elif isinstance(node, list):
        for v in node:
            _keys(v, acc)
    return acc


def test_network_events_complements_questions_directory(sources):
    out = program_network.network("garosugil", "cafe", "카페·디저트", "pre_founder", today=TODAY)
    ids = [e["id"] for e in out["events"]]
    assert ids == ["bev-EVEN_1", "ks-1004", "bev-EVEN_4"],         "행사·네트워크 공고 + 기업마당 행사 · 끝난 행사·다른 시도(대전) 행사 제외 · 이 지역 먼저(업종 언급 우선) · 전국은 뒤"
    assert out["complements"] and all(c["lift"] for c in out["complements"]), "서울 범위 카페 동반 업종"
    assert len(out["questions"]) >= 5
    assert out["directory"][0]["url"] == "https://www.seoulsbdc.or.kr", "지역 기관이 먼저"
    seminar = next(e for e in out["events"] if e["id"] == "bev-EVEN_1")
    assert seminar["kind"] == "세미나" and any(m.startswith("업종 언급") for m in seminar["matched"])


def test_network_events_local_before_nationwide(sources, monkeypatch):
    """예전에는 시작일 순이라 3월부터 모집 중인 다른 지역 기관의 전국 공고가 맨 위에 섰다(11-08 실측)."""
    monkeypatch.setattr(sys.modules[__name__], "KS_ROWS", KS_ROWS + [
        ks("1008", "전국 창업 네트워킹(마감 임박)", regin="전국", clsfc="행사ㆍ네트워크", end="20261110")])
    out = program_network.network("garosugil", today=TODAY)
    ids = [e["id"] for e in out["events"]]
    assert ids[:2] == ["ks-1004", "bev-EVEN_1"] and set(ids[2:]) == {"ks-1008", "bev-EVEN_4"},         "마감이 가장 가까워도 전국 공고는 이 지역 공고 뒤"
    seminar = next(e for e in out["events"] if e["id"] == "bev-EVEN_1")
    assert (seminar["start"], seminar["end"]) == ("2026-11-20", "2026-11-20"), "실제 기간 필드(eventBeginEndDe)를 읽는다"
    assert "bev-EVEN_3" not in ids, "다른 시도(대전)에서 열리는 행사가 섞였다"
    with_industry = program_network.network("garosugil", "cafe", "카페·디저트", today=TODAY)
    assert with_industry["events"][0]["id"] == "bev-EVEN_1", "같은 지역 안에서는 업종 언급이 먼저"


def test_network_response_has_no_personal_contact_fields(sources):
    body = client.get(f"{API}/network", params={"district_id": "garosugil", "industry": "cafe"}).json()
    keys = _keys(body)
    forbidden = {k for k in keys if re.search(r"phone|tel|contact|email|mobile|prch_cnpl|전화", k, re.I)}
    assert not forbidden, f"연락처 칸이 생겼다: {forbidden}"
    text = json.dumps(body, ensure_ascii=False)
    assert "02-000-0000" not in text and "02-111-1111" not in text, "원천의 문의 번호가 새어 나왔다"


def test_network_without_industry_explains_complements(sources):
    out = program_network.network("garosugil", None, None, None, today=TODAY)
    assert out["complements"] == [] and "업종을 고르면" in out["complements_note"]


def test_network_is_for_the_opened_space_not_before_contract(sources):
    """2026-11-22 「Program = 개업 후 계약을 맺은 공실에 대한 네트워킹·오프라인 마케팅」 — 계약 전 질문과 지원사업 신청 창구를 싣지 않는다."""
    out = program_network.network("garosugil", "cafe", "카페·디저트", "founder", today=TODAY)
    questions = " ".join(out["questions"])
    for pre_contract in ("권리금", "임대인", "원상복구", "문을 닫거나"):
        assert pre_contract not in questions, f"계약 전 질문이 남았다: {pre_contract}"
    assert "상인회" in questions and "교차 쿠폰" in questions, "개업 뒤 이웃·상인 조직과 이야기할 것"
    urls = {d["url"] for d in out["directory"]}
    for grant in ("sbiz24.kr", "k-startup.go.kr", "bizinfo.go.kr", "gjsinbo.or.kr"):
        assert not any(grant in u for u in urls), f"지원사업 신청·보증 창구가 남았다: {grant}"
    assert "개업한 자리" in out["note"]
    founder = [e for e in out["events"] if any(m.startswith("단계:") for m in e["matched"])]
    assert all("기창업자(개업 후)" in " ".join(e["matched"]) for e in founder)


# ── 실행 카드 ──────────────────────────────────────────────────────────────
_MONEY = re.compile(r"\d[\d,]*\s*(원|만원)|예산\s*\d|\d+\s*%")


def test_plan_cards_from_evidence_only(monkeypatch):
    near = [{"id": f"e{i}", "n": f"행사{i}", "when": "2026-11-01~2026-11-30", "place": "광장", "distance_m": 100 * i,
             "org": "구청", "src": "culture-portal"} for i in range(1, 5)]
    far = [{"id": "far", "n": "먼 행사", "when": "2026-11-01~2026-11-30", "place": "먼 곳", "distance_m": 2500}]
    monkeypatch.setattr(events, "for_district", lambda d, today=None: near + far)
    monkeypatch.setattr(mkt, "get_district_events", lambda d: {"events_source": "public-open-data"})
    monkeypatch.setattr(mkt, "_events_unavailable_note", lambda d: None)
    monkeypatch.setattr(mkt, "context_rows", lambda d: [("demand", "flpop_tmzon_17_21", 30.0),
                                                         ("demand", "selng_tmzon_17_21", 20.0),
                                                         ("demand", "flpop_tmzon_11_14", 20.0),
                                                         ("demand", "selng_tmzon_11_14", 25.0)])
    monkeypatch.setattr(nearby_stores, "colocated_top", lambda d, ind: [
        {"key": "bar", "label": "술집", "lift": 1.39, "n_both": 2263},
        {"key": "pharmacy", "label": "약국", "lift": 1.48, "n_both": 1252}])
    out = program_plan.plan("garosugil", "cafe", "popup")
    kinds = [c["kind"] for c in out["cards"]]
    assert kinds == ["event", "event", "event", "time", "neighbor", "own"], kinds
    assert "먼 행사" not in json.dumps(out, ensure_ascii=False), "걸어갈 거리 밖 행사를 연계 카드로 냈다"
    assert all(c["measure"] for c in out["cards"]), "측정 없는 카드"
    for c in out["cards"]:
        blob = " ".join([c["title"], c["when"], c["where"], c["who"], c["what"], c["measure"]])
        assert not _MONEY.search(blob), f"금액·비율을 지어냈다: {blob}"
    assert "17~21시" in out["cards"][3]["when"]


def test_plan_defaults_to_after_opening_and_measures_into_the_ledger(monkeypatch):
    """2026-11-22 — 화면은 개업 뒤(actual_open)만 부른다. 기본값도 그렇고, 카드의 측정은 없어진 가설 판정표가 아니라 실행 기록으로 간다."""
    monkeypatch.setattr(events, "for_district", lambda d, today=None: [])
    monkeypatch.setattr(mkt, "get_district_events", lambda d: {"events_source": "public-open-data"})
    monkeypatch.setattr(mkt, "_events_unavailable_note", lambda d: None)
    monkeypatch.setattr(mkt, "context_rows", lambda d: None)
    monkeypatch.setattr(nearby_stores, "colocated_top", lambda d, ind: [
        {"key": "bar", "label": "술집", "lift": 1.39, "n_both": 2263}])
    out = program_plan.plan("garosugil", "cafe")
    assert out["mode"] == "actual_open"
    neighbor = next(c for c in out["cards"] if c["kind"] == "neighbor")
    own = next(c for c in out["cards"] if c["kind"] == "own")
    assert neighbor["when"] == "개업 뒤" and own["when"] == "개업 뒤"
    assert "사전 예약" not in own["title"] + own["what"] and "다시 방문" in own["measure"]
    assert "실행 기록" in out["note"] and "가설" not in out["note"]
    body = client.get(f"{API}/plan", params={"district_id": "garosugil", "industry": "cafe"}).json()
    assert body["mode"] == "actual_open", "API 기본값도 개업 뒤"


def test_plan_without_evidence_still_gives_own_card_and_says_why(monkeypatch):
    monkeypatch.setattr(mkt, "_events_unavailable_note", lambda d: "행사 자료는 서울만 있어요 — 수원 상권은 수집하지 않았어요.")
    monkeypatch.setattr(mkt, "get_district_events", lambda d: {"events_source": "none"})
    monkeypatch.setattr(mkt, "context_rows", lambda d: None)
    out = program_plan.plan("suwonst", None, "mvp")
    assert [c["kind"] for c in out["cards"]] == ["own"] and "사전주문" in out["cards"][0]["title"]
    assert any("서울만" in n for n in out["notes"]) and any("TRDAR" in n for n in out["notes"])
    assert "옥외광고물" in out["cards"][0]["caveat"]


# ── API ────────────────────────────────────────────────────────────────────
def test_routes_shape_and_validation(sources):
    r = client.get(f"{API}/network", params={"district_id": "garosugil", "industry": "cafe", "stage": "founder"})
    assert r.status_code == 200 and r.json()["region"]["label"] == "서울특별시 강남구"
    assert client.get(f"{API}/network", params={"district_id": "no-such-hub"}).status_code == 404
    assert client.get(f"{API}/network", params={"district_id": "garosugil", "stage": "x"}).status_code == 422
    assert client.get(f"{API}/plan", params={"district_id": "garosugil", "mode": "x"}).status_code == 422
    assert client.get(f"{API}/plan", params={"district_id": "garosugil"}).status_code == 200
    assert SECRET not in r.text
    # 2026-11-22 지원 공고(/program/support)는 지웠다 — 경로가 없다
    assert client.get(f"{API}/support", params={"district_id": "garosugil"}).status_code == 404


def test_routes_do_not_shadow_campaigns():
    """같은 접두어의 /program/campaigns 는 그대로 인증을 요구한다."""
    assert client.get(f"{API}/campaigns").status_code == 401
