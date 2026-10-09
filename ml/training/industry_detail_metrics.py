"""동일 테스트 표본의 세부 업종별 관측. 공개 임계값을 임의로 정하지 않는다."""
from __future__ import annotations

import numpy as np

from data.config.industry_details import DETAILS


def per_class_metrics(classes: list[str], y: np.ndarray, pred: np.ndarray,
                      train: np.ndarray, test: np.ndarray,
                      hit: np.ndarray, baseline_hit: np.ndarray) -> list[dict]:
    out = []
    for item in DETAILS:
        key = item["key"]
        if key not in classes:
            out.append({"key": key, "train_n": 0, "test_n": 0, "status": "no_training_class",
                        "precision": None, "recall": None, "top3": None, "baseline_top3": None})
            continue
        k = classes.index(key)
        actual, predicted = test & (y == k), test & (pred == k)
        n, pn = int(actual.sum()), int(predicted.sum())
        tp = int((actual & predicted).sum())
        out.append({"key": key, "train_n": int((train & (y == k)).sum()), "test_n": n,
                    "status": "evaluation_only" if n else "no_test_samples",
                    "precision": tp / pn if pn else None, "recall": tp / n if n else None,
                    "top3": float(hit[actual].mean()) if n else None,
                    "baseline_top3": float(baseline_hit[actual].mean()) if n else None})
    return out
