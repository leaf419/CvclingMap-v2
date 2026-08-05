"""只读探针：打印各数据源的列结构（用于 schema 设计）

用法: python database/scripts/probe_sources.py
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

STREETVIEW_CSV = BASE / "raw" / "streetview" / "streetview_direction_metrics_20260801-143827.csv"
POI_CSV = BASE / "raw" / "poi" / "北京市.csv"
STATION_SHP = BASE / "raw" / "stations" / "北京共享单车停车位.shp"
PROCESSED_GPKGS = sorted((BASE / "processed").glob("*.gpkg"))
OUTPUT_GEOJSONS = sorted((BASE / "output").glob("*.geojson"))


def probe_csv(path: Path, n: int = 3) -> None:
    import pandas as pd
    print(f"\n=== CSV: {path.name} ===")
    df = pd.read_csv(path, nrows=n)
    print(f"columns ({len(df.columns)}):")
    for c in df.columns:
        print(f"  - {c}")
    print("first row:")
    print(df.iloc[0].to_dict())


def probe_gdf(path: Path, n: int = 3) -> None:
    import geopandas as gpd
    print(f"\n=== GIS: {path.name} ===")
    gdf = gpd.read_file(path, rows=n) if path.suffix == ".gpkg" else gpd.read_file(path)
    print(f"crs: {gdf.crs}  geometry: {gdf.geometry.geom_type.iloc[0]}")
    print(f"columns ({len(gdf.columns)}):")
    for c in gdf.columns:
        print(f"  - {c}")
    print("first row (attrs only):")
    attrs = {k: v for k, v in gdf.iloc[0].to_dict().items() if k != "geometry"}
    print(attrs)


def main() -> None:
    print(f"python: {sys.version}")
    try:
        import pandas  # noqa: F401
        print(f"pandas: {pandas.__version__}")
    except ImportError as e:
        print(f"pandas NOT available: {e}")
    try:
        import geopandas  # noqa: F401
        print(f"geopandas: {geopandas.__version__}")
    except ImportError as e:
        print(f"geopandas NOT available: {e}")
    try:
        import shapely  # noqa: F401
        print(f"shapely: {shapely.__version__}")
    except ImportError as e:
        print(f"shapely NOT available: {e}")

    probe_csv(STREETVIEW_CSV)
    probe_csv(POI_CSV)
    probe_gdf(STATION_SHP)
    for p in PROCESSED_GPKGS:
        probe_gdf(p)
    for p in OUTPUT_GEOJSONS:
        probe_gdf(p)


if __name__ == "__main__":
    main()
