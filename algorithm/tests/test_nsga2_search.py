"""NSGA-II路径搜索测试"""
import pytest
import networkx as nx
import geopandas as gpd
from shapely.geometry import Point, LineString
from algorithm.routing.nsga2_search import build_nx_graph, evaluate_route, nsga2_search
from algorithm.routing.station_constraint import station_density_bonus


def test_build_nx_graph():
    """测试NetworkX图构建"""
    segments = gpd.GeoDataFrame({
        "seg_id": [0, 1, 2],
        "length": [100.0, 150.0, 80.0],
        "cost_composite": [50.0, 70.0, 30.0],
        "w_safety": [0.6, 0.5, 0.8],
        "w_scenery": [0.7, 0.4, 0.6],
        "w_comfort": [0.5, 0.6, 0.7],
        "f_traffic_stress": [0.4, 0.6, 0.2],
        "v_beauty": [0.7, 0.4, 0.6],
    }, geometry=[
        LineString([(0, 0), (1, 1)]),
        LineString([(1, 1), (2, 2)]),
        LineString([(2, 2), (3, 3)]),
    ], crs="EPSG:4326")

    G = build_nx_graph(segments)
    assert G.number_of_nodes() >= 3
    assert G.number_of_edges() >= 2


def test_evaluate_route():
    """测试路线评估"""
    G = nx.Graph()
    G.add_edge(0, 1, length=100.0, cost_composite=50.0,
               f_traffic_stress=0.4, v_beauty=0.7, pref_score=0.8)
    G.add_edge(1, 2, length=150.0, cost_composite=70.0,
               f_traffic_stress=0.6, v_beauty=0.4, pref_score=0.5)

    objectives = evaluate_route([0, 1, 2], G)
    assert len(objectives) == 4
    assert objectives[0] == 250.0
    assert objectives[1] == 1.0


def test_nsga2_search_small():
    """测试小规模NSGA-II搜索"""
    G = nx.Graph()
    for i in range(10):
        G.add_edge(i, i + 1, length=100.0, cost_composite=50.0,
                   f_traffic_stress=0.4, v_beauty=0.7, pref_score=0.7)

    routes = nsga2_search(G, source=0, target=10, pop_size=20, n_gen=10)
    assert len(routes) > 0
    assert all(isinstance(r, list) for r in routes)


def test_station_density_bonus():
    """测试站点密度奖励"""
    stations = gpd.GeoDataFrame(
        geometry=[Point(0.5, 0.5), Point(1.5, 1.5)], crs="EPSG:4326"
    )
    G = nx.Graph()
    G.add_edge(0, 1, length=100.0)
    G.nodes[0]["pos"] = (0, 0)
    G.nodes[1]["pos"] = (2, 2)

    bonus = station_density_bonus([0, 1], G, stations, buffer=10000)
    assert bonus >= 0
