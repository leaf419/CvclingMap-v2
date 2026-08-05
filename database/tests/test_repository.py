"""数据库层 repository 访问层测试（Phase 1-4 验收）"""
import sqlite3

import pytest

from database.repository import (
    read_buildings,
    read_districts,
    read_meta,
    read_poi,
    read_routes,
    read_segments,
    read_stations,
    read_streetview,
    table_row_counts,
    to_geodataframe,
)
from database.schema import DB_PATH


def test_read_streetview():
    df = read_streetview()
    assert len(df) == 10131
    assert len(df.columns) == 181
    assert {"point_id", "direction", "lon_wgs", "lat_wgs"} <= set(df.columns)


def test_read_poi():
    df = read_poi()
    assert len(df) == 806960
    assert {"poi_id", "name", "category_big", "lon", "lat"} <= set(df.columns)


def test_read_stations():
    df = read_stations()
    assert len(df) == 3293
    assert {"station_id", "capacity", "lon_wgs", "lat_wgs"} <= set(df.columns)


def test_read_segments_is_gdf():
    gdf = read_segments()
    assert len(gdf) == 2376
    assert gdf.crs.to_epsg() == 4326
    assert gdf.geometry.geom_type.eq("LineString").all()
    assert "geometry_wkt" not in gdf.columns


def test_read_buildings_is_gdf():
    gdf = read_buildings()
    assert len(gdf) == 1152
    assert gdf.geometry.geom_type.eq("Polygon").all()


def test_read_districts_and_routes():
    dist = read_districts()
    assert len(dist) == 16 and dist.geometry.notna().all()
    routes = read_routes()
    assert len(routes) == 1


def test_read_meta_records():
    meta = read_meta()
    assert len(meta) == 7
    datasets = {m["dataset"] for m in meta}
    assert datasets == {
        "streetview_observations", "poi", "stations", "segments", "buildings", "districts", "routes",
    }


def test_table_row_counts():
    counts = table_row_counts()
    assert counts["streetview_observations"] == 10131
    assert counts["poi"] == 806960
    assert counts["stations"] == 3293


def test_to_geodataframe_points():
    df = read_stations().head(10)
    gdf = to_geodataframe(df, "lon_wgs", "lat_wgs")
    assert gdf.crs.to_epsg() == 4326
    assert gdf.geometry.geom_type.eq("Point").all()
