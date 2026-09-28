"""공실 예측(LSTM)의 베이스라인 대비 실력 판정 — 통계 코어.

`scripts/kpi_baseline.py` 에서 **옮겨 왔다**(2026-09-28). 이유는 하나다: 화면이
LSTM 예측 옆에 판정(`실력`·`구분불가`·`열위`·`확인대기`)을 붙여야 하는데, 배포
이미지는 `.dockerignore` 로 `scripts/` 를 뺀다. 판정을 프론트에 박아 두면 낡는다
(09-28 실측: 화면에 07-25 MAE 1.109 가 박혀 있었다). 그래서 판정 로직을 서빙
패키지 안에 두고, `scripts/kpi_baseline.py` 는 이것을 **다시 내보낸다** — 출처는
하나다. 설계 근거·베이스라인 선택 이유는 `scripts/kpi_baseline.py` 독스트링에 있다.

표준 라이브러리만 쓴다. 이 모듈은 `app` 의 다른 것을 import 하지 않는다 —
`kpi_baseline` 이 파일 경로로 직접 싣기 때문이다(`app` 패키지 초기화를 타지 않는다).
"""
from __future__ import annotations

import math

# ─────────────────────────── 통계 ───────────────────────────

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """이항 비율의 Wilson 신뢰구간. n 이 작을 때 정규근사보다 정직하다."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(b: int, c: int) -> float:
    """McNemar 정확검정(양측) p값. b·c 는 불일치 칸.

    카이제곱 근사는 b+c 가 작으면 못 쓴다(여기 실측이 21 이다). 정확검정은
    b+c 를 시행수, 0.5 를 성공확률로 보는 이항검정이다.
    """
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    tail = sum(math.comb(n, i) for i in range(lo + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def cluster_bootstrap_ci(hits_by_cluster: list[list[float]], reps: int = 2000,
                         seed: int = 42) -> tuple[float, float]:
    """거점 단위 군집 부트스트랩 95% 구간 — 표본 평균의 구간.

    롤링 오리진으로 거점당 표본이 여럿이면 **이항 공식을 쓰면 안 된다** — 같은 거점의
    이웃 분기는 상관돼 있어 표본이 독립이 아니고, Wilson 구간은 그만큼 좁게 나온다.
    거점(군집)을 복원추출해 구간을 낸다. 거점당 1건이면 보통 부트스트랩과 같아진다.

    원소는 적중(bool)이면 정확도 구간, **쌍대 차이**(모델 − 베이스라인, 표본마다)면
    실력 구간이 된다. 같은 표본 위의 비교라 두 구간을 따로 내서 겹치는지 보는 것보다
    차이 하나의 구간을 보는 쪽이 옳다.
    """
    import random

    k = len(hits_by_cluster)
    if k == 0:
        return (0.0, 0.0)
    rng = random.Random(seed)
    accs: list[float] = []
    for _ in range(reps):
        picked = [hits_by_cluster[rng.randrange(k)] for _ in range(k)]
        flat = [h for c in picked for h in c]
        if flat:
            accs.append(sum(flat) / len(flat))
    if not accs:
        return (0.0, 0.0)
    accs.sort()
    return (accs[int(0.025 * len(accs))], accs[min(len(accs) - 1, int(0.975 * len(accs)))])


def cluster_bootstrap_ratio_ci(clusters: list[tuple[float, int]], reps: int = 2000,
                               seed: int = 42) -> tuple[float, float]:
    """군집별 (값의 합, 건수) 로 낸 **비율**의 군집 부트스트랩 95% 구간.

    `cluster_bootstrap_ci` 와 같은 재표본(군집 복원추출 → Σ합/Σ건수)인데 원소를 펼치지
    않는다. GNN test 는 수천 자리라 펼치면 판정 한 번에 수천만 번을 돈다 — 쌍대 차이는
    {+1, −1, 0} 이라 군집마다 합과 건수만 있으면 같은 값이 나온다.
    """
    import random

    cl = [(float(s), int(n)) for s, n in clusters if n > 0]
    k = len(cl)
    if k == 0:
        return (0.0, 0.0)
    rng = random.Random(seed)
    ratios: list[float] = []
    for _ in range(reps):
        tot_s = tot_n = 0.0
        for _ in range(k):
            s, n = cl[rng.randrange(k)]
            tot_s += s
            tot_n += n
        ratios.append(tot_s / tot_n)
    ratios.sort()
    return (ratios[int(0.025 * reps)], ratios[min(reps - 1, int(0.975 * reps))])


ALPHA = 0.05

SKILL = "실력"            # 통과는 이것 하나뿐
UNRESOLVED = "구분불가"   # 부호와 무관하게 구간이 0 을 품는다 — 달성도 미달도 아니다
WORSE = "열위"            # 베이스라인이 유의하게 낫다
UNTESTABLE = "검정불가"   # 표본 수가 산출물에 없어 구간을 못 낸다 — 추정으로 대신하지 않는다
PENDING = "확인대기"      # 본 적 없는 분기의 표본이 아직 없다 — 참고 판정만 있다(2026-09-27)


def verdict(ci: tuple[float, float] | list[float], p: float | None = None) -> str:
    """실력 구간(모델 − 베이스라인)으로 세 갈래 판정을 낸다.

    구간이 0 위에 있어야 `실력`, 아래에 있어야 `열위`, 0 을 품으면 `구분불가`다.
    `p` 를 주면 그 검정도 유의해야 한다(방향 축: 군집 구간 + McNemar 둘 다) —
    McNemar 는 표본 독립을 가정하고 군집 구간은 거점 상관을 반영하므로, 가정이 다른
    두 절차가 **둘 다** 동의할 때만 가른다. 보수적인 쪽을 택한 것이다.
    """
    lo, hi = ci
    sig = p is None or p < ALPHA
    if lo > 0 and sig:
        return SKILL
    if hi < 0 and sig:
        return WORSE
    return UNRESOLVED


def skew_robust(tp: int, fp: int, fn: int, tn: int) -> dict:
    """쏠린 이진 표본에서 **상수 규칙이 구조적으로 못 이기는** 지표들.

    원시 정확도는 다수 클래스 비율에 지배된다(실측: 하락 51 · 상승 14 에서 '항상 하락'
    이 78.5%). 균형정확도와 MCC 는 상수 규칙이 각각 정확히 50%·0 이므로, 모델에
    신호가 있는지를 원시 정확도와 **독립적으로** 드러낸다.

    ⚠ 이 값들은 **관측**이다. 판정 지표를 결과를 보고 바꾸면 그 자체가 metric shopping
    이라 이 저장소가 막아 온 누수와 같은 종류가 된다. 판정에 쓰려면 재학습 **전에**
    확정해야 한다 — docs/finding-lstm-direction-diagnosis-2026-09-16.md §무엇을 하면 되나.
    """
    rec_pos = tp / (tp + fn) if tp + fn else 0.0
    rec_neg = tn / (tn + fp) if tn + fp else 0.0
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return {
        "recall_up": rec_pos, "recall_down": rec_neg,
        "precision_up": tp / (tp + fp) if tp + fp else 0.0,
        "balanced_acc": (rec_pos + rec_neg) / 2,      # 상수 규칙 = 0.5
        "mcc": ((tp * tn - fp * fn) / den) if den else 0.0,   # 상수 규칙 = 0
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def _sgn(x: float) -> int:
    return (x > 0) - (x < 0)


# ─────────────────────────── LSTM ───────────────────────────

def lstm_skill(forecast: dict) -> dict:
    """공실 예측 — 방향정확도·오차 두 축을 각각 베이스라인에 댄다.

    **두 축의 답이 갈릴 수 있어 하나만 인용하면 어느 쪽이든 거짓이 된다** — 그래서
    둘 다 돌려준다. 실제로 갈렸고, 09-24 누수 차단 재학습에서는 **서로 자리를 바꿨다**
    (방향 −7.7%p → +4.6%p · 오차 +20.5% → −86.9%). 그래서 여기엔 어느 축이 이긴다고
    적지 않는다 — 그런 문장이 낡는 것이 이 저장소의 주된 실패 양식이다.
    """
    hold = forecast.get("holdout") or {}
    # 키는 `거점@분기`(롤링 오리진) 또는 `거점`(단일 원점). 군집 단위는 **거점**이라
    # `hub` 필드를 우선 쓰고, 없으면 키에서 `@` 앞을 떼어 옛 산출물도 읽는다.
    rows = [(v.get("hub") or str(k).split("@")[0],
             v.get("pred"), v.get("actual"), v.get("prev")) for k, v in hold.items()]
    rows = [r for r in rows if None not in r[1:]]
    n = len(rows)
    if n == 0:
        return {"available": False, "reason": "holdout 표가 비어 있다"}

    hits = sum(1 for _, p, a, pr in rows if _sgn(p - pr) == _sgn(a - pr))
    up = sum(1 for _, _, a, pr in rows if a - pr > 0)
    down = sum(1 for _, _, a, pr in rows if a - pr < 0)
    # 사후적 다수 방향 — 모델에 불리한(즉 방어에 적합한) 베이스라인
    base_hits, base_label = (down, "항상 하락") if down >= up else (up, "항상 상승")

    # 쌍대 비교: 모델만 맞은 칸 b · 베이스라인만 맞은 칸 c
    b = c = 0
    base_down = base_hits == down
    for _, p, a, pr in rows:
        m_hit = _sgn(p - pr) == _sgn(a - pr)
        base_hit = (a - pr < 0) if base_down else (a - pr > 0)
        b += int(m_hit and not base_hit)
        c += int(base_hit and not m_hit)

    mae_m = sum(abs(p - a) for _, p, a, _ in rows) / n
    rmse_m = math.sqrt(sum((p - a) ** 2 for _, p, a, _ in rows) / n)
    mae_p = sum(abs(pr - a) for _, _, a, pr in rows) / n        # 지속성
    rmse_p = math.sqrt(sum((pr - a) ** 2 for _, _, a, pr in rows) / n)

    # 혼동행렬(상승=양성) — 소수 클래스에 신호가 있는지 본다
    tp = sum(1 for _, p, a, pr in rows if p - pr > 0 and a - pr > 0)
    fp = sum(1 for _, p, a, pr in rows if p - pr > 0 and a - pr <= 0)
    fn = sum(1 for _, p, a, pr in rows if p - pr <= 0 and a - pr > 0)
    tn = n - tp - fp - fn

    # 군집(거점) 단위 목록 → 부트스트랩 구간. 셋을 같은 군집 구조로 모은다:
    #   적중(정확도 구간) · 방향 쌍대 차이(실력 구간) · 절대오차 쌍대 차이(오차 실력 구간)
    by_hub: dict[str, list[bool]] = {}
    dir_diff: dict[str, list[int]] = {}
    err_diff: dict[str, list[float]] = {}
    for hub, p, a, pr in rows:
        m_hit = _sgn(p - pr) == _sgn(a - pr)
        base_hit = (a - pr < 0) if base_down else (a - pr > 0)
        by_hub.setdefault(hub, []).append(m_hit)
        dir_diff.setdefault(hub, []).append(int(m_hit) - int(base_hit))
        # 양수 = 모델이 지속성보다 가깝다
        err_diff.setdefault(hub, []).append(abs(pr - a) - abs(p - a))
    n_hubs = len(by_hub)
    per_hub = n / n_hubs if n_hubs else 0.0
    # 거점당 1건이면 Wilson 과 사실상 같으므로 굳이 부트스트랩을 돌리지 않는다.
    ci_kind = "wilson" if per_hub <= 1.0 else "cluster_bootstrap"
    ci = (list(wilson(hits, n)) if ci_kind == "wilson"
          else list(cluster_bootstrap_ci(list(by_hub.values()))))
    # 실력 구간은 거점당 건수와 무관하게 군집 부트스트랩이다(거점당 1건이면 보통 부트스트랩).
    skill_ci = cluster_bootstrap_ci(list(dir_diff.values()))
    p_mc = mcnemar_exact(b, c)
    mae_diff_ci = cluster_bootstrap_ci(list(err_diff.values()))

    acc, base_acc = hits / n, base_hits / n
    return {
        "available": True,
        "n": n,
        "n_hubs": n_hubs,
        "samples_per_hub": per_hub,
        "direction": {
            "model_hits": hits, "model_acc": acc, "model_ci95": ci, "ci_kind": ci_kind,
            "baseline_label": base_label, "baseline_hits": base_hits,
            "baseline_acc": base_acc, "baseline_ci95": list(wilson(base_hits, n)),
            "skill_pp": (acc - base_acc) * 100.0,
            "skill_ci95_pp": [skill_ci[0] * 100.0, skill_ci[1] * 100.0],
            "mcnemar": {"b_model_only": b, "c_baseline_only": c,
                        "p_two_sided": p_mc},
            "actual_up": up, "actual_down": down,
            # 점추정의 **부호**다 — 판정이 아니다. 판정은 아래 verdict.
            "beats_baseline": acc > base_acc,
            "verdict": verdict(skill_ci, p_mc),
            # 관측 전용 — 판정에 쓰지 않는다(위 skew_robust 독스트링 참조)
            "observed": skew_robust(tp, fp, fn, tn),
        },
        "error": {
            "model_mae": mae_m, "model_rmse": rmse_m,
            "persistence_mae": mae_p, "persistence_rmse": rmse_p,
            # 기술점수(skill score) — 1 − 모델/베이스라인. 양수면 베이스라인보다 낫다.
            "mae_skill": (1.0 - mae_m / mae_p) if mae_p else 0.0,
            "rmse_skill": (1.0 - rmse_m / rmse_p) if rmse_p else 0.0,
            # MAE 기술점수의 구간 = (지속성 − 모델) 절대오차 차이의 구간 ÷ 지속성 MAE
            "mae_skill_ci95": ([mae_diff_ci[0] / mae_p, mae_diff_ci[1] / mae_p]
                               if mae_p else [0.0, 0.0]),
            # 점추정의 **부호**다 — 판정이 아니다. 판정은 아래 verdict.
            "beats_persistence": mae_m < mae_p,
            "verdict": verdict(mae_diff_ci),
        },
    }


# ─────────────────────────── 확정 표본 (2026-09-27) ───────────────────────────

def apply_confirmation(lstm: dict, forecast: dict) -> None:
    """`protocol.confirm_after` 가 있으면 **그 이후 분기** holdout 만으로 게이트를 판정한다.

    사전등록 §0-B ③: 이미 본 test 분기로는 `실력`을 확정하지 않는다. 전체 holdout 판정
    (`verdict`)은 **참고**로 남기고, 게이트 판정(`gate_verdict`)은 본 적 없는 분기의
    부분표본에서 낸다. 그런 표본이 0건이면 `확인대기` 다.

    `confirm_after` 가 없는 산출물(09-26 이전 학습본)은 종전대로 전체 판정이 곧 게이트
    판정이다 — 그 규칙이 생기기 전에 만든 산출물에 소급하지 않는다.
    분기 문자열은 `YYYYQ` 5자리라 사전식 비교가 곧 시간순이다.
    """
    d, e = lstm["direction"], lstm["error"]
    after = ((forecast or {}).get("protocol") or {}).get("confirm_after")
    if not after:
        d["gate_verdict"], e["gate_verdict"] = d["verdict"], e["verdict"]
        return
    fresh = {k: v for k, v in (forecast.get("holdout") or {}).items()
             if str(v.get("quarter") or "") > str(after)}
    conf = lstm_skill({"holdout": fresh}) if fresh else {"available": False}
    if conf.get("available"):
        d["gate_verdict"] = conf["direction"]["verdict"]
        e["gate_verdict"] = conf["error"]["verdict"]
    else:
        d["gate_verdict"] = e["gate_verdict"] = PENDING
    lstm["confirmation"] = {
        "after": str(after),
        "n_fresh": conf.get("n", 0) if conf.get("available") else 0,
        "direction": conf.get("direction") if conf.get("available") else None,
        "error": conf.get("error") if conf.get("available") else None,
    }
