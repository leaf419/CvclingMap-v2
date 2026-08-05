"""天地图数据加载器测试"""
import pytest
from unittest.mock import patch
import geopandas as gpd
from shapely.geometry import LineString, Polygon
from algorithm.data.basemap_loader import (
    fetch_street_network,
    segments_to_gdf,
    buildings_to_gdf,
)


def test_segments_to_gdf():
    """测试天地图返回的GeoJSON街道段转换为GeoDataFrame"""
    mock_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"length": 100.0},
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            },
            {
                "type": "Feature",
                "properties": {"length": 200.0},
                "geometry": {"type": "LineString", "coordinates": [[1, 1], [2, 2]]},
            },
        ],
    }

    gdf = segments_to_gdf(mock_geojson)
    assert len(gdf) == 2
    assert "length" in gdf.columns
    assert "seg_id" in gdf.columns


def test_buildings_to_gdf():
    """测试建筑转换为GeoDataFrame"""
    mock_buildings = gpd.GeoDataFrame({
        "levels": [3, 5],
    }, geometry=[
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),
    ], crs="EPSG:4326")

    result = buildings_to_gdf(mock_buildings)
    assert "height_m" in result.columns
    assert result["height_m"].iloc[0] == 9.0   # 3层×3米
    assert result["height_m"].iloc[1] == 15.0  # 5层×3米


@patch("algorithm.data.basemap_loader.tianditu")
def test_fetch_street_network(mock_tianditu):
    """测试街道网络获取（天地图矢量服务）"""
    mock_tianditu.get_street_geojson.return_value = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"length": 100.0},
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            }
        ],
    }
    result = fetch_street_network(["Xicheng, Beijing"])
    mock_tianditu.get_street_geojson.assert_called_once()
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
