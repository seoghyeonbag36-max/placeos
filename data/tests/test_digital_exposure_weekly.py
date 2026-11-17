import datetime as dt
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "digital_exposure_weekly", Path(__file__).resolve().parents[2] / "scripts" / "digital_exposure_weekly.py")
weekly = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(weekly)

TODAY = dt.date(2026, 11, 23)


def _snap(root: Path, day: str) -> None:
    d = root / day
    d.mkdir(parents=True)
    (d / weekly.SNAP).write_text("{}", encoding="utf-8")


def test_age_is_none_without_any_snapshot(tmp_path):
    assert weekly.snapshot_age_days(tmp_path, TODAY) is None
    assert weekly.snapshot_age_days(tmp_path / "없는폴더", TODAY) is None


def test_age_uses_the_newest_dated_snapshot_and_ignores_other_folders(tmp_path):
    _snap(tmp_path, "2026-11-10")
    _snap(tmp_path, "2026-11-17")
    (tmp_path / "not-a-date").mkdir()
    (tmp_path / "2026-11-22").mkdir()  # 날짜 폴더지만 스냅샷 파일이 없다 → 무시
    assert weekly.snapshot_age_days(tmp_path, TODAY) == 6


def test_summarize_counts_errors_and_median_precision():
    snap = {"hubs": {
        "a": {"queries": {"맛집": {"precision": 0.2, "n": 1000}, "카페": {"precision": 0.8, "n": 1000, "error": "Timeout"}}},
        "b": {"queries": {"맛집": {"precision": 0.5, "n": 0}, "카페": {"precision": None, "n": 1000}}},
    }}
    assert weekly.summarize(snap) == {"hubs": 2, "queries": 4, "errors": 1, "empty": 1, "precision_median": 0.5}
