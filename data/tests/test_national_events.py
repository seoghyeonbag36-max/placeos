"""전국 행사 Gold(문화포털·TourAPI) 파이프라인 — 네트워크 없이 순수 함수만(2026-11-07)."""
from __future__ import annotations

import json
from collections import Counter
from datetime import date

from data.pipelines import build_national_events as b

AS_OF = date(2026, 11, 7)


def test_parse_ymd():
    assert b.parse_ymd("20261107") == date(2026, 11, 7)
    assert b.parse_ymd("2026-11-07") is None, "Bronze 원천 형식은 YYYYMMDD 뿐이다"
    assert b.parse_ymd("") is None and b.parse_ymd(None) is None
    assert b.parse_ymd("20261332") is None


def test_check_dates_drops_ended_missing_and_implausible():
    assert b.check_dates(date(2026, 11, 1), date(2026, 11, 7), AS_OF) is None, "기준일에 끝나는 행사는 남긴다"
    assert b.check_dates(date(2026, 10, 1), date(2026, 11, 6), AS_OF) == "기준일 전에 끝남"
    assert b.check_dates(None, date(2026, 12, 1), AS_OF) == "날짜 없음"
    assert b.check_dates(date(2015, 11, 21), date(9405, 12, 2), AS_OF) == "엉터리 날짜", "11-07 문화포털 실측 행"
    assert b.check_dates(date(2026, 12, 2), date(2026, 12, 1), AS_OF) == "엉터리 날짜"


def test_unescape_twice_handles_double_escaped_titles():
    assert b.unescape_twice("&amp;lt;빛의 정원&amp;gt;") == "<빛의 정원>"


def test_normalize_culture_keeps_contract_fields_and_counts_drops():
    drop = Counter()
    rows = [
        {"seq": "1", "title": "골목 사진전", "startDate": "20261101", "endDate": "20261130", "gpsX": "127.0",
         "gpsY": "37.5", "realmName": "전시", "place": "갤러리"},
        {"seq": "2", "title": "좌표 없는 공연", "startDate": "20261101", "endDate": "20261130", "gpsX": "",
         "gpsY": "", "realmName": "공연"},
        {"seq": "3", "title": "끝난 축제", "startDate": "20261001", "endDate": "20261005", "gpsX": "127.0",
         "gpsY": "37.5", "realmName": "축제"},
    ]
    out = b.normalize_culture(rows, AS_OF, drop)
    assert [e["id"] for e in out] == ["cp-1"]
    e = out[0]
    assert e["when"] == "2026-11-01~2026-11-30" and e["ic"] == "🖼" and e["src"] == "culture-portal"
    assert e["link"] is None and e["org"] is None and e["fee"] is None, "목록 응답에 없는 값을 지어내지 않는다"
    assert drop == Counter({"좌표 없음": 1, "기준일 전에 끝남": 1})


def test_normalize_tour_maps_category_codes_and_never_carries_images():
    drop = Counter()
    rows = [{"contentid": "9", "title": "강변 축제", "eventstartdate": "20261101", "eventenddate": "20261110",
             "mapx": "126.9", "mapy": "35.1", "lclsSystm3": "EV010100", "addr1": "광주 동구", "addr2": "",
             "firstimage": "http://tong.visitkorea.or.kr/x.jpg", "cpyrhtDivCd": "Type3"}]
    out = b.normalize_tour(rows, {"EV010100": "문화관광축제"}, AS_OF, drop)
    assert out[0]["category"] == "문화관광축제" and out[0]["ic"] == "🎪" and out[0]["place"] == "광주 동구"
    assert "firstimage" not in json.dumps(out[0]) and "visitkorea" not in json.dumps(out[0]), "사진 URL 금지(공공누리 3유형)"


def test_dedup_prefers_first_source_within_300m():
    a = b.event_record(src="culture-portal", sid="1", title="[서울] 가을 음악회", lat=37.5, lng=127.0,
                       start=date(2026, 11, 10), end=date(2026, 11, 12), category="공연", place="A")
    dup = b.event_record(src="tourapi", sid="2", title="서울 가을음악회", lat=37.5005, lng=127.0,
                         start=date(2026, 11, 10), end=date(2026, 11, 12), category="공연", place="A")
    far = b.event_record(src="tourapi", sid="3", title="서울 가을음악회", lat=37.6, lng=127.0,
                         start=date(2026, 11, 10), end=date(2026, 11, 12), category="공연", place="B")
    kept, removed = b.dedup([a, dup, far])
    assert [e["id"] for e in kept] == ["cp-1", "ta-3"] and removed == Counter({"tourapi": 1})


def test_assign_radius_sort_and_cap():
    evs = [b.event_record(src="culture-portal", sid=str(i), title=f"행사{i}", lat=37.5 + i * 0.001, lng=127.0,
                          start=date(2026, 11, 1), end=date(2026, 11, 30), category="전시", place="P")
           for i in range(5)]
    out = b.assign(evs, {"hub": (37.5, 127.0), "far": (35.0, 129.0)}, radius_m=350, max_per_hub=3)
    assert [e["id"] for e in out["hub"]] == ["cp-0", "cp-1", "cp-2"], "반경 안 · 가까운 순 · 상한"
    assert out["hub"][1]["distance_m"] == 111
    assert out["far"] == [], "덮었지만 0건이면 빈 목록"


def test_build_writes_gold_contract(tmp_path, monkeypatch):
    """Bronze 두 파일(원응답 형식 그대로) → Gold 최상위 계약 키."""
    folder = tmp_path / "bronze" / "national_events" / AS_OF.isoformat()
    folder.mkdir(parents=True)
    xml = ("<response><header><resultCode>00</resultCode></header><body><totalCount>1</totalCount><items><item>"
           "<seq>7</seq><title>골목 사진전</title><startDate>20261101</startDate><endDate>20261130</endDate>"
           "<place>갤러리</place><realmName>전시</realmName><gpsX>127.0</gpsX><gpsY>37.5</gpsY>"
           "</item></items></body></response>")
    (folder / "culture_portal.json").write_text(json.dumps({
        "source_id": "culture-portal", "name": "문화포털", "endpoint": "e", "dataset_page": "d", "license": "제한 없음",
        "fetched_at": "t", "pages": [{"PageNo": 1, "http": 200, "body": xml}]}), encoding="utf-8")
    tour_body = {"response": {"header": {"resultCode": "0000"}, "body": {"totalCount": 0, "items": ""}}}
    (folder / "tourapi_festivals.json").write_text(json.dumps({
        "source_id": "tourapi", "name": "TourAPI", "endpoint": "e", "dataset_page": "d", "license": "제한 없음",
        "fetched_at": "t", "pages": [{"pageNo": 1, "http": 200, "body": tour_body}], "lcls_codes": {}}),
        encoding="utf-8")
    monkeypatch.setattr(b, "_hubs", lambda: {"hub": (37.5, 127.0)})
    out = b.build(AS_OF, bronze_root=tmp_path / "bronze", silver_root=tmp_path / "silver", gold_root=tmp_path / "gold")
    gold = json.loads(out["path"].read_text(encoding="utf-8"))
    assert {"source", "built_at", "as_of", "radius_m", "max_per_hub", "note", "sources", "districts"} <= set(gold)
    assert [s["id"] for s in gold["sources"]] == ["culture-portal", "tourapi"]
    assert gold["districts"]["hub"][0]["id"] == "cp-7" and gold["districts"]["hub"][0]["distance_m"] == 0
    assert (tmp_path / "silver" / b.SILVER_NAME).exists()
