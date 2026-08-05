"""数据库层 — 统一访问层（只读 API，供算法层与网关层使用）

所有数据从 database/bikeflow.sqlite 读取，屏蔽底层存储细节：
    - 点数据返回 DataFrame（含 lon/lat 列）
    - 线/面数据返回 GeoDataFrame（WKT 反序列化为 shapely 几何，CRS=EPSG:4326）
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import wkt

from database.schema import DB_PATH, get_connection

__all__ = [
    "read_streetview",
    "read_poi",
    "read_stations",
    "read_segments",
    "read_buildings",
    "read_districts",
    "read_routes",
    "read_meta",
    "table_row_counts",
    "to_geodataframe",
]


def _read_sql(sql: str, db_path: str | Path = DB_PATH) -> pd.DataFrame:
    conn = get_connection(db_path)
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def _wkt_to_gdf(df: pd.DataFrame, geom_col: str = "geometry_wkt") -> gpd.GeoDataFrame:
    """将含 WKT 列的 DataFrame 转为 GeoDataFrame（EPSG:4326）"""
    geoms = df[geom_col].apply(lambda s: wkt.loads(s) if s else None)
    gdf = gpd.GeoDataFrame(df.drop(columns=[geom_col]), geometry=geoms, crs="EPSG:4326")
    return gdf


def to_geodataframe(df: pd.DataFrame, lon_col: str = "lon", lat_col: str = "lat") -> gpd.GeoDataFrame:
    """将含经纬度列的 DataFrame 转为点 GeoDataFrame（EPSG:4326）"""
    lon = pd.to_numeric(df[lon_col], errors="coerce")
    lat = pd.to_numeric(df[lat_col], errors="coerce")
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(lon, lat), crs="EPSG:4326")


# ── 点数据（返回 DataFrame） ──


def read_streetview(db_path: str | Path = DB_PATH) -> pd.DataFrame:
    """读取全部街景观测原始记录（181 列，10131 行；不含内部主键 id）"""
    conn = get_connection(db_path)
    try:
        cols = [r[1] for r in conn.execute('PRAGMA table_info("streetview_observations")').fetchall()]
        cols = [c for c in cols if c != "id"]  # 屏蔽内部主键，返回与源 CSV 一致的列
        col_sql = ",".join(f'"{c}"' for c in cols)
        return pd.read_sql_query(f"SELECT {col_sql} FROM streetview_observations", conn)
    finally:
        conn.close()


def read_poi(db_path: str | Path = DB_PATH) -> pd.DataFrame:
    """读取全部 POI（约 80 万行）"""
    return _read_sql("SELECT * FROM poi", db_path)


def read_stations(db_path: str | Path = DB_PATH) -> pd.DataFrame:
    """读取全部共享单车停车点（3293 行）"""
    return _read_sql("SELECT * FROM stations", db_path)


# ── 空间数据（返回 GeoDataFrame，WKT 反序列化） ──


def read_segments(db_path: str | Path = DB_PATH) -> gpd.GeoDataFrame:
    """读取骑行街道段（LineString）"""
    return _wkt_to_gdf(_read_sql("SELECT * FROM segments", db_path))


def read_buildings(db_path: str | Path = DB_PATH) -> gpd.GeoDataFrame:
    """读取建筑轮廓（Polygon）"""
    return _wkt_to_gdf(_read_sql("SELECT * FROM buildings", db_path))


def read_districts(db_path: str | Path = DB_PATH) -> gpd.GeoDataFrame:
    """读取北京六区轮廓（MultiLineString）"""
    return _wkt_to_gdf(_read_sql("SELECT * FROM districts", db_path))


def read_routes(db_path: str | Path = DB_PATH) -> gpd.GeoDataFrame:
    """读取历史路线结果（LineString）"""
    return _wkt_to_gdf(_read_sql("SELECT * FROM routes", db_path))


# ── 元数据 / 统计 ──


def read_meta(db_path: str | Path = DB_PATH) -> list[dict]:
    """读取数据集元数据"""
    df = _read_sql("SELECT dataset, source_path, row_count, ingested_at, note FROM dataset_meta ORDER BY dataset", db_path)
    return df.to_dict(orient="records")


def table_row_counts(db_path: str | Path = DB_PATH) -> dict[str, int]:
    """各表行数统计（用于数据完整性校验）"""
    conn = get_connection(db_path)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()]
        return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
    finally:
        conn.close()
