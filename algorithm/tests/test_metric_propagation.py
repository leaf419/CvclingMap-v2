"""街景指标传播测试"""
import pytest
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString
from algorithm.graph.metric_propagation import propagate_metrics_to_segments


def test_propagation_basic(sample_obs_gdf, sample_segments_gdf):
    """测试基本传播功能"""
    result = propagate_metrics_to_segments(
        sample_obs_gdf, sample_segments_gdf, k=2, max_dist=10000
    )
    assert "s_bike_lane_type" in result.columns
    assert "v_greenery" in result.columns
    assert "x_perceived_safety" in result.columns
    assert result["s_bike_lane_type"].min() >= 0
    assert result["s_bike_lane_type"].max() <= 1


def test_propagation_has_observation_flag(sample_obs_gdf, sample_segments_gdf):
    """测试has_observation标记"""
    result = propagate_metrics_to_segments(
        sample_obs_gdf, sample_segments_gdf, k=2, max_dist=10000
    )
    assert "has_observation" in result.columns
    assert result["has_observation"].dtype == bool


def test_propagation_distance_weighted(sample_obs_gdf):
    """测试距离反比加权: 更近的观测点应有更大权重"""
    segments = gpd.GeoDataFrame({
        "seg_id": [0, 1],
    }, geometry=[
        LineString([(116.359,39.909),(116.361,39.911)]),  # 靠近obs[0]
        LineString([(116.379,39.929),(116.381,39.931)]),  # 靠近obs[2]
    ], crs="EPSG:4326")

    result = propagate_metrics_to_segments(
        sample_obs_gdf, segments, k=3, max_dist=10000
    )
    # seg[0]靠近obs[0](s_bike_lane_type=0.65), 应偏高
    # seg[1]靠近obs[2](s_bike_lane_type=0.45), 应偏低
    assert result.iloc[0]["s_bike_lane_type"] > result.iloc[1]["s_bike_lane_type"]
