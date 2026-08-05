"""GeoScene SceneView 3D场景数据导出

将算法层产出的街道段、站点、路线导出为GeoJSON，
供前端GeoScene SceneView 3D场景加载。
"""
import json
import geopandas as gpd
from pathlib import Path
from typing import List

SEGMENT_EXPORT_COLS = [
    "seg_id", "length", "cost_composite",
    "w_safety", "w_comfort", "w_scenery", "f_traffic_stress",
    "v_beauty", "v_greenery", "pref_score",
]

STATION_EXPORT_COLS = ["station_id", "name", "capacity"]


def export_segments_geojson(
    segments_gdf: gpd.GeoDataFrame,
    output_path: str,
) -> None:
    """导出街道段为GeoJSON"""
    cols = [c for c in SEGMENT_EXPORT_COLS if c in segments_gdf.columns]
    export_gdf = segments_gdf[cols + ["geometry"]].copy()

    for c in cols:
        if c != "seg_id":
            export_gdf[c] = export_gdf[c].fillna(0).astype(float)

    if export_gdf.crs is None:
        export_gdf = export_gdf.set_crs("EPSG:4326")
    elif export_gdf.crs.to_string() != "EPSG:4326":
        export_gdf = export_gdf.to_crs("EPSG:4326")

    export_gdf.to_file(output_path, driver="GeoJSON")


def export_stations_geojson(
    stations_gdf: gpd.GeoDataFrame,
    output_path: str,
) -> None:
    """导出站点为GeoJSON"""
    cols = [c for c in STATION_EXPORT_COLS if c in stations_gdf.columns]
    export_gdf = stations_gdf[cols + ["geometry"]].copy()
    export_gdf = export_gdf[export_gdf.geometry.type == "Point"]

    if export_gdf.crs is None:
        export_gdf = export_gdf.set_crs("EPSG:4326")
    elif export_gdf.crs.to_string() != "EPSG:4326":
        export_gdf = export_gdf.to_crs("EPSG:4326")

    export_gdf.to_file(output_path, driver="GeoJSON")


def export_buildings_geojson(
    buildings_gdf: gpd.GeoDataFrame,
    output_path: str,
) -> None:
    """导出建筑体块为GeoJSON（供前端SceneView白模拉伸）

    Args:
        buildings_gdf: 含 height_m, area_m2 列的GeoDataFrame
        output_path: 输出路径
    """
    cols = ["place_id", "height_m", "area_m2", "geometry"]
    avail = [c for c in cols if c in buildings_gdf.columns]
    export_gdf = buildings_gdf[avail].copy()

    if export_gdf.crs is None:
        export_gdf = export_gdf.set_crs("EPSG:4326")
    elif export_gdf.crs.to_string() != "EPSG:4326":
        export_gdf = export_gdf.to_crs("EPSG:4326")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    export_gdf.to_file(output_path, driver="GeoJSON")


def export_scene_config(
    output_path: str,
    center_lon: float,
    center_lat: float,
    zoom: int = 14,
    layers: List[str] = None,
    **extra_kwargs,
) -> None:
    """导出GeoScene WebScene 3D场景配置JSON"""
    if layers is None:
        layers = ["segments", "stations", "routes"]

    config = {
        "version": "2.0",
        "type": "WebScene",
        "sceneView": {
            "viewingMode": "global",
            "center": [center_lon, center_lat],
            "zoom": zoom,
        },
        "center": [center_lon, center_lat],
        "zoom": zoom,
        "layers": layers,
        "projection": "EPSG:4326",
        "terrain": {"enabled": False},
        "buildings": {"enabled": True, "extrude": True},
        **extra_kwargs,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
