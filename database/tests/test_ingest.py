"""数据库层入库结果测试（Phase 1-3 验收：行数与数据内容校验）"""
import sqlite3

import pytest

from database.schema import DB_PATH

# 预期行数（与 DATA_STATS 一致）
EXPECTED_ROWS = {
    "streetview_observations": 10131,  # 2563 点 × 4 方向
    "poi": 806960,                     # 约 80 万
    "stations": 3293,                  # 2017 共享单车停车位
}


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(DB_PATH)
    yield c
    c.close()


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_row_counts_match_expected(conn):
    for table, expected in EXPECTED_ROWS.items():
        assert _count(conn, table) == expected, f"{table} 行数不符"


def test_all_tables_nonempty(conn):
    for table in ["segments", "buildings", "districts", "routes"]:
        assert _count(conn, table) > 0, f"{table} 为空"


def test_dataset_meta_records(conn):
    rows = conn.execute("SELECT dataset, row_count FROM dataset_meta ORDER BY dataset").fetchall()
    assert len(rows) == 7
    meta = dict(rows)
    assert meta["poi"] == 806960 and meta["stations"] == 3293


def test_poi_sample_content(conn):
    """POI 中文列映射正确、坐标在北京范围内"""
    row = conn.execute(
        "SELECT poi_id, name, category_big, lon, lat FROM poi LIMIT 5"
    ).fetchall()
    assert len(row) == 5
    for poi_id, name, category, lon, lat in row:
        assert poi_id >= 0
        assert category is not None and len(category) > 0, "POI 大类为空"
        assert 115.0 <= lon <= 117.5, f"POI 经度越界: {lon}"
        assert 39.0 <= lat <= 41.0, f"POI 纬度越界: {lat}"


def test_poi_categories_present(conn):
    cats = conn.execute(
        "SELECT DISTINCT category_big FROM poi WHERE category_big IS NOT NULL LIMIT 20"
    ).fetchall()
    assert len(cats) >= 10, "POI 大类种类过少"


def test_stations_content(conn):
    row = conn.execute(
        "SELECT station_id, name, capacity, lon_wgs, lat_wgs FROM stations LIMIT 3"
    ).fetchall()
    assert len(row) == 3
    for sid, name, cap, lon, lat in row:
        assert sid >= 0
        assert cap >= 0, "车位数不能为负"
        assert 115.0 <= lon <= 117.5 and 39.0 <= lat <= 41.0


def test_streetview_sample(conn):
    row = conn.execute(
        "SELECT point_id, direction, lon_wgs, lat_wgs, "
        "metric_bike_lane_type_value, metric_bike_lane_type_confidence_0_1 "
        "FROM streetview_observations LIMIT 5"
    ).fetchall()
    assert len(row) == 5
    for pid, direction, lon, lat, *_ in row:
        assert pid is not None and direction in ("E", "W", "S", "N", "NNE", "E", "W", "S", "N")
        # 宽表列全为 TEXT，坐标需显式转 float
        assert 115.0 <= float(lon) <= 117.5 and 39.0 <= float(lat) <= 41.0


def test_geometry_wkt_prefixes(conn):
    seg = conn.execute("SELECT geometry_wkt FROM segments LIMIT 1").fetchone()[0]
    assert seg.startswith("LINESTRING"), f"segments 几何异常: {seg[:40]}"
    bld = conn.execute("SELECT geometry_wkt FROM buildings LIMIT 1").fetchone()[0]
    assert bld.startswith("POLYGON"), f"buildings 几何异常: {bld[:40]}"
    dist = conn.execute("SELECT geometry_wkt FROM districts LIMIT 1").fetchone()[0]
    assert dist.startswith(("LINESTRING", "MULTILINESTRING")), f"districts 几何异常: {dist[:40]}"
