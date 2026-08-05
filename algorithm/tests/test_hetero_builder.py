"""异构图构建器测试"""
import pytest
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon
from algorithm.graph.hetero_builder import (
    build_morphological_graph,
    connect_observations_to_segments,
    connect_pois_to_segments,
    connect_stations_to_segments,
    build_hetero_graph,
)


def test_build_morphological_graph(sample_segments_gdf):
    """测试city2graph形态图构建"""
    buildings = gpd.GeoDataFrame({
        "place_id": [0, 1],
        "height_m": [9.0, 15.0],
        "area_m2": [100.0, 200.0],
    }, geometry=[
        Polygon([(116.35,39.90),(116.36,39.90),(116.36,39.91),(116.35,39.91)]),
        Polygon([(116.38,39.92),(116.39,39.92),(116.39,39.93),(116.38,39.93)]),
    ], crs="EPSG:4326")

    nodes, edges = build_morphological_graph(buildings, sample_segments_gdf)
    assert "movement" in nodes or "segment" in nodes
    assert isinstance(edges, dict)


def test_connect_observations_to_segments(sample_obs_gdf, sample_segments_gdf):
    """测试观测点→街道段连接"""
    result = connect_observations_to_segments(
        sample_obs_gdf, sample_segments_gdf, max_distance=10000
    )
    assert len(result) > 0
    assert "obs_id" in result.columns
    assert "seg_id" in result.columns


def test_connect_pois_to_segments(sample_poi_df, sample_segments_gdf):
    """测试POI→街道段连接"""
    poi_gdf = gpd.GeoDataFrame(
        sample_poi_df,
        geometry=gpd.points_from_xy(sample_poi_df["经度"], sample_poi_df["纬度"]),
        crs="EPSG:4326"
    )
    poi_gdf["poi_id"] = range(len(poi_gdf))
    result = connect_pois_to_segments(poi_gdf, sample_segments_gdf, k=2, max_distance=10000)
    assert len(result) > 0
    assert "poi_id" in result.columns
    assert "seg_id" in result.columns


def test_build_hetero_graph_structure():
    """测试异构图结构完整性"""
    from algorithm.graph.hetero_builder import HeteroGraphData
    import numpy as np

    nodes = {
        "segment": gpd.GeoDataFrame(
            {"seg_id": [0, 1]},
            geometry=[LineString([(0,0),(1,1)]), LineString([(1,1),(2,2)])],
            crs="EPSG:4326"),
        "observation": gpd.GeoDataFrame(
            {"obs_id": [0]},
            geometry=[Point(0.5, 0.5)],
            crs="EPSG:4326"),
    }
    edges = {
        ("segment","connected_to","segment"): gpd.GeoDataFrame({"src":[0], "dst":[1]}),
        ("observation","observed_at","segment"): gpd.GeoDataFrame({"src":[0], "dst":[0]}),
    }

    hg = HeteroGraphData(nodes=nodes, edges=edges)
    assert "segment" in hg.node_types
    assert "observation" in hg.node_types
    assert ("observation","observed_at","segment") in hg.edge_types
    assert hg.total_nodes == 3
