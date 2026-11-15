"""Platform 개업 뒤 24개월 생존 — 정제 규칙·칸·채점 규칙 잠금 (사전등록 2026-11-15).

합성 입력(실측값 아님)으로 규칙을 고정한다. 사전등록: docs/prereg-platform-rank-survival-2026-11-15.md
이 테스트는 **결과를 본 뒤 규칙을 고치지 못하게** 하는 장치이기도 하다 — 규칙 상수가 바뀌면 사전등록 문서와 같이 바뀌어야 통과한다.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from data.pipelines import build_platform_survival as P
from data.validation import score_rank_survival as S

ROOT = Path(__file__).resolve().parents[2]
D = lambda y, m, d: date(y, m, d).toordinal()   # noqa: E731


def _rec(pnu="p1", name="가게", s=(2020, 1, 1), e=None, it="한식"):
    return {"pnu": pnu, "name": name, "start": D(*s), "end": None if e is None else D(*e), "it": it}


# ── 정제: 한 업소로 묶기 ─────────────────────────────────────────────────
def test_norm_name_strips_spaces_and_company_marks() -> None:
    assert P.norm_name("(주) 맛 있는집") == "맛있는집" and P.norm_name("㈜맛있는집") == "맛있는집"
    assert P.norm_name(None) == "" and P.norm_name("  ") == ""


def test_succession_within_gap_is_one_spell_and_beyond_is_two() -> None:
    a = _rec(s=(2020, 1, 1), e=(2020, 6, 1))
    near = _rec(s=(2020, 8, 30), e=(2021, 5, 1))      # 간격 90일 — 묶는다
    far = _rec(s=(2020, 8, 31), e=(2021, 5, 1))       # 간격 91일 — 안 묶는다
    sp, bad = P.merge_spells([a, near])
    assert bad == 0 and len(sp) == 1 and sp[0]["start"] == D(2020, 1, 1) and sp[0]["end"] == D(2021, 5, 1)
    assert len(P.merge_spells([a, far])[0]) == 2


def test_overlap_merges_and_end_is_the_latest_not_the_last() -> None:
    """앞 기록 안에 든 짧은 기록이 끝을 앞당기지 않는다(사전등록 §2-2 정정)."""
    outer = _rec(s=(2018, 1, 1), e=(2020, 12, 31))
    inner = _rec(s=(2019, 5, 1), e=(2019, 12, 31))
    sp, _ = P.merge_spells([outer, inner])
    assert len(sp) == 1 and sp[0]["end"] == D(2020, 12, 31)


def test_open_record_is_not_merged_with_a_later_one() -> None:
    open_ = _rec(s=(2018, 1, 1), e=None)
    later = _rec(s=(2019, 1, 1), e=(2019, 6, 1))
    sp, _ = P.merge_spells([open_, later])
    assert len(sp) == 2 and sorted(s["end"] is None for s in sp) == [False, True]


def test_later_open_record_keeps_the_spell_open() -> None:
    sp, _ = P.merge_spells([_rec(s=(2020, 1, 1), e=(2020, 3, 1)), _rec(s=(2020, 4, 1), e=None)])
    assert len(sp) == 1 and sp[0]["end"] is None


def test_different_parcel_or_name_is_never_merged_and_empty_name_stands_alone() -> None:
    sp, _ = P.merge_spells([_rec(pnu="p1", e=(2020, 3, 1)), _rec(pnu="p2", s=(2020, 3, 2))])
    assert len(sp) == 2
    sp, _ = P.merge_spells([_rec(name="가게", e=(2020, 3, 1)), _rec(name="다른가게", s=(2020, 3, 2))])
    assert len(sp) == 2
    sp, _ = P.merge_spells([_rec(name="", e=(2020, 3, 1)), _rec(name="", s=(2020, 3, 2))])
    assert len(sp) == 2


def test_invalid_end_before_start_is_dropped_and_counted() -> None:
    sp, bad = P.merge_spells([_rec(s=(2020, 5, 1), e=(2020, 4, 1)), _rec(name="ok")])
    assert bad == 1 and len(sp) == 1


# ── 코호트 · 생존 · 칸 ───────────────────────────────────────────────────
def test_cohort_window_is_half_open() -> None:
    assert P.in_cohort(D(2016, 1, 1)) and not P.in_cohort(D(2015, 12, 31))
    assert P.in_cohort(D(2024, 6, 30)) and not P.in_cohort(D(2024, 7, 1))


def test_survival_horizon_is_730_days() -> None:
    s = D(2020, 1, 1)
    assert P.survived(s, None) is True                       # 영업 중은 생존
    assert P.survived(s, s + 730) is False                   # 730일째 폐업 = 24개월 안에 폐업
    assert P.survived(s, s + 731) is True


def test_wilson_interval_sanity() -> None:
    lo, hi = P.wilson(50, 100)
    assert abs(lo - 0.404) < 0.002 and abs(hi - 0.596) < 0.002
    assert P.wilson(0, 0) == (0.0, 0.0)


def test_cell_below_min_n_has_no_rate() -> None:
    thin = P.cell_of(10, P.MIN_N - 1)
    assert thin["eligible"] is False and thin["rate"] is None and thin["ci95"] is None and thin["n"] == P.MIN_N - 1
    ok = P.cell_of(15, P.MIN_N)
    assert ok["eligible"] is True and ok["rate"] == 0.5 and len(ok["ci95"]) == 2


def _row(pnu, name, start, end, it):
    return {"pnu": pnu, "record": {"start_date": start, "end_date": end, "industry_type": it, "business_name": name}}


def test_hub_cells_counts_cohort_mapping_and_continuations() -> None:
    rows = []
    for i in range(40):                                       # 한식 코호트 40: 10 은 1년 안에 폐업
        rows.append(_row(f"p{i}", f"식당{i}", "20200101", "20201201" if i < 10 else None, "한식"))
    rows.append(_row("px", "기타가게", "20200101", None, "기타"))        # 미매핑
    rows.append(_row("py", "옛가게", "20140101", "20170101", "한식"))   # 2014 에 열고
    rows.append(_row("py", "옛가게", "20170110", None, "한식"))         # 이어짐 — 개업이 2014 라 코호트 밖
    rows.append(_row("pz", "너무최근", "20250101", None, "한식"))       # 2024-07 이후 개업 — 코호트 밖
    rows.append(_row("pw", "날짜없음", "", None, "한식"))               # 개업일 없음
    cells, cov = P.hub_cells(rows)
    r = cells["restaurant"]
    assert (r["n"], r["survived"], r["eligible"], r["rate"]) == (40, 30, True, 0.75)
    assert cells["cafe"]["n"] == 0 and cells["cafe"]["eligible"] is False
    assert cov["cohort_unmapped"] == 1 and cov["bad_date"] == 1
    assert cov["cohort_spells"] == 41                         # 한식 40 + 기타 1 (옛가게·너무최근은 코호트 밖)


# ── 사전등록 문서와 코드의 동기화 ───────────────────────────────────────
def test_mapping_matches_the_preregistration_table() -> None:
    doc = (ROOT / "docs" / "prereg-platform-rank-survival-2026-11-15.md").read_text(encoding="utf-8")
    for key, terms in P.MAPPING.items():
        line = next(l for l in doc.splitlines() if l.startswith(f"| `{key}`"))
        items = tuple(t.strip() for t in line.split("|")[2].split("·"))
        assert items == terms, f"{key}: 문서 {items} ≠ 코드 {terms}"


def test_rule_constants_match_the_preregistration_text() -> None:
    doc = (ROOT / "docs" / "prereg-platform-rank-survival-2026-11-15.md").read_text(encoding="utf-8")
    assert f"G = {P.GAP_DAYS}일" in doc and f"**{P.HORIZON_DAYS}일 안에" in doc
    assert "2016-01-01" in doc and "2024-07-01" in doc and f"n ≥ {P.MIN_N}" in doc
    assert (P.COHORT_START, P.COHORT_END) == (D(2016, 1, 1), D(2024, 7, 1))
    assert f"seed {S.SEED}" in doc and f"{S.MIN_HUBS} 미만" in doc


def test_build_end_to_end_with_missing_hub(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(P, "seoul_hubs", lambda: ["h1", "h2"])
    d = tmp_path / "building_history" / "h1"
    d.mkdir(parents=True)
    rows = [_row(f"p{i}", f"식당{i}", "20200101", None, "한식") for i in range(35)]
    (d / "licensing_lots.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    out = tmp_path / "out.json"
    doc = P.build(silver_root=tmp_path, out=out)
    assert doc["diagnostics"]["hubs_missing_silver"] == ["h2"] and list(doc["hubs"]) == ["h1"]
    assert doc["hubs"]["h1"]["industries"]["restaurant"]["rate"] == 1.0
    assert set(doc["sensitivity"]) == {"gap30", "gap180"} and doc["rules"]["gap_days"] == 90
    assert json.loads(out.read_text(encoding="utf-8"))["schema"] == "platform-survival/1"


# ── 채점 ──────────────────────────────────────────────────────────────────
def test_ranks_average_ties_and_spearman_edges() -> None:
    assert S._ranks([10, 20, 20, 30]) == [1, 2.5, 2.5, 4]
    xs = list(range(10))
    assert S.spearman(xs, [x * 2 for x in xs]) == 1.0
    assert abs(S.spearman(xs, [-x for x in xs]) + 1.0) < 1e-12
    assert S.spearman(xs, [1] * 10) is None and S.spearman([1, 2], [1, 2]) is None


def _survival(rates: dict[str, float], n=50, key="restaurant", eligible=None) -> dict:
    hubs = {}
    for h, r in rates.items():
        ok = (n >= P.MIN_N) if eligible is None else eligible.get(h, True)
        hubs[h] = {"industries": {key: {"n": n, "survived": round(r * n), "eligible": ok, "rate": r if ok else None, "ci95": None}}}
    return {"hubs": hubs, "rules": {"mapping": {key: []}, "gap_days": 90, "min_n": 30, "cohort": ["a", "b"], "horizon_days": 730}}


def _snapshot(fit: dict[str, float], share: dict[str, float], key="restaurant") -> dict:
    return {"frozen_on": "2026-11-15", "industries": {key: {"label": "음식점", "districts": [
        {"district_id": h, "fit": fit.get(h), "same_share": share.get(h)} for h in sorted(set(fit) | set(share))]}}}


def _hubs(n=30):
    return [f"h{i:02d}" for i in range(n)]


def test_fit_that_tracks_survival_while_share_does_not_is_skill() -> None:
    hubs = _hubs()
    rate = {h: 0.3 + 0.01 * i for i, h in enumerate(hubs)}
    fit = {h: i for i, h in enumerate(hubs)}                  # 생존과 같은 순서 → ρ = 1
    share = {h: (i * 7) % 30 for i, h in enumerate(hubs)}     # 순열 — 생존과 거의 무관
    res = S.score(_survival(rate), _snapshot(fit, share), reps=200)
    g = res["gate"]
    assert g["verdict"] == "실력" and g["ci95"][0] > 0 and res["kind"].startswith("참고")
    assert res["industries"]["restaurant"]["rho_fit"] == 1.0


def test_identical_scores_cannot_be_separated() -> None:
    hubs = _hubs()
    rate = {h: 0.3 + 0.01 * ((i * 5) % 30) for i, h in enumerate(hubs)}
    score_ = {h: i for i, h in enumerate(hubs)}
    res = S.score(_survival(rate), _snapshot(score_, dict(score_)), reps=100)
    assert res["industries"]["restaurant"]["delta"] == 0 and res["gate"]["verdict"] == "구분불가"


def test_fit_that_runs_against_survival_is_inferior() -> None:
    hubs = _hubs()
    rate = {h: 0.3 + 0.01 * i for i, h in enumerate(hubs)}
    fit = {h: -i for i, h in enumerate(hubs)}
    share = {h: i for i, h in enumerate(hubs)}
    assert S.score(_survival(rate), _snapshot(fit, share), reps=100)["gate"]["verdict"] == "열위"


def test_fewer_than_min_hubs_is_untestable() -> None:
    hubs = _hubs(S.MIN_HUBS - 1)
    rate = {h: 0.3 + 0.01 * i for i, h in enumerate(hubs)}
    fit = {h: i for i, h in enumerate(hubs)}
    g = S.score(_survival(rate), _snapshot(fit, {h: (i * 3) % 19 for i, h in enumerate(hubs)}), reps=50)["gate"]
    assert g["verdict"] == "검정불가" and str(S.MIN_HUBS) in g["reason"]


def test_ineligible_and_unranked_hubs_are_excluded_and_counted() -> None:
    hubs = _hubs()
    rate = {h: 0.3 + 0.01 * i for i, h in enumerate(hubs)}
    fit = {h: i for i, h in enumerate(hubs) if i != 0}                        # h00 은 fit 없음
    share = {h: (i * 7) % 30 for i, h in enumerate(hubs) if i != 1}           # h01 은 same_share 없음
    surv = _survival(rate, eligible={"h02": False})                           # h02 는 n 부족
    res = S.score(surv, _snapshot(fit, share), reps=50)["industries"]["restaurant"]
    assert res["n_hubs"] == 27
    assert res["excluded"] == {"hub_not_in_snapshot": 0, "no_fit": 1, "no_same_share": 1, "not_eligible": 1}


def test_sensitivity_recomputes_from_counts_and_keeps_the_min_n_rule() -> None:
    hubs = _hubs()
    rate = {h: 0.3 + 0.01 * i for i, h in enumerate(hubs)}
    surv = _survival(rate)
    # G=30 칸: (n, 생존 수)만 있다 — h00 은 n 이 모자라 eligible 이 아니다
    surv["sensitivity"] = {"gap30": {h: {"restaurant": {"n": 10 if i == 0 else 50, "survived": 5 if i == 0 else round(rate[h] * 50)}}
                                     for i, h in enumerate(hubs)}}
    fit = {h: i for i, h in enumerate(hubs)}
    share = {h: (i * 7) % 30 for i, h in enumerate(hubs)}
    res = S.score(surv, _snapshot(fit, share), reps=100)
    s = res["sensitivity"]["gap30"]["restaurant"]
    assert s["n_hubs"] == 29 and s["delta"] is not None and s["ci95"] is not None   # 주 업종만 구간
    assert res["gate"]["verdict"] == "실력"                                          # 민감도는 판정에 영향이 없다


def test_top_k_gap_observation() -> None:
    rows = [{"fit": i, "share": -i, "rate": 0.5 + 0.01 * i, "n": 50} for i in range(15)]
    assert S.top_k_gap(rows, "fit") > 0 > S.top_k_gap(rows, "share")
    assert S.top_k_gap(rows[:S.TOP_K], "fit") is None          # 나머지가 비면 None
