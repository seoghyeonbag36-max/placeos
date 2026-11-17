import datetime as dt
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "digital_exposure_weekly", Path(__file__).resolve().parents[2] / "scripts" / "digital_exposure_weekly.py")
weekly = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(weekly)


def test_summarize_counts_errors_and_median_precision():
    snap = {"hubs": {
        "a": {"queries": {"맛집": {"precision": 0.2, "n": 1000}, "카페": {"precision": 0.8, "n": 1000, "error": "Timeout"}}},
        "b": {"queries": {"맛집": {"precision": 0.5, "n": 0}, "카페": {"precision": None, "n": 1000}}},
    }}
    assert weekly.summarize(snap) == {"hubs": 2, "queries": 4, "errors": 1, "empty": 1, "precision_median": 0.5}


def test_snapshot_age_uses_newest_dated_folder_with_a_snapshot_file(tmp_path):
    assert weekly.snapshot_age_days(tmp_path, dt.date(2026, 11, 23)) is None
    for day in ("2026-11-10", "2026-11-17"):
        d = tmp_path / day
        d.mkdir()
        (d / "naver_blog_exposure.json").write_text("{}", encoding="utf-8")
    (tmp_path / "2026-11-22").mkdir()  # 파일 없는 폴더는 무시
    assert weekly.snapshot_age_days(tmp_path, dt.date(2026, 11, 23)) == 6
