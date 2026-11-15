"""순위 스냅샷 동결의 변환 규칙 잠금 (2026-11-15) — scripts/freeze_ranking_snapshot.py.

실호출(서빙 데이터)은 데이터에 기대므로 여기서 세지 않는다. **무엇을 남기고 무엇을 남기지 않는지**만 잠근다:
전방 검증이 이 파일로 오늘의 순위를 오늘의 결과로 잰다 — 결과 값이 섞이면 그 검증이 오염된다.
"""
import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "freeze_ranking_snapshot.py"
_spec = importlib.util.spec_from_file_location("freeze_ranking_snapshot", _SCRIPT)
fz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fz)

INDUSTRIES = [
    {"key": "cafe", "label": "카페·디저트", "model_label": "카페"},
    {"key": "bar", "label": "술집", "model_label": None},          # 순위 모델이 없다 → 순위가 없다
    {"key": "culture", "label": "전시·공연", "model_label": "문화시설"},
]


def _fit(key):
    if key == "culture":
        return {"model_covered": False, "fit_model": "m", "rank_groups": [], "districts": [
            {"district_id": "a", "name": "A", "gu": "가", "fit": None, "fit_rank": None, "same_share": 0.1}]}
    return {"model_covered": True, "fit_model": "industry-gnn",
            "rank_groups": [{"key": "industry-gnn/서울특별시", "fit_model": "industry-gnn", "name": "서울", "ranked_n": 1,
                             "mean_fit": 0.2, "extra": "버려진다"}],
            "districts": [{"district_id": "a", "name": "A", "gu": "가", "fit": 0.31, "fit_rank": 1,
                           "rank_group": "industry-gnn/서울특별시", "rank_n": 1, "fit_model": "industry-gnn",
                           "same_n": 12, "sample_n": 100, "same_share": 0.12,
                           "rent_1f_per_pyeong": 99.9, "rent_shared": False}]}


def test_only_industries_with_a_rank_model_are_kept():
    snap = fz.snapshot(INDUSTRIES, _fit)
    assert set(snap) == {"cafe", "culture"}                       # bar 는 model_label 이 없어 순위가 없다


def test_uncovered_model_is_recorded_not_dropped():
    snap = fz.snapshot(INDUSTRIES, _fit)
    assert snap["culture"]["model_covered"] is False
    assert snap["culture"]["districts"][0]["fit"] is None          # 점수가 없는 것을 0 으로 채우지 않는다


def test_only_whitelisted_row_fields_survive():
    row = fz.snapshot(INDUSTRIES, _fit)["cafe"]["districts"][0]
    assert set(row) == {"district_id", "name", "gu", "fit", "fit_rank", "rank_group", "rank_n", "fit_model",
                        "same_n", "sample_n", "same_share"}
    assert "rent_1f_per_pyeong" not in row                         # 순위와 무관한 값은 얼리지 않는다
    assert row["fit"] == 0.31 and row["same_share"] == 0.12


def test_no_outcome_fields_can_leak_into_the_snapshot():
    """결과(생존·폐업) 값이 서빙 응답에 있더라도 스냅샷에는 들어가지 않는다 — 전방 검증 오염 방지."""
    def leaky(key):
        r = _fit(key)
        for d in r["districts"]:
            d.update({"survival_24m": 0.8, "closure_rate": 0.2})
        return r
    row = fz.snapshot(INDUSTRIES, leaky)["cafe"]["districts"][0]
    assert not any(("surviv" in k or "closure" in k) for k in row)


def test_unknown_industry_response_is_skipped():
    assert fz.snapshot(INDUSTRIES, lambda key: None) == {}
