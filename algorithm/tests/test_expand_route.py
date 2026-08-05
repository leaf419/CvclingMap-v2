"""路线坐标展开与端点投影测试"""
import networkx as nx

from rendering.export.route_overlay import expand_route_to_coords


def _graph_and_lookup():
    """构造图：seg0 (0,0)→(10,0)，seg1 (10,0)→(10,10)"""
    G = nx.Graph()
    G.add_edge((0, 0), (10, 0), seg_id=0, length=10.0, cost_composite=10.0)
    G.add_edge((10, 0), (10, 10), seg_id=1, length=10.0, cost_composite=10.0)
    lookup = {
        0: [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)],   # 折线含中间点
        1: [(10.0, 0.0), (10.0, 5.0), (10.0, 10.0)],
    }
    return G, lookup


def test_expand_follows_road_geometry():
    """路线沿路段实际几何展开，含中间点"""
    G, lookup = _graph_and_lookup()
    route = [(0, 0), (10, 0), (10, 10)]
    coords = expand_route_to_coords(route, G, lookup)
    # 期望：seg0 三点 + seg1 后两点（跳首点）
    assert coords == [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 5.0), (10.0, 10.0)]


def test_expand_projects_endpoints():
    """起终点投影到所在路段实际线上"""
    G, lookup = _graph_and_lookup()
    route = [(0, 0), (10, 0), (10, 10)]
    coords = expand_route_to_coords(
        route, G, lookup,
        source=(3.0, 0.0),   # 位于 seg0 线上
        target=(10.0, 7.0),  # 位于 seg1 线上
    )
    assert abs(coords[0][0] - 3.0) < 1e-9 and abs(coords[0][1] - 0.0) < 1e-9
    assert abs(coords[-1][0] - 10.0) < 1e-9 and abs(coords[-1][1] - 7.0) < 1e-9


def test_expand_off_road_endpoint():
    """起终点在路外时投影到最近点"""
    G, lookup = _graph_and_lookup()
    route = [(0, 0), (10, 0)]
    coords = expand_route_to_coords(route, G, lookup, source=(2.0, 3.0))
    # 起点 (2,3) 投影到 y=0 线 → (2,0)
    assert abs(coords[0][0] - 2.0) < 1e-6
    assert abs(coords[0][1]) < 1e-6
