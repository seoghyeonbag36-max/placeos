"""GNN 입력 — 겹치는 거점의 같은 점포를 **1점포 1행**으로 줄인다.

torch 없이 import 되도록 `train_gnn` 에서 떼어 냈다(data/tests/test_gnn_dedup.py).

## 왜 (2026-09-27 실측)

09-15 에 점포 노드 저장층을 카카오 → 상가정보로 옮긴 뒤(8432cbc), 거점마다 반경 안의
점포를 따로 받아 붙이므로 반경이 겹치는 거점(홍대·연남 · 압구정로데오·도산 · 강남·
테헤란로 …)에 **같은 점포가 거점마다 한 행씩** 들어간다. 라벨 있는 노드 106,865행 중
실제 점포는 88,239곳 — 34,921행(32.7%)이 중복 묶음이다.

GNN 에서 이게 두 가지를 망친다:
  ① **누수** — 같은 점포가 거점 A 로는 train, 거점 B 로는 test 에 들어갈 수 있다.
     위치·건물 피처가 같은 쌍둥이를 train 에서 본 셈이라 Top-3 가 부풀려진다.
  ② **고립 노드** — 엣지가 `node_id` 로 이어지고 색인이 `{node_id: 위치}` 라 중복 중
     마지막 행만 이웃을 받는다.

## 결정 (창업자 2026-09-27, 안 A)

- **GNN 입력에서만** 줄인다. gold 그래프·사이드카는 그대로 둔다 — 그쪽 소비자(집계구
  배정·엣지·건물 피처)는 `node_id` 로 조인하므로 중복이 있어도 결과가 같다.
- 귀속은 **점포 좌표에서 가장 가까운 거점 중심**. 거리가 같으면 slug 사전순(결정적).
- 분할 함수(60/20/20 층화)는 바꾸지 않는다 — 줄어든 모집단 위에서 그대로 돈다.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

_LAT0 = math.radians(37.55)   # 서울 — 경도 1도의 거리를 위도에 맞춰 줄인다(등거리 근사)


def one_row_per_store(nodes: pd.DataFrame,
                      centers: dict[str, tuple[float, float]]) -> tuple[pd.DataFrame, int]:
    """`node_id` 가 여러 거점에 걸린 행을 가장 가까운 거점 중심 하나로 줄인다.

    centers: slug → (경도, 위도). 중심을 모르는 거점의 행은 거리 무한대로 밀린다.
    반환: (줄인 노드 — 원래 행 순서 유지, 걷어 낸 행 수)
    """
    if not nodes["node_id"].duplicated().any():
        return nodes, 0
    cx = nodes["district_id"].map(lambda d: centers.get(d, (np.nan, np.nan))[0])
    cy = nodes["district_id"].map(lambda d: centers.get(d, (np.nan, np.nan))[1])
    d2 = (((nodes["lon"] - cx) * math.cos(_LAT0)) ** 2 + (nodes["lat"] - cy) ** 2)
    d2 = d2.fillna(np.inf)
    order = (nodes.assign(_d2=d2.to_numpy(), _pos=np.arange(len(nodes)))
             .sort_values(["node_id", "_d2", "district_id"], kind="mergesort"))
    kept = order.drop_duplicates("node_id", keep="first").sort_values("_pos")
    dropped = len(nodes) - len(kept)
    return kept.drop(columns=["_d2", "_pos"]).reset_index(drop=True), dropped
