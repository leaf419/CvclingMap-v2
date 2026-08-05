"""共享测试fixtures — algorithm层测试"""
import sys
from pathlib import Path

# 确保项目根目录在Python路径中，使 from algorithm.xxx 可用
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import numpy as np

@pytest.fixture
def sample_streetview_df():
    """模拟街景指标数据 (10条记录, 2个采样点×4方向)"""
    return pd.DataFrame({
        "point_id": [1,1,1,1, 2,2,2,2, 3,3],
        "direction": ["E","N","S","W", "E","N","S","W", "E","N"],
        "lon_wgs": [116.36,116.36,116.36,116.36, 116.37,116.37,116.37,116.37, 116.38,116.38],
        "lat_wgs": [39.91,39.91,39.91,39.91, 39.92,39.92,39.92,39.92, 39.93,39.93],
        "metric_bike_lane_type_value": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.5,0.4],
        "metric_bike_lane_type_confidence_0_1": [0.9,0.8,0.7,0.6, 0.9,0.8,0.7,0.6, 0.8,0.7],
        "metric_physical_separation_value": [0.7,0.6,0.5,0.4, 0.8,0.7,0.6,0.5, 0.3,0.2],
        "metric_physical_separation_confidence_0_1": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.7,0.6],
        "metric_motor_traffic_pressure_value": [0.3,0.4,0.5,0.6, 0.2,0.3,0.4,0.5, 0.6,0.7],
        "metric_motor_traffic_pressure_confidence_0_1": [0.9,0.8,0.7,0.6, 0.9,0.8,0.7,0.6, 0.8,0.7],
        "metric_road_surface_quality_value": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.4,0.3],
        "metric_road_surface_quality_confidence_0_1": [0.9,0.8,0.7,0.6, 0.9,0.8,0.7,0.6, 0.8,0.7],
        "metric_visible_greenery_value": [0.6,0.5,0.4,0.3, 0.8,0.7,0.6,0.5, 0.5,0.4],
        "metric_visible_greenery_confidence_0_1": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.7,0.6],
        "metric_beauty_value": [0.7,0.6,0.5,0.4, 0.8,0.7,0.6,0.5, 0.4,0.3],
        "metric_beauty_confidence_0_1": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.7,0.6],
        "metric_perceived_safety_value": [0.6,0.5,0.4,0.3, 0.7,0.6,0.5,0.4, 0.3,0.2],
        "metric_perceived_safety_confidence_0_1": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.7,0.6],
    })

@pytest.fixture
def sample_poi_df():
    """模拟POI数据 (5条)"""
    return pd.DataFrame({
        "名称": ["A餐厅","B超市","C医院","D学校","E景点"],
        "大类": ["餐饮美食","购物消费","医疗保健","科教文化","旅游景点"],
        "经度": [116.36, 116.37, 116.38, 116.39, 116.40],
        "纬度": [39.91, 39.92, 39.93, 39.94, 39.95],
    })

@pytest.fixture
def sample_segments_gdf():
    """模拟街道段GeoDataFrame"""
    return gpd.GeoDataFrame({
        "seg_id": [0, 1, 2, 3],
        "length": [100.0, 150.0, 80.0, 200.0],
        "highway": ["residential","primary","residential","secondary"],
    }, geometry=[
        LineString([(116.35,39.90),(116.37,39.91)]),
        LineString([(116.37,39.91),(116.39,39.92)]),
        LineString([(116.39,39.92),(116.40,39.93)]),
        LineString([(116.40,39.93),(116.42,39.94)]),
    ], crs="EPSG:4326")

@pytest.fixture
def sample_obs_gdf():
    """模拟街景聚合后的观测点GeoDataFrame (含指标列)"""
    return gpd.GeoDataFrame({
        "obs_id": [0, 1, 2],
        "s_bike_lane_type": [0.65, 0.75, 0.45],
        "s_physical_separation": [0.55, 0.65, 0.25],
        "s_motor_pressure": [0.45, 0.35, 0.65],
        "s_heavy_vehicle": [0.30, 0.20, 0.50],
        "s_parking_encroach": [0.25, 0.15, 0.45],
        "s_intersection_conflict": [0.35, 0.25, 0.55],
        "f_surface_quality": [0.65, 0.75, 0.35],
        "f_pothole": [0.20, 0.10, 0.40],
        "f_overall_comfort": [0.60, 0.70, 0.30],
        "f_traffic_stress": [0.40, 0.30, 0.60],
        "v_greenery": [0.45, 0.65, 0.35],
        "v_beauty": [0.55, 0.65, 0.25],
        "v_tranquility": [0.50, 0.60, 0.30],
        "x_perceived_safety": [0.45, 0.55, 0.25],
        "x_active_frontage": [0.60, 0.50, 0.20],
        "x_cleanliness": [0.65, 0.55, 0.35],
        "x_lighting": [0.50, 0.60, 0.30],
    }, geometry=[
        Point(116.36, 39.91),
        Point(116.37, 39.92),
        Point(116.38, 39.93),
    ], crs="EPSG:4326")


@pytest.fixture
def temp_sqlite_db(tmp_path):
    """创建与真实库同构的临时 SQLite 数据库，返回 (连接, 路径字符串)"""
    from database.schema import init_database
    db_path = tmp_path / "test_algo.sqlite"
    conn = init_database(db_path)
    yield conn, str(db_path)
    conn.close()
