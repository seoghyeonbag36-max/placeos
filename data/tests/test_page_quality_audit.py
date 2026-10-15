"""완료율 대신 결측·참조·실제 커버리지를 보고하는 감사기의 회귀 테스트."""
import subprocess
from types import SimpleNamespace

from scripts import page_quality_audit as A


def test_profile_requires_both_days_24_hours_and_positive_area():
    profile = {"wd": [1] * 24, "we": [2] * 24, "area_m2": 1000}
    assert A.valid_profile(profile)
    for invalid in ({**profile, "we": [2] * 23}, {**profile, "area_m2": 0},
                    {**profile, "wd": [float("nan")] * 24}, {**profile, "we": [-1] * 24}):
        assert not A.valid_profile(invalid)


def test_history_checks_master_pnu_not_only_file_presence():
    master = {"features": [{"properties": {"id": "a", "pnu": "correct"}}]}
    errors = []
    A.history_metrics(master, {"schema": "lot-history/1", "lots": {"wrong": [{}]},
                              "buildings": {"a": "wrong"}}, errors)
    assert errors and "참조 오류" in errors[0]


def test_floor_duplicate_and_false_confirmed_are_errors():
    master = {"features": [{"properties": {"id": "a", "pnu": "lot", "status": "partial",
                                           "com_floors": [1, 2, 3], "occ_floors": [1], "unknown_n": 1}}]}
    unit = {"id": "u", "building_id": "a", "pnu": "lot", "floor": 2,
            "certainty": "confirmed", "area_m2": 10}
    errors = []
    A.floor_metrics(master, {"units": [unit, unit], "counts": {"units": 2}}, errors)
    assert any("중복" in e for e in errors)
    assert any("배정 불일치" in e for e in errors)


def test_audit_missing_artifacts_remain_errors_not_full_completion(tmp_path):
    report = A.audit(tmp_path, {"active": SimpleNamespace(name="활성")})
    assert report["hub_count"] == 1
    assert report["global_errors"]
    assert report["hubs"][0]["errors"]
    assert report["hubs"][0]["rent"]["per_m2_krw_thousand"] is None


def test_deployment_uses_nul_paths_on_windows(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setattr(A, "ROOT", tmp_path)
    gold = tmp_path / "data" / "gold"
    (gold / "active").mkdir(parents=True)
    files = list(A.RUNTIME_FILES) + ["page_footfall_jipgyegu.json", "page_footfall_hourly.json",
                                   "platform_posting_inputs.json"]
    for name in files:
        path = gold / "active" / name if name in A.RUNTIME_FILES else gold / name
        path.write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    result = A.deployment(gold, {"active": None})
    assert result == {"untracked": [], "ignored_by_rules": [], "ignore_exit_code": 1}
    (tmp_path / ".gitignore").write_text("data/gold/*/coverage.json\n", encoding="utf-8")
    result = A.deployment(gold, {"active": None})
    assert result["ignored_by_rules"] == ["data/gold/active/coverage.json"]
    assert result["untracked"] == []
