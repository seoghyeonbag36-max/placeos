"""GNN 입력 1점포 1행 잠금 (2026-09-27, 창업자 결정 안 A).

겹치는 거점에 같은 점포가 거점마다 한 행씩 있으면 같은 점포가 train·test 양쪽에 들어가
Top-3 가 부풀려진다(누수). 여기서 잠그는 것은 **GNN 입력에서** 1점포 1행이 되고, 귀속이
가장 가까운 거점 중심이라는 성질이다. → ml/training/graph_dedup.py
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

pd = pytest.importorskip("pandas")

from ml.training.graph_dedup import one_row_per_store  # noqa: E402

CENTERS = {"a": (127.00, 37.50), "b": (127.01, 37.50)}


def _nodes(rows):
    return pd.DataFrame(rows, columns=["node_id", "district_id", "lon", "lat"])


def test_shared_store_goes_to_the_nearest_hub_center() -> None:
    nodes = _nodes([
        ("s1", "a", 127.008, 37.50),   # b 중심에 더 가깝다 → b 로
        ("s1", "b", 127.008, 37.50),
        ("s2", "a", 127.001, 37.50),   # a 에 더 가깝다 → a 로
        ("s2", "b", 127.001, 37.50),
        ("s3", "a", 127.000, 37.50),   # 겹치지 않는 점포는 그대로
    ])
    out, dropped = one_row_per_store(nodes, CENTERS)
    assert dropped == 2
    assert out["node_id"].is_unique
    got = dict(zip(out["node_id"], out["district_id"]))
    assert got == {"s1": "b", "s2": "a", "s3": "a"}


def test_no_duplicates_is_a_no_op() -> None:
    nodes = _nodes([("s1", "a", 127.0, 37.5), ("s2", "b", 127.01, 37.5)])
    out, dropped = one_row_per_store(nodes, CENTERS)
    assert dropped == 0
    assert out.equals(nodes)


def test_equal_distance_is_deterministic() -> None:
    """거리가 같으면 slug 사전순 — 돌릴 때마다 귀속이 바뀌면 분할도 바뀐다."""
    nodes = _nodes([("s1", "b", 127.005, 37.50), ("s1", "a", 127.005, 37.50)])
    out, _ = one_row_per_store(nodes, CENTERS)
    assert out["district_id"].tolist() == ["a"]


def test_unknown_hub_center_loses_to_a_known_one() -> None:
    nodes = _nodes([("s1", "zz", 127.0, 37.5), ("s1", "a", 127.0, 37.5)])
    out, _ = one_row_per_store(nodes, CENTERS)
    assert out["district_id"].tolist() == ["a"]


def test_gnn_loader_and_building_join_use_it() -> None:
    """학습기가 로더에서 줄이고, 건물 피처를 (node_id, 거점) 으로 붙여야 한다."""
    src = (ROOT / "ml" / "training" / "train_gnn.py").read_text(encoding="utf-8")
    body = src.split("def load_graph(")[1].split("\ndef ")[0]
    assert "one_row_per_store(" in body, "로더가 중복을 걷지 않는다 — train·test 누수"
    assert 'set_index(["node_id", "district_id"])' in src, (
        "건물 피처를 node_id 하나로 색인한다 — 겹치는 거점에서 중복 색인으로 죽는다")
