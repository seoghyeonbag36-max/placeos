"""세부 업종 실험의 **입지 피처 보강** 비교. 서빙 모델·JSON·체크포인트는 건드리지 않는다.

기존 `industry_detail_experiment.py` 의 그래프(61,165노드 · 27클래스 · 132피처)에 아직 안 들어간
입지 피처 묶음을 하나씩 얹어 **같은 분할 · 같은 거점 사전분포 기준선**과 비교한다.
`train_gnn.train()` 은 고치지 않는다 — 이 파일이 실행 시점에 `_features`(피처 블록 덧붙임)와
`_split`(분할 시드 고정)만 바꿔 끼운다. `save=False, resume=False, ckpt_every=0`.

묶음(결과를 보기 전에 정했다 — 근거는 docs/finding-industry-features-2026-10-16.md §2):
  floor    층      노드의 `floor`(공실 자리도 층은 관측된다). 지하/지상·2층·3층+ 로 업종 입지가 갈린다
  transit  교통    `gold/page_bus_stops.json` 정류소 일평균 승하차를 노드 300m 반경으로 집계
  hourly   시간대  행정동 24시간 생활인구 프로필 10열(야간·주말 비중 등) — `train_gnn._adong_hour_block`
  all      위 셋 전부 (같은 세 묶음의 합. 네 번째 가설이 아니다)
  control  보강 없음 (기존 132피처)

실행(스레드 1개 · UTF-8 필수):
  OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8 python -m ml.training.industry_detail_features run-all
  OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8 python -m ml.training.industry_detail_features report \
      --output ml/reports/industry_detail_features_experiment_2026-10-16.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WORK_DIR = ROOT / "ml" / "artifacts" / "_detail_features_runs"   # .gitignore 대상
BUS_JSON = ROOT / "data" / "gold" / "page_bus_stops.json"
PRIOR_REPORT = ROOT / "ml" / "reports" / "industry_detail_experiment_2026-10-16.json"

ARMS = ("control", "floor", "transit", "hourly", "all")
SPLIT_SEED = 42                # 분할은 모든 팔·시드에서 같다
INIT_SEEDS = (42, 43, 44)      # 모델 초기화·드롭아웃 시드 — 42 가 10-16 기존 실행과 같다
EPOCHS, PATIENCE, HIDDEN = 80, 15, 64   # 10-16 보고서와 같은 설정
BOOT_N = 2000
BUS_RADIUS_M = 300.0
_M_PER_DEG_LAT, _M_PER_DEG_LON = 111000.0, 88300.0


# ── 피처 블록 ─────────────────────────────────────────────────────────

def parse_floor(raw) -> tuple[bool, int]:
    """상가정보 `floor` 문자열 → (알 수 있는가, 층 번호). 지하는 음수.

    '1'~'30' 은 층, '지'·'B1'·'B2'·'반지층' 은 지하(-1 이하)로 읽는다. 공란이거나
    호실 번호로 보이는 값('403', '912', 'B145' 등 31 이상)은 **모른다**로 둔다 —
    추측해서 층으로 만들지 않는다.
    """
    s = ("" if raw is None else str(raw)).strip()
    if not s or s.lower() == "nan":
        return False, 0
    if s in ("지", "반", "반지층"):
        return True, -1
    if s[0] in "Bb지":
        digits = s[1:]
        if digits == "":
            return True, -1
        if digits.isdigit() and 1 <= int(digits) <= 9:
            return True, -int(digits)
        return False, 0
    if s.isdigit() and 1 <= int(s) <= 30:
        return True, int(s)
    return False, 0


def floor_block(nodes) -> tuple[np.ndarray, list[str]]:
    """층 피처 5열: 층 정보 유무 · 지하 · 1층 · 2층 · 3층 이상(log). 표준화하지 않는다(0/1 위주)."""
    parsed = [parse_floor(v) for v in nodes["floor"].to_numpy()]
    known = np.array([k for k, _ in parsed], dtype=float)
    fl = np.array([f for _, f in parsed], dtype=float)
    base = known > 0
    cols = [known,
            (base & (fl < 0)).astype(float),
            (base & (fl == 1)).astype(float),
            (base & (fl == 2)).astype(float),
            np.where(base & (fl >= 3), np.log(np.maximum(fl, 1.0)), 0.0)]
    return np.column_stack(cols), ["flr_known", "flr_basement", "flr_ground", "flr_2f", "flr_3f_up_log"]


def transit_block(nodes, bus_path: Path = BUS_JSON) -> tuple[np.ndarray, list[str]]:
    """노드 300m 안 버스 정류소의 일평균 승하차 집계 4열(z-score).

    정류소 파일은 서울 전역 10,651곳이며 노드 최근접 정류소 거리 최대가 432m 라
    (실측 2026-10-16) 거점 밖 노드의 결측은 없다. 승하차는 2026-10-04~10 7일 평균이다.
    """
    from scipy.spatial import cKDTree
    stops = json.loads(bus_path.read_text(encoding="utf-8"))["stops"]
    s = np.array([[r[2], r[3], r[4]] for r in stops], dtype=float)   # lat, lng, daily_total
    tree = cKDTree(np.c_[s[:, 0] * _M_PER_DEG_LAT, s[:, 1] * _M_PER_DEG_LON])
    pts = np.c_[nodes["lat"].to_numpy(float) * _M_PER_DEG_LAT,
                nodes["lon"].to_numpy(float) * _M_PER_DEG_LON]
    dist, near = tree.query(pts)
    within = tree.query_ball_point(pts, r=BUS_RADIUS_M)
    n_in = np.array([len(w) for w in within], dtype=float)
    riders = np.array([s[w, 2].sum() if len(w) else 0.0 for w in within])
    block = np.column_stack([np.log1p(n_in), np.log1p(riders), np.log1p(dist), np.log1p(s[near, 2])])
    sd = block.std(axis=0)
    sd[sd == 0] = 1.0
    block = (block - block.mean(axis=0)) / sd
    return np.nan_to_num(block), ["bus_log_n300", "bus_log_riders300", "bus_log_dist_nearest", "bus_log_riders_nearest"]


def _hourly_block(nodes):
    from ml.training import train_gnn
    blk = train_gnn._adong_hour_block(nodes)
    if blk is None:
        # 조용히 빠지면 이 팔이 control 과 같아진다 — 실패로 드러낸다
        raise RuntimeError("행정동 시간 피처 블록을 만들지 못했다 — 팔을 control 로 두지 않는다")
    return blk


_BLOCKS = {"floor": (floor_block,), "transit": (transit_block,), "hourly": (_hourly_block,),
           "all": (floor_block, transit_block, _hourly_block), "control": ()}


# ── 한 번의 학습(팔 × 시드) ────────────────────────────────────────────

def run_one(arm: str, seed: int, out_dir: Path) -> dict:
    from ml.training import train_gnn as tg
    blocks = _BLOCKS[arm]
    orig_features, orig_split = tg._features, tg._split
    info: dict = {}

    def features(nodes, edges, **kw):
        x, names = orig_features(nodes, edges, **kw)
        base_n = len(names)
        for fn in blocks:
            b, nm = fn(nodes)
            if len(b) != len(x) or not np.isfinite(b).all():
                raise RuntimeError(f"{fn.__name__}: 행 수 불일치 또는 비유한 값")
            x = np.column_stack([x, b]).astype(np.float32)
            names = names + list(nm)
        info.update(base_features=base_n, added_features=len(names) - base_n, added_names=names[base_n:])
        return x, names

    def split(y, rng):                      # 시드와 무관하게 분할은 고정
        return orig_split(y, np.random.default_rng(SPLIT_SEED))

    def log_mlflow(metrics, params):         # 서빙 실험(industry_gnn)과 섞지 않는다
        try:
            import mlflow
        except ImportError:
            return
        mlflow.set_tracking_uri((ROOT / "ml" / "mlruns").as_uri())
        mlflow.set_experiment("industry_detail_features")
        with mlflow.start_run(run_name=f"{arm}-s{seed}"):
            mlflow.log_params({**params, "arm": arm, "init_seed": seed, "split_seed": SPLIT_SEED})
            mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})

    tg._features, tg._split, tg._log_mlflow, tg.SEED = features, split, log_mlflow, seed
    out_dir.mkdir(parents=True, exist_ok=True)
    dump = out_dir / f"{arm}_s{seed}_preds.json"
    try:
        metrics = tg.train(label_level="business_detail", epochs=EPOCHS, patience=PATIENCE, hidden=HIDDEN,
                           save=False, resume=False, ckpt_every=0, dump_preds=str(dump))
    finally:
        tg._features, tg._split = orig_features, orig_split
    run = {"arm": arm, "init_seed": seed, "split_seed": SPLIT_SEED, "created_at": datetime.now(timezone.utc).isoformat(),
           **info, "metrics": {k: v for k, v in metrics.items() if k not in ("per_class", "test_top3_paired")}}
    (out_dir / f"{arm}_s{seed}_run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    return run


def run_all(work_dir: Path, arms=ARMS, seeds=INIT_SEEDS, retries: int = 2) -> None:
    """팔×시드마다 **별도 프로세스**로 돌린다 — 이 PC 는 세그폴트가 잦아 한 판이 죽어도 이어진다.

    이미 산출물이 있으면 건너뛴다. 실패는 같은 명령을 최대 `retries` 번 다시 시도하고 그래도
    안 되면 중단한다(원인을 숨기고 다음으로 넘어가지 않는다).
    """
    env_note = "OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8"
    for seed in seeds:
        for arm in arms:
            if (work_dir / f"{arm}_s{seed}_run.json").exists():
                print(f"[skip] {arm} s{seed}")
                continue
            cmd = [sys.executable, "-u", "-m", "ml.training.industry_detail_features", "run",
                   "--arm", arm, "--seed", str(seed), "--work-dir", str(work_dir)]
            for attempt in range(1, retries + 2):
                print(f"[run] {arm} s{seed} 시도 {attempt}/{retries + 1}  ({env_note})", flush=True)
                if subprocess.run(cmd, cwd=ROOT).returncode == 0:
                    break
            else:
                raise SystemExit(f"{arm} s{seed}: {retries + 1}회 모두 실패 — 중단")


# ── 집계 · 부트스트랩 ──────────────────────────────────────────────────

def cluster_bootstrap(values: np.ndarray, clusters: np.ndarray, n_boot: int = BOOT_N, seed: int = 0) -> dict:
    """노드별 값(0/1 또는 차이)의 평균에 대한 **거점 군집** 부트스트랩 95% 구간.

    같은 거점의 자리는 독립이 아니므로 거점 단위로 재표본한다. 표본 0 은 산출 불가(null).
    """
    values = np.asarray(values, float)
    n = len(values)
    if n == 0:
        return {"n": 0, "n_clusters": 0, "mean": None, "ci95": None}
    uniq, inv = np.unique(clusters, return_inverse=True)
    sums = np.bincount(inv, weights=values, minlength=len(uniq))
    cnts = np.bincount(inv, minlength=len(uniq)).astype(float)
    k = len(uniq)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, k, size=(n_boot, k))
    means = sums[idx].sum(1) / cnts[idx].sum(1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"n": n, "n_clusters": int(k), "mean": float(values.mean()),
            "ci95": [float(lo), float(hi)]}


def verdict(ci, positive: str, negative: str) -> str | None:
    """구간이 0 을 품으면 구분 불가. 구간이 없으면(표본 0) null."""
    if ci is None:
        return None
    return positive if ci[0] > 0 else negative if ci[1] < 0 else "구분불가"


def _load_arm(work_dir: Path, arm: str) -> tuple[list[dict], list[dict]]:
    runs, dumps = [], []
    for seed in INIT_SEEDS:
        runs.append(json.loads((work_dir / f"{arm}_s{seed}_run.json").read_text(encoding="utf-8")))
        dumps.append(json.loads((work_dir / f"{arm}_s{seed}_preds.json").read_text(encoding="utf-8"))["test_rows"])
    return runs, dumps


def build_report(work_dir: Path, n_boot: int = BOOT_N) -> dict:
    from data.config.industry_details import DETAILS
    arms: dict = {}
    ref_ids = None
    for arm in ARMS:
        runs, dumps = _load_arm(work_dir, arm)
        ids = [r["node_id"] for r in dumps[0]]
        for d in dumps:
            if [r["node_id"] for r in d] != ids:
                raise RuntimeError(f"{arm}: 시드 간 test 노드가 다르다 — 분할이 고정되지 않았다")
        if ref_ids is None:
            ref_ids = ids
        elif ids != ref_ids:
            raise RuntimeError(f"{arm}: control 과 test 노드가 다르다")
        arms[arm] = {"runs": runs,
                     "hit": np.mean([[r["hit_top3"] for r in d] for d in dumps], axis=0),   # 시드 평균 적중률
                     "hit_by_seed": np.array([[r["hit_top3"] for r in d] for d in dumps], float),
                     "prior": np.array([r["prior_hit_top3"] for r in dumps[0]], float),
                     "y": np.array([r["y"] for r in dumps[0]]), "district": np.array([r["district"] for r in dumps[0]])}
    # 클래스 코드 → 키: 학습기는 sorted(unique(키)) 로 인덱싱한다
    from ml.training import train_gnn as tg
    nodes, edges = tg.load_graph()
    nodes = nodes.reset_index(drop=True)
    nodes, _, _ = tg._label_population(nodes, edges, "business_detail")
    _, classes = tg._labels(nodes, "business_detail")
    ctrl = arms["control"]
    y, did = ctrl["y"], ctrl["district"]

    def block(arm: str, mask: np.ndarray) -> dict:
        a = arms[arm]
        m, p, c = a["hit"][mask], a["prior"][mask], ctrl["hit"][mask]
        d = did[mask]
        n = int(mask.sum())
        if n == 0:
            return {"test_n": 0, "model_top3": None, "baseline_top3": None, "vs_baseline": None, "vs_control": None,
                    "model_top3_by_seed": None}
        vs_base = cluster_bootstrap(m - p, d, n_boot, 1)
        out = {"test_n": n, "n_clusters": vs_base["n_clusters"],
               "model_top3": float(m.mean()), "baseline_top3": float(p.mean()),
               "model_top3_by_seed": [float(h[mask].mean()) for h in a["hit_by_seed"]],
               "vs_baseline": {"diff": vs_base["mean"], "ci95": vs_base["ci95"],
                               "verdict": verdict(vs_base["ci95"], "기준선 상회", "기준선 열위")}}
        if arm == "control":
            out["vs_control"] = None
        else:
            vs_ctrl = cluster_bootstrap(m - c, d, n_boot, 2)
            out["vs_control"] = {"diff": vs_ctrl["mean"], "ci95": vs_ctrl["ci95"],
                                 "verdict": verdict(vs_ctrl["ci95"], "보강 우위", "보강 열위")}
        return out

    per_class = []
    for item in DETAILS:
        k = item["key"]
        row = {"key": k, "label": item["label"], "parent": item["parent"]}
        if k not in classes:
            row.update(status="산출 불가(학습 표본 없음)", arms={a: None for a in ARMS})
        else:
            mask = y == classes.index(k)
            row["status"] = "평가" if mask.any() else "산출 불가(test 표본 0)"
            row["arms"] = {a: block(a, mask) for a in ARMS}
        per_class.append(row)

    all_mask = np.ones(len(y), bool)
    overall = {a: block(a, all_mask) for a in ARMS}
    for a in ARMS:
        runs = arms[a]["runs"]
        overall[a]["val_best_top1_by_seed"] = [r["metrics"]["val_best"] for r in runs]
        overall[a]["test_top1_by_seed"] = [r["metrics"]["test_top1"] for r in runs]
        overall[a]["features"] = runs[0]["metrics"]["features"]
        overall[a]["added_names"] = runs[0].get("added_names", [])

    # 층 정보가 있는 자리 / 없는 자리로 나눠 본다. 이득이 '층 값'에서 오는지, 아니면 층이 비어 있다는
    # 사실(등록 형태)에서 오는지 가르는 진단이다 — 공실 자리는 층이 알려져 있으므로 '있는 자리'가 서빙과 닮았다.
    pos = {nid: i for i, nid in enumerate(nodes["node_id"])}
    known = np.array([parse_floor(nodes["floor"].iloc[pos[nid]])[0] for nid in ref_ids])
    floor_split = {}
    for label, mask in (("floor_known", known), ("floor_unknown", ~known)):
        floor_split[label] = {a: block(a, mask) for a in ("control", "floor", "all")}

    prior = json.loads(PRIOR_REPORT.read_text(encoding="utf-8"))
    files = [ROOT / "data/gold/platform13" / f"platform_store_graph_{p}.parquet" for p in ("nodes", "edges")]
    sha = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    sha["page_bus_stops.json"] = hashlib.sha256(BUS_JSON.read_bytes()).hexdigest()
    ctrl_s42 = arms["control"]["runs"][0]["metrics"]
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "세부 업종 그래프에 입지 피처 묶음을 얹었을 때 같은 분할·같은 거점 사전분포 기준선 대비 변화. 서빙 연결·추천 활성화 판단 아님",
        "inputs_sha256": sha,
        "inputs_match_prior_report": all(prior["inputs_sha256"].get(k) == sha[k] for k in prior["inputs_sha256"]),
        "parameters": {"epochs": EPOCHS, "patience": PATIENCE, "hidden": HIDDEN, "split_seed": SPLIT_SEED,
                       "init_seeds": list(INIT_SEEDS), "bootstrap_n": n_boot, "bootstrap_unit": "district(거점) 군집",
                       "model_selection": "val Top-1 조기종료(학습기 기본). test 는 선택에 쓰지 않음",
                       "save": False, "resume": False, "ckpt_every": 0},
        "reproduces_prior_report": {
            "prior_test_top3": prior["metrics"]["test_top3"], "control_seed42_test_top3": ctrl_s42["test_top3"],
            "prior_baseline_top3": prior["metrics"]["baseline_district_prior_top3"],
            "control_seed42_baseline_top3": ctrl_s42["baseline_district_prior_top3"],
            "match": ctrl_s42["test_top3"] == prior["metrics"]["test_top3"]},
        "prior_report_per_class_top3": {r["key"]: {"model": r["top3"], "baseline": r["baseline_top3"], "test_n": r["test_n"]}
                                        for r in prior["metrics"]["per_class"]},
        "bundles": {"floor": "노드 floor 파싱 5열", "transit": "버스 정류소 300m 승하차 4열(page_bus_stops.json)",
                    "hourly": "행정동 24시간 생활인구 10열(_adong_hour_block)", "all": "세 묶음 전부"},
        "overall": overall,
        "floor_known_split": floor_split,
        "per_class": per_class,
        "reading_rules": [
            "시드 3개의 적중률을 노드별로 평균한 뒤 거점 군집 부트스트랩을 한다. 구간에는 test 표본 변동만 담기고 학습 시드 변동은 model_top3_by_seed 로 따로 본다.",
            "구간이 0 을 품으면 구분불가. 클래스 24개 × 팔 4개를 보므로 5% 수준의 우연한 '우위'가 섞인다 — 다중비교 보정을 하지 않았다.",
            "test_n 이 작거나 n_clusters 가 적은 클래스의 구간은 거점 몇 곳에 좌우된다.",
            "현존 점포 업종 분류 성능이며 매출·생존·상권 추천 정답률이 아니다.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--arm", choices=ARMS, required=True)
    r.add_argument("--seed", type=int, required=True); r.add_argument("--work-dir", type=Path, default=WORK_DIR)
    a = sub.add_parser("run-all"); a.add_argument("--work-dir", type=Path, default=WORK_DIR)
    a.add_argument("--arms", default=",".join(ARMS)); a.add_argument("--seeds", default=",".join(map(str, INIT_SEEDS)))
    p = sub.add_parser("report"); p.add_argument("--work-dir", type=Path, default=WORK_DIR)
    p.add_argument("--output", type=Path, required=True); p.add_argument("--bootstrap", type=int, default=BOOT_N)
    args = ap.parse_args()
    if args.cmd == "run":
        run_one(args.arm, args.seed, args.work_dir)
    elif args.cmd == "run-all":
        run_all(args.work_dir, tuple(args.arms.split(",")), tuple(int(s) for s in args.seeds.split(",")))
    else:
        if args.output.exists():
            raise FileExistsError(f"기존 실험 기록 보존: {args.output}")
        rep = build_report(args.work_dir, args.bootstrap)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[report] {args.output}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
