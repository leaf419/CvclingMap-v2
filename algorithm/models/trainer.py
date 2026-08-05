"""NeighborSampler mini-batch训练管道"""
import torch
import torch.nn.functional as F
from torch_geometric.loader import NeighborLoader
from torch_geometric.data import HeteroData
import numpy as np
from typing import Tuple
import time

from algorithm.config import TRAIN_CFG
from algorithm.models.hgt_model import BikeFlowGNN_v2


def create_train_loader(
    hetero_data: HeteroData,
    train_mask: torch.Tensor = None,
) -> NeighborLoader:
    """创建mini-batch数据加载器

    Args:
        hetero_data: 完整的HeteroData
        train_mask: segment节点的训练掩码

    Returns:
        NeighborLoader实例
    """
    if train_mask is None:
        n_seg = hetero_data["segment"].x.shape[0]
        train_mask = torch.ones(n_seg, dtype=torch.bool)

    num_neighbors = {}
    for et in hetero_data.edge_types:
        l1 = TRAIN_CFG.num_neighbors_l1.get(et, 5)
        l2 = TRAIN_CFG.num_neighbors_l2.get(et, 3)
        num_neighbors[et] = [l1, l2]

    loader = NeighborLoader(
        hetero_data,
        num_neighbors=num_neighbors,
        batch_size=TRAIN_CFG.batch_size,
        input_nodes=("segment", train_mask),
        shuffle=True,
        num_workers=TRAIN_CFG.num_workers,
    )

    return loader


def generate_preference_labels(
    hetero_data: HeteroData,
    cost_col: str = "cost_composite",
) -> torch.Tensor:
    """基于综合成本生成偏好标签 (自监督)

    高成本边 → 低偏好(0), 低成本边 → 高偏好(1)

    Args:
        hetero_data: 含segment连接边的HeteroData
        cost_col: 成本列名

    Returns:
        偏好标签 tensor(E,)
    """
    edge_type = ("segment", "connected_to", "segment")
    if edge_type not in hetero_data.edge_types:
        return torch.tensor([])

    costs = hetero_data[edge_type].get(cost_col)
    if costs is None:
        n_edges = hetero_data[edge_type].edge_index.shape[1]
        return torch.rand(n_edges)

    costs = costs.float()
    normalized = (costs - costs.min()) / (costs.max() - costs.min() + 1e-8)
    labels = 1.0 - normalized
    return labels


def train_model(
    hetero_data: HeteroData,
    train_mask: torch.Tensor = None,
    device: str = "cuda",
) -> Tuple[BikeFlowGNN_v2, list]:
    """完整训练流程

    Args:
        hetero_data: PyG HeteroData
        train_mask: 训练集segment掩码
        device: 'cuda' 或 'cpu'

    Returns:
        (训练好的模型, loss历史)
    """
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    print(f"设备: {device}")
    print(f"节点类型: {hetero_data.node_types}")
    print(f"边类型: {hetero_data.edge_types}")

    train_loader = create_train_loader(hetero_data, train_mask)
    print(f"每epoch batch数: {len(train_loader)}")

    metadata = (hetero_data.node_types, hetero_data.edge_types)
    model = BikeFlowGNN_v2(
        metadata,
        hidden_dim=TRAIN_CFG.hidden_dim,
        num_heads=TRAIN_CFG.num_heads,
        num_layers=TRAIN_CFG.num_layers
    ).to(device)

    if TRAIN_CFG.use_compile and hasattr(torch, "compile"):
        model = torch.compile(model, dynamic=True)
        print("已启用 torch.compile")

    optimizer = torch.optim.Adam(model.parameters(), lr=TRAIN_CFG.lr)
    use_fp16 = TRAIN_CFG.use_fp16 and device == "cuda"
    scaler = torch.cuda.amp.GradScaler(enabled=use_fp16)

    loss_history = []
    start_time = time.time()

    for epoch in range(TRAIN_CFG.epochs):
        model.train()
        total_loss = 0
        n_batches = 0

        for batch in train_loader:
            batch = batch.to(device)
            optimizer.zero_grad()

            with torch.cuda.amp.autocast(enabled=use_fp16):
                x_dict = model(batch.x_dict, batch.edge_index_dict)

                edge_type = ("segment", "connected_to", "segment")
                if edge_type in batch.edge_types and batch[edge_type].edge_index.shape[1] > 0:
                    ei = batch[edge_type].edge_index
                    pred = model.predict_preference(x_dict["segment"], ei[0], ei[1])
                    labels = torch.rand(ei.shape[1], device=device)
                    loss = F.binary_cross_entropy(pred, labels.float())
                else:
                    target = batch["segment"].x
                    loss = F.mse_loss(x_dict["segment"], target)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            total_loss += loss.item()
            n_batches += 1

        avg_loss = total_loss / max(n_batches, 1)
        loss_history.append(avg_loss)

        if (epoch + 1) % 10 == 0:
            elapsed = time.time() - start_time
            print(f"Epoch {epoch+1}/{TRAIN_CFG.epochs}: loss={avg_loss:.4f}, "
                  f"elapsed={elapsed:.1f}s")

    total_time = time.time() - start_time
    print(f"\n训练完成: {TRAIN_CFG.epochs} epochs, 总耗时 {total_time:.1f}s "
          f"({total_time/60:.1f}分钟)")

    return model, loss_history


def export_embeddings(
    model: BikeFlowGNN_v2,
    hetero_data: HeteroData,
    device: str = "cuda",
) -> dict:
    """导出训练后的节点嵌入

    Args:
        model: 训练好的模型
        hetero_data: 完整图数据
        device: 设备

    Returns:
        {node_type: ndarray(N, hidden_dim)} 嵌入字典
    """
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    model.eval()
    hetero_data = hetero_data.to(device)

    with torch.no_grad():
        embeddings = model(hetero_data.x_dict, hetero_data.edge_index_dict)

    result = {}
    for nt, emb in embeddings.items():
        result[nt] = emb.cpu().numpy()

    return result
