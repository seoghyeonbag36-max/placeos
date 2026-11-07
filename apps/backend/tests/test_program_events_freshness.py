"""행사 서빙 — 끝난 행사 제외 · 두 원천 병합(2026-11-07 Program 리뉴얼).

못 박는 것:
  1. 종료일이 오늘(KST)보다 앞이면 서빙하지 않는다 — 10-11 적재본은 11-07 에 749건 중 498건이 끝나 있었는데
     화면과 LLM 컨텍스트가 그것을 「예정 행사」로 실었다
  2. 종료일을 못 읽으면 끝났다고 단정하지 않는다(모름 ≠ 종료)
  3. 서울 문화행사 Gold 와 전국 행사 Gold 를 합치고, 같은 행사는 서울 쪽을 남긴다(시각·요금·링크가 그쪽에만 있다)
  4. 전국 Gold 가 덮는 서울 밖 거점은 출처가 "public-open-data" 이고 「서울만」 안내가 붙지 않는다
  5. 시각을 모르는 행사로 「빈 시간대에 열리는 행사는 없다」를 단정하지 않는다
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from app.services import events
from app.services import marketing as mkt

TODAY = date(2026, 11, 7)


def _ev(i: str, n: str, when: str, dist: int, **kw) -> dict:
    return {"id": i, "n": n, "lat": 37.5, "lng": 127.0, "ic": "🎪", "when": when, "place": "장소",
            "distance_m": dist, **kw}


@pytest.fixture
def gold(tmp_path, monkeypatch):
    """두 Gold 를 임시 파일로 바꿔 끼운다. 쓰는 쪽이 dict 를 넘기면 그 내용으로 파일을 만든다."""
    seoul_p, national_p = tmp_path / "platform_events.json", tmp_path / "platform_events_national.json"
    monkeypatch.setattr(events, "_EVENTS_JSON", seoul_p)
    monkeypatch.setattr(events, "_NATIONAL_JSON", national_p)
    events._cache.clear()

    def write(seoul: dict | None = None, national: dict | None = None):
        for p, doc in ((seoul_p, seoul), (national_p, national)):
            if doc is None:
                p.unlink(missing_ok=True)
            else:
                p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        events._cache.clear()

    yield write
    events._cache.clear()


def test_event_dates_and_ended():
    assert events.event_dates({"when": "2026-10-17~2026-10-25"}) == (date(2026, 10, 17), date(2026, 10, 25))
    assert events.event_dates({"when": "2026.11.30"}) == (date(2026, 11, 30), date(2026, 11, 30))
    assert events.event_dates({"when": "매월 둘째 금"}) == (None, None)
    assert events.is_ended({"when": "2026-10-17~2026-11-06"}, TODAY)
    assert not events.is_ended({"when": "2026-10-17~2026-11-07"}, TODAY), "오늘 끝나는 행사는 아직 열려 있다"
    assert not events.is_ended({"when": "상시"}, TODAY), "종료일을 모르면 끝났다고 단정하지 않는다"


def test_ended_events_are_not_served(gold):
    gold(seoul={"as_of": "2026-10-11", "districts": {"garosugil": [
        _ev("a", "끝난 축제", "2026-10-01~2026-10-25", 100),
        _ev("b", "진행 중 전시", "2026-10-20~2026-11-30", 200),
        _ev("c", "상시 마켓", "매주 토", 300),
    ]}})
    got = events.for_district("garosugil", today=TODAY)
    assert [e["id"] for e in got] == ["b", "c"]
    assert all(e["src"] == events.SRC_SEOUL for e in got)


def test_none_vs_empty_semantics(gold):
    gold()
    assert events.for_district("garosugil", today=TODAY) is None, "두 Gold 모두 없으면 None(미적재)"
    gold(national={"as_of": "2026-11-07", "sources": [], "districts": {"suwonst": []}})
    assert events.for_district("suwonst", today=TODAY) == [], "적재됐고 0건이면 빈 목록"
    assert events.national_covers("suwonst") and not events.national_covers("no-such-hub")


def test_merge_dedups_and_prefers_seoul_then_sorts_by_distance(gold):
    gold(seoul={"as_of": "2026-10-11", "districts": {"garosugil": [
        _ev("s1", "[서울] 가을 음악회", "2026-11-10~2026-11-12", 450, link="https://example.org/s1"),
    ]}}, national={"as_of": "2026-11-07", "sources": [{"id": "culture-portal"}], "districts": {"garosugil": [
        _ev("cp-1", "서울 가을음악회", "2026-11-10~2026-11-12", 440, src="culture-portal"),   # 같은 행사
        _ev("cp-2", "골목 사진전", "2026-11-01~2026-12-01", 120, src="culture-portal"),
        _ev("ta-9", "끝난 축제", "2026-10-01~2026-10-05", 50, src="tourapi"),
    ]}})
    got = events.for_district("garosugil", today=TODAY)
    assert [e["id"] for e in got] == ["cp-2", "s1"], "중복은 서울 쪽만, 끝난 것은 빼고, 가까운 순"
    assert got[1]["link"] == "https://example.org/s1"


def test_outside_seoul_hub_gets_public_source_when_national_covers(gold, monkeypatch):
    hub = "suwonst"
    gold(seoul={"as_of": "2026-10-11", "districts": {}},
         national={"as_of": "2026-11-07", "sources": [{"id": "culture-portal"}],
                   "districts": {hub: [_ev("cp-3", "수원 화성 문화제", "2026-11-01~2026-11-20", 800,
                                           src="culture-portal")]}})
    body = mkt.get_district_events(hub)
    assert body["events_source"] == "public-open-data"
    assert body["events_note"] is None, "전국 Gold 가 덮으면 「서울만」 안내를 붙이지 않는다"
    assert [e["id"] for e in body["events"]] == ["cp-3"]


def test_outside_seoul_hub_without_national_says_seoul_only(gold):
    gold(seoul={"as_of": "2026-10-11", "districts": {}})
    body = mkt.get_district_events("suwonst")
    assert body["events_source"] == "none" and body["events"] == [] and "서울만" in body["events_note"]


def test_seoul_hub_source_switches_when_national_loaded(gold):
    gold(seoul={"as_of": "2026-10-11", "districts": {"garosugil": []}})
    assert mkt.get_district_events("garosugil")["events_source"] == "seoul-open-data"
    gold(seoul={"as_of": "2026-10-11", "districts": {"garosugil": []}},
         national={"as_of": "2026-11-07", "sources": [], "districts": {"garosugil": []}})
    assert mkt.get_district_events("garosugil")["events_source"] == "public-open-data"


def test_untimed_events_do_not_prove_absence_in_gap_band(monkeypatch):
    monkeypatch.setattr(events, "for_district", lambda d: [
        {"n": "사진전", "when": "2026-11-01~2026-12-01", "place": "갤러리", "distance_m": 200},   # tm 없음(전국 Gold)
    ])
    ctx = mkt._events_context("garosugil", "17_21")
    assert "확인된 행사는 없다" in ctx and "시각 정보가 없는 행사 1건" in ctx
    assert "열리는 행사는 없다." not in ctx, "모르는 시각을 「안 열린다」로 단정했다"


def test_source_mtime_takes_latest(gold, tmp_path):
    gold(seoul={"districts": {}}, national={"districts": {}})
    assert events.source_mtime() == max(events._EVENTS_JSON.stat().st_mtime,
                                        events._NATIONAL_JSON.stat().st_mtime)


def test_sources_meta_names_loaded_sources(gold):
    gold(seoul={"as_of": "2026-10-11", "districts": {}},
         national={"as_of": "2026-11-07", "districts": {},
                   "sources": [{"id": "culture-portal", "license": "공공누리 1유형"}, {"id": "tourapi"}]})
    meta = events.sources_meta()
    assert [m["id"] for m in meta] == [events.SRC_SEOUL, "culture-portal", "tourapi"]
    assert meta[1]["name"] == "문화포털" and meta[1]["license"] == "공공누리 1유형"
