"""무인 거점 배치(scripts/run_hub_chain_batch.py) — 실패를 「완료」로 적지 않는다.

2026-10-28 gg3 배치 9거점 중 3곳에서 자식 프로세스가 시작조차 못 했는데(0xC0000142), 배치는 다음
단계로 넘어가 `calibration.json` 까지 만들었고 `stage_done` 은 그 파일만 보고 「완료」로 쳤다 —
단대오거리는 정밀커버리지 5.5% 인 채로, 신흥은 공실유닛 없이 끝난 것으로 남았다. 같은 날 오후에는 쿼터가
끝난 뒤에도 배치가 거점마다 429 로 헛돌았다. 아래가 그 자리들과, 같은 날 리뷰가 찾은 구멍을 고정한다.

실행: (레포 루트에서) python -m pytest -q data/tests/test_hub_chain_batch.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time

import pytest

from scripts import run_hub_chain_batch as rb

SLUG = "chain-probe"


@pytest.fixture
def root(tmp_path, monkeypatch):
    """배치의 ROOT·LOG 를 임시 폴더로 돌리고, 점포·대장(완주)은 이미 있는 거점을 만든다."""
    monkeypatch.setattr(rb, "ROOT", tmp_path)
    monkeypatch.setattr(rb, "LOG", tmp_path / "data" / "logs" / "batch.log")
    monkeypatch.setattr(rb, "STATE", tmp_path / "reports" / "hub_chain_batch.json")
    monkeypatch.setattr(rb, "ledger_gap", lambda slug: 0)
    monkeypatch.setattr(rb, "RETRY_WAIT_S", 0)
    stores = tmp_path / "data" / "bronze" / SLUG / "2026-10-28" / "stores_raw.json"
    stores.parent.mkdir(parents=True)
    stores.write_text("[]", encoding="utf-8")
    gold = tmp_path / "data" / "gold" / SLUG
    gold.mkdir(parents=True)
    (gold / "building_vacancy.json").write_text("[]", encoding="utf-8")
    return tmp_path


def _gold(root, name):
    return root / "data" / "gold" / SLUG / name


def _touch(path, age_s=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("{}", encoding="utf-8")
    t = time.time() - age_s
    os.utime(path, (t, t))
    return path


def _licensing(root, age_s=0):
    return _touch(root / "data" / "bronze" / SLUG / "2026-10-28" / "licensing_biz.json", age_s)


def _fake_run(calls, fail_at=None):
    def run(mod, label):
        calls.append(label)
        return label != fail_at
    return run


def _counts(monkeypatch, *values):
    """ledger_counts 가 차례로 values 를 돌려준다(마지막 값은 계속). 값 = (후보, 받음, 429 행)."""
    seq = list(values)
    monkeypatch.setattr(rb, "ledger_counts", lambda slug: seq.pop(0) if len(seq) > 1 else seq[0])


GOLD_STEPS = ["건물속성", "분모 재계산", "Page 마스터", "공실유닛", "층 단위 빈 자리"]


# ── run(): 시작조차 못 한 실패만 다시 부른다 ─────────────────────────────────────────

def _completed(code):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout="", stderr="")


def test_run_retries_dll_init_failure_then_succeeds(root, monkeypatch):
    codes = [0xC0000142, 0xC0000142, 0]
    monkeypatch.setattr(rb.subprocess, "run", lambda *a, **k: _completed(codes.pop(0)))
    monkeypatch.setattr(rb.time, "sleep", lambda s: None)
    assert rb.run(["data.pipelines.build_vacant_units", SLUG], "공실유닛") is True
    assert codes == [], "0xC0000142 를 다시 부르지 않았다"


def test_run_does_not_retry_real_failures(root, monkeypatch):
    calls = []
    monkeypatch.setattr(rb.subprocess, "run", lambda *a, **k: calls.append(1) or _completed(1))
    assert rb.run(["data.pipelines.build_vacant_units", SLUG], "공실유닛") is False
    assert len(calls) == 1, "코드가 실패한 것을 되풀이해 불렀다"


def test_run_gives_up_after_retries(root, monkeypatch):
    calls = []
    monkeypatch.setattr(rb.subprocess, "run",
                        lambda *a, **k: calls.append(1) or _completed(0xC0000142))
    monkeypatch.setattr(rb.time, "sleep", lambda s: None)
    assert rb.run(["x", SLUG], "공실유닛") is False
    assert len(calls) == rb.RETRIES


# ── 실패 표식: 실패한 단계 뒤는 돌리지 않고, 끝까지 가야 지운다 (§지키는 것 4) ──────────

def test_failed_step_stops_the_hub_and_leaves_a_marker(root, monkeypatch):
    calls = []
    monkeypatch.setattr(rb, "run", _fake_run(calls, fail_at="공실유닛"))
    # 대장까지 받은 거점(stage "ledger") — 공실유닛에서 실패한다
    assert rb.do_hub(SLUG, skip_ledger=False) == "ledger"
    assert "층 단위 빈 자리" not in calls and "앵커 보정" not in calls, "실패 뒤 단계를 돌렸다"
    assert rb.failed_from(SLUG) == "ledger"


def test_marker_beats_an_existing_calibration(root):
    """`calibration.json` 이 남아 있어도 표식이 있으면 완료가 아니다 — 10-28 의 그 자리다."""
    _touch(_gold(root, "page_building_master.geojson"))
    _touch(_gold(root, "calibration.json"))
    assert rb.stage_done(SLUG) == "anchor"
    rb.mark_failed(SLUG, "층별개요")
    assert rb.stage_done(SLUG) == "stores", "표식이 있는데 「완료」로 쳤다"


def test_redo_from_marker_reruns_calibration_and_then_clears_it(root, monkeypatch):
    """표식으로 Gold 를 다시 세웠으면 앵커 보정도 다시 한다 — 옛 calibration 이 남아 있어도. 끝나야 표식을 지운다."""
    _touch(_gold(root, "page_building_master.geojson"))
    _touch(_gold(root, "calibration.json"))
    rb.mark_failed(SLUG, "분모 재계산")
    calls = []
    monkeypatch.setattr(rb, "run", _fake_run(calls))
    assert rb.do_hub(SLUG, skip_ledger=False) == "anchor"
    assert calls == GOLD_STEPS + ["앵커 보정"]
    assert not _gold(root, "chain_failed.json").exists(), "끝까지 갔는데 표식이 남았다"


def test_marker_survives_an_early_return(root, monkeypatch):
    """`--skip-ledger` 로 일찍 돌아가면 아무것도 다시 안 했다 — 표식이 남아야 한다(리뷰 #1).

    종전에는 do_hub 첫머리에서 표식을 지워, 옛 calibration 위에서 거점이 「완료」로 보였다."""
    _touch(_gold(root, "page_building_master.geojson"))
    _touch(_gold(root, "calibration.json"))
    rb.mark_failed(SLUG, "분모 재계산")
    calls = []
    monkeypatch.setattr(rb, "run", _fake_run(calls))
    rb.do_hub(SLUG, skip_ledger=True)
    assert calls == [] and rb.stage_done(SLUG) == "ledger", "다시 밀지도 않았는데 완료가 됐다"


def test_same_step_failing_three_times_is_given_up(root, monkeypatch):
    """같은 단계가 연달아 실패하면 사람 확인으로 넘긴다 — 재개 작업이 10분마다 되풀이하지 않게(리뷰 #6)."""
    for _ in range(rb.GIVE_UP_AFTER - 1):
        rb.mark_failed(SLUG, "공실유닛")
    assert not rb.gave_up(SLUG)
    rb.mark_failed(SLUG, "공실유닛")
    assert rb.gave_up(SLUG)
    rb.mark_failed(SLUG, "Page 마스터")          # 다른 단계면 처음부터 센다
    assert not rb.gave_up(SLUG)


def test_resume_does_not_count_given_up_hubs(root, monkeypatch):
    sys.path.insert(0, str(rb.Path(rb.__file__).resolve().parent))
    import run_hub_chain_batch as rb_plain     # resume 이 부르는 모듈 이름 그대로
    from scripts import resume_hub_chain as rs
    monkeypatch.setattr(rb_plain, "hubs_of", lambda batch: ["a", "b"])
    monkeypatch.setattr(rb_plain, "stage_done", lambda slug: "ledger")
    monkeypatch.setattr(rb_plain, "gave_up", lambda slug: slug == "b")
    assert rs.remaining("gg3") == ["a"]


# ── 인허가가 Page 마스터보다 늦으면 Gold 는 낡았다 ──────────────────────────────────

def test_licensing_newer_than_master_marks_gold_stale(root):
    _touch(_gold(root, "page_building_master.geojson"), age_s=3600)   # 마스터가 인허가보다 한 시간 먼저 섰다
    _touch(_gold(root, "calibration.json"))
    _licensing(root)
    assert rb.stage_done(SLUG) == "ledger"
    _touch(_gold(root, "page_building_master.geojson"))               # 마스터를 다시 세운 뒤에는 완료
    _licensing(root, age_s=60)
    assert rb.stage_done(SLUG) == "anchor"


def test_recalibrating_alone_does_not_hide_stale_licensing(root):
    """앵커 보정만 다시 돌아 calibration 이 새로워져도 마스터가 인허가보다 낡았으면 낡은 것이다(리뷰 #2b)."""
    _touch(_gold(root, "page_building_master.geojson"), age_s=3600)
    _licensing(root, age_s=1800)
    _touch(_gold(root, "calibration.json"))                           # 인허가보다 새롭다
    assert rb.stage_done(SLUG) == "ledger"


def test_marker_does_not_mask_licensing_staleness(root, monkeypatch):
    """표식 'master' 가 있어도 인허가가 마스터보다 새로우면 마스터부터 다시 세운다(리뷰 #2a)."""
    _touch(_gold(root, "page_building_master.geojson"), age_s=3600)
    _touch(_gold(root, "calibration.json"), age_s=3600)
    _licensing(root)
    rb.mark_failed(SLUG, "앵커 보정")
    assert rb.stage_done(SLUG) == "ledger"
    calls = []
    monkeypatch.setattr(rb, "run", _fake_run(calls))
    rb.do_hub(SLUG, skip_ledger=False)
    assert "Page 마스터" in calls and "건물 이력" in calls and calls[-1] == "앵커 보정"


def test_building_history_runs_only_when_licensing_exists(root, monkeypatch):
    """건물 이력은 인허가가 있을 때만 — 없으면 빌더가 exit 1 이라 실패 표식으로 영영 막힌다."""
    calls = []
    monkeypatch.setattr(rb, "run", _fake_run(calls))
    rb.do_hub(SLUG, skip_ledger=False)                 # 인허가 없음
    assert "건물 이력" not in calls
    _licensing(root)
    _gold(root, "calibration.json").unlink(missing_ok=True)
    _gold(root, "page_building_master.geojson").unlink(missing_ok=True)
    calls.clear()
    rb.do_hub(SLUG, skip_ledger=False)                 # 인허가 있음 → Page 마스터 바로 뒤
    assert "건물 이력" in calls and calls.index("건물 이력") == calls.index("Page 마스터") + 1


# ── 쿼터: 받은 건물 수로 잰다 (§지키는 것 5) ──────────────────────────────────────────

def test_rate_limited_rows_are_not_received_buildings(root, monkeypatch):
    """수집기는 429 로 못 받은 건물을 rate_limited 로 적고 재개 때 다시 받는다 — 받은 것으로 세면 안 된다(리뷰 #3)."""
    import data.collectors.building_vacancy as bv
    import data.collectors.common as common
    monkeypatch.setattr(common, "load_latest", lambda slug, name: [{"bldMngNo": f"b{i}"} for i in range(4)])
    monkeypatch.setattr(bv, "group_by_building", lambda stores: {s["bldMngNo"]: s for s in stores})
    _gold(root, "building_vacancy.json").write_text(json.dumps(
        [{"capacity_method": "floor_ouln"}] + [{"capacity_method": "rate_limited"}] * 3), encoding="utf-8")
    assert rb.ledger_counts(SLUG) == (4, 1, 3)


def test_fresh_hub_with_only_429_rows_is_quota(root, monkeypatch):
    """대장 파일이 없던 거점에 429 행만 생겼다 — 진전이 아니라 쿼터 소진이다(리뷰 #3)."""
    _counts(monkeypatch, (279, 0, 0), (279, 0, 5))
    monkeypatch.setattr(rb, "stage_done", lambda slug: "stores")
    calls = []
    monkeypatch.setattr(rb, "run", _fake_run(calls))
    assert rb.do_hub(SLUG, skip_ledger=False) == rb.QUOTA
    assert calls == ["대장(전유부)", "층별개요"], "쿼터가 끝났는데 Gold 를 세웠다"


def test_no_rows_at_all_is_reported_as_no_response(root, monkeypatch, capsys):
    """한 행도 안 생겼으면(키 없음·네트워크) 쿼터라고 단정하지 않는다 — 멈추되 이유를 다르게 적는다(리뷰 #7a)."""
    _counts(monkeypatch, (279, 0, 0), (279, 0, 0))
    monkeypatch.setattr(rb, "stage_done", lambda slug: "stores")
    monkeypatch.setattr(rb, "run", _fake_run([]))
    assert rb.do_hub(SLUG, skip_ledger=False) == rb.QUOTA
    assert "키·네트워크" in capsys.readouterr().out


def test_partial_ledger_does_not_build_gold_on_a_truncated_denominator(root, monkeypatch):
    _counts(monkeypatch, (300, 0, 0), (300, 180, 3))    # 받긴 받았지만 아직 120동 남았다
    monkeypatch.setattr(rb, "stage_done", lambda slug: "stores")
    calls = []
    monkeypatch.setattr(rb, "run", _fake_run(calls))
    assert rb.do_hub(SLUG, skip_ledger=False) == "stores"
    assert "Page 마스터" not in calls and "앵커 보정" not in calls


def test_complete_ledger_builds_gold_and_calibrates(root, monkeypatch):
    _counts(monkeypatch, (300, 120, 0), (300, 300, 0))
    monkeypatch.setattr(rb, "stage_done", lambda slug: "stores")
    calls = []
    monkeypatch.setattr(rb, "run", _fake_run(calls))
    rb.do_hub(SLUG, skip_ledger=False)
    assert calls == ["대장(전유부)", "층별개요"] + GOLD_STEPS + ["앵커 보정"]


def test_quota_out_skips_the_ledger_but_still_rebuilds(root, monkeypatch):
    """쿼터가 끝난 날에도 대장이 필요 없는 일(표식 재빌드)은 민다 — 첫 쿼터에서 배치를 통째로 멈추지 않는다(리뷰 #7b)."""
    calls = []
    monkeypatch.setattr(rb, "run", _fake_run(calls))
    monkeypatch.setattr(rb, "stage_done", lambda slug: "stores")
    assert rb.do_hub(SLUG, skip_ledger=False, quota_out=True) == "stores" and calls == []
    monkeypatch.setattr(rb, "stage_done", lambda slug: "ledger")
    rb.do_hub(SLUG, skip_ledger=False, quota_out=True)
    assert calls == GOLD_STEPS + ["앵커 보정"], "대장이 필요 없는 재빌드를 건너뛰었다"


def test_resume_does_not_relaunch_on_a_quota_day(monkeypatch):
    from scripts import resume_hub_chain as rs
    launched = []
    monkeypatch.setattr(rs, "already_running", lambda batch: None)
    monkeypatch.setattr(rs, "remaining", lambda batch: ["x"])
    monkeypatch.setattr(rs, "launch", lambda batch: launched.append(batch) or 1)
    monkeypatch.setattr(rs, "say", lambda msg: None)
    monkeypatch.setattr(sys, "argv", ["resume_hub_chain.py", "--batch", "gg3"])
    monkeypatch.setattr(rs, "quota_spent_today", lambda: True)
    assert rs.main() == 0 and launched == [], "쿼터가 끝난 날에 배치를 되살렸다"
    monkeypatch.setattr(rs, "quota_spent_today", lambda: False)
    assert rs.main() == 0 and launched == ["gg3"]
    # quota_spent_today 는 상태파일의 오늘 날짜만 본다 — 어제 멈춘 기록은 오늘을 막지 않는다
    monkeypatch.undo()
    sys.path.insert(0, str(rb.Path(rb.__file__).resolve().parent))
    import run_hub_chain_batch as rb2           # resume 이 부르는 모듈 이름 그대로
    today = dt.date.today()
    monkeypatch.setattr(rb2, "load_state", lambda: {"quota_day": today.isoformat()})
    assert rs.quota_spent_today() is True
    monkeypatch.setattr(rb2, "load_state", lambda: {"quota_day": (today - dt.timedelta(days=1)).isoformat()})
    assert rs.quota_spent_today() is False


# ── 배터리: 인허가 전량 스캔은 배터리가 낮으면 시작하지 않는다 (리뷰 #10) ─────────────────

@pytest.mark.parametrize("power, scans", [((False, 10), False), ((False, 50), True), ((True, 3), True)])
def test_license_scan_waits_for_power(root, monkeypatch, power, scans):
    seen = []
    monkeypatch.setattr(rb, "power", lambda: power)
    monkeypatch.setattr(rb, "keep_awake", lambda hold=True: True)
    monkeypatch.setattr(rb, "license_upfront", lambda hubs: seen.append(hubs))
    monkeypatch.setattr(rb, "hubs_of", lambda batch: [])
    monkeypatch.setattr(sys, "argv", ["run_hub_chain_batch.py", "--batch", "gg3"])
    assert rb.main() == 0
    assert bool(seen) is scans
