"""입지 피처 실험의 순수 함수 검증 — 층 파싱·군집 부트스트랩·판정 규칙. 학습은 돌리지 않는다."""
import pytest

np = pytest.importorskip("numpy", reason="세부 업종 ML 지표는 numpy가 필요합니다")
from ml.training.industry_detail_features import cluster_bootstrap, parse_floor, verdict


@pytest.mark.parametrize("raw,expected", [
    ("1", (True, 1)), ("12", (True, 12)), ("지", (True, -1)), ("B1", (True, -1)), ("B2", (True, -2)),
    ("반지층", (True, -1)), ("", (False, 0)), (None, (False, 0)), ("nan", (False, 0)),
    ("403", (False, 0)), ("B145", (False, 0)),   # 호실 번호로 보이는 값은 층으로 추측하지 않는다
])
def test_parse_floor_does_not_guess_room_numbers(raw, expected):
    assert parse_floor(raw) == expected


def test_bootstrap_zero_sample_is_null_not_zero():
    r = cluster_bootstrap(np.array([]), np.array([]))
    assert r["n"] == 0 and r["mean"] is None and r["ci95"] is None
    assert verdict(r["ci95"], "상회", "열위") is None


def test_interval_containing_zero_is_indistinguishable():
    rng = np.random.default_rng(0)
    clusters = np.repeat(np.arange(20), 10)
    diff = rng.choice([-1.0, 0.0, 1.0], size=200)
    r = cluster_bootstrap(diff, clusters, n_boot=500)
    assert r["n_clusters"] == 20
    assert verdict(r["ci95"], "상회", "열위") == "구분불가"


def test_consistent_gain_is_flagged():
    clusters = np.repeat(np.arange(10), 10)
    r = cluster_bootstrap(np.ones(100), clusters, n_boot=200)
    assert verdict(r["ci95"], "상회", "열위") == "상회"
    r = cluster_bootstrap(-np.ones(100), clusters, n_boot=200)
    assert verdict(r["ci95"], "상회", "열위") == "열위"
