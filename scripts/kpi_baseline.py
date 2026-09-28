"""KPI 실력 검정 — 모델이 **무정보 베이스라인**을 실제로 이기는지 잰다.

## 왜 필요한가 (2026-09-15 실측으로 드러난 구멍)

KPI① 이 "AI 정확도 70%+" 한 줄이라 **임계값만 넘으면 달성**으로 찍혀 왔다. 그런데
임계값 자체가 모델을 보증하지 못한다 — 같은 홀드아웃에서 입력을 **하나도 안 보는**
규칙이 그 임계값을 이미 넘는다:

| KPI | 모델 | 무정보 베이스라인 | 판정 |
|---|---|---|---|
| LSTM 방향정확도 ≥70% | 70.8% (46/65) | **항상 하락 78.5% (51/65)** | 베이스라인이 **7.7%p 더 높다** |
| GNN 업종추천 Top-3 ≥70% | 91.7% | **거점 사전분포 89.4%** | 베이스라인이 임계값을 19.4%p 초과 |

즉 두 게이트 모두 **0 짜리 모델도 통과**한다. 임계값을 넘었다는 사실에는 정보가 없고,
정보는 **베이스라인과의 차이**에만 있다. 이 모듈은 그 차이를 잰다.

## 무엇을 재나 — 세 겹

1. **실력(skill)** — 모델 − 베이스라인. 0 이하면 모델이 기여한 것이 없다.
2. **불확실성** — Wilson 95% 신뢰구간. 점추정으로 달성/미달을 가르면 표본 65개에서
   ±11%p 를 무시하게 된다(70.8% 의 구간은 [58.8%, 80.4%] 라 목표 70% 를 품는다).
3. **쌍대 검정** — 같은 홀드아웃 위의 비교라 독립표본 검정이 아니라 McNemar 정확검정을
   쓴다. "유의하지 않다"는 "차이가 없다"가 아니라 "이 표본으로는 못 가른다"는 뜻이다.
4. **세 갈래 판정(`verdict`)** — `실력` · `구분불가` · `열위` (+ 표본 수가 없으면
   `검정불가`). **통과는 `실력` 하나뿐이다.** 실력(모델 − 베이스라인)의 95% 구간이 0 을
   품으면 부호가 양수여도 `구분불가`다 — KPI 규칙 2("구간이 목표를 품으면 구분 불가이지
   달성이 아니다")를 판정 안에 박아 둔 것이다.

   ⚠ 2026-09-26 에 넣었다. 그 전까지는 `beats_*`(점추정의 부호)가 곧 판정이었고,
   09-24 누수 차단 재학습 뒤 방향 축이 +4.6%p · McNemar p=0.460 · 구간이 베이스라인을
   품는 상태로 **게이트가 닫혀 있었다**. 같은 날 finding 이 "이겼다로 읽지 말 것"이라
   적었는데 게이트는 이겼다고 세고 있었다. `beats_*` 는 부호 관측으로 남긴다.

## 베이스라인을 어떻게 고르나

- **LSTM 방향** — `{항상 상승, 항상 하락}` 중 **홀드아웃에서 더 잘 맞는 쪽**을 쓴다.
  사후적 선택이라 모델에 불리하지만, 그래서 **모델이 이기면 진짜로 이긴 것**이다.
  방어선으로 쓰기에 이쪽이 옳다.
- **LSTM 오차** — 지속성(persistence, 예측=직전 분기값). 시계열에서 표준 대조군이다.
- **2026-09-30 개정 — LSTM 두 축 모두 '강한 쪽'.** holdout 행에 `clim`(그 거점 train 기간
  타깃 평균)이 있으면 오차는 지속성·거점 평균 중 MAE 가 낮은 쪽, 방향은 위 상수·'평균 쪽'
  (sign(clim − 직전값)) 중 정확도가 높은 쪽에 댄다. `vac_proxy` 는 평균회귀가 강해 거점
  평균만 내밀어도 지속성을 이긴다(docs/finding-lstm-climatology-baseline-2026-09-28.md).
  `clim` 이 없는 산출물(09-27 서빙본)은 **종전 기준으로 물러나고 출력에 그렇다고 적는다.**
- **GNN** — 거점 사전분포(`baseline_district_prior_*`). 학습이 이미 남겨 둔 값을 읽는다.

읽기만 한다. 네트워크·파일 쓰기 없음. 표준 라이브러리만 쓴다(numpy·torch 불필요).

실행: python scripts/kpi_baseline.py          사람용
      python scripts/kpi_baseline.py --json   기계 판독용
반환 코드: 0 = 전 축 `실력` · 1 = 하나라도 `실력` 아님(CI 에서 잡으라고 비-0)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "gold"
FORECAST = GOLD / "platform_vacancy_forecast.json"
RECOMMEND = GOLD / "platform_industry_recommend.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────── 통계 코어 · LSTM · 확정 표본 ───────────────────────
#
# 2026-09-28: 서빙 패키지(`apps/backend/app/services/forecast_skill.py`)로 옮겼다 —
# 배포 이미지에 `scripts/` 가 없어 백엔드가 여기를 못 읽는데, 화면이 같은 판정을
# 보여야 하기 때문이다. 이름은 그대로 다시 내보낸다(테스트·pppp_status 가 import 한다).
# `app` 패키지 초기화를 타지 않도록 파일 경로로 싣는다.

def _load_core():
    import importlib.util

    path = ROOT / "apps" / "backend" / "app" / "services" / "forecast_skill.py"
    spec = importlib.util.spec_from_file_location("placeos_forecast_skill", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_core = _load_core()
wilson = _core.wilson
mcnemar_exact = _core.mcnemar_exact
cluster_bootstrap_ci = _core.cluster_bootstrap_ci
cluster_bootstrap_ratio_ci = _core.cluster_bootstrap_ratio_ci
ALPHA = _core.ALPHA
SKILL = _core.SKILL
UNRESOLVED = _core.UNRESOLVED
WORSE = _core.WORSE
UNTESTABLE = _core.UNTESTABLE
PENDING = _core.PENDING
verdict = _core.verdict
skew_robust = _core.skew_robust
_sgn = _core._sgn
lstm_skill = _core.lstm_skill
_apply_confirmation = _core.apply_confirmation


# ─────────────────────────── GNN ───────────────────────────

def detectability(p: float, n: int) -> dict:
    """이 표본으로 **얼마나 작은 차이까지 가를 수 있나**.

    2026-08-26 GNN 레버 실험이 남긴 교훈이 이것이다: +2.05%p 가 McNemar 에서
    p=0.111 이라 "유의하지 않다" 로 끝났는데, 그건 **차이가 없다**가 아니라
    **이 표본으로는 못 가른다**는 뜻이었다. 표본 크기를 옆에 안 적으면 그 둘이
    구분되지 않고, 못 가른 것이 기각으로 읽힌다.

    근사식은 `docs/scope-offprior-sample-2026-09-06.md` 가 쓴 것과 같다(단일 팔
    표준오차의 2배). ⚠ 같은 test 집합 위의 **쌍대** 비교라 올바른 검정은 McNemar
    이고, 그 2×2 표는 노드별 예측을 남겨야 만들 수 있다(`--dump-preds`).
    여기 값은 "표본이 이 정도는 돼야 말할 수 있다" 는 눈금이지 검정 결과가 아니다.
    """
    if n <= 0:
        return {"n": 0, "se_pp": None, "min_detectable_pp": None}
    se = math.sqrt(max(p * (1 - p), 0.0) / n) * 100.0
    return {"n": n, "se_pp": round(se, 2), "min_detectable_pp": round(2 * se, 2)}


def gnn_skill(recommend: dict) -> dict:
    """업종추천 — 학습이 남긴 거점 사전분포 기준선에 댄다.

    off-prior 는 사전분포가 **원리적으로 못 맞히는** 자리만 모은 표본이라 여기서
    실력이 가장 정직하게 드러난다. 값은 있는 그대로 싣고 판정에는 쓰지 않는다
    (게이트는 2026-08-26 에 관측 전용으로 강등됐다).
    """
    m = (recommend or {}).get("metrics") or {}
    top3, top1 = m.get("test_top3"), m.get("test_top1")
    b3 = m.get("baseline_district_prior_top3")
    b1 = m.get("baseline_district_prior_top1")
    if top3 is None or b3 is None:
        return {"available": False, "reason": "metrics 에 test_top3/baseline 이 없다"}
    skill_pp = (top3 - b3) * 100.0
    # test 표본 수. 옛 산출물에는 `nodes`(전체 그래프)뿐이라 없으면 **추정하지 않고**
    # None 으로 둔다 — 추정한 n 으로 낸 검정력은 근거가 아니다.
    n_test = m.get("test_nodes")
    det = detectability(top3, n_test) if n_test else {"n": None, "se_pp": None,
                                                      "min_detectable_pp": None}
    mdp = det.get("min_detectable_pp")
    # 판정 — 우선순위: ① 쌍대 표(`test_top3_paired`, 2026-09-27~ 학습본) → 거점 군집
    # 부트스트랩 실력 구간 + McNemar, LSTM 방향 축과 같은 규칙. ② 쌍대 표가 없는 옛
    # 산출물 → 분해능(단일 팔 SE 의 2배)을 구간 반폭으로 쓰는 근사. ③ test 표본 수도
    # 없으면 **추정하지 않고** 검정불가로 물러난다.
    paired = m.get("test_top3_paired") or {}
    by_d = paired.get("by_district") or {}
    skill_ci_pp = mc = None
    if by_d:
        lo, hi = cluster_bootstrap_ratio_ci([(v[0] - v[1], v[2]) for v in by_d.values()])
        skill_ci_pp = [lo * 100.0, hi * 100.0]
        mc = {"b_model_only": paired["b_model_only"],
              "c_prior_only": paired["c_prior_only"],
              "p_two_sided": mcnemar_exact(paired["b_model_only"], paired["c_prior_only"])}
        v, basis = verdict((lo, hi), mc["p_two_sided"]), "paired"
    elif mdp is not None:
        v, basis = verdict((skill_pp - mdp, skill_pp + mdp)), "detectability"
    else:
        v, basis = UNTESTABLE, "none"
    out = {
        "available": True,
        "top3": top3, "baseline_top3": b3, "skill_pp_top3": skill_pp,
        # 점추정의 **부호**다 — 판정이 아니다. 판정은 verdict.
        "beats_baseline": top3 > b3,
        "verdict": v,
        "verdict_basis": basis,
        "skill_ci95_pp": skill_ci_pp,
        "mcnemar": mc,
        "detectability": det,
        # 실력이 양수라도 그 크기가 분해능 아래면 **말할 수 없는 차이**다.
        "skill_is_detectable": (abs(skill_pp) >= mdp) if mdp is not None else None,
        "offprior_top3": m.get("test_offprior_top3"),
        "offprior_nodes": m.get("offprior_nodes"),
        "offprior_detectability": (
            detectability(m["test_offprior_top3"], m["offprior_nodes"])
            if m.get("test_offprior_top3") is not None and m.get("offprior_nodes")
            else None),
        "test_nodes": n_test,
        "graph_nodes": m.get("nodes"),
    }
    if top1 is not None and b1 is not None:
        out.update({"top1": top1, "baseline_top1": b1,
                    "skill_pp_top1": (top1 - b1) * 100.0})
    return out


# ─────────────────────────── GNN 어휘 점검 (2026-09-28) ───────────────────────────
#
# 쌍대 판정은 "같은 test 에서 사전분포보다 나은가"만 묻고 **추천 어휘를 제품으로 쓸 수
# 있는가**는 묻지 않는다. 09-27 재학습의 어휘 (a) `group` 은 추천 1순위의 74% 가
# "미분류"였는데도 `실력`이 나왔고, 사람이 JSON 을 열어서 잡았다.
# → docs/finding-gnn-81hub-retrain-2026-09-27.md §판정기의 사각
#
# 결정 어휘: (b) `group_mapped` — 7종에 사상된 점포만, 미분류는 클래스가 아니다(창업자 2026-09-27).
# → docs/finding-gnn-81hub-retrain-2026-09-27.md §결정. 기준 ①②③ 은 창업자 승인(2026-09-28).
SERVING_LABEL_LEVEL = "group_mapped"
SERVING_VOCAB = ("음식점", "카페", "편의점", "병원", "약국", "숙박", "문화시설")
UNMAPPED_LABEL = "미분류"
VOCAB_PASS = "합격"
VOCAB_FAIL = "어휘 불합격"


def gnn_vocab_check(recommend: dict) -> dict:
    """서빙 추천 산출물 하나로 어휘 기준 ①②③ 을 잰다. 입력은 이 산출물뿐이다.

    ① 서빙 어휘 일치 — `metrics.label_level == SERVING_LABEL_LEVEL`. 기록이 없으면 `검정불가`.
    ② 미분류 0 — 서빙 추천 Top-3 어디에도 "미분류"가 없다.
    ③ 어휘 폭 — 추천에 나타나는 라벨 수 ≥ 결정 어휘 라벨 수 − 1. 빠진 라벨은 경고로 싣는다.

    하나라도 어기면 `어휘 불합격`, ① 기록이 없으면 `검정불가` — 어느 쪽이든 게이트를
    `실력`으로 닫지 않는다. 1순위 쏠림은 **관측**으로만 싣는다(판정에 쓰지 않는다).
    """
    rec = recommend or {}
    level = (rec.get("metrics") or {}).get("label_level")
    top1: dict[str, int] = {}
    seen: set[str] = set()
    unmapped = n = 0
    for nodes in (rec.get("districts") or {}).values():
        for v in nodes.values():
            tops = [r.get("industry") for r in v.get("top") or []]
            if not tops:
                continue
            n += 1
            top1[tops[0]] = top1.get(tops[0], 0) + 1
            seen.update(tops)
            unmapped += tops.count(UNMAPPED_LABEL)
    missing = [lab for lab in SERVING_VOCAB if lab not in seen]
    width_min = len(SERVING_VOCAB) - 1
    checks = {
        "label_level": {"ok": level == SERVING_LABEL_LEVEL, "value": level,
                        "want": SERVING_LABEL_LEVEL},
        "no_unmapped": {"ok": n > 0 and unmapped == 0, "value": unmapped},
        "width": {"ok": len(seen) >= width_min, "value": len(seen), "want": width_min,
                  "of": len(SERVING_VOCAB)},
    }
    if level is None:
        v = UNTESTABLE
    elif all(c["ok"] for c in checks.values()):
        v = VOCAB_PASS
    else:
        v = VOCAB_FAIL
    lead = max(top1.items(), key=lambda kv: kv[1]) if top1 else (None, 0)
    return {
        "verdict": v,
        "checks": checks,
        "labels": sorted(seen),
        "missing": missing,
        "outside_vocab": sorted(seen - set(SERVING_VOCAB)),
        "slots": n,
        # [관측] 1순위 쏠림 — 판정에 쓰지 않는다(기준 밖이라 결과를 보고 끼우면 안 된다)
        "top1_lead": {"label": lead[0], "share": (lead[1] / n) if n else None},
    }


def _vocab_why(vc: dict) -> str:
    """어휘 점검이 게이트를 막은 이유 — 어긴 기준만."""
    c = vc["checks"]
    if vc["verdict"] == UNTESTABLE:
        return "산출물에 label_level 기록이 없어 어휘를 확인할 수 없다"
    out = []
    if not c["label_level"]["ok"]:
        out.append(f"① label_level={c['label_level']['value']} ≠ {SERVING_LABEL_LEVEL}")
    if not c["no_unmapped"]["ok"]:
        out.append(f"② Top-3 에 {UNMAPPED_LABEL} {c['no_unmapped']['value']:,}건")
    if not c["width"]["ok"]:
        out.append(f"③ 라벨 {c['width']['value']}/{c['width']['of']}종 < {c['width']['want']}")
    return " · ".join(out)


# ─────────────────────────── 종합 ───────────────────────────

def check(forecast_path: Path = FORECAST, recommend_path: Path = RECOMMEND) -> dict:
    def _load(p: Path) -> dict | None:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    fc, rec = _load(forecast_path), _load(recommend_path)
    lstm = lstm_skill(fc) if fc else {"available": False, "reason": f"{forecast_path.name} 없음"}
    gnn = gnn_skill(rec) if rec else {"available": False, "reason": f"{recommend_path.name} 없음"}
    if lstm.get("available"):
        _apply_confirmation(lstm, fc)
    if gnn.get("available"):
        gnn["gate_verdict"] = gnn["verdict"]
        # 2026-09-28: 통계로 `실력`이어도 어휘 기준을 어기면 닫지 않는다(§GNN 어휘 점검).
        vc = gnn["vocab"] = gnn_vocab_check(rec)
        if gnn["verdict"] == SKILL and vc["verdict"] != VOCAB_PASS:
            gnn["gate_verdict"] = vc["verdict"]

    # 실패는 **게이트 판정(gate_verdict)이 실력이 아닌 모든 축**이다. 부호가 양수여도
    # 구분불가면 적는다 — 그게 규칙 2 다. 문구는 무엇에 졌는지(베이스라인 이름)와
    # 판정을 함께 말한다. 확인대기면 참고 판정을 옆에 붙인다.
    failures: list[str] = []
    if lstm.get("available"):
        d = lstm["direction"]
        cf = lstm.get("confirmation")
        pend = (f" · 확정은 {cf['after']} 이후 분기 표본 필요(현재 {cf['n_fresh']}건)"
                if cf and d["gate_verdict"] == PENDING else "")
        if d["gate_verdict"] != SKILL:
            lo, hi = d["skill_ci95_pp"]
            failures.append(
                f"LSTM 방향정확도 {d['model_acc']:.1%} vs 베이스라인({d['baseline_label']}) "
                f"{d['baseline_acc']:.1%} — 실력 {d['skill_pp']:+.1f}%p "
                f"[{lo:+.1f}, {hi:+.1f}] · McNemar p={d['mcnemar']['p_two_sided']:.3f} "
                f"→ {d['gate_verdict']}" + (f"(참고 {d['verdict']})" if pend else "") + pend)
        e = lstm["error"]
        if e["gate_verdict"] != SKILL:
            lo, hi = e["mae_skill_ci95"]
            failures.append(
                f"LSTM MAE {e['model_mae']:.3f} vs {e['baseline_label']} 베이스라인 "
                f"{e['baseline_mae']:.3f} "
                f"— 기술점수 {e['mae_skill']:+.1%} [{lo:+.1%}, {hi:+.1%}] → {e['gate_verdict']}"
                + (f"(참고 {e['verdict']})" if pend else "") + pend)
    if gnn.get("available") and gnn["gate_verdict"] != SKILL:
        if gnn["verdict"] == SKILL:
            # 통계는 넘었는데 어휘가 막았다 — 무엇을 어겼는지를 말한다
            why = f"통계는 실력이지만 {_vocab_why(gnn['vocab'])}"
        elif gnn["verdict_basis"] == "paired":
            lo, hi = gnn["skill_ci95_pp"]
            why = f"[{lo:+.2f}, {hi:+.2f}] · McNemar p={gnn['mcnemar']['p_two_sided']:.3f}"
        elif gnn["verdict"] == UNTESTABLE:
            why = "test 표본 수가 산출물에 없어 가를 수 없다"
        else:
            why = f"분해능 ±{gnn['detectability']['min_detectable_pp']}%p"
        failures.append(
            f"GNN Top-3 {gnn['top3']:.1%} vs 거점 사전분포 {gnn['baseline_top3']:.1%} "
            f"— 실력 {gnn['skill_pp_top3']:+.2f}%p · {why} → {gnn['gate_verdict']}")

    return {"lstm": lstm, "gnn": gnn, "failures": failures, "ok": not failures}


_MARK = {SKILL: "✅", UNRESOLVED: "⚠", WORSE: "❌", UNTESTABLE: "⚠", PENDING: "⏳",
         VOCAB_PASS: "✅", VOCAB_FAIL: "❌"}


def _fmt(res: dict) -> str:
    out: list[str] = []
    out.append("KPI 실력 검정 — 모델 vs 무정보 베이스라인")
    out.append("=" * 78)

    lstm = res["lstm"]
    out.append("\n[LSTM] 공실 예측")
    if not lstm.get("available"):
        out.append(f"   재지 못했다 — {lstm.get('reason')}")
    else:
        d, e = lstm["direction"], lstm["error"]
        if lstm["baseline_basis"] == "legacy_no_clim":
            out.append("   [기준] 종전 기준(지속성 · 다수방향 상수) — 이 산출물에 거점 평균(clim)이 "
                       "없어 강한 쪽 기준으로 못 잰다(2026-09-30 개정 전 학습본)")
        else:
            out.append("   [기준] 축마다 두 무정보 규칙 중 강한 쪽 — 오차: 지속성·거점 평균 · "
                       "방향: 다수방향 상수·평균 쪽(2026-09-30 개정)")
        lo, hi = d["model_ci95"]
        slo, shi = d["skill_ci95_pp"]
        out.append(f"   방향정확도  모델 {d['model_acc']:.1%} "
                   f"({d['model_hits']}/{lstm['n']}) · 95%CI [{lo:.1%}, {hi:.1%}]")
        out.append(f"               베이스라인({d['baseline_label']}) {d['baseline_acc']:.1%} "
                   f"({d['baseline_hits']}/{lstm['n']})")
        if d["meanward_acc"] is not None:
            out.append(f"               후보: {d['constant_label']} {d['constant_acc']:.1%} · "
                       f"평균 쪽 {d['meanward_acc']:.1%} — 강한 쪽을 기준으로 쓴다")
        out.append(f"   {_MARK[d['verdict']]} {d['verdict']} — 실력 {d['skill_pp']:+.1f}%p "
                   f"[{slo:+.1f}, {shi:+.1f}] · McNemar "
                   f"b={d['mcnemar']['b_model_only']} c={d['mcnemar']['c_baseline_only']} "
                   f"p={d['mcnemar']['p_two_sided']:.3f}")
        out.append(f"      실제 방향 상승 {d['actual_up']} · 하락 {d['actual_down']} "
                   f"— 한쪽으로 쏠려 있어 상수 규칙이 강하다")
        ob = d.get("observed") or {}
        if ob:
            c = ob["confusion"]
            out.append(f"   [관측] 균형정확도 {ob['balanced_acc']:.1%}(상수 50.0%) · "
                       f"MCC {ob['mcc']:+.3f}(상수 0)")
            out.append(f"          상승 재현율 {ob['recall_up']:.1%}"
                       f"({c['tp']}/{c['tp'] + c['fn']}) · "
                       f"정밀도 {ob['precision_up']:.1%} · "
                       f"하락 재현율 {ob['recall_down']:.1%}"
                       f"({c['tn']}/{c['tn'] + c['fp']})")
            out.append("          → 상수 규칙은 균형정확도 50%·MCC 0 이다. 이 둘이 그보다 "
                       "높으면 **모델에 신호는 있다**는 뜻이고,")
            out.append("            원시 정확도로 상수와 못 가르는 것은 표본 쏠림 탓일 수 있다. "
                       "⚠ 관측일 뿐 판정 지표가 아니다(결과를 보고 바꾸면 metric shopping)")
        if lstm.get("samples_per_hub", 0) > 1:
            out.append(f"   [분할] 거점 {lstm['n_hubs']}곳 × 거점당 "
                       f"{lstm['samples_per_hub']:.1f}건 (롤링 오리진) · "
                       f"구간은 {d['ci_kind']} — 같은 거점의 이웃 분기는 독립이 아니다")
        elo, ehi = e["mae_skill_ci95"]
        if e["climatology_mae"] is None:
            out.append(f"   오차        모델 MAE {e['model_mae']:.3f} · "
                       f"지속성 {e['persistence_mae']:.3f}")
        else:
            out.append(f"   오차        모델 MAE {e['model_mae']:.3f} · "
                       f"지속성 {e['persistence_mae']:.3f} · 거점 평균 "
                       f"{e['climatology_mae']:.3f} → 기준 {e['baseline_label']}")
        out.append(f"   {_MARK[e['verdict']]} {e['verdict']} — 기술점수 MAE "
                   f"{e['mae_skill']:+.1%} [{elo:+.1%}, {ehi:+.1%}] · "
                   f"RMSE {e['rmse_skill']:+.1%}")
        if d["verdict"] != e["verdict"]:
            out.append("      두 축의 판정이 다르다 — 하나만 인용하면 어느 쪽이든 거짓이 된다")
        cf = lstm.get("confirmation")
        if cf:
            out.append(f"   [확정] 위 판정은 **참고**다 — 게이트는 {cf['after']} 이후 분기 holdout "
                       f"{cf['n_fresh']}건으로 판정: 방향 {_MARK[d['gate_verdict']]} "
                       f"{d['gate_verdict']} · 오차 {_MARK[e['gate_verdict']]} {e['gate_verdict']}")

    gnn = res["gnn"]
    out.append("\n[GNN] 업종 추천")
    if not gnn.get("available"):
        out.append(f"   재지 못했다 — {gnn.get('reason')}")
    else:
        out.append(f"   Top-3       모델 {gnn['top3']:.1%} · "
                   f"거점 사전분포 {gnn['baseline_top3']:.1%}")
        line = f"   {_MARK[gnn['verdict']]} {gnn['verdict']} — 실력 {gnn['skill_pp_top3']:+.2f}%p"
        if gnn.get("verdict_basis") == "paired":
            glo, ghi = gnn["skill_ci95_pp"]
            gm = gnn["mcnemar"]
            line += (f" [{glo:+.2f}, {ghi:+.2f}] · McNemar b={gm['b_model_only']} "
                     f"c={gm['c_prior_only']} p={gm['p_two_sided']:.3f} (쌍대 · 거점 군집)")
        out.append(line)
        vc = gnn.get("vocab")
        if vc:
            c = vc["checks"]
            mk = {True: "✓", False: "✗"}
            out.append(f"   [어휘] {_MARK[vc['verdict']]} {vc['verdict']} — "
                       f"① label_level {c['label_level']['value']} {mk[c['label_level']['ok']]} · "
                       f"② {UNMAPPED_LABEL} {c['no_unmapped']['value']:,}건 "
                       f"{mk[c['no_unmapped']['ok']]} · "
                       f"③ 라벨 {c['width']['value']}/{c['width']['of']}종 "
                       f"(≥{c['width']['want']}) {mk[c['width']['ok']]}")
            if vc["missing"]:
                out.append(f"          ⚠ 결정 어휘 중 추천에 안 나오는 라벨: "
                           f"{', '.join(vc['missing'])}")
            if vc["outside_vocab"]:
                out.append(f"          ⚠ 결정 어휘 밖 라벨: {', '.join(vc['outside_vocab'])}")
            lead = vc["top1_lead"]
            if lead["share"] is not None:
                out.append(f"          [관측] 1순위 쏠림 — {lead['label']} {lead['share']:.1%} "
                           f"({vc['slots']:,}자리) · 판정에 쓰지 않는다")
            if gnn["gate_verdict"] != gnn["verdict"]:
                out.append(f"   [게이트] {_MARK[gnn['gate_verdict']]} {gnn['gate_verdict']} — "
                           f"통계 판정({gnn['verdict']})을 어휘 점검이 막았다")
        det = gnn.get("detectability") or {}
        if det.get("min_detectable_pp") is not None:
            verdict = ("가를 수 있다" if gnn.get("skill_is_detectable")
                       else "**이 표본으로는 못 가른다**")
            out.append(f"   [검정력] test {det['n']}자리 · SE {det['se_pp']}%p · "
                       f"가별 최소 차이 ≈{det['min_detectable_pp']}%p → {verdict}")
        else:
            out.append("   [검정력] test 표본 수가 산출물에 없다 — 재학습하면 "
                       "`test_nodes` 가 채워진다(추정으로 대신하지 않는다)")
        od = gnn.get("offprior_detectability")
        if od and od.get("min_detectable_pp") is not None:
            out.append(f"   [검정력] off-prior {od['n']}자리 · 가별 최소 차이 "
                       f"≈{od['min_detectable_pp']}%p — 라벨 축(category2)으로 가면 "
                       f"자리가 4.35배가 된다(scope-offprior-sample-2026-09-06)")
        if "top1" in gnn:
            out.append(f"   Top-1       모델 {gnn['top1']:.1%} · "
                       f"사전분포 {gnn['baseline_top1']:.1%} "
                       f"(실력 {gnn['skill_pp_top1']:+.2f}%p)")
        if gnn.get("offprior_top3") is not None:
            out.append(f"   off-prior   {gnn['offprior_top3']:.1%} "
                       f"({gnn.get('offprior_nodes')}자리) — 사전분포가 못 맞히는 자리")

    out.append("\n" + "=" * 78)
    if res["ok"]:
        out.append("✅ 전 축이 베이스라인을 구간 기준으로 넘는다.")
    else:
        out.append("❌ 실력 미확인 — 이 축의 '목표 달성' 표기는 근거가 없다:")
        out.extend(f"   · {f}" for f in res["failures"])
    out.append("\n⚠ 임계값(70%)만 넘긴 것은 달성이 아니다. 같은 홀드아웃에서 무정보 규칙이")
    out.append("  그 임계값을 넘는지 먼저 본다 — 넘으면 그 게이트는 모델을 보증하지 못한다.")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    res = check()
    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(_fmt(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
