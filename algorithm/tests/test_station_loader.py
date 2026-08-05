"""单车停车点加载器测试（数据库模式 + 文件模式）"""
import pytest
import geopandas as gpd
from shapely.geometry import Point
from algorithm.data.station_loader import load_stations, normalize_stations


def test_load_stations_from_database(temp_sqlite_db):
    """测试从数据库加载 (默认模式)"""
    conn, db_path = temp_sqlite_db
    conn.executemany(
        "INSERT INTO stations (station_id, name, location, capacity, lon_wgs, lat_wgs) "
        "VALUES (?,?,?,?,?,?)",
        [(0, "站A", "位置A", 10, 116.36, 39.91), (1, "站B", "位置B", 20, 116.37, 39.92)],
    )
    conn.commit()

    result = load_stations(db_path=db_path)
    assert len(result) == 2
    assert "station_id" in result.columns
    assert "capacity" in result.columns
    assert result.crs.to_epsg() == 4326
    assert result["capacity"].tolist() == [10, 20]


def test_load_stations_shapefile(tmp_path):
    """测试从Shapefile加载 (显式文件路径模式)"""
    gdf = gpd.GeoDataFrame(
        {"站点名": ["站A", "站B"], "车位数": [10, 20]},
        geometry=[Point(116.36, 39.91), Point(116.37, 39.92)],
        crs="EPSG:4326"
    )
    path = tmp_path / "stations.shp"
    gdf.to_file(path)

    result = load_stations(file_path=str(path))
    assert len(result) == 2
    assert "station_id" in result.columns
    assert "capacity" in result.columns
    assert result.crs.to_epsg() == 4326


def test_normalize_stations_capacity_mapping():
    """测试车位数列映射"""
    gdf = gpd.GeoDataFrame(
        {"站点名": ["站A"], "车位数": [15]},
        geometry=[Point(116.36, 39.91)],
        crs="EPSG:4326"
    )
    result = normalize_stations(gdf)
    assert "station_id" in result.columns
    assert "capacity" in result.columns
    assert result["capacity"].iloc[0] == 15
    assert result["station_id"].iloc[0] == 0


def test_normalize_stations_no_capacity():
    """测试无车位数列时的默认值"""
    gdf = gpd.GeoDataFrame(
        {"name": ["站A"]},
        geometry=[Point(116.36, 39.91)],
        crs="EPSG:4326"
    )
    result = normalize_stations(gdf)
    assert result["capacity"].iloc[0] == 0
