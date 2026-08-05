"""数据库层 — SQLite 空间库 schema 定义与建库入口

`database/bikeflow.sqlite` 是全量数据的主存储（真实数据库系统）：

    表                         内容                                  来源
    -----------------------------------------------------------------------------
    dataset_meta                数据集元数据（来源/行数/入库时间）      入库脚本写入
    streetview_observations     街景观测原始记录（2563点×4方向）        raw/streetview/*.csv
    poi                         北京 POI 全量（约80万）                raw/poi/北京市.csv
    stations                    共享单车停车点（3293个）               raw/stations/*.shp
    segments                    骑行街道段（LineString, WKT）          processed/beijing_segments_bike.gpkg
    buildings                   建筑轮廓（Polygon, WKT）               processed/beijing_buildings_6district.gpkg
    districts                   北京六区轮廓（MultiLineString, WKT）    output/beijing_districts_osm.geojson
    routes                      历史路线结果（LineString, WKT）        output/routes.geojson

空间几何以 WKT（TEXT）存储，避免对 SpatiaLite 扩展的运行时依赖；
点状数据同时保留 lon/lat 数值列，便于空间查询与 KDTree 构建。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bikeflow.sqlite"

# ── 各数据源相对 BASE_DIR 的路径 ──
STREETVIEW_CSV = BASE_DIR / "raw" / "streetview" / "streetview_direction_metrics_20260801-143827.csv"
POI_CSV = BASE_DIR / "raw" / "poi" / "北京市.csv"
STATION_SHP = BASE_DIR / "raw" / "stations" / "北京共享单车停车位.shp"
SEGMENTS_GPKG = BASE_DIR / "processed" / "beijing_segments_bike.gpkg"
BUILDINGS_GPKG = BASE_DIR / "processed" / "beijing_buildings_6district.gpkg"
DISTRICTS_GEOJSON = BASE_DIR / "output" / "beijing_districts_osm.geojson"
ROUTES_GEOJSON = BASE_DIR / "output" / "routes.geojson"

# 固定表 DDL（streetview_observations 为宽表，见 create_streetview_table）
FIXED_TABLES: dict[str, str] = {
    "dataset_meta": """
        CREATE TABLE IF NOT EXISTS dataset_meta (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset     TEXT NOT NULL UNIQUE,
            source_path TEXT NOT NULL,
            row_count   INTEGER NOT NULL DEFAULT 0,
            ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
            note        TEXT
        )
    """,
    "poi": """
        CREATE TABLE IF NOT EXISTS poi (
            poi_id       INTEGER PRIMARY KEY,
            name         TEXT,
            category_big TEXT,
            category_mid TEXT,
            lon          REAL NOT NULL,
            lat          REAL NOT NULL,
            province     TEXT,
            district     TEXT
        )
    """,
    "stations": """
        CREATE TABLE IF NOT EXISTS stations (
            station_id INTEGER PRIMARY KEY,
            code       TEXT,
            name       TEXT,
            location   TEXT,
            capacity   INTEGER NOT NULL DEFAULT 0,
            lon_wgs    REAL NOT NULL,
            lat_wgs    REAL NOT NULL
        )
    """,
    "segments": """
        CREATE TABLE IF NOT EXISTS segments (
            seg_id       INTEGER PRIMARY KEY,
            highway      TEXT,
            name         TEXT,
            length       REAL,
            geometry_wkt TEXT
        )
    """,
    "buildings": """
        CREATE TABLE IF NOT EXISTS buildings (
            place_id     INTEGER PRIMARY KEY,
            levels       INTEGER,
            height_m     REAL,
            area_m2      REAL,
            geometry_wkt TEXT
        )
    """,
    "districts": """
        CREATE TABLE IF NOT EXISTS districts (
            name         TEXT,
            admin_level  TEXT,
            geometry_wkt TEXT
        )
    """,
    "routes": """
        CREATE TABLE IF NOT EXISTS routes (
            route_id          INTEGER PRIMARY KEY,
            total_length      REAL,
            total_cost        REAL,
            avg_safety        REAL,
            avg_comfort       REAL,
            avg_scenery       REAL,
            avg_traffic_stress REAL,
            avg_beauty        REAL,
            avg_pref_score    REAL,
            num_segments      INTEGER,
            geometry_wkt      TEXT
        )
    """,
}

# 常用索引
INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_poi_category ON poi(category_big)",
    "CREATE INDEX IF NOT EXISTS idx_poi_lonlat ON poi(lon, lat)",
    "CREATE INDEX IF NOT EXISTS idx_stations_lonlat ON stations(lon_wgs, lat_wgs)",
]


def get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    """打开数据库连接（开启 WAL 与外键）"""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def read_streetview_columns(csv_path: str | Path = STREETVIEW_CSV) -> list[str]:
    """只读 CSV 表头（不读数据），返回全部列名"""
    import pandas as pd

    header = pd.read_csv(csv_path, nrows=0, encoding="utf-8-sig")
    return list(header.columns)


def create_streetview_table(conn: sqlite3.Connection, columns: list[str]) -> None:
    """动态创建 streetview_observations 宽表（保留 CSV 全部原始列，无损入库）"""
    col_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
    for c in columns:
        if c == "id":
            continue
        col_defs.append(f'"{c.replace(chr(34), chr(34)+chr(34))}" TEXT')
    ddl = "CREATE TABLE IF NOT EXISTS streetview_observations (\n    " + ",\n    ".join(col_defs) + "\n)"
    conn.execute(ddl)


def create_all_tables(conn: sqlite3.Connection) -> None:
    """创建全部固定表 + streetview 宽表 + 索引"""
    for ddl in FIXED_TABLES.values():
        conn.execute(ddl)
    create_streetview_table(conn, read_streetview_columns())
    for idx in INDEXES:
        conn.execute(idx)
    conn.commit()


def init_database(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    """初始化（建库）并返回连接。可安全重复调用。"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    create_all_tables(conn)
    return conn


def table_names(conn: sqlite3.Connection) -> list[str]:
    """查询当前库中所有表名（用于验证）"""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


if __name__ == "__main__":
    conn = init_database()
    print(f"database initialized: {DB_PATH}")
    print("tables:", ", ".join(table_names(conn)))
    conn.close()
