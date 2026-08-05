"""5类节点6类边异构图构建"""
import geopandas as gpd
import pandas as pd
import city2graph as c2g
from dataclasses import dataclass
from typing import Dict, Tuple
from pathlib import Path
from shapely.geometry import Point

from algorithm.config import GRAPH_CFG, DISTRICT_CENTERS


@dataclass
class HeteroGraphData:
    """异构图数据容器"""
    nodes: Dict[str, gpd.GeoDataFrame]
    edges: Dict[Tuple[str, str, str], gpd.GeoDataFrame]

    @property
    def node_types(self) -> list:
        return list(self.nodes.keys())

    @property
    def edge_types(self) -> list:
        return list(self.edges.keys())

    @property
    def total_nodes(self) -> int:
        return sum(len(gdf) for gdf in self.nodes.values())

    @property
    def total_edges(self) -> int:
        return sum(len(gdf) for gdf in self.edges.values())

    def summary(self) -> str:
        lines = [f"节点类型: {self.node_types}"]
        for nt, gdf in self.nodes.items():
            lines.append(f"  {nt}: {len(gdf)} 节点")
        lines.append(f"边类型: {self.edge_types}")
        for et, gdf in self.edges.items():
            lines.append(f"  {et}: {len(gdf)} 边")
        lines.append(f"总计: {self.total_nodes} 节点, {self.total_edges} 边")
        return "\n".join(lines)


def build_morphological_graph(
    buildings_gdf: gpd.GeoDataFrame,
    segments_gdf: gpd.GeoDataFrame,
) -> Tuple[dict, dict]:
    """使用city2graph构建街道+建筑形态图

    自动将EPSG:4326投影到EPSG:32650 (UTM Zone 50N, 北京地区)。

    Returns:
        (nodes_dict, edges_dict)
        nodes_dict: {"movement": segments, "place": buildings}
        edges_dict: {("movement","connected_to","movement"): ..., ...}
    """
    # city2graph要求投影坐标系(米)，将WGS84投影到UTM 50N
    bld_proj = buildings_gdf.to_crs("EPSG:32650")
    seg_proj = segments_gdf.to_crs("EPSG:32650")

    center = Point(*DISTRICT_CENTERS[0])
    nodes, edges = c2g.morphological_graph(
        bld_proj,
        seg_proj,
        center_point=center,
        distance=GRAPH_CFG.morpho_distance,
        as_nx=False
    )
    return nodes, edges


def connect_observations_to_segments(
    obs_gdf: gpd.GeoDataFrame,
    segments_gdf: gpd.GeoDataFrame,
    max_distance: float = None,
) -> gpd.GeoDataFrame:
    """观测点→最近街道段 (observed_at边)

    Args:
        obs_gdf: 街景观测点GeoDataFrame (含obs_id)
        segments_gdf: 街道段GeoDataFrame (含seg_id)
        max_distance: 最大连接距离(米)

    Returns:
        含 obs_id, seg_id, distance 列的连接表
    """
    if max_distance is None:
        max_distance = GRAPH_CFG.obs_max_distance

    obs_proj = obs_gdf.to_crs("EPSG:32650")
    seg_proj = segments_gdf.to_crs("EPSG:32650")

    if "seg_id" not in seg_proj.columns:
        seg_proj["seg_id"] = range(len(seg_proj))

    joined = gpd.sjoin_nearest(
        obs_proj, seg_proj[["seg_id", "geometry"]],
        how="left",
        max_distance=max_distance,
        lsuffix="obs", rsuffix="seg"
    )

    result = joined[["obs_id", "seg_id"]].copy()
    result = result.dropna(subset=["seg_id"])
    if len(result) > 0:
        left_geo = obs_proj.loc[result.index].reset_index(drop=True)
        right_geo = seg_proj.set_index("seg_id").loc[result["seg_id"].values].reset_index(drop=True)
        result["distance"] = left_geo.distance(right_geo.geometry, align=False).values
    else:
        result["distance"] = []

    return result


def connect_pois_to_segments(
    poi_gdf: gpd.GeoDataFrame,
    segments_gdf: gpd.GeoDataFrame,
    k: int = None,
    max_distance: float = None,
) -> gpd.GeoDataFrame:
    """POI→最近k个街道段 (nearby边)

    Args:
        poi_gdf: POI GeoDataFrame (含poi_id)
        segments_gdf: 街道段GeoDataFrame (含seg_id)
        k: 每个POI连接的最近segment数
        max_distance: 最大连接距离(米)

    Returns:
        含 poi_id, seg_id, distance 列的连接表
    """
    if k is None:
        k = GRAPH_CFG.poi_k_neighbors
    if max_distance is None:
        max_distance = GRAPH_CFG.poi_max_distance

    poi_proj = poi_gdf.to_crs("EPSG:32650")
    seg_proj = segments_gdf.to_crs("EPSG:32650")

    if "seg_id" not in seg_proj.columns:
        seg_proj["seg_id"] = range(len(seg_proj))

    # 使用 STRtree 空间索引替代 O(n*m) 逐点遍历
    from shapely import STRtree
    seg_tree = STRtree(seg_proj.geometry.values)
    seg_geoms = list(seg_proj.geometry)

    results = []
    for idx, poi_row in poi_proj.iterrows():
        # 空间索引预筛选（距离缓冲内，不创建buffer几何体）
        hits = seg_tree.query(poi_row.geometry, predicate="dwithin", distance=max_distance)
        if len(hits) == 0:
            continue
        # 计算候选段的精确距离，取最近k个
        hit_dists = [(h, seg_geoms[h].distance(poi_row.geometry)) for h in hits]
        hit_dists.sort(key=lambda x: x[1])
        for seg_hit, dist in hit_dists[:k]:
            if dist <= max_distance:
                results.append({
                    "poi_id": poi_row["poi_id"],
                    "seg_id": seg_proj.iloc[seg_hit]["seg_id"],
                    "distance": dist,
                })

    return pd.DataFrame(results)


def connect_stations_to_segments(
    station_gdf: gpd.GeoDataFrame,
    segments_gdf: gpd.GeoDataFrame,
    max_distance: float = None,
) -> gpd.GeoDataFrame:
    """单车停车点→最近街道段 (served_by边)"""
    if max_distance is None:
        max_distance = GRAPH_CFG.station_max_distance

    station_proj = station_gdf.to_crs("EPSG:32650")
    seg_proj = segments_gdf.to_crs("EPSG:32650")

    if "seg_id" not in seg_proj.columns:
        seg_proj["seg_id"] = range(len(seg_proj))

    joined = gpd.sjoin_nearest(
        station_proj, seg_proj[["seg_id", "geometry"]],
        how="left",
        max_distance=max_distance,
        lsuffix="sta", rsuffix="seg"
    )

    result = joined[["station_id", "seg_id"]].copy()
    return result.dropna(subset=["seg_id"])


def _connect_places_to_segments(place_gdf, segments_gdf, max_distance=150.0):
    """建筑最近街道段 (faced_to 边)"""
    place = place_gdf.to_crs("EPSG:32650").copy()
    if "place_id" not in place.columns:
        place["place_id"] = range(len(place))
    seg = segments_gdf.to_crs("EPSG:32650")[["seg_id", "geometry"]]
    joined = gpd.sjoin_nearest(
        place[["place_id", "geometry"]], seg,
        how="left", max_distance=max_distance,
    )
    return joined[["place_id", "seg_id"]].dropna(subset=["seg_id"])


def build_hetero_graph(
    segments_gdf: gpd.GeoDataFrame,
    buildings_gdf: gpd.GeoDataFrame,
    poi_gdf: gpd.GeoDataFrame,
    station_gdf: gpd.GeoDataFrame,
    obs_gdf: gpd.GeoDataFrame,
    use_city2graph: bool = False,
) -> HeteroGraphData:
    """构建完整的5类节点6类边异构图

    节点类型:
        - segment (街道段)
        - place (建筑地块)
        - poi (兴趣点)
        - station (单车停车点)
        - observation (街景观测点)

    边类型:
        - (segment, connected_to, segment)
        - (place, faced_to, segment)
        - (place, touched_to, place)
        - (poi, nearby, segment)
        - (station, served_by, segment)
        - (observation, observed_at, segment)

    当 use_city2graph=False 或 city2graph 无结果时，
    自动回退到几何相交+空间索引的快速构建路径。
    """
    edges_dict = {}

    if use_city2graph:
        # city2graph形态图 (segment + place + 3类边) — 仅真实数据有用
        nodes_dict, edges_dict = build_morphological_graph(buildings_gdf, segments_gdf)
        if "movement" in nodes_dict:
            nodes_dict["segment"] = nodes_dict.pop("movement")
        seg_nodes = nodes_dict.get("segment")
    else:
        nodes_dict = {}
        seg_nodes = None

    # 回退: 基于几何相交+空间索引构建segment连通性（快速路径）
    if seg_nodes is None or len(seg_nodes) == 0:
        nodes_dict["segment"] = segments_gdf
        nodes_dict["place"] = buildings_gdf

        # 将路段投影到UTM，检测几何相交来形成交叉口连接
        seg_proj = segments_gdf.to_crs("EPSG:32650")
        adj_rows = []
        for i in range(len(seg_proj)):
            for j in range(i + 1, len(seg_proj)):
                if seg_proj.iloc[i].geometry.intersects(seg_proj.iloc[j].geometry):
                    adj_rows.append({"seg_id_src": segments_gdf.iloc[i]["seg_id"],
                                    "seg_id_dst": segments_gdf.iloc[j]["seg_id"]})

        if adj_rows:
            import pandas as pd
            edges_dict[("segment", "connected_to", "segment")] = pd.DataFrame(adj_rows)

        # place→segment (faced_to)
        place_edges = _connect_places_to_segments(buildings_gdf, segments_gdf)
        if len(place_edges) > 0:
            edges_dict[("place", "faced_to", "segment")] = place_edges

    # 2. 观测点→segment
    obs_edges = connect_observations_to_segments(obs_gdf, segments_gdf)
    edges_dict[("observation", "observed_at", "segment")] = obs_edges

    # 3. POI→segment
    poi_edges = connect_pois_to_segments(poi_gdf, segments_gdf)
    edges_dict[("poi", "nearby", "segment")] = poi_edges

    # 4. station→segment
    sta_edges = connect_stations_to_segments(station_gdf, segments_gdf)
    edges_dict[("station", "served_by", "segment")] = sta_edges

    # 合并所有节点
    all_nodes = {
        "segment": nodes_dict.get("segment", segments_gdf),
        "place": nodes_dict.get("place", buildings_gdf),
        "poi": poi_gdf,
        "station": station_gdf,
        "observation": obs_gdf,
    }

    return HeteroGraphData(nodes=all_nodes, edges=edges_dict)
