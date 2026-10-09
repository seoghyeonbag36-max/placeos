"""합성 예측으로 업종별 결측과 같은 분할 기준선 집계를 검증한다."""
import pytest

# 최소 데이터 CI에는 ML 선택 의존성이 없다. 설치된 환경에서 지표를 검증한다.
np = pytest.importorskip("numpy", reason="세부 업종 ML 지표는 numpy가 필요합니다")
from ml.training.industry_detail_metrics import per_class_metrics


def test_missing_classes_and_unpredicted_classes_are_explicit():
    y = np.array([0, 1, 0, 1])
    rows = per_class_metrics(["bar_beer", "beauty_nail"], y, np.array([0, 0, 0, 0]),
                             np.array([True, True, False, False]), np.array([False, False, True, True]),
                             np.array([True, False, True, False]), np.array([False, True, False, True]))
    by_key = {r["key"]: r for r in rows}
    assert by_key["bar_beer"]["precision"] == .5
    assert by_key["bar_beer"]["top3"] == 1
    assert by_key["bar_beer"]["baseline_top3"] == 0
    assert by_key["beauty_nail"]["precision"] is None
    assert by_key["beauty_nail"]["recall"] == 0
    assert by_key["culture_performance"]["status"] == "no_training_class"
