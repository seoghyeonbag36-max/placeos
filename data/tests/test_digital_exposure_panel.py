import datetime as dt
import json

from data.collectors import digital_exposure_panel as panel


def _snap(day, hubs=None):
    hubs = hubs or {"a": {"token": "가", "queries": {
        "맛집": {"total": 1000, "n": 1000, "capped": True, "oldest": "20261109", "window_days": 9,
                "rate_per_day": 111.11, "precision": 0.9},
        "카페": {"total": 500, "n": 1000, "capped": True, "oldest": "20261105", "window_days": 13,
                "rate_per_day": 76.9, "precision": 0.4, "error": "Timeout"}}}}
    return {"collected_at": day, "hubs": hubs}


def _write_bronze(root, day, snap):
    d = root / day
    d.mkdir(parents=True)
    (d / panel.SNAP).write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")


# ── 패널 CSV ────────────────────────────────────────────────────────────────

def test_snapshot_rows_keep_only_numbers_and_keys_not_text():
    rows = panel.snapshot_rows(_snap("2026-11-17"))
    assert [r["suffix"] for r in rows] == ["맛집", "카페"]
    assert set(rows[0]) == set(panel.COLUMNS)  # 본문·스니펫·months 같은 열이 없다
    assert rows[1]["error"] == "Timeout" and rows[0]["capped"] == 1


def test_upsert_is_idempotent_and_overwrites_only_the_same_key(tmp_path):
    p = tmp_path / "panel.csv"
    first = panel.snapshot_rows(_snap("2026-11-17"))
    assert panel.upsert_panel(first, p) == 2
    assert panel.upsert_panel(first, p) == 2  # 같은 날 다시 → 중복 없음
    second = panel.snapshot_rows(_snap("2026-11-24"))
    assert panel.upsert_panel(second, p) == 4
    changed = [dict(r, total=1234) for r in panel.snapshot_rows(_snap("2026-11-17"))]
    assert panel.upsert_panel(changed, p) == 4  # 같은 키는 덮어쓴다
    got = {(r["collected_at"], r["suffix"]): r["total"] for r in panel.read_panel(p)}
    assert got[("2026-11-17", "맛집")] == "1234" and got[("2026-11-24", "맛집")] == "1000"


def test_rebuild_from_bronze_recovers_every_dated_snapshot(tmp_path):
    bronze = tmp_path / "platform13"
    _write_bronze(bronze, "2026-11-17", _snap("2026-11-17"))
    _write_bronze(bronze, "2026-11-24", _snap("2026-11-24"))
    (bronze / "2026-11-30").mkdir()  # 스냅샷 파일 없는 날짜 폴더는 무시
    assert panel.rebuild_from_bronze(bronze, tmp_path / "p.csv") == 4
    assert {r["collected_at"] for r in panel.read_panel(tmp_path / "p.csv")} == {"2026-11-17", "2026-11-24"}


# ── 빈 주 ───────────────────────────────────────────────────────────────────

D = dt.date


def test_is_due_is_per_iso_week_so_a_late_boot_still_catches_up():
    have = [D(2026, 11, 17)]  # 화요일
    assert not panel.is_due(have, D(2026, 11, 22))  # 같은 주 일요일
    assert panel.is_due(have, D(2026, 11, 23))      # 다음 주 월요일
    assert panel.is_due([], D(2026, 11, 23))


def test_missing_weeks_counts_past_weeks_only_not_the_current_one():
    have = [D(2026, 11, 17), D(2026, 12, 8)]  # W47, W50 — W48·W49 가 비었다
    assert panel.missing_weeks(have, D(2026, 12, 9)) == ["2026-W48", "2026-W49"]
    assert panel.missing_weeks(have, D(2026, 11, 23)) == []   # W48 은 아직 이번 주(보충 가능)
    assert panel.missing_weeks(have, D(2026, 11, 24)) == []
    assert panel.missing_weeks(have, D(2026, 11, 30)) == ["2026-W48"]
    assert panel.missing_weeks([], D(2026, 11, 30)) == []


# ── 오프사이트 ──────────────────────────────────────────────────────────────

def test_offsite_dir_env_off_custom_and_onedrive_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PLACEOS_OFFSITE_DIR", "off")
    assert panel.offsite_dir(tmp_path) is None
    monkeypatch.setenv("PLACEOS_OFFSITE_DIR", str(tmp_path / "x"))
    assert panel.offsite_dir(tmp_path) == tmp_path / "x"
    monkeypatch.delenv("PLACEOS_OFFSITE_DIR")
    assert panel.offsite_dir(tmp_path) is None  # OneDrive 폴더가 없으면 끈 것과 같다
    (tmp_path / "OneDrive").mkdir()
    assert panel.offsite_dir(tmp_path) == tmp_path / "OneDrive" / "PlaceOS-backup" / "digital-exposure"


def test_offsite_copy_copies_skips_and_heals_a_wiped_destination(tmp_path):
    bronze = tmp_path / "platform13"
    _write_bronze(bronze, "2026-11-17", _snap("2026-11-17"))
    csv_path = tmp_path / "panel.csv"
    panel.upsert_panel(panel.snapshot_rows(_snap("2026-11-17")), csv_path)
    dest = tmp_path / "backup"
    r1 = panel.offsite_copy(bronze, csv_path, dest)
    assert (r1["copied"], r1["skipped"], r1["failed"]) == (2, 0, [])
    r2 = panel.offsite_copy(bronze, csv_path, dest)
    assert (r2["copied"], r2["skipped"]) == (0, 2)  # 같은 내용은 건너뜀
    (dest / "panel.csv").unlink()
    r3 = panel.offsite_copy(bronze, csv_path, dest)
    assert (r3["copied"], r3["skipped"]) == (1, 1)  # 지워진 것만 복구
    assert (dest / "bronze" / "platform13" / "2026-11-17" / panel.SNAP).exists()
