"""数据库层 schema 测试（Phase 1-2 验收）"""
import sqlite3

import pytest

from database.schema import (
    FIXED_TABLES,
    INDEXES,
    create_all_tables,
    init_database,
    read_streetview_columns,
    table_names,
)


@pytest.fixture()
def db_conn(tmp_path):
    """在临时文件上初始化数据库"""
    db_path = tmp_path / "test_bikeflow.sqlite"
    conn = init_database(db_path)
    yield conn
    conn.close()


def test_init_creates_all_fixed_tables(db_conn):
    tables = table_names(db_conn)
    for name in FIXED_TABLES:
        assert name in tables, f"missing table {name}"


def test_init_creates_streetview_wide_table(db_conn):
    tables = table_names(db_conn)
    assert "streetview_observations" in tables
    cols = [r[1] for r in db_conn.execute('PRAGMA table_info("streetview_observations")').fetchall()]
    # 181 个源列 + id 主键列
    assert len(cols) == 182
    assert cols[0] == "id"
    # 抽样关键列
    for c in ["point_id", "direction", "lon_wgs", "lat_wgs",
              "metric_bike_lane_type_value", "metric_bike_lane_type_confidence_0_1",
              "quality_viewpoint_usable_value"]:
        assert c in cols, f"missing streetview column {c}"


def test_streetview_source_columns_from_csv():
    """CSV 表头读取与宽表列数一致（无损入库的前提）"""
    columns = read_streetview_columns()
    assert len(columns) == 181
    assert "point_id" in columns and "lon_wgs" in columns


def test_poi_table_columns(db_conn):
    cols = [r[1] for r in db_conn.execute('PRAGMA table_info("poi")').fetchall()]
    for c in ["poi_id", "name", "category_big", "category_mid", "lon", "lat"]:
        assert c in cols


def test_indexes_created(db_conn):
    indexes = [r[0] for r in db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]
    for idx in ["idx_poi_category", "idx_poi_lonlat", "idx_stations_lonlat"]:
        assert idx in indexes


def test_init_is_idempotent(tmp_path):
    db_path = tmp_path / "again.sqlite"
    conn1 = init_database(db_path)
    conn1.close()
    conn2 = init_database(db_path)
    tables = table_names(conn2)
    assert "poi" in tables
    conn2.close()
