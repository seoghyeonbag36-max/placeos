"""내 업종으로 본 상권(화면설계서 3판) — 창업자·업종 바꾸기·상권 옮기기 사업자용 비교.

이 그물이 잡는 회귀:
  - 모델 라벨 없는 업종에 **순위나 적합도가 지어져** 나가는 것(가까운 업종 점수로 채우기)
  - 모델 라벨은 있지만 **서빙 어휘에 없는** 업종이 0.0 으로 줄 세워지는 것(09-27 전시·공연)
  - 순위가 적합도 순이 아니거나, 적합도 없는 상권이 0 으로 순위에 섞이는 것
  - 업종 key 가 바뀌어 브라우저에 저장된 「내 사업」이 조용히 깨지는 것
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import business_fit, industry_recommend

client = TestClient(app)


def test_industry_list_is_the_stable_twelve():
    body = client.get("/api/v1/ai/industries").json()
    keys = [i["key"] for i in body["industries"]]
    # key 는 저장값이다 — 바꾸거나 지우면 이미 설정한 사용자의 「내 사업」이 사라진다.
    assert keys == ["cafe", "restaurant", "bar", "beauty", "clinic", "pharmacy",
                    "convenience", "fashion", "education", "fitness", "lodging", "culture"]
    labels = {i["model_label"] for i in body["industries"]} - {None}
    assert labels == {"카페", "음식점", "병원", "약국", "편의점", "숙박", "문화시설"}
    # 규칙(needles)은 응답에 싣지 않는다
    assert all(set(i) == {"key", "label", "input", "model_label", "fit_unavailable_reason"}
               for i in body["industries"])


def test_fit_ranks_districts_by_model_fit():
    resp = client.get("/api/v1/ai/industry-fit", params={"industry": "cafe"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_covered"] is True
    ranked = [d for d in body["districts"] if d["fit_rank"] is not None]
    assert ranked, "카페는 모델 7종 안이라 순위가 있어야 한다"
    assert body["ranked_n"] == len(ranked)
    assert [d["fit_rank"] for d in ranked] == list(range(1, len(ranked) + 1))
    fits = [d["fit"] for d in ranked]
    assert fits == sorted(fits, reverse=True)
    # 순위 없는 상권은 순위 있는 상권 뒤에만 온다(0 으로 섞이지 않는다)
    first_unranked = next((i for i, d in enumerate(body["districts"]) if d["fit_rank"] is None), None)
    if first_unranked is not None:
        assert all(d["fit_rank"] is None for d in body["districts"][first_unranked:])
    assert 0 < body["seoul_fit"] < 1
    assert "매출·생존율이 아니다" in body["note"]


def test_fit_rows_carry_sample_share_and_rent_without_vacancy():
    body = client.get("/api/v1/ai/industry-fit", params={"industry": "cafe"}).json()
    row = next(d for d in body["districts"] if d["same_n"] is not None)
    assert row["sample_n"] >= row["same_n"] >= 0
    assert abs(row["same_share"] - row["same_n"] / row["sample_n"]) < 1e-3
    # 공실률은 화면이 상권 목록에서 합친다 — 두 엔드포인트가 같은 값을 따로 만들지 않는다
    assert "vacancy_rate" not in row


def test_uncovered_industry_gets_no_rank_or_fit():
    body = client.get("/api/v1/ai/industry-fit", params={"industry": "bar"}).json()
    assert body["model_covered"] is False
    assert body["seoul_fit"] is None
    assert body["ranked_n"] == 0
    assert all(d["fit"] is None and d["fit_rank"] is None for d in body["districts"])
    # 순위가 없으면 가나다순 — 어떤 기준으로도 줄 세운 것처럼 보이지 않게
    names = [d["name"] for d in body["districts"]]
    assert names == sorted(names)
    # 같은 업종 비중은 그대로 준다
    assert any((d["same_n"] or 0) > 0 for d in body["districts"])


def test_district_industries_ranks_covered_first_and_marks_uncovered():
    resp = client.get("/api/v1/ai/district-industries/yeonnam")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == len(business_fit.INDUSTRIES)
    # 순위가 나는 건 model_label 이 있고 **서빙 어휘에도 있는** 업종뿐이다
    covered = [r for r in rows if r["fit_unavailable_reason"] is None]
    assert covered and all(r["model_label"] for r in covered)
    assert [r["fit_rank"] for r in covered] == list(range(1, len(covered) + 1))
    assert [r["fit"] for r in covered] == sorted((r["fit"] for r in covered), reverse=True)
    uncovered = rows[len(covered):]
    assert uncovered and all(r["fit"] is None and r["fit_rank"] is None and r["fit_unavailable_reason"]
                             for r in uncovered)


def test_unknown_industry_and_district_are_404():
    assert client.get("/api/v1/ai/industry-fit", params={"industry": "nope"}).status_code == 404
    assert client.get("/api/v1/ai/district-industries/nowhere").status_code == 404


def test_same_counts_follow_needles(monkeypatch):
    rows = [("category", "카페", 22.0), ("category", "커피전문점", 10.0), ("category", "호프,요리주점", 5.0),
            ("category", "성형외과", 18.0), ("category", "CU", 3.0), ("demand", "stor_co", 100.0)]
    monkeypatch.setattr(business_fit.marketing, "context_rows", lambda _id: rows)
    counts, total = business_fit._same_counts("any")
    assert total == 58
    assert counts["cafe"] == 32 and counts["bar"] == 5 and counts["clinic"] == 18
    assert counts["convenience"] == 3 and counts["beauty"] == 0


# ── 서빙 어휘 밖 업종(모델 라벨은 있으나 산출물에 없음) ─────────────────────────────

@pytest.fixture
def fresh_cache():
    business_fit._cache.clear()
    yield
    business_fit._cache.clear()


def _fake_gold(labels_by_district: dict[str, list[tuple[str, float]]]) -> dict:
    return {"model": "industry-gnn", "metrics": {}, "districts": {
        did: {"n0": {"lat": 0.0, "lon": 0.0,
                     "top": [{"industry": k, "score": v} for k, v in top]}}
        for did, top in labels_by_district.items()}}


def _assert_unranked(body: dict) -> None:
    assert body["model_covered"] is False
    assert body["ranked_n"] == 0
    assert body["seoul_fit"] is None
    assert all(d["fit"] is None and d["fit_rank"] is None for d in body["districts"])
    names = [d["name"] for d in body["districts"]]
    assert names == sorted(names)


def test_served_labels_come_from_the_gold_artifact(fresh_cache):
    labels = business_fit.served_labels()
    # 어휘는 산출물이 정한다 — 코드에 박힌 7종이 아니다
    assert labels and "카페" in labels
    covered = {i["key"] for i in business_fit.INDUSTRIES
               if i["model_label"] and i["model_label"] in labels}
    for key in covered:
        assert business_fit.fit_by_district(key)["model_covered"] is True


def test_label_missing_from_real_vocab_gets_no_rank(fresh_cache):
    """실제 gold 기준 — 09-27 재학습 뒤 어휘에 없는 라벨을 가진 업종 전부(현재 전시·공연)."""
    labels = business_fit.served_labels()
    missing = [i for i in business_fit.INDUSTRIES
               if i["model_label"] and i["model_label"] not in labels]
    for item in missing:
        body = client.get("/api/v1/ai/industry-fit", params={"industry": item["key"]}).json()
        _assert_unranked(body)
        assert "어휘에 없음" in body["fit_unavailable_reason"]
        # model_label 은 지우지 않는다 — 다음 재학습에서 돌아오면 순위가 난다
        assert body["industry"]["model_label"] == item["model_label"]
        # 같은 업종 비교 표본은 계속 나온다
        assert any(d["sample_n"] is not None for d in body["districts"])
    # 사유는 model_label 없는 업종과 구분된다
    bar = client.get("/api/v1/ai/industry-fit", params={"industry": "bar"}).json()
    assert bar["fit_unavailable_reason"] == business_fit.REASON_NO_MODEL_LABEL
    cafe = client.get("/api/v1/ai/industry-fit", params={"industry": "cafe"}).json()
    assert cafe["model_covered"] is True and cafe["ranked_n"] > 0
    assert cafe["fit_unavailable_reason"] is None


def test_culture_unranked_in_district_view_with_real_gold(fresh_cache):
    if "문화시설" in (business_fit.served_labels() or ()):
        pytest.skip("서빙 어휘에 문화시설이 돌아왔다 — 이 회귀 조건이 성립하지 않는다")
    rows = client.get("/api/v1/ai/district-industries/yeonnam").json()["rows"]
    culture = next(r for r in rows if r["key"] == "culture")
    assert culture["fit"] is None and culture["fit_rank"] is None
    assert "어휘에 없음" in culture["fit_unavailable_reason"]
    ranked = [r for r in rows if r["fit_rank"] is not None]
    assert [r["fit_rank"] for r in ranked] == list(range(1, len(ranked) + 1))
    assert rows[:len(ranked)] == ranked  # 순위 없는 업종은 뒤에만


def test_vocab_is_read_from_artifact_not_code(monkeypatch, fresh_cache):
    """가짜 산출물 — 문화시설이 있으면 순위가 나고, 카페가 빠지면 카페가 순위를 잃는다."""
    fake = _fake_gold({"yeonnam": [("문화시설", 0.3), ("음식점", 0.6)],
                       "hongdae": [("문화시설", 0.1), ("음식점", 0.8)]})
    monkeypatch.setattr(industry_recommend, "_load", lambda: fake)
    monkeypatch.setattr(business_fit, "_served",
                        lambda: [{"id": "yeonnam", "name": "연남", "gu": "마포구"},
                                 {"id": "hongdae", "name": "홍대", "gu": "마포구"}])
    assert business_fit.served_labels() == {"문화시설", "음식점"}

    culture = business_fit.fit_by_district("culture")
    assert culture["model_covered"] is True and culture["ranked_n"] == 2
    assert culture["fit_unavailable_reason"] is None
    assert [d["district_id"] for d in culture["districts"]] == ["yeonnam", "hongdae"]

    cafe = business_fit.fit_by_district("cafe")
    _assert_unranked(cafe)
    assert cafe["fit_unavailable_reason"] == business_fit.REASON_NOT_IN_VOCAB.format(label="카페")

    rows = business_fit.industries_in_district("yeonnam")["rows"]
    by_key = {r["key"]: r for r in rows}
    assert by_key["restaurant"]["fit_rank"] == 1 and by_key["culture"]["fit_rank"] == 2
    assert by_key["cafe"]["fit"] is None and by_key["cafe"]["fit_rank"] is None
    assert "어휘에 없음" in by_key["cafe"]["fit_unavailable_reason"]
    assert by_key["bar"]["fit_unavailable_reason"] == business_fit.REASON_NO_MODEL_LABEL


def test_missing_artifact_ranks_nothing(monkeypatch, fresh_cache):
    monkeypatch.setattr(industry_recommend, "_load", lambda: None)
    body = business_fit.fit_by_district("cafe")
    _assert_unranked(body)
    assert body["fit_unavailable_reason"] == business_fit.REASON_NO_ARTIFACT
