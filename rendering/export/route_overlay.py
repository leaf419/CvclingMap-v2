"""路线叠加与指标汇总

将 NSGA-II/Dijkstra 搜索到的路线转换为可视化叠加层，
计算路线级别的指标汇总。
"""
import json
import numpy as np
import networkx as nx
import geopandas as gpd
from shapely.geometry import LineString
from typing import List, Dict, Any
from pathlib import Path


def build_route_overlay(
    route: list,
    G: nx.Graph,
    segments_gdf: gpd.GeoDataFrame,
) -> Dict[str, Any]:
    """构建路线叠加数据"""
    if len(route) < 2:
        return {"geometry": None, "metrics": {}, "segments": []}

    coords = []
    seg_ids = []
    for u, v in zip(route[:-1], route[1:]):
        if G.has_edge(u, v):
            seg_ids.append(G[u][v].get("seg_id", None))
            u_pos = _node_pos(G, u)
            v_pos = _node_pos(G, v)
            if u_pos and v_pos:
                if not coords or coords[-1] != u_pos:
                    coords.append(u_pos)
                coords.append(v_pos)

    valid_ids = [s for s in seg_ids if s is not None]
    if valid_ids and "seg_id" in segments_gdf.columns:
        seg_rows = segments_gdf[segments_gdf["seg_id"].isin(valid_ids)]
        if len(seg_rows) > 0:
            precise = []
            for _, row in seg_rows.iterrows():
                if hasattr(row.geometry, "coords"):
                    precise.extend(list(row.geometry.coords))
            if len(precise) >= 2:
                coords = precise

    geometry = LineString(coords) if len(coords) >= 2 else None
    metrics = compute_route_metrics_summary(route, G)
    return {"geometry": geometry, "metrics": metrics, "segments": valid_ids}


def _node_pos(G, node):
    if isinstance(node, tuple):
        return node
    if "pos" in G.nodes[node]:
        return G.nodes[node]["pos"]
    return None


def compute_route_metrics_summary(route: list, G: nx.Graph) -> Dict[str, float]:
    """计算路线级别指标汇总"""
    if len(route) < 2:
        return {
            "total_length": 0, "total_cost": 0,
            "avg_safety": 0, "avg_comfort": 0, "avg_scenery": 0,
            "avg_traffic_stress": 0, "avg_beauty": 0, "avg_pref_score": 0,
            "num_segments": 0,
        }

    edges = list(zip(route[:-1], route[1:]))
    lengths, safeties, comforts, sceneries, stresses, beauties, prefs, costs = (
        [], [], [], [], [], [], [], []
    )

    for u, v in edges:
        if G.has_edge(u, v):
            d = G[u][v]
            lengths.append(d.get("length", 0))
            costs.append(d.get("cost_composite", 0))
            safeties.append(d.get("w_safety", 0.5))
            comforts.append(d.get("w_comfort", 0.5))
            sceneries.append(d.get("w_scenery", 0.5))
            stresses.append(d.get("f_traffic_stress", 0.5))
            beauties.append(d.get("v_beauty", 0.5))
            prefs.append(d.get("pref_score", 0.5))

    n = len(lengths)
    return {
        "total_length": float(sum(lengths)),
        "total_cost": float(sum(costs)),
        "avg_safety": float(np.mean(safeties)) if n else 0,
        "avg_comfort": float(np.mean(comforts)) if n else 0,
        "avg_scenery": float(np.mean(sceneries)) if n else 0,
        "avg_traffic_stress": float(np.mean(stresses)) if n else 0,
        "avg_beauty": float(np.mean(beauties)) if n else 0,
        "avg_pref_score": float(np.mean(prefs)) if n else 0,
        "num_segments": n,
    }


def _get_coord(G, node):
    if isinstance(node, tuple):
        return node
    if G.has_node(node) and "pos" in G.nodes[node]:
        return G.nodes[node]["pos"]
    return None


def _project_to_line(point: tuple, pts: list) -> tuple:
    """将点投影到折线上，返回投影点 (lon, lat)"""
    from shapely.geometry import LineString, Point
    line = LineString(pts)
    proj = line.project(Point(point))
    pp = line.interpolate(proj)
    return (pp.x, pp.y)


def expand_route_to_coords(route: list, G, seg_id_to_coords: dict,
                           source: tuple = None, target: tuple = None) -> list:
    """将节点序列展开为沿路段实际几何的坐标链

    不再用节点间直线连线，而是沿每条路段的实际 LineString 坐标走，
    使路线贴合真实路网，避免"穿楼"。

    Args:
        route: 节点序列（Dijkstra/NSGA-II 路径输出）
        G: NetworkX 图（边含 seg_id 属性）
        seg_id_to_coords: {seg_id: [(lon,lat), ...]} 路段实际坐标
        source: 起点原始坐标 (lon, lat)，提供时投影到首段使路线真正连接起点
        target: 终点原始坐标 (lon, lat)，提供时投影到末段使路线真正连接终点

    Returns:
        [(lon, lat), ...] 沿路网的展开坐标链（首尾已接入起终点所在路段）
    """
    coords = []
    first_pts, last_pts = None, None
    for u, v in zip(route[:-1], route[1:]):
        if G.has_edge(u, v):
            seg_id = G[u][v].get("seg_id")
            if seg_id is not None and seg_id in seg_id_to_coords:
                pts = seg_id_to_coords[seg_id]
                if not coords:
                    coords.extend(pts)
                    first_pts = pts
                else:
                    # 跳过第一点（与前一段路最后一个点重合）
                    coords.extend(pts[1:])
                last_pts = pts
            else:
                # 回退：直接用节点坐标
                uc = (u[0], u[1]) if isinstance(u, tuple) else _get_coord(G, u)
                vc = (v[0], v[1]) if isinstance(v, tuple) else _get_coord(G, v)
                if uc and vc:
                    if not coords:
                        coords.append(uc)
                        first_pts = [uc, vc]
                    coords.append(vc)
                    last_pts = [uc, vc]

    # 端点投影：将首/尾点吸附到起终点所在路段的实际线上
    if coords and source is not None and first_pts and len(first_pts) >= 2:
        coords[0] = _project_to_line(source, first_pts)
    if coords and target is not None and last_pts and len(last_pts) >= 2:
        coords[-1] = _project_to_line(target, last_pts)
    return coords


def export_routes_geojson(
    routes: List[list],
    G: nx.Graph,
    output_path: str,
    seg_id_to_coords: dict = None,
    source: tuple = None,
    target: tuple = None,
) -> None:
    """导出多条路线为GeoJSON

    Args:
        routes: 路线列表
        G: NetworkX图
        output_path: 输出路径
        seg_id_to_coords: {seg_id: [(lon,lat),...]} 提供时路线沿路网展开
        source/target: 起终点原始坐标，提供时路线端点投影接入
    """
    features = []
    for idx, route in enumerate(routes):
        summary = compute_route_metrics_summary(route, G)
        if seg_id_to_coords:
            coords = expand_route_to_coords(route, G, seg_id_to_coords, source=source, target=target)
        else:
            coords = [_get_coord(G, node) for node in route]
            coords = [c for c in coords if c is not None]

        if len(coords) >= 2:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[c[0], c[1]] for c in coords],
                },
                "properties": {"route_id": idx, **summary},
            })

    geojson = {"type": "FeatureCollection", "features": features}
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
