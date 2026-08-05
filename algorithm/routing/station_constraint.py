"""历史单车停车点密度约束"""
import numpy as np
import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString
from algorithm.config import NSGA2_CFG


def station_density_bonus(
    route: list,
    G: nx.Graph,
    station_gdf: gpd.GeoDataFrame,
    buffer: float = None,
) -> float:
    """计算路线经过区域的站点密度奖励

    Args:
        route: 路线节点序列
        G: NetworkX图 (节点需有pos属性)
        station_gdf: 站点GeoDataFrame
        buffer: 缓冲距离(米)

    Returns:
        每公里站点密度 (越高越好)
    """
    if buffer is None:
        buffer = NSGA2_CFG.station_buffer

    positions = []
    for node in route:
        if "pos" in G.nodes[node]:
            positions.append(G.nodes[node]["pos"])
        elif isinstance(node, tuple):
            positions.append(node)

    if len(positions) < 2:
        return 0.0

    route_line = LineString(positions)
    route_gdf = gpd.GeoDataFrame(
        {"id": [0]}, geometry=[route_line], crs="EPSG:4326"
    ).to_crs("EPSG:32650")

    station_proj = station_gdf.to_crs("EPSG:32650")
    distances = station_proj.geometry.distance(route_gdf.geometry.iloc[0])
    nearby_count = (distances < buffer).sum()

    route_length_km = route_gdf.geometry.iloc[0].length / 1000.0
    if route_length_km == 0:
        return 0.0

    return float(nearby_count / route_length_km)


def rank_routes_by_station_access(
    routes: list,
    G: nx.Graph,
    station_gdf: gpd.GeoDataFrame,
    buffer: float = None,
) -> list:
    """按站点可达性对Pareto路线排序"""
    scored = []
    for route in routes:
        density = station_density_bonus(route, G, station_gdf, buffer)
        scored.append((route, density))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
