"""HGT (Heterogeneous Graph Transformer) 模型定义 — PyG 2.8 兼容"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import HGTConv
from torch_geometric.data import HeteroData
import numpy as np


class BikeFlowGNN_v2(nn.Module):
    """异构图Transformer模型 (PyG 2.8+)

    PyG 2.8 HGTConv 行为:
        - out_dict 仅含作为边目标的节点类型（无消息到达的节点为None）
        - 需要自行跳过 None 值的节点类型
    """

    def __init__(
        self,
        metadata,
        hidden_dim: int = 64,
        num_heads: int = 4,
        num_layers: int = 2,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim

        self.lin_dict = nn.ModuleDict()
        for node_type in metadata[0]:
            self.lin_dict[node_type] = nn.Linear(hidden_dim, hidden_dim)

        self.convs = nn.ModuleList([
            HGTConv(hidden_dim, hidden_dim, metadata, heads=num_heads)
            for _ in range(num_layers)
        ])

        self.pref_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid()
        )

    def forward(self, x_dict, edge_index_dict):
        """前向传播 (兼容 PyG 2.8: 跳过None输出)"""
        x_dict = {nt: self.lin_dict[nt](x.float()) for nt, x in x_dict.items()}

        for conv in self.convs:
            out = conv(x_dict, edge_index_dict)
            # PyG 2.8: out只含作为边目标的节点类型; 未更新的保留原值
            for nt, val in out.items():
                if val is not None:
                    x_dict[nt] = val.relu()

        return x_dict

    def predict_preference(self, segment_emb, src_idx, dst_idx):
        """预测segment对的骑行偏好分数"""
        src_emb = segment_emb[src_idx]
        dst_emb = segment_emb[dst_idx]
        paired = torch.cat([src_emb, dst_emb], dim=-1)
        return self.pref_head(paired).squeeze(-1)


def create_hetero_data(
    nodes: dict,
    edges: dict,
    node_counts: dict,
    hidden_dim: int = 64,
) -> HeteroData:
    """从节点特征和边索引创建PyG HeteroData"""
    data = HeteroData()

    for node_type, features in nodes.items():
        if features is not None and len(features) > 0:
            if features.shape[1] < hidden_dim:
                padding = np.zeros(
                    (features.shape[0], hidden_dim - features.shape[1]),
                    dtype=np.float32
                )
                features = np.hstack([features, padding])
            elif features.shape[1] > hidden_dim:
                features = features[:, :hidden_dim]
            data[node_type].x = torch.tensor(features, dtype=torch.float32)
        else:
            count = node_counts.get(node_type, 0)
            data[node_type].x = torch.randn(count, hidden_dim)

    for edge_type, (src, dst) in edges.items():
        if len(src) > 0:
            data[edge_type].edge_index = torch.tensor(
                np.stack([src, dst]), dtype=torch.long
            )

    return data
