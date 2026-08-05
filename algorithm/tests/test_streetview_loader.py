"""街景数据加载器测试（数据库模式）"""
import pytest
import pandas as pd
import geopandas as gpd
from algorithm.data.streetview_loader import (
    load_streetview_csv,
    aggregate_by_point,
    to_geodataframe,
    METRIC_MAPPING,
)


def test_load_streetview_csv(sample_streetview_df, temp_sqlite_db):
    """测试从数据库加载CSV（sample 列为真实宽表 181 列的子集）"""
    conn, db_path = temp_sqlite_db
    cols = list(sample_streetview_df.columns)
    col_sql = ",".join(f'"{c}"' for c in cols)
    placeholders = ",".join("?" * len(cols))
    rows = sample_streetview_df.where(pd.notna(sample_streetview_df), None).values.tolist()
    conn.executemany(
        f"INSERT INTO streetview_observations ({col_sql}) VALUES ({placeholders})",
        rows,
    )
    conn.commit()

    df = load_streetview_csv(db_path=db_path)
    assert len(df) == 10
    assert "point_id" in df.columns
    assert "lon_wgs" in df.columns


def test_metric_mapping_completeness():
    """测试指标映射涵盖4个维度"""
    assert "s_bike_lane_type" in METRIC_MAPPING["safety"]
    assert "f_surface_quality" in METRIC_MAPPING["comfort"]
    assert "v_greenery" in METRIC_MAPPING["scenery"]
    assert "x_perceived_safety" in METRIC_MAPPING["experience"]


def test_aggregate_by_point(sample_streetview_df):
    """测试按采样点4方向confidence加权聚合"""
    agg = aggregate_by_point(sample_streetview_df)
    assert len(agg) == 3  # 3个唯一point_id
    assert "s_bike_lane_type" in agg.columns
    # point_id=1的bike_lane_type: 4方向confidence加权
    # (0.8*0.9 + 0.7*0.8 + 0.6*0.7 + 0.5*0.6) / (0.9+0.8+0.7+0.6)
    # = (0.72+0.56+0.42+0.30) / 3.0 = 2.0/3.0 ≈ 0.667
    row = agg[agg["point_id"] == 1].iloc[0]
    assert abs(row["s_bike_lane_type"] - 0.667) < 0.01


def test_to_geodataframe(sample_streetview_df):
    """测试转换为GeoDataFrame"""
    agg = aggregate_by_point(sample_streetview_df)
    gdf = to_geodataframe(sample_streetview_df, agg)
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.crs.to_epsg() == 4326
    assert len(gdf) == 3
    assert "obs_id" in gdf.columns
