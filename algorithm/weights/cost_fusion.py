"""四维边权加权融合为综合骑行成本"""
import geopandas as gpd
from algorithm.config import WEIGHT_CFG


def fuse_composite_cost(
    segments_gdf: gpd.GeoDataFrame,
    alpha: float = None,
    beta: float = None,
    gamma: float = None,
    delta: float = None,
) -> gpd.GeoDataFrame:
    """将四维边权融合为综合骑行成本C(e)

    公式: C(e) = length × (1 - (α·S + β·F + γ·V + δ·X))

    高权重(好路况) → 低成本; 长距离 → 高成本

    Args:
        segments_gdf: 含 w_safety, w_comfort, w_scenery, w_experience, length 列
        alpha/beta/gamma/delta: 四维权重

    Returns:
        添加 cost_composite 列
    """
    if alpha is None:
        alpha = WEIGHT_CFG.alpha
    if beta is None:
        beta = WEIGHT_CFG.beta
    if gamma is None:
        gamma = WEIGHT_CFG.gamma
    if delta is None:
        delta = WEIGHT_CFG.delta

    result = segments_gdf.copy()

    quality = (
        alpha * result["w_safety"] +
        beta * result["w_comfort"] +
        gamma * result["w_scenery"] +
        delta * result["w_experience"]
    )
    # 确保 quality 在 [0, 1] 范围内（权重可能因数值波动略超边界）
    quality = quality.clip(lower=0.0, upper=1.0)

    result["cost_composite"] = result["length"] * (1.0 - quality)
    result["cost_composite"] = result["cost_composite"].clip(lower=0.1)

    return result
