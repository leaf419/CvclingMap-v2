"""POI数据加载器测试（数据库模式）"""
import pytest
import pandas as pd
import geopandas as gpd
from algorithm.data.poi_loader import load_poi_csv, encode_categories, RIDING_RELEVANT_CATEGORIES


def _insert_sample_poi(conn, sample_poi_df):
    """将 sample_poi_df（中文列）映射为 poi 表英文列并插入临时库"""
    df = sample_poi_df.rename(columns={
        "名称": "name", "大类": "category_big", "经度": "lon", "纬度": "lat",
    })
    df["poi_id"] = range(len(df))
    rows = df[["poi_id", "name", "category_big", "lon", "lat"]].values.tolist()
    conn.executemany(
        "INSERT INTO poi (poi_id, name, category_big, lon, lat) VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()


def test_load_poi_csv(sample_poi_df, temp_sqlite_db):
    """测试从数据库加载POI"""
    conn, db_path = temp_sqlite_db
    _insert_sample_poi(conn, sample_poi_df)

    gdf = load_poi_csv(db_path=db_path)
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.crs.to_epsg() == 4326
    assert len(gdf) == 5
    assert "poi_id" in gdf.columns
    assert "category_big" in gdf.columns


def test_encode_categories(sample_poi_df, temp_sqlite_db):
    """测试POI大类编码（数据库英文列名）"""
    conn, db_path = temp_sqlite_db
    _insert_sample_poi(conn, sample_poi_df)

    gdf = load_poi_csv(db_path=db_path)
    gdf = encode_categories(gdf)
    assert "category_code" in gdf.columns
    assert gdf["category_code"].nunique() == 5
    assert gdf["category_code"].min() == 0


def test_riding_relevant_categories():
    """测试骑行相关POI大类列表"""
    assert "餐饮美食" in RIDING_RELEVANT_CATEGORIES
    assert "购物消费" in RIDING_RELEVANT_CATEGORIES
    assert "交通设施" in RIDING_RELEVANT_CATEGORIES
    assert "旅游景点" in RIDING_RELEVANT_CATEGORIES
