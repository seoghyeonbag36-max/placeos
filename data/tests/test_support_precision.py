"""지원 공고 매칭 정밀도 — 표본 구성과 채점 규칙 잠금 (사전등록 2026-11-15).

합성 입력(실측값 아님)으로 규칙을 고정한다. 라이브 호출·실제 공고는 쓰지 않는다.
사전등록: docs/prereg-program-support-precision-2026-11-15.md
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from data.validation import support_sample as SS
from data.validation.score_support_labels import MIN_PAIRS, OK, NO, UNKNOWN, score


# ── 합성 질의 결과 ────────────────────────────────────────────────────────
def _outputs(districts=("d1", "d2", "d3", "d4"), per_query=6, with_national=True) -> dict[str, list[dict]]:
    """질의마다: 그 거점 전용 공고 + 단계 전용 공고 + (선택) 전국 공고. id 는 전역에서 유일하다."""
    out: dict[str, list[dict]] = {}
    for q in SS.frame(list(districts)):
        d, s, _ = SS.parse_qid(q)
        items = [{"id": f"loc-{d}-{s}-{k}", "source": "kstartup", "title": f"{d} {s} 공고 {k}", "org": f"{d}청",
                  "target": "대상", "region": d, "summary": "요약", "end": "2026-12-31", "deadline_text": None,
                  "url": "https://example.test/x", "matched": [f"지역: {d}", f"단계: {s}"]} for k in range(per_query)]
        if with_national:
            items += [{"id": f"nat-{k}", "source": "bizinfo", "title": f"전국 공고 {k}", "org": "중앙부처",
                       "target": "누구나", "region": "전국", "summary": "요약", "end": None, "deadline_text": "상시",
                       "url": "https://example.test/n", "matched": ["전국(중앙부처)"]} for k in range(3)]
        out[q] = items
    return out


def test_frame_is_districts_x_stages_x_industries() -> None:
    assert len(SS.frame(["a", "b", "c", "d"])) == 4 * 2 * 3


def test_draw_districts_is_deterministic_sorted_unique() -> None:
    slugs = [f"hub{n:02d}" for n in range(30)]
    a, b = SS.draw_districts(slugs), SS.draw_districts(list(reversed(slugs)))
    assert a == b and len(a) == SS.N_DISTRICTS == len(set(a)) and a == sorted(a)


def test_design_is_deterministic() -> None:
    assert SS.build_design(_outputs()) == SS.build_design(_outputs())


def test_pairs_per_stage_and_counts() -> None:
    d = SS.build_design(_outputs())
    assert d["n_pairs"] == 2 * SS.PAIRS_PER_STAGE
    assert sum(p["stage"] == "pre_founder" for p in d["pairs"]) == SS.PAIRS_PER_STAGE
    assert d["n_dropped"] == 0 and d["excluded_queries"] == []
    assert [p["pair_id"] for p in d["pairs"]][:2] == ["P001", "P002"]


def test_control_is_query_blind_and_never_in_the_querys_own_result() -> None:
    """C = 같은 질의에는 걸러졌지만, 거점도 단계도 다른 질의에는 보인 공고."""
    out = _outputs()
    d = SS.build_design(out)
    for p in d["pairs"]:
        own = {it["id"] for it in out[p["qid"]]}
        assert p["M"]["id"] in own and p["C"]["id"] not in own
        # C 는 다른 거점·다른 단계 질의의 결과에서 왔다
        sources = [q for q, items in out.items() if any(it["id"] == p["C"]["id"] for it in items)]
        assert sources and all(SS.parse_qid(q)[0] != p["district"] and SS.parse_qid(q)[1] != p["stage"] for q in sources)


def test_same_query_notice_is_not_drawn_twice() -> None:
    d = SS.build_design(_outputs(per_query=1, with_national=False), per_stage=3)
    seen = [(p["qid"], p["M"]["id"]) for p in d["pairs"]]
    assert len(seen) == len(set(seen))


def test_empty_queries_are_excluded_and_recorded() -> None:
    out = _outputs()
    empty = SS.frame(["d1"])[0]
    out[empty] = []
    d = SS.build_design(out)
    assert empty in d["excluded_queries"] and empty not in d["queries_used"]
    assert all(p["qid"] != empty for p in d["pairs"])


def test_pair_is_dropped_when_no_control_pool() -> None:
    """거점이 하나뿐이면 「거점이 다른 질의」가 없어 C 풀이 비어 있다 — 짝을 지어내지 않고 센다."""
    d = SS.build_design(_outputs(districts=("only",)))
    assert d["n_pairs"] == 0 and d["n_dropped"] > 0


# ── 표본 파일 ─────────────────────────────────────────────────────────────
def _write(tmp: Path) -> Path:
    design = SS.build_design(_outputs())
    return SS.write_sample(design, tmp / "support_sample_t", district_labels={"d1": "서울특별시 가구"},
                           frozen_at="2026-11-15T00:00:00+00:00", source_status=[{"id": "kstartup", "status": "ok"}])


def test_labels_csv_is_blind(tmp_path: Path) -> None:
    d = _write(tmp_path)
    with (d / "labels.csv").open(encoding="utf-8-sig", newline="") as fp:
        r = csv.DictReader(fp)
        head = r.fieldnames or []
        rows = list(r)
    assert "arm" not in head and "matched" not in head and "pair_id" not in head
    assert "라벨" in head and len(rows) == 2 * 2 * SS.PAIRS_PER_STAGE
    assert all(x["라벨"] == "" for x in rows)                   # 동결 직후 라벨은 비어 있다
    text = (d / "labels.csv").read_text(encoding="utf-8-sig")
    assert "지역: d1" not in text and "단계: pre_founder" not in text   # 매칭 표시가 새지 않는다
    with (d / "key.csv").open(encoding="utf-8-sig", newline="") as fp:
        key = list(csv.DictReader(fp))
    assert {k["arm"] for k in key} == {"M", "C"}


def test_rows_are_shuffled_not_arm_ordered(tmp_path: Path) -> None:
    d = _write(tmp_path)
    with (d / "key.csv").open(encoding="utf-8-sig", newline="") as fp:
        arms = [k["arm"] for k in csv.DictReader(fp)]
    assert arms != sorted(arms) and arms != ["M", "C"] * (len(arms) // 2)


def test_write_refuses_to_overwrite_labelled_sample(tmp_path: Path) -> None:
    d = _write(tmp_path)
    with pytest.raises(FileExistsError):
        SS.write_sample(SS.build_design(_outputs()), d)


# ── 채점 ──────────────────────────────────────────────────────────────────
def _label(d: Path, fn) -> None:
    """fn(arm, pair_index) → 라벨. key.csv 로 팔을 찾아 labels.csv 를 채운다."""
    with (d / "key.csv").open(encoding="utf-8-sig", newline="") as fp:
        key = {k["id"]: k for k in csv.DictReader(fp)}
    with (d / "labels.csv").open(encoding="utf-8-sig", newline="") as fp:
        rd = csv.DictReader(fp)
        head, rows = rd.fieldnames, list(rd)
    for r in rows:
        k = key[r["id"]]
        r["라벨"] = fn(k["arm"], int(k["pair_id"][1:]))
    with (d / "labels.csv").open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=head)
        w.writeheader()
        w.writerows(rows)


def test_no_labels_is_untestable(tmp_path: Path) -> None:
    res = score(_write(tmp_path), reps=50)
    assert res["verdict"] == "라벨없음" and res["gate"]["verdict"] == "검정불가"
    assert res["lift"] is None and res["ci95"] is None


def test_matcher_that_separates_is_skill(tmp_path: Path) -> None:
    d = _write(tmp_path)
    _label(d, lambda arm, i: OK if arm == "M" else NO)
    res = score(d, reps=200)
    assert res["gate"]["verdict"] == "실력" and res["gate"]["lift_pp"] == 100.0
    assert res["arms"]["M"]["precision"] == 1.0 and res["arms"]["C"]["precision"] == 0.0


def test_matcher_that_does_not_separate_is_unresolved(tmp_path: Path) -> None:
    d = _write(tmp_path)
    _label(d, lambda arm, i: OK if i % 2 else NO)               # 두 팔이 같은 짝 안에서 같은 라벨
    res = score(d, reps=200)
    assert res["gate"]["verdict"] == "구분불가" and res["lift"] == 0.0
    assert res["ci95"][0] <= 0 <= res["ci95"][1]


def test_matcher_that_is_worse_is_inferior(tmp_path: Path) -> None:
    d = _write(tmp_path)
    _label(d, lambda arm, i: NO if arm == "M" else OK)
    assert score(d, reps=200)["gate"]["verdict"] == "열위"


def test_too_few_valid_pairs_is_untestable_even_if_lift_is_large(tmp_path: Path) -> None:
    """유효한 짝 < 20 — 구간이 아무리 좋아 보여도 판정하지 않는다."""
    d = _write(tmp_path)
    _label(d, lambda arm, i: (OK if arm == "M" else NO) if i <= MIN_PAIRS - 1 else "")
    res = score(d, reps=100)
    assert res["pairs"]["both_valid"] == MIN_PAIRS - 1
    assert res["verdict"] == "표본부족" and res["gate"]["verdict"] == "검정불가"


def test_unknown_and_blank_are_excluded_and_pair_needs_both_rows(tmp_path: Path) -> None:
    d = _write(tmp_path)
    # 짝 1~10: C 가 「판단 불가」 · 짝 11~: 정상
    _label(d, lambda arm, i: (UNKNOWN if arm == "C" else OK) if i <= 10 else (OK if arm == "M" else NO))
    res = score(d, reps=100)
    assert res["pairs"]["both_valid"] == res["pairs"]["total"] - 10
    assert res["arms"]["C"]["unknown"] == 10
    assert res["answered"] == res["drawn"] - 10                  # 판단 불가만 응답에서 빠진다


def test_bootstrap_is_reproducible(tmp_path: Path) -> None:
    d = _write(tmp_path)
    _label(d, lambda arm, i: OK if (arm == "M" or i % 3 == 0) else NO)
    a, b = score(d, reps=300), score(d, reps=300)
    assert a["ci95"] == b["ci95"] and a["lift"] == b["lift"]


def test_metadata_in_design_json(tmp_path: Path) -> None:
    d = _write(tmp_path)
    meta = json.loads((d / "design.json").read_text(encoding="utf-8"))
    assert meta["frozen_at"] and meta["source_status"] == [{"id": "kstartup", "status": "ok"}]
    assert meta["n_pairs"] == len(meta["pairs"]) == 2 * SS.PAIRS_PER_STAGE
