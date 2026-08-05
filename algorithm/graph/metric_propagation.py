"""街景指标从观测点到街道段的KDTree空间传播"""
import numpy as np
import geopandas as gpd
from scipy.spatial import cKDTree

from algorithm.config import GRAPH_CFG


def propagate_metrics_to_segments(
    obs_gdf: gpd.GeoDataFrame,
    segments_gdf: gpd.GeoDataFrame,
    k: int = None,
    max_dist: float = None,
) -> gpd.GeoDataFrame:
    """将观测点指标传播到街道段

    策略: 每个segment取最近的k个观测点的距离反比加权平均

    Args:
        obs_gdf: 观测点GeoDataFrame (含s_/f_/v_/x_前缀的指标列)
        segments_gdf: 街道段GeoDataFrame
        k: 最近邻数
        max_dist: 最大传播距离(米)

    Returns:
        segments_gdf添加传播后的指标列 + has_observation标记
    """
    if k is None:
        k = GRAPH_CFG.propagation_k
    if max_dist is None:
        max_dist = GRAPH_CFG.propagation_max_dist

    obs_proj = obs_gdf.to_crs("EPSG:32650")
    seg_proj = segments_gdf.to_crs("EPSG:32650").copy()

    obs_coords = np.array([(g.x, g.y) for g in obs_proj.geometry])
    tree = cKDTree(obs_coords)

    seg_centers = np.array([
        (g.centroid.x, g.centroid.y) for g in seg_proj.geometry
    ])

    actual_k = min(k, len(obs_proj))
    distances, indices = tree.query(seg_centers, k=actual_k)

    if actual_k == 1:
        distances = distances.reshape(-1, 1)
        indices = indices.reshape(-1, 1)

    weights = 1.0 / (distances + 1e-6)
    weights = weights / weights.sum(axis=1, keepdims=True)

    metric_cols = [c for c in obs_proj.columns
                   if c.startswith(("s_", "f_", "v_", "x_"))]

    for col in metric_cols:
        obs_values = obs_proj[col].values
        obs_values = np.nan_to_num(obs_values, nan=0.0)
        seg_values = np.average(obs_values[indices], axis=1, weights=weights)
        seg_proj[col] = seg_values

    seg_proj["has_observation"] = distances[:, 0] < max_dist

    result = seg_proj.to_crs("EPSG:4326")
    return result
