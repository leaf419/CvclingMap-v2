"""点对点直接搜索：Dijkstra + 用户画像多变体路径

通勤者：单次 cost_composite Dijkstra（高效点对点）。
其他画像（游客/健身/家庭）：基于现有四维边权（safety/comfort/scenery/cost）
生成多个加权变体，各跑一次 Dijkstra，去重后按画像偏好得分排序，
返回 top-K 条推荐路线。

比 NSGA-II 快 2-3 个数量级（秒级 vs 分钟级）。
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import networkx as nx
import numpy as np

from algorithm.routing.nsga2_search import _find_nearest_node
from algorithm.routing.recommender import USER_TEMPLATES, compute_route_score, UserProfile

# ── 默认返回路线数 ──
DEFAULT_TOP_K = {"commuter": 2, "tourist": 5, "fitness": 5, "family": 4}


# ── 各画像的边权变体生成策略 ──
# 每种变体 = (标签, edge_weight_function)，返回该边的新权重
def _variant_weight(G, u, v, label: str) -> float:
    """根据变体标签计算边的自定义权重，值越低越优先走该边"""
    base = G[u][v].get("cost_composite", 50.0)
    w_safety = G[u][v].get("w_safety", 0.5)
    w_scenery = G[u][v].get("w_scenery", 0.5)
    w_comfort = G[u][v].get("w_comfort", 0.5)

    variant_handlers = {
        # 基础
        "shortest":       base,
        "shortest_len":   G[u][v].get("length", 100.0),          # 纯距离最短
        # 安全向
        "safe":           base * max(0.25, 2.5 - w_safety * 2.5),
        "safety_first":   base * max(0.15, 3.5 - w_safety * 4.0),
        "ultra_safe":     base * max(0.10, 4.0 - w_safety * 5.0),
        # 风景向（不同绕行程度）
        "scenic":         base * max(0.25, 2.5 - w_scenery * 2.5),
        "scenic_first":   base * max(0.15, 3.5 - w_scenery * 4.0),
        "moderate_scenic": base * max(0.20, 2.8 - w_scenery * 3.0),  # 中等绕行
        "long_scenic":    base * max(0.08, 4.0 - w_scenery * 5.0),   # 长距离绕行风景
        # 舒适向
        "comfort":        base * max(0.25, 2.5 - w_comfort * 2.5),
        "long_comfort":   base * max(0.10, 3.5 - w_comfort * 4.0),   # 长距离舒适
        # 混合
        "balance":        base * (1.8 - (w_safety * 0.4 + w_scenery * 0.4 + w_comfort * 0.3)),
        "leisure":        base * max(0.20, 3.0 - w_comfort * 3.0 - w_scenery * 1.5),
        "long_ride":      base * max(0.30, 1.5 - w_comfort * 0.8 - w_scenery * 0.6),
        "any_path":       base * 0.3,                                # 最大绕行（权重极低）
    }
    return max(variant_handlers.get(label, base), 0.1 * base)


# 各画像的搜索变体（覆盖短/中/长不同长度范围）
PROFILE_VARIANTS = {
    "commuter": ["shortest", "shortest_len"],
    "tourist":  ["scenic_first", "moderate_scenic", "long_scenic", "balance", "shortest_len"],
    "fitness":  ["long_ride", "long_scenic", "long_comfort", "comfort", "scenic", "any_path"],
    "family":   ["ultra_safe", "safety_first", "safe", "shortest_len"],
}


def _single_dijkstra(
    G: nx.Graph,
    source: tuple,
    target: tuple,
    weight_label: str,
) -> Optional[list]:
    """单次 Dijkstra 搜索，返回节点序列或 None"""
    # 构建临时边权
    for u, v in G.edges():
        G[u][v]["_tmp_weight"] = _variant_weight(G, u, v, weight_label)
    try:
        path = nx.shortest_path(G, source, target, weight="_tmp_weight")
        return path
    except (nx.NetworkXNoPath, nx.NodeNotFound, KeyError):
        return None


def _routes_are_similar(r1: list, r2: list, threshold: float = 0.75) -> bool:
    """判断两条路线是否相似（共享边比例 >= threshold 视为重复）"""
    if not r1 or not r2:
        return False
    edges1 = set(zip(r1[:-1], r1[1:]))
    edges2 = set(zip(r2[:-1], r2[1:]))
    if not edges1 or not edges2:
        return False
    intersection = edges1 & edges2
    return len(intersection) / max(len(edges1), len(edges2)) >= threshold


def _deduplicate_routes(routes: List[list], threshold: float = 0.3) -> List[list]:
    """去重：按路线长度排序，保留差异足够大的路线（共享边 < 30% 视为不同）"""
    if not routes:
        return []
    sorted_routes = sorted(routes, key=len, reverse=True)
    keep: List[list] = []
    for r in sorted_routes:
        if all(not _routes_are_similar(r, k, threshold) for k in keep):
            keep.append(r)
    return keep


def direct_search(
    G: nx.Graph,
    source: Tuple[float, float],
    target: Tuple[float, float],
    user_template: str = "commuter",
    top_k: Optional[int] = None,
) -> Tuple[List[list], Optional[list]]:
    """点对点多变体搜索主入口

    Args:
        G: NetworkX 图（由 build_nx_graph 构建，边含 cost_composite/w_safety/w_scenery/w_comfort）
        source: 起点 (lon, lat)
        target: 终点 (lon, lat)
        user_template: 用户画像名 (commuter/tourist/fitness/family)
        top_k: 返回路线数，默认按画像取最佳数量

    Returns:
        (routes, best_route)：routes 为按画像偏好得分降序的路线列表，best_route 为最优路线
    """
    if top_k is None:
        top_k = DEFAULT_TOP_K.get(user_template, 3)

    profile = USER_TEMPLATES.get(user_template, USER_TEMPLATES["commuter"])
    variants = PROFILE_VARIANTS.get(user_template, ["shortest"])

    # 0. 坐标吸附到最近图节点
    source_node = _find_nearest_node(G, source)
    target_node = _find_nearest_node(G, target)

    # 1. 运行全部变体 Dijkstra
    raw_routes: List[list] = []
    for label in variants:
        path = _single_dijkstra(G, source_node, target_node, label)
        if path and len(path) >= 2:
            raw_routes.append(path)

    # 2. 去重
    unique = _deduplicate_routes(raw_routes)

    # 3. 按画像偏好得分排序
    if unique:
        scored = [(r, compute_route_score(r, G, profile)) for r in unique]
        scored.sort(key=lambda x: x[1], reverse=True)
        routes = [r for r, _ in scored[:top_k]]
        best = routes[0] if routes else None
    else:
        routes, best = [], None

    return routes, best
