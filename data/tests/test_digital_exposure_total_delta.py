import math
import random

from data.pipelines import digital_exposure_total_delta as td


def _panel(n_snapshots, hubs=40, shrink=0.0, seed=1, precision=0.9):
    """주 1회 스냅샷. 거점 h 의 일일 유입 flow_h 에 total 이 선형으로 쌓이고, 그 flow 가 거점의 진짜 노출 강도다."""
    rng = random.Random(seed)
    flow = {f"h{i}": math.exp(rng.uniform(0, 4)) for i in range(hubs)}
    rows = []
    for k in range(n_snapshots):
        day = f"2026-11-{17 + 7 * k:02d}" if k < 2 else f"2026-12-{(17 + 7 * k) - 30:02d}"
        for s, f in flow.items():
            for suffix in ("맛집", "카페"):
                noise = 1 + rng.uniform(-0.05, 0.05)
                total = 100000 + f * 7 * k * noise
                if shrink and rng.random() < shrink:
                    total -= 12 * f  # 색인 변동 — 주간 증가분(7f)보다 크게 줄어 그 구간의 Δtotal 이 음수가 된다
                rows.append({"collected_at": day, "slug": s, "suffix": suffix, "total": total,
                             "rate_per_day": f * (1 + rng.uniform(-0.6, 0.6)), "precision": precision, "error": ""})
    return rows, {s: f * (1 + rng.uniform(-0.3, 0.3)) for s, f in flow.items()}


def test_ranks_average_ties_and_spearman_handles_constants():
    assert td.ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]
    assert td.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert td.spearman([1, 2, 3], [5, 5, 5]) is None
    assert td.spearman([1, 2], [1, 2]) is None


def test_fewer_than_four_snapshots_is_insufficient_not_a_verdict():
    rows, level = _panel(3)
    out = td.analyze(rows, level)
    assert out["verdict"] == "표본부족" and out["n_snapshots"] == 3
    assert out["G1_negative"]["share_negative"] == 0.0  # 그래도 단조성은 보여 준다


def test_clean_accumulating_totals_pass_both_gates_and_reach_a_real_verdict():
    rows, level = _panel(5)
    out = td.analyze(rows, level)
    assert out["G1_negative"]["share_negative"] == 0.0
    assert out["G2_rank_persistence"]["median"] >= 0.9
    assert out["verdict"] in {"개선", "구분불가"}  # 게이트는 통과 — 열위·표본부족이 아니다
    assert out["primary_precision_filtered"]["hubs"] == 40


def test_totals_that_shrink_fail_gate_one_and_are_inferior():
    rows, level = _panel(5, shrink=0.4)
    out = td.analyze(rows, level)
    assert out["G1_negative"]["share_negative"] >= td.G1_MAX_NEGATIVE_SHARE
    assert out["verdict"] == "열위" and "게이트 실패" in out["reason"]


def test_low_precision_hubs_leave_the_primary_set_too_small():
    rows, level = _panel(5, precision=0.3)
    out = td.analyze(rows, level)
    assert out["primary_precision_filtered"]["hubs"] == 0
    assert out["verdict"] == "표본부족"
    assert out["secondary_all_hubs"]["hubs"] == 40  # 참고용 전 거점 결과는 그대로 싣는다


def test_error_rows_are_dropped_before_computing_intervals():
    rows, _ = _panel(4)
    rows[0]["error"] = "Timeout"
    assert len(td.clean_rows(rows)) == len(rows) - 1
