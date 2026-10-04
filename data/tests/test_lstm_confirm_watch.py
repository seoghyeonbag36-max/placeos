"""LSTM 확정 감시(scripts/lstm_confirm_watch.py)와 그 받침 — 네트워크·작업 스케줄러 없이.

무인으로 도는 코드라 틀리면 아무도 모른다. 그래서 세 가지를 테스트로 묶는다:
'언제 돌고 언제 안 도는가'(decide · gold_check), '무엇을 돌리는가'(사전등록 그리드만),
'공표 판정을 어떻게 읽는가'(2026-10-04 실측 응답 모양).
"""
from __future__ import annotations

import json
import ssl
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import lstm_confirm_watch as w  # noqa: E402


# ── 분기 ─────────────────────────────────────────────────────────────────────

def test_next_quarter_rolls_year():
    assert w.next_quarter("20262") == "20263"
    assert w.next_quarter("20264") == "20271"


def test_rone_time_id_matches_measured_format():
    # 2026-10-04 실측: WRTTIME_IDTFR_ID=202602 → 276행 · 5자리 형식은 INFO-200
    assert w.rone_time_id("20262") == "202602"
    assert w.rone_time_id("20263") == "202603"


def test_target_quarter_is_after_served_holdout(tmp_path):
    p = tmp_path / "fc.json"
    p.write_text(json.dumps({"protocol": {"confirm_after": "20262"},
                             "holdout": {"a@20254": {"quarter": "20254"},
                                         "a@20262": {"quarter": "20262"}}}), encoding="utf-8")
    assert w.target_quarter(p) == "20263"


def test_target_quarter_falls_back_to_confirm_after_then_none(tmp_path):
    p = tmp_path / "fc.json"
    p.write_text(json.dumps({"protocol": {"confirm_after": "20262"}, "holdout": {}}), encoding="utf-8")
    assert w.target_quarter(p) == "20263"
    assert w.target_quarter(tmp_path / "missing.json") is None


def test_quarters_extend_to_last_ended_quarter():
    """QUARTERS 가 2026Q2 에 손으로 박혀 있으면 20263 이 공표돼도 수집기가 묻지 않는다."""
    from data.config.platform_districts import ended_quarters
    assert ended_quarters(date(2026, 9, 30))[-1] == "20262"
    assert ended_quarters(date(2026, 10, 1))[-1] == "20263"
    assert ended_quarters(date(2027, 1, 1))[-1] == "20264"
    assert ended_quarters(date(2026, 10, 1))[0] == "20211"


# ── 공표 판정 ────────────────────────────────────────────────────────────────

def test_parse_seoul_published_empty_and_unknown():
    ok = {"VwsmTrdarStorQq": {"list_total_count": 75912, "row": [{"STDR_YYQU_CD": "20262"}]}}
    assert w.parse_seoul(ok, "VwsmTrdarStorQq", "20262") is True
    # 분기 필터가 무시돼 다른 분기 행이 오면 '공표'로 읽지 않는다
    assert w.parse_seoul(ok, "VwsmTrdarStorQq", "20263") is False
    empty = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
    assert w.parse_seoul(empty, "VwsmTrdarStorQq", "20263") is False
    bad_key = {"RESULT": {"CODE": "INFO-100", "MESSAGE": "인증키가 유효하지 않습니다."}}
    assert w.parse_seoul(bad_key, "VwsmTrdarStorQq", "20263") is None


def test_parse_rone_published_empty_and_unknown():
    ok = {"SttsApiTblData": [{"head": [{"list_total_count": 276}, {"RESULT": {"CODE": "INFO-000"}}]},
                             {"row": [{"WRTTIME_IDTFR_ID": "202602", "WRTTIME_DESC": "2026년 2분기"}]}]}
    assert w.parse_rone(ok, "20262") is True
    assert w.parse_rone(ok, "20263") is False
    assert w.parse_rone({"RESULT": {"CODE": "INFO-200"}}, "20263") is False
    assert w.parse_rone({"RESULT": {"CODE": "ERROR-290"}}, "20263") is None


# ── 언제 도는가 ──────────────────────────────────────────────────────────────

def test_decide():
    mx = w.MAX_ATTEMPTS
    assert w.decide({}, "20263", 1234) == "busy"
    assert w.decide({}, None, None) == "no_target"
    assert w.decide({"target": "20263", "status": "done"}, "20263", None) == "done"
    # 다음 분기로 넘어갔으면 끝난 기록에 막히지 않는다(다시 켜면 20264 를 기다린다)
    assert w.decide({"target": "20263", "status": "done"}, "20264", None) == "probe"
    assert w.decide({"target": "20263", "status": "failed", "attempts": mx}, "20263", None) == "gave_up"
    assert w.decide({"target": "20263", "status": "failed", "attempts": mx - 1}, "20263", None) == "probe"
    assert w.decide({"target": "20263", "status": "waiting", "attempts": 0}, "20263", None) == "probe"


# ── 무엇을 돌리는가 ──────────────────────────────────────────────────────────

def test_pipeline_runs_preregistered_grid_and_nothing_else():
    """확정은 사전등록 그리드로만. GNN·블로그·Program CSV 를 건드리는 단계가 끼면 안 된다."""
    from ml.training.lstm_grids import GRIDS

    _, args, critical, _ = w.TRAIN_STEP
    assert critical and args[args.index("--grid") + 1] == w.GRID == "reg-0928"
    assert GRIDS[w.GRID]["prereg"].endswith("finding-lstm-regularization-prereg-2026-09-28.md")
    flat = [" ".join(a) for _, a, _, _ in w.STEPS] + [" ".join(args)]
    assert not any(x in s for s in flat for x in ("train_gnn", "naver_blog", "store_graph"))
    gold = [a for _, a, _, _ in w.STEPS if "data.pipelines.build_gold" in a]
    assert len(gold) == 1 and "--platform13-timeseries" in gold[0] and "--platform13" not in gold[0]


# ── 재학습 전 관문 ───────────────────────────────────────────────────────────

FEATS = ("vac_proxy", "vac_small")


def _frame(rows):
    return pd.DataFrame(rows, columns=["district_id", "quarter", *FEATS])


def test_gold_check_passes_when_target_added_everywhere():
    before = {"a": {"20261", "20262"}, "b": {"20261", "20262"}}
    after = _frame([("a", "20261", 1, 1), ("a", "20262", 1, 1), ("a", "20263", 1, 1),
                    ("b", "20261", 1, 1), ("b", "20262", 1, 1), ("b", "20263", 1, 1)])
    r = w.gold_check(before, after, "20263", FEATS)
    assert r["ok"] and r["hubs_with_target"] == 2 and r["finite_target_rows"] == 2
    assert r["max_quarter"] == "20263"


def test_gold_check_fails_on_lost_history():
    """부분 수집본이 최신 Bronze 가 되면 옛 분기가 사라진다 — 그 Gold 로 학습하면 안 된다."""
    after = _frame([("a", "20262", 1, 1), ("a", "20263", 1, 1)])
    r = w.gold_check({"a": {"20261", "20262"}}, after, "20263", FEATS)
    assert not r["ok"] and r["lost_pairs"] == 1


def test_gold_check_fails_when_target_missing_or_not_finite():
    hubs = [f"h{i}" for i in range(10)]
    nan = float("nan")
    rows = ([(h, "20262", 1, 1) for h in hubs]
            + [(h, "20263", 1, nan if i < 2 else 1) for i, h in enumerate(hubs)])
    r = w.gold_check({}, _frame(rows), "20263", FEATS)
    assert not r["ok"] and r["finite_target_rows"] == 8          # 80% < 90%
    rows = [(h, "20262", 1, 1) for h in hubs] + [(h, "20263", 1, 1) for h in hubs[:8]]
    r = w.gold_check({}, _frame(rows), "20263", FEATS)
    assert not r["ok"] and r["hubs_with_target"] == 8
    assert w.gold_check({}, None, "20263", FEATS)["ok"] is False


# ── 보고서가 사람에게 남기는 것 ──────────────────────────────────────────────

def test_interpret_leaves_decisions_to_people():
    base = {"target": "20263", "outcome": "done", "reason": "완료",
            "training": {"selection": {"eligible": 16, "trials": 16, "chosen": 10, "fallback": False},
                         "served": True},
            "kpi": {"confirmation": {"after": "20262", "n_fresh": 80},
                    "direction": {"gate_verdict": "구분불가"}, "error": {"gate_verdict": "실력"}}}
    summary, todo = w.interpret(base)
    assert any("방향 구분불가" in s and "80건" in s for s in summary)
    assert any("창업자 결정" in t for t in todo)
    assert any("커밋" in t for t in todo)                     # 배포는 사람이 한다
    fb = {**base, "training": {"selection": {"eligible": 0, "trials": 16, "chosen": 3, "fallback": True},
                               "served": False}}
    assert any("⑥" in t for t in w.interpret(fb)[1])
    both = {**base, "kpi": {**base["kpi"], "direction": {"gate_verdict": "실력"}}}
    assert any("닫혔다" in t for t in w.interpret(both)[1])
    assert any("로그" in t for t in w.interpret({"target": "20263", "outcome": "failed", "reason": "x"})[1])


def test_pppp_status_note_reads_watch_state(tmp_path):
    import pppp_status as ps

    assert "감시 없음" in ps._confirm_watch_note(tmp_path / "none.json")
    p = tmp_path / "st.json"
    p.write_text(json.dumps({"target": "20263", "status": "waiting",
                             "last_check": "2026-10-05T09:17:03"}), encoding="utf-8")
    assert ps._confirm_watch_note(p) == " · 감시: 20263 미공표(2026-10-05 09:17)"
    p.write_text(json.dumps({"target": "20263", "status": "done", "finished": "2026-11-02T10:00:00",
                             "report": "reports/lstm_confirm_20263_2026-11-02.json"}), encoding="utf-8")
    assert ps._confirm_watch_note(p).endswith("→ reports/lstm_confirm_20263_2026-11-02.json")


# ── 받침: 수집기 ─────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, body):
        self._b = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._b


def test_trdar_info200_is_empty_not_error(monkeypatch):
    from data.collectors import seoul_trdar as st

    empty = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
    monkeypatch.setattr(st.requests, "get", lambda url, timeout=30: _Resp(empty))
    assert st._fetch_page("k", "VwsmTrdarStorQq", 1, 1, "/20263") == ([], 0)
    bad = {"RESULT": {"CODE": "INFO-100", "MESSAGE": "인증키가 유효하지 않습니다."}}
    monkeypatch.setattr(st.requests, "get", lambda url, timeout=30: _Resp(bad))
    with pytest.raises(RuntimeError):
        st._fetch_page("k", "VwsmTrdarStorQq", 1, 1, "/20263")


def test_trdar_stor_skips_unpublished_quarter(monkeypatch):
    """공표 전 분기면 상권코드마다 묻지 않는다 — 352콜이 1콜이 된다."""
    from data.collectors import seoul_trdar as st

    calls: list[tuple[str, str]] = []

    def fake(key, service, start, end, extra=""):
        calls.append((service, extra))
        return [], 0

    saved: dict[str, list] = {}
    monkeypatch.setenv("SEOUL_OPENAPI_KEY", "k")
    monkeypatch.setattr(st, "_fetch_page", fake)
    monkeypatch.setattr(st, "save_json", lambda obj, d, name, date=None: saved.setdefault(name, obj))
    monkeypatch.setattr(st, "QUARTERS", ("20263",))
    monkeypatch.setattr(st, "ALL_TRDAR_CODES", ("c1", "c2"))
    st.collect_platform13()
    assert ("VwsmTrdarStorQq", "/20263") in calls
    assert not [e for s, e in calls if s == "VwsmTrdarStorQq" and e.startswith("/20263/")]
    assert saved["seoul_trdar_stor.json"] == []


def test_rone_uses_certifi_trust_store_not_disabled_verification(monkeypatch):
    from data.collectors import rone_rent as rr

    seen = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"SttsApiTblData": [{"head": [{"list_total_count": 0}]},
                                                  {"row": []}]}).encode()

    def fake_urlopen(url, timeout=30, context=None):
        seen["ctx"] = context
        return Resp()

    monkeypatch.setattr(rr.urllib.request, "urlopen", fake_urlopen)
    rr._fetch_all("k", "T1")
    assert isinstance(seen["ctx"], ssl.SSLContext)
    assert seen["ctx"].verify_mode == ssl.CERT_REQUIRED and seen["ctx"].check_hostname
