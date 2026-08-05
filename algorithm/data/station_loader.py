"""共享单车停车点加载 (支持Shapefile/GeoJSON/CSV)"""
import pandas as pd
import geopandas as gpd
from pathlib import Path
from algorithm.config import DATA_DIR, STATION_FILE


def load_stations(file_path: str = None, db_path: str = None) -> gpd.GeoDataFrame:
    """加载单车停车点数据（优先经 database/repository 读取，支持文件读取）

    实际数据: 北京共享单车停车位.shp (3,293个站点, EPSG:4326)
    列名: 站点编, 站点名, 位置, 车位数, 经度_WGS, 纬度_WGS

    Args:
        file_path: 文件路径（shp/geojson/csv），显式提供时走文件读取；
                   为 None 时优先从数据库读取
        db_path: 数据库路径（file_path 为 None 时生效），默认 database/bikeflow.sqlite

    Returns:
        GeoDataFrame, CRS=EPSG:4326, 含station_id/capacity列
    """
    if file_path is None:
        try:
            from database.repository import read_stations, to_geodataframe
            df = read_stations(db_path) if db_path else read_stations()
            if len(df) > 0:
                return to_geodataframe(df, "lon_wgs", "lat_wgs")
        except Exception:
            pass
        file_path = DATA_DIR / STATION_FILE

    path = Path(file_path)

    if path.suffix in (".shp", ".geojson", ".json"):
        # Shapefile 或 GeoJSON → geopandas直接读取
        gdf = gpd.read_file(path)
    elif path.suffix == ".csv":
        df = pd.read_csv(path)
        lon_col = next((c for c in ["经度_WGS", "lng", "lon", "经度", "longitude"]
                        if c in df.columns), None)
        lat_col = next((c for c in ["纬度_WGS", "lat", "纬度", "latitude"]
                        if c in df.columns), None)
        if lon_col is None or lat_col is None:
            raise ValueError(f"CSV中未找到经纬度列，现有列: {list(df.columns)}")
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
            crs="EPSG:4326"
        )
    else:
        raise ValueError(f"不支持的文件格式: {path.suffix}")

    return normalize_stations(gdf)


def normalize_stations(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """标准化站点GeoDataFrame

    处理:
        - 统一EPSG:4326
        - 添加station_id
        - 将"车位数"列映射为"capacity"（兼容Shapefile实际列名）
        - 缺失capacity时默认0

    Args:
        gdf: 原始站点GeoDataFrame

    Returns:
        含station_id和capacity列的标准化GeoDataFrame
    """
    gdf = gdf.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    gdf["station_id"] = range(len(gdf))

    # 映射实际列名: 车位数 → capacity
    if "capacity" not in gdf.columns:
        if "车位数" in gdf.columns:
            gdf["capacity"] = gdf["车位数"].fillna(0).astype(int)
        else:
            gdf["capacity"] = 0

    return gdf
