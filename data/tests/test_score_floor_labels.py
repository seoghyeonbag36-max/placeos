"""층 단위 라벨 채점기 — 손으로 계산되는 합성 표본(실측값 아님)으로 가중 추정 규칙을 고정한다."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from data.validation.score_floor_labels import score

_KEY = ["id", "slug", "pnu", "floor", "band", "stratum", "cls", "certainty", "weight", "N_h", "n_h"]
_LAB = ["id", "label_actual", "label_use", "label_date", "label_method", "memo"]


def _sample(tmp: Path, rows: list[tuple[str, str, str, str]], strata_N: dict[str, int]) -> Path:
    """rows = (id, stratum, pnu, label_actual)."""
    d = tmp / "floor_sample_t"
    d.mkdir()
    with (d / "key.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=_KEY)
        w.writeheader()
        for rid, h, pnu, _ in rows:
            cls, band = h.split("|")
            w.writerow({"id": rid, "slug": "x", "pnu": pnu, "floor": 2, "band": band, "stratum": h,
                        "cls": cls, "certainty": "", "weight": "", "N_h": strata_N[h], "n_h": ""})
    with (d / "labels.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=_LAB)
        w.writeheader()
        for rid, _h, _p, lab in rows:
            w.writerow({"id": rid, "label_actual": lab, "label_method": "현장"})
    (d / "design.json").write_text(json.dumps({"strata": {h: {"N": n} for h, n in strata_N.items()}}),
                                   encoding="utf-8")
    return d


def test_weighted_estimates_match_hand_calculation(tmp_path: Path) -> None:
    v, o = "vacant_confirmed|2F+", "occupied|2F+"
    rows = [("a1", v, "p1", "공실"), ("a2", v, "p2", "공실"), ("a3", v, "p3", "공실"),
            ("a4", v, "p4", "영업"),
            ("b1", o, "q1", "영업"), ("b2", o, "q2", "영업"), ("b3", o, "q3", "영업"),
            ("b4", o, "q4", "부분공실")]
    res = score(_sample(tmp_path, rows, {v: 100, o: 900}), reps=200)
    e = res["estimates"]
    assert e["precision_strict"] == 0.75
    assert e["floor_vacancy_strict"] == 0.075            # (100·0.75 + 900·0) / 1000
    assert e["floor_vacancy_broad"] == 0.3               # (100·0.75 + 900·0.25) / 1000
    assert e["recall_strict"] == 1.0 and e["recall_broad"] == 0.25
    lo, hi = res["ci95_cluster_bootstrap"]["floor_vacancy_broad"]
    assert lo <= e["floor_vacancy_broad"] <= hi
    assert res["verdict"] == "표본부족"                   # 계층당 응답 10 미만
    # 사전등록(2026-10-19) 판정 재료 — 2층↑ 띠 하나뿐이라 띠 기준 = 틀 전체 기준
    assert e["baseline_strict"] == 0.075 and e["baseline_broad"] == 0.3
    assert e["precision_lift_strict"] == 0.675           # 0.75 − 0.075
    assert e["precision_lift_broad"] == 0.45             # 0.75 − 0.3
    assert e["recall_lift_strict"] == 0.9                # 1.0 − 목록 비율 100/1000
    assert e["recall_lift_broad"] == 0.15                # 0.25 − 0.1
    assert res["gate"]["verdict"] == "검정불가"           # 표본부족이면 판정하지 않는다


def test_unknown_is_dropped_and_reweighted(tmp_path: Path) -> None:
    v = "vacant_confirmed|2F+"
    rows = [("a1", v, "p1", "공실"), ("a2", v, "p2", "불명"), ("a3", v, "p3", "")]
    res = score(_sample(tmp_path, rows, {v: 50}), reps=50)
    assert res["answered"] == 1 and res["unknown"] == 1 and res["blank"] == 1
    assert res["estimates"]["precision_strict"] == 1.0   # 응답 1건이 계층 50층을 대표한다


def _rows(prefix: str, h: str, labels: list[str]) -> list[tuple[str, str, str, str]]:
    """계층 h 에 라벨 목록대로 행을 만든다 — 지번(pnu)은 행마다 다르다."""
    return [(f"{prefix}{i}", h, f"{prefix}p{i}", lab) for i, lab in enumerate(labels)]


_V, _O2, _O1 = "vacant_confirmed|2F+", "occupied|2F+", "occupied|1F"
_N = {_V: 100, _O2: 900, _O1: 1000}


def test_baseline_is_the_stronger_uninformative_rule(tmp_path: Path) -> None:
    """2층↑ 띠의 층 공실률(0.18)이 틀 전체(0.09)보다 높으면 그쪽이 기준이다.

    약한 쪽(틀 전체)에 대면 「2층↑ 층을 아무거나 내미는」 규칙도 못 이기는 목록이 실력으로 읽힌다.
    """
    rows = (_rows("v", _V, ["공실"] * 9 + ["영업"]) + _rows("o", _O2, ["공실"] + ["영업"] * 9)
            + _rows("g", _O1, ["영업"] * 10))
    res = score(_sample(tmp_path, rows, _N), reps=300)
    e = res["estimates"]
    assert e["floor_vacancy_strict"] == 0.09             # (100·0.9 + 900·0.1 + 1000·0) / 2000
    assert e["baseline_strict"] == 0.18                  # 2층↑ 띠 (90 + 90) / 1000
    assert e["precision_lift_strict"] == 0.72            # 0.9 − 0.18
    assert res["verdict"] == "추정가능"
    assert res["gate"]["verdict"] == "실력"
    assert res["gate"]["lift_pp"] == 72.0 and res["gate"]["ci95_pp"][0] > 0


def test_precision_equal_to_baseline_is_unresolved(tmp_path: Path) -> None:
    """화면 빈 층이 아무 2층↑ 층과 같은 비율로만 비어 있으면 실력이 아니다(구간이 0 을 품는다)."""
    rows = (_rows("v", _V, ["공실"] * 2 + ["영업"] * 8) + _rows("o", _O2, ["공실"] * 2 + ["영업"] * 8)
            + _rows("g", _O1, ["영업"] * 10))
    res = score(_sample(tmp_path, rows, _N), reps=300)
    assert res["estimates"]["precision_lift_strict"] == 0.0
    assert res["gate"]["verdict"] == "구분불가"


def test_no_labels_is_untestable(tmp_path: Path) -> None:
    """라벨이 없으면 판정 자체가 없다 — 0 이나 실패로 채우지 않는다."""
    res = score(_sample(tmp_path, _rows("v", _V, [""] * 3), {_V: 50}), reps=20)
    assert res["verdict"] == "라벨없음"
    assert res["gate"]["verdict"] == "검정불가"


def test_preregistered_sample_is_in_the_repo() -> None:
    """사전등록이 가리키는 표본(458층 · 8계층)이 저장소에 있어야 한다 — 지우면 판정 대상이 사라진다."""
    from data.validation.score_floor_labels import _OUT, KPI_SAMPLE_TAG

    d = _OUT / f"floor_sample_{KPI_SAMPLE_TAG}"
    design = json.loads((d / "design.json").read_text(encoding="utf-8"))
    assert len(design["strata"]) == 8
    with (d / "key.csv").open(encoding="utf-8-sig", newline="") as fp:
        assert sum(1 for _ in csv.DictReader(fp)) == 458


def test_stratum_without_answers_is_reported_not_zero_filled(tmp_path: Path) -> None:
    v, u = "vacant_confirmed|2F+", "unlisted|1F"
    rows = [("a1", v, "p1", "공실"), ("c1", u, "r1", "")]
    res = score(_sample(tmp_path, rows, {v: 10, u: 990}), reps=50)
    assert res["missing_strata"] == [u]
    # 응답 없는 계층을 0 으로 채웠다면 층 공실률이 10/1000 = 0.01 로 나왔을 것이다
    assert res["estimates"]["floor_vacancy_strict"] == 1.0
    assert res["verdict"] == "표본부족"
