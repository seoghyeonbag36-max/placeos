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


def test_unknown_is_dropped_and_reweighted(tmp_path: Path) -> None:
    v = "vacant_confirmed|2F+"
    rows = [("a1", v, "p1", "공실"), ("a2", v, "p2", "불명"), ("a3", v, "p3", "")]
    res = score(_sample(tmp_path, rows, {v: 50}), reps=50)
    assert res["answered"] == 1 and res["unknown"] == 1 and res["blank"] == 1
    assert res["estimates"]["precision_strict"] == 1.0   # 응답 1건이 계층 50층을 대표한다


def test_stratum_without_answers_is_reported_not_zero_filled(tmp_path: Path) -> None:
    v, u = "vacant_confirmed|2F+", "unlisted|1F"
    rows = [("a1", v, "p1", "공실"), ("c1", u, "r1", "")]
    res = score(_sample(tmp_path, rows, {v: 10, u: 990}), reps=50)
    assert res["missing_strata"] == [u]
    # 응답 없는 계층을 0 으로 채웠다면 층 공실률이 10/1000 = 0.01 로 나왔을 것이다
    assert res["estimates"]["floor_vacancy_strict"] == 1.0
    assert res["verdict"] == "표본부족"
