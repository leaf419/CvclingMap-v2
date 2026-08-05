"""NSGA-II多目标路径搜索"""
import networkx as nx
import numpy as np
import geopandas as gpd
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import IntegerRandomSampling
from pymoo.optimize import minimize
from typing import List

from algorithm.config import NSGA2_CFG


def build_nx_graph(segments_gdf: gpd.GeoDataFrame) -> nx.Graph:
    """从segment GeoDataFrame构建NetworkX图

    Args:
        segments_gdf: 含 seg_id, length, cost_composite, w_* 列

    Returns:
        NetworkX无向图, 节点=路口, 边=街道段
    """
    G = nx.Graph()

    for _, row in segments_gdf.iterrows():
        geom = row.geometry
        if geom is None or len(geom.coords) < 2:
            continue

        u = (round(geom.coords[0][0], 6), round(geom.coords[0][1], 6))
        v = (round(geom.coords[-1][0], 6), round(geom.coords[-1][1], 6))

        G.add_edge(u, v, **{
            "length": row.get("length", geom.length),
            "cost_composite": row.get("cost_composite", 50.0),
            "f_traffic_stress": row.get("f_traffic_stress", 0.5),
            "v_beauty": row.get("v_beauty", 0.5),
            "w_safety": row.get("w_safety", 0.5),
            "w_scenery": row.get("w_scenery", 0.5),
            "w_comfort": row.get("w_comfort", 0.5),
            "pref_score": row.get("pref_score", 0.5),
            "seg_id": row.get("seg_id", 0),
        })

    return G


def evaluate_route(route: list, G: nx.Graph) -> List[float]:
    """评估路线的4个目标函数

    目标:
        f1: 总距离 (最小化)
        f2: 总交通压力 (最小化)
        f3: -总风景 (风景最大化→取负最小化)
        f4: -总偏好分 (偏好最大化→取负最小化)
    """
    if len(route) < 2:
        return [0, 0, 0, 0]

    edges = list(zip(route[:-1], route[1:]))
    total_dist = sum(G[u][v].get("length", 0) for u, v in edges)
    total_stress = sum(G[u][v].get("f_traffic_stress", 0) for u, v in edges)
    total_beauty = sum(G[u][v].get("v_beauty", 0) for u, v in edges)
    total_pref = sum(G[u][v].get("pref_score", 0) for u, v in edges)

    return [total_dist, total_stress, -total_beauty, -total_pref]


class RouteProblem(Problem):
    """NSGA-II路径优化问题"""

    def __init__(self, G: nx.Graph, source, target, max_len: int = 50):
        self.G = G
        self.source = source
        self.target = target
        self.max_len = max_len

        self.nodes = list(G.nodes())
        if source in self.nodes:
            self.nodes.remove(source)
        if target in self.nodes:
            self.nodes.remove(target)

        super().__init__(
            n_var=max_len - 2,
            n_obj=4,
            n_constr=0,
            xl=0,
            xu=max(len(self.nodes) - 1, 0),
            type_var=int,
        )

    def _decode(self, x):
        """解码决策变量为路径"""
        route = [self.source]
        for idx in x:
            if int(idx) < len(self.nodes):
                node = self.nodes[int(idx)]
                if node not in route:
                    route.append(node)
        route.append(self.target)
        return route

    def _evaluate(self, X, out, *args, **kwargs):
        """评估种群"""
        objectives = []
        for x in X:
            route = self._decode(x)
            valid = all(self.G.has_edge(route[i], route[i+1])
                       for i in range(len(route) - 1))
            if valid:
                obj = evaluate_route(route, self.G)
            else:
                obj = [1e6, 1e6, 1e6, 1e6]
            objectives.append(obj)

        out["F"] = np.array(objectives)


def _find_nearest_node(G, coord):
    """找到图中最近的节点（坐标非精确匹配时自动吸附；已是图中节点则直接返回）"""
    if coord in G:  # 传入的已是图中节点（如 int/tuple 节点键）
        return coord
    key = (round(coord[0], 6), round(coord[1], 6))
    if key in G:
        return key
    nodes = np.array(list(G.nodes()))
    dist = np.sqrt(np.sum((nodes - np.array(coord))**2, axis=1))
    return tuple(nodes[np.argmin(dist)])


def nsga2_search(
    G: nx.Graph,
    source,
    target,
    pop_size: int = None,
    n_gen: int = None,
) -> List[List]:
    """执行NSGA-II多目标路径搜索"""
    if pop_size is None:
        pop_size = NSGA2_CFG.pop_size
    if n_gen is None:
        n_gen = NSGA2_CFG.n_gen

    source = _find_nearest_node(G, source)
    target = _find_nearest_node(G, target)

    problem = RouteProblem(G, source, target)

    algorithm = NSGA2(
        pop_size=pop_size,
        sampling=IntegerRandomSampling(),
        crossover=SBX(prob=0.9, eta=15),
        mutation=PM(eta=20),
        eliminate_duplicates=True,
    )

    result = minimize(
        problem,
        algorithm,
        termination=("n_gen", n_gen),
        seed=42,
        verbose=False,
    )

    pareto_routes = []
    for x in result.X:
        route = problem._decode(x)
        valid = all(G.has_edge(route[i], route[i+1])
                   for i in range(len(route) - 1))
        if valid and len(route) >= 2:
            pareto_routes.append(route)

    if not pareto_routes and nx.has_path(G, source, target):
        shortest = nx.shortest_path(G, source, target, weight="cost_composite")
        pareto_routes.append(shortest)

    return pareto_routes
