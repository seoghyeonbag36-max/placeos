"""세부 업종 재학습 실험. 기존 모델·서빙 JSON은 교체하지 않는다.

OMP_NUM_THREADS=1 python -m ml.training.industry_detail_experiment
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def run(epochs: int, patience: int, hidden: int, output: Path) -> dict:
    from ml.training.train_gnn import train
    if output.exists():
        raise FileExistsError(f"기존 실험 기록 보존: {output}")
    root = Path(__file__).resolve().parents[2]
    paths = [root / "data/gold/platform13" / f"platform_store_graph_{part}.parquet" for part in ("nodes", "edges")]
    inputs = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    metrics = train(label_level="business_detail", epochs=epochs, patience=patience, hidden=hidden,
                    save=False, resume=False, ckpt_every=0)
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "inputs_sha256": inputs,
              "parameters": {"epochs": epochs, "patience": patience, "hidden": hidden},
              "serving_status": "review_required", "metrics": metrics,
              "limitations": ["현존 점포 업종 분류 실험이며 매출·생존 예측이 아님",
                              "기존 노드 분할 검증: 미관측 상권·미래 시점 일반화 검증은 별도 필요",
                              "같은 학습/테스트 분할의 거점 사전분포와 비교. 공개 여부 미판정"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--patience", type=int, default=15)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--output", type=Path, default=Path("ml/reports/industry_detail_experiment.json"))
    args = ap.parse_args()
    run(args.epochs, args.patience, args.hidden, args.output)
