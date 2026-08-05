"""HGT模型测试 — PyG 2.8 兼容"""
import pytest
import torch
import numpy as np
from torch_geometric.data import HeteroData
from algorithm.models.hgt_model import BikeFlowGNN_v2, create_hetero_data


def test_model_forward():
    """测试HGT前向传播"""
    metadata = (
        ["segment", "poi", "observation", "place", "station"],
        [
            ("segment", "connected_to", "segment"),
            ("observation", "observed_at", "segment"),
            ("poi", "nearby", "segment"),
        ]
    )

    model = BikeFlowGNN_v2(metadata, hidden_dim=32, num_heads=2, num_layers=2)

    x_dict = {
        "segment": torch.randn(10, 32),
        "poi": torch.randn(20, 32),
        "observation": torch.randn(5, 32),
        "place": torch.randn(8, 32),
        "station": torch.randn(3, 32),
    }
    edge_index_dict = {
        ("segment", "connected_to", "segment"): torch.randint(0, 10, (2, 15)),
        ("observation", "observed_at", "segment"): torch.randint(0, 10, (2, 5)),
        ("poi", "nearby", "segment"): torch.randint(0, 10, (2, 20)),
    }

    out = model(x_dict, edge_index_dict)
    assert "segment" in out
    assert out["segment"].shape == (10, 32)
    # place/station 不是边目标，特征保持不变
    assert out["place"].shape == (8, 32)


def test_preference_head():
    """测试偏好预测头"""
    # PyG 2.8 要求至少1个边类型作为目标接收消息
    metadata = (
        ["segment"],
        [("segment", "self", "segment")]
    )
    model = BikeFlowGNN_v2(metadata, hidden_dim=32, num_heads=2, num_layers=1)

    x_dict = {"segment": torch.randn(10, 32)}
    edge_index_dict = {
        ("segment", "self", "segment"): torch.tensor([[0], [0]]),
    }

    embeddings = model(x_dict, edge_index_dict)

    src = torch.tensor([0, 1, 2])
    dst = torch.tensor([1, 2, 3])
    pred = model.predict_preference(embeddings["segment"], src, dst)
    assert pred.shape == (3,)
    assert (pred >= 0).all() and (pred <= 1).all()


def test_create_hetero_data():
    """测试HeteroData创建"""
    nodes = {
        "segment": np.random.randn(10, 5).astype(np.float32),
        "poi": np.random.randn(20, 1).astype(np.float32),
    }
    edges = {
        ("segment", "connected_to", "segment"): (np.array([0, 1, 2]), np.array([1, 2, 3])),
        ("poi", "nearby", "segment"): (np.array([0, 1]), np.array([0, 1])),
    }
    node_counts = {"segment": 10, "poi": 20}

    hetero_data = create_hetero_data(nodes, edges, node_counts, hidden_dim=32)

    assert isinstance(hetero_data, HeteroData)
    assert "segment" in hetero_data.node_types
    assert hetero_data["segment"].x.shape[0] == 10
