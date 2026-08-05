"""数据库层入库脚本 — 将 database/raw、database/processed、database/output 的全量数据写入 bikeflow.sqlite

用法:
    python database/scripts/ingest_all.py                 # 全量入库
    python database/scripts/ingest_all.py --dataset poi   # 单数据集入库

入库后向 dataset_meta 记录来源与行数；重复入库会先清空对应表（幂等）。
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent  # database/
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.schema import (  # noqa: E402
    DB_PATH,
    STREETVIEW_CSV,
    POI_CSV,
    STATION_SHP,
    SEGMENTS_GPKG,
    BUILDINGS_GPKG,
    DISTRICTS_GEOJSON,
    ROUTES_GEOJSON,
    get_connection,
    init_database,
)

# ── POI 中文列名 → 数据库英文列名 ──
POI_COLUMN_MAP = {
    "名称": "name",
    "大类": "category_big",
    "中类": "category_mid",
    "经度": "lon",
    "纬度": "lat",
    "省份": "province",
    "区县": "district",
}


def _read_csv_any_encoding(path: Path) -> pd.DataFrame:
    """读取 CSV：优先 UTF-8（含 BOM），失败回退 GB18030"""
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="gb18030")


def _write_meta(conn: sqlite3.Connection, dataset: str, source: Path, count: int, note: str = "") -> None:
    conn.execute(
        "INSERT OR REPLACE INTO dataset_meta (dataset, source_path, row_count, note) VALUES (?, ?, ?, ?)",
        (dataset, str(source), count, note),
    )
    conn.commit()  # 立即提交，避免最后一个数据集元数据滞留在未提交事务中


def _frame_to_sql_rows(df: pd.DataFrame) -> list[list]:
    """DataFrame → SQL 行列表（NaN → None）"""
    return df.where(pd.notna(df), None).values.tolist()


def ingest_streetview(conn: sqlite3.Connection, clear: bool = True) -> int:
    """streetview_observations：全量 181 列无损入库"""
    df = _read_csv_any_encoding(STREETVIEW_CSV)
    columns = list(df.columns)
    if clear:
        conn.execute("DELETE FROM streetview_observations")
    col_sql = ",".join(f'"{c}"' for c in columns)
    placeholders = ",".join("?" * len(columns))
    conn.executemany(
        f"INSERT INTO streetview_observations ({col_sql}) VALUES ({placeholders})",
        _frame_to_sql_rows(df),
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM streetview_observations").fetchone()[0]
    _write_meta(conn, "streetview_observations", STREETVIEW_CSV, count,
                note=f"{len(columns)} 列，2563 采样点 × 4 方向")
    return count


def ingest_poi(conn: sqlite3.Connection, clear: bool = True) -> int:
    """poi：80 万 POI 全量入库（中文列名映射为英文）"""
    df = _read_csv_any_encoding(POI_CSV)
    rename = {k: v for k, v in POI_COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)
    for col in ("lon", "lat"):
        if col not in df.columns:
            raise ValueError(f"POI CSV 缺少 {col} 列，现有列: {list(df.columns)}")
    df["poi_id"] = range(len(df))
    cols = ["poi_id", "name", "category_big", "category_mid", "lon", "lat", "province", "district"]
    cols = [c for c in cols if c in df.columns]
    if clear:
        conn.execute("DELETE FROM poi")
    col_sql = ",".join(cols)
    placeholders = ",".join("?" * len(cols))
    conn.executemany(
        f"INSERT INTO poi ({col_sql}) VALUES ({placeholders})",
        _frame_to_sql_rows(df[cols]),
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM poi").fetchone()[0]
    _write_meta(conn, "poi", POI_CSV, count, note="北京全量 POI")
    return count


def ingest_stations(conn: sqlite3.Connection, clear: bool = True) -> int:
    """stations：共享单车停车点 shp → 点表"""
    import geopandas as gpd

    gdf = gpd.read_file(STATION_SHP)
    gdf = gdf.to_crs("EPSG:4326")
    col_map = {
        "站点编": "code", "站点名": "name", "位置": "location",
        "车位数": "capacity", "经度_WGS": "lon_wgs", "纬度_WGS": "lat_wgs",
    }
    rename = {k: v for k, v in col_map.items() if k in gdf.columns}
    gdf = gdf.rename(columns=rename)
    if "lon_wgs" not in gdf.columns:
        gdf["lon_wgs"] = gdf.geometry.x
        gdf["lat_wgs"] = gdf.geometry.y
    gdf["station_id"] = range(len(gdf))
    gdf["capacity"] = gdf.get("capacity", 0).fillna(0).astype(int)
    cols = ["station_id", "code", "name", "location", "capacity", "lon_wgs", "lat_wgs"]
    cols = [c for c in cols if c in gdf.columns]
    if clear:
        conn.execute("DELETE FROM stations")
    col_sql = ",".join(cols)
    placeholders = ",".join("?" * len(cols))
    conn.executemany(
        f"INSERT INTO stations ({col_sql}) VALUES ({placeholders})",
        _frame_to_sql_rows(gdf[cols]),
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
    _write_meta(conn, "stations", STATION_SHP, count, note="2017 年共享单车停车位")
    return count


def _ingest_geodataframe(
    conn: sqlite3.Connection,
    table: str,
    source: Path,
    col_map: dict[str, str],
    clear: bool,
    note: str,
) -> int:
    """通用空间数据入库：几何转 WKT，属性列映射"""
    import geopandas as gpd

    gdf = gpd.read_file(source)
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")
    rename = {k: v for k, v in col_map.items() if k in gdf.columns}
    gdf = gdf.rename(columns=rename)
    gdf["geometry_wkt"] = gdf.geometry.apply(lambda g: g.wkt if g is not None else None)
    cols = list(col_map.values()) + ["geometry_wkt"]
    cols = [c for c in cols if c in gdf.columns]
    if clear:
        conn.execute(f"DELETE FROM {table}")
    col_sql = ",".join(cols)
    placeholders = ",".join("?" * len(cols))
    conn.executemany(
        f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})",
        _frame_to_sql_rows(gdf[cols]),
    )
    conn.commit()
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    _write_meta(conn, table, source, count, note=note)
    return count


def ingest_segments(conn: sqlite3.Connection, clear: bool = True) -> int:
    return _ingest_geodataframe(
        conn, "segments", SEGMENTS_GPKG,
        {"seg_id": "seg_id", "highway": "highway", "name": "name", "length": "length"},
        clear, "骑行街道段（processed gpkg）",
    )


def ingest_buildings(conn: sqlite3.Connection, clear: bool = True) -> int:
    return _ingest_geodataframe(
        conn, "buildings", BUILDINGS_GPKG,
        {"place_id": "place_id", "levels": "levels", "height_m": "height_m", "area_m2": "area_m2"},
        clear, "建筑轮廓（processed gpkg）",
    )


def ingest_districts(conn: sqlite3.Connection, clear: bool = True) -> int:
    return _ingest_geodataframe(
        conn, "districts", DISTRICTS_GEOJSON,
        {"name": "name", "admin_level": "admin_level"},
        clear, "北京六区轮廓（output geojson）",
    )


def ingest_routes(conn: sqlite3.Connection, clear: bool = True) -> int:
    return _ingest_geodataframe(
        conn, "routes", ROUTES_GEOJSON,
        {
            "route_id": "route_id", "total_length": "total_length",
            "total_cost": "total_cost", "avg_safety": "avg_safety",
            "avg_comfort": "avg_comfort", "avg_scenery": "avg_scenery",
            "avg_traffic_stress": "avg_traffic_stress", "avg_beauty": "avg_beauty",
            "avg_pref_score": "avg_pref_score", "num_segments": "num_segments",
        },
        clear, "历史路线结果（output geojson）",
    )


INGESTORS = {
    "streetview": ingest_streetview,
    "poi": ingest_poi,
    "stations": ingest_stations,
    "segments": ingest_segments,
    "buildings": ingest_buildings,
    "districts": ingest_districts,
    "routes": ingest_routes,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="入库脚本：raw/processed/output → bikeflow.sqlite")
    parser.add_argument("--dataset", choices=list(INGESTORS) + ["all"], default="all",
                        help="入库的数据集，默认 all")
    parser.add_argument("--db", default=str(DB_PATH), help="数据库路径")
    args = parser.parse_args()

    conn = init_database(args.db)
    targets = list(INGESTORS) if args.dataset == "all" else [args.dataset]

    print(f"database: {args.db}")
    results = {}
    for name in targets:
        count = INGESTORS[name](conn)
        results[name] = count
        print(f"  [{name}] {count} rows")

    # 汇总
    print("\n=== dataset_meta ===")
    rows = conn.execute(
        "SELECT dataset, row_count, ingested_at FROM dataset_meta ORDER BY dataset"
    ).fetchall()
    for r in rows:
        print(f"  {r[0]:<24} {r[1]:>9}  {r[2]}")
    conn.close()


if __name__ == "__main__":
    main()
