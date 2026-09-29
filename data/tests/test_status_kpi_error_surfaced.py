"""진행률 계측기가 kpi_baseline 예외를 삼키지 않는지 — 판정 실패가 조용히 진행률을 바꾸지 않게.

2026-09-28 밤 같은 명령이 연달아 Platform 40.0 · 50.0 을 냈다가 이후 네 번은 66.7 이었다.
`scripts/pppp_status.py::_kpi_baseline()` 이 `except Exception: return None` 으로 예외를
삼켜, 실패하면 GNN 게이트가 "판정 없음"으로 0 이 되고 LSTM 두 게이트는 사라졌다.
여기서는 가짜 예외를 넣어 ① 예외 종류·첫 줄이 남는지 ② stderr 에 한 줄 찍히는지
③ 진행률 옆에 "판정 실패로 떨어진 값" 이 붙는지 ④ 정상일 때는 아무 표시도 없는지 본다.
판정 규칙(`실력`만 닫힌다)은 바꾸지 않았다.
"""

import importlib
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _fresh_module():
    sys.modules.pop("pppp_status", None)
    return importlib.import_module("pppp_status")


def _broken_kpi_baseline(monkeypatch) -> None:
    def check():
        raise KeyError("model_ci95\n두 번째 줄은 보고에 싣지 않는다")

    monkeypatch.setitem(sys.modules, "kpi_baseline", types.SimpleNamespace(check=check))


def test_exception_kind_and_first_line_are_recorded(monkeypatch, capsys) -> None:
    m = _fresh_module()
    _broken_kpi_baseline(monkeypatch)
    assert m._kpi_baseline() is None, "실패 시 None 으로 물러나는 계약은 유지된다"
    assert m._KPI_ERROR.startswith("KeyError: "), m._KPI_ERROR
    assert "model_ci95" in m._KPI_ERROR
    assert "두 번째 줄" not in m._KPI_ERROR, "첫 줄만 싣는다"
    err = capsys.readouterr().err
    assert "kpi_baseline 판정 실패" in err and "KeyError" in err
    assert len([ln for ln in err.splitlines() if "판정 실패" in ln]) == 1, "stderr 에 한 줄"


def test_platform_track_is_marked_as_fallen_by_failure(monkeypatch) -> None:
    m = _fresh_module()
    _broken_kpi_baseline(monkeypatch)
    t = m.platform_track()
    assert t.judgement_error.startswith("kpi_baseline KeyError"), t.judgement_error
    fails = [g for g in t.gates if "판정 실패" in g.detail]
    assert fails, "판정 실패가 어느 게이트에도 드러나지 않았다"
    assert all(g.value == 0.0 for g in fails), "판정 규칙 그대로 — 판정 못 낸 게이트는 닫히지 않는다"


def test_text_output_labels_the_value(monkeypatch, capsys) -> None:
    m = _fresh_module()
    _broken_kpi_baseline(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["pppp_status.py"])
    m.main()
    out = capsys.readouterr().out
    platform_line = next(ln for ln in out.splitlines() if ln.startswith("Platform"))
    after = out.split(platform_line, 1)[1].splitlines()[1]
    assert "판정 실패로 떨어진 값" in after and "KeyError" in after
    rank = next(ln for ln in out.splitlines() if ln.startswith("진행률 순위"))
    assert "Platform" in rank and "판정 실패로 떨어진 값" in rank


def test_json_output_carries_the_error(monkeypatch, capsys) -> None:
    m = _fresh_module()
    _broken_kpi_baseline(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["pppp_status.py", "--json"])
    m.main()
    data = json.loads(capsys.readouterr().out)
    plat = next(t for t in data["tracks"] if t["name"] == "Platform")
    assert plat["judgement_error"].startswith("kpi_baseline KeyError")
    others = [t for t in data["tracks"] if t["name"] != "Platform"]
    assert all(t["judgement_error"] is None for t in others)


def test_no_label_when_kpi_baseline_succeeds(monkeypatch, capsys) -> None:
    m = _fresh_module()
    monkeypatch.setitem(sys.modules, "kpi_baseline",
                        types.SimpleNamespace(check=lambda: {"lstm": {"available": False},
                                                             "gnn": {"available": False}}))
    t = m.platform_track()
    assert m._KPI_ERROR == "" and t.judgement_error == ""
    assert "판정 실패" not in capsys.readouterr().err


# ── 09-28 밤 40.0 · 50.0 의 실제 경로 — 있는 Gold JSON 을 못 읽은 경우 ──────────────
# 옛 코드로 재현하면 kpi_baseline 예외는 Platform 75.0 을 내고(LSTM 두 게이트가 사라짐),
# 40.0 은 recommend.json · 50.0 은 forecast.json 을 못 읽은 경우와 값이 맞는다.

def test_existing_but_unreadable_artifact_is_recorded(monkeypatch, tmp_path, capsys) -> None:
    m = _fresh_module()
    bad = tmp_path / "platform_industry_recommend.json"
    bad.write_text('{"metrics": ', encoding="utf-8")   # 쓰다 만 파일
    assert m._load(bad) is None
    assert m._LOAD_ERRORS[bad.name].startswith("JSONDecodeError"), m._LOAD_ERRORS
    assert "산출물 읽기 실패" in capsys.readouterr().err
    assert m._load(tmp_path / "없는파일.json") is None
    assert "없는파일.json" not in m._LOAD_ERRORS, "없는 파일은 게이트가 '없음'으로 적는다 — 실패가 아니다"


def test_platform_marked_when_gold_json_read_fails(monkeypatch, capsys) -> None:
    m = _fresh_module()
    orig = m._load

    def flaky(p):
        if p.name == "platform_industry_recommend.json":
            m._LOAD_ERRORS[p.name] = "OSError: 가짜 읽기 실패"
            return None
        return orig(p)

    monkeypatch.setattr(m, "_load", flaky)
    monkeypatch.setattr(sys, "argv", ["pppp_status.py"])
    m.main()
    out = capsys.readouterr().out
    assert "판정 실패로 떨어진 값" in out and "platform_industry_recommend.json 읽기 실패" in out


def test_kpi_baseline_reports_unreadable_not_missing(tmp_path) -> None:
    sys.modules.pop("kpi_baseline", None)
    import kpi_baseline

    fc = tmp_path / "platform_vacancy_forecast.json"
    fc.write_text("{", encoding="utf-8")
    res = kpi_baseline.check(forecast_path=fc, recommend_path=tmp_path / "없음.json")
    assert "읽기 실패" in res["lstm"]["reason"], res["lstm"]["reason"]
    assert res["gnn"]["reason"].endswith("없음")
    assert res["ok"] is False, "있는 파일을 못 읽었는데 종료코드 0 으로 넘어가면 fail-open 이다"
