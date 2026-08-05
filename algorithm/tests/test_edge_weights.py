"""四维边权模型测试"""
import pytest
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString
from algorithm.weights.edge_weights import (
    safety_from_streetview,
    comfort_from_streetview,
    scenery_from_streetview,
    experience_from_streetview,
    compute_all_weights,
)
from algorithm.weights.cost_fusion import fuse_composite_cost


def test_safety_from_streetview(sample_obs_gdf):
    """测试安全性计算"""
    metrics = sample_obs_gdf.iloc[0].to_dict()
    s = safety_from_streetview(metrics)
    assert 0 <= s <= 1
    assert s > 0.4


def test_safety_inverts_negative_metrics():
    """测试负面指标反转"""
    metrics = {
        "s_bike_lane_type": 0.2,
        "s_physical_separation": 0.1,
        "s_motor_pressure": 0.9,
        "s_heavy_vehicle": 0.8,
        "s_parking_encroach": 0.7,
        "s_intersection_conflict": 0.6,
    }
    s = safety_from_streetview(metrics)
    assert s < 0.3


def test_comfort_from_streetview(sample_obs_gdf):
    """测试舒适度计算"""
    metrics = sample_obs_gdf.iloc[0].to_dict()
    f = comfort_from_streetview(metrics)
    assert 0 <= f <= 1


def test_scenery_from_streetview(sample_obs_gdf):
    """测试风景计算"""
    metrics = sample_obs_gdf.iloc[0].to_dict()
    v = scenery_from_streetview(metrics)
    assert 0 <= v <= 1


def test_experience_from_streetview(sample_obs_gdf):
    """测试综合体验计算"""
    metrics = sample_obs_gdf.iloc[0].to_dict()
    x = experience_from_streetview(metrics)
    assert 0 <= x <= 1


def test_compute_all_weights(sample_segments_gdf):
    """测试批量计算所有边权"""
    gdf = sample_segments_gdf.copy()
    gdf["s_bike_lane_type"] = [0.6, 0.7, 0.5, 0.8]
    gdf["s_physical_separation"] = [0.5, 0.6, 0.4, 0.7]
    gdf["s_motor_pressure"] = [0.4, 0.3, 0.5, 0.2]
    gdf["s_heavy_vehicle"] = [0.3, 0.2, 0.4, 0.1]
    gdf["s_parking_encroach"] = [0.2, 0.1, 0.3, 0.0]
    gdf["s_intersection_conflict"] = [0.3, 0.2, 0.4, 0.1]
    gdf["f_surface_quality"] = [0.6, 0.7, 0.5, 0.8]
    gdf["f_pothole"] = [0.2, 0.1, 0.3, 0.0]
    gdf["f_overall_comfort"] = [0.6, 0.7, 0.5, 0.8]
    gdf["f_traffic_stress"] = [0.4, 0.3, 0.5, 0.2]
    gdf["v_greenery"] = [0.5, 0.6, 0.4, 0.7]
    gdf["v_beauty"] = [0.5, 0.6, 0.4, 0.7]
    gdf["v_tranquility"] = [0.5, 0.6, 0.4, 0.7]
    gdf["x_perceived_safety"] = [0.5, 0.6, 0.4, 0.7]
    gdf["x_active_frontage"] = [0.5, 0.6, 0.4, 0.7]
    gdf["x_cleanliness"] = [0.5, 0.6, 0.4, 0.7]
    gdf["x_lighting"] = [0.5, 0.6, 0.4, 0.7]

    result = compute_all_weights(gdf)
    assert "w_safety" in result.columns
    assert "w_comfort" in result.columns
    assert "w_scenery" in result.columns
    assert "w_experience" in result.columns
    assert result["w_safety"].between(0, 1).all()


def test_fuse_composite_cost():
    """测试综合成本融合"""
    import pandas as pd
    df = pd.DataFrame({
        "w_safety": [0.6, 0.8],
        "w_comfort": [0.5, 0.7],
        "w_scenery": [0.7, 0.6],
        "w_experience": [0.5, 0.8],
        "length": [100.0, 200.0],
    })
    result = fuse_composite_cost(df, alpha=0.3, beta=0.25, gamma=0.25, delta=0.2)
    assert "cost_composite" in result.columns
    assert result["cost_composite"].iloc[0] < result["cost_composite"].iloc[1] * 2
