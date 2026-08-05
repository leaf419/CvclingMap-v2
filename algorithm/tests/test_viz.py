"""GeoScene SceneView 3D场景数据导出测试"""
import pytest
import json
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString, Point
from rendering.export.geoscene_export import (
    export_segments_geojson,
    export_stations_geojson,
    export_scene_config,
)
from rendering.export.route_overlay import (
    build_route_overlay,
    compute_route_metrics_summary,
    export_routes_geojson,
)


def test_export_segments_geojson(tmp_path, sample_segments_gdf):
    """测试街道段GeoJSON导出"""
    # 添加导出所需的列
    gdf = sample_segments_gdf.copy()
    gdf["cost_composite"] = [50.0, 70.0, 30.0, 90.0]
    gdf["w_safety"] = [0.6, 0.5, 0.8, 0.4]
    gdf["w_comfort"] = [0.5, 0.6, 0.7, 0.4]
    gdf["w_scenery"] = [0.7, 0.4, 0.6, 0.3]
    gdf["f_traffic_stress"] = [0.4, 0.6, 0.2, 0.7]
    gdf["v_beauty"] = [0.7, 0.4, 0.6, 0.3]

    out_path = tmp_path / "segments.geojson"
    export_segments_geojson(gdf, str(out_path))

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == len(gdf)
    props = data["features"][0]["properties"]
    assert "seg_id" in props


def test_export_stations_geojson(tmp_path):
    """测试站点GeoJSON导出"""
    stations = gpd.GeoDataFrame(
        {"station_id": [0, 1], "name": ["站A", "站B"]},
        geometry=[Point(116.36, 39.91), Point(116.37, 39.92)],
        crs="EPSG:4326",
    )
    out_path = tmp_path / "stations.geojson"
    export_stations_geojson(stations, str(out_path))

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert len(data["features"]) == 2
    assert data["features"][0]["geometry"]["type"] == "Point"


def test_export_scene_config(tmp_path):
    """测试3D场景配置导出"""
    out_path = tmp_path / "scene_config.json"
    export_scene_config(
        str(out_path),
        center_lon=116.40,
        center_lat=39.92,
        zoom=14,
        layers=["segments", "stations", "routes"],
    )

    assert out_path.exists()
    config = json.loads(out_path.read_text())
    assert config["center"][0] == 116.40
    assert config["center"][1] == 39.92
    assert config["zoom"] == 14
    assert "segments" in config["layers"]


def test_build_route_overlay(sample_segments_gdf):
    """测试路线叠加构建"""
    import networkx as nx

    G = nx.Graph()
    coords = list(sample_segments_gdf.geometry[0].coords)
    u = (round(coords[0][0], 6), round(coords[0][1], 6))
    v = (round(coords[-1][0], 6), round(coords[-1][1], 6))
    G.add_edge(u, v, length=100.0, w_safety=0.7, w_comfort=0.6,
               w_scenery=0.5, cost_composite=40.0, seg_id=0)

    overlay = build_route_overlay([u, v], G, sample_segments_gdf)
    assert "geometry" in overlay
    assert "metrics" in overlay
    assert overlay["metrics"]["total_length"] > 0


def test_compute_route_metrics_summary():
    """测试路线指标汇总"""
    import networkx as nx

    G = nx.Graph()
    G.add_edge(0, 1, length=100.0, w_safety=0.8, w_comfort=0.6,
               w_scenery=0.7, cost_composite=40.0, f_traffic_stress=0.3,
               v_beauty=0.7, pref_score=0.8)
    G.add_edge(1, 2, length=150.0, w_safety=0.6, w_comfort=0.5,
               w_scenery=0.4, cost_composite=60.0, f_traffic_stress=0.5,
               v_beauty=0.5, pref_score=0.6)

    summary = compute_route_metrics_summary([0, 1, 2], G)
    assert summary["total_length"] == 250.0
    assert summary["avg_safety"] == pytest.approx(0.7, abs=0.01)
    assert summary["num_segments"] == 2


def test_export_routes_geojson(tmp_path):
    """测试多路线GeoJSON导出"""
    import networkx as nx

    G = nx.Graph()
    G.add_edge(0, 1, length=100.0, w_safety=0.8, w_comfort=0.6,
               w_scenery=0.7, cost_composite=40.0, f_traffic_stress=0.3,
               v_beauty=0.7, pref_score=0.8)
    G.nodes[0]["pos"] = (116.36, 39.91)
    G.nodes[1]["pos"] = (116.37, 39.92)

    out_path = tmp_path / "routes.geojson"
    export_routes_geojson([[0, 1]], G, str(out_path))

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert len(data["features"]) == 1
    assert data["features"][0]["geometry"]["type"] == "LineString"
