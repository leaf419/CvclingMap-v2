"""街景指标数据加载与4方向confidence加权聚合"""
import pandas as pd
import geopandas as gpd
from algorithm.config import DATA_DIR, STREETVIEW_CSV

# ── 指标映射表: 输出列名 → (原始value字段, 原始confidence字段) ──
# 注意: 字段名已对齐实际CSV列名（非计划中的假设列名）
METRIC_MAPPING = {
    "safety": {
        "s_bike_lane_type": ("metric_bike_lane_type_value",
                             "metric_bike_lane_type_confidence_0_1"),
        "s_physical_separation": ("metric_physical_separation_value",
                                  "metric_physical_separation_confidence_0_1"),
        "s_motor_pressure": ("metric_motor_traffic_pressure_value",
                             "metric_motor_traffic_pressure_confidence_0_1"),
        "s_heavy_vehicle": ("metric_heavy_vehicle_exposure_value",
                            "metric_heavy_vehicle_exposure_confidence_0_1"),
        "s_parking_encroach": ("metric_parking_encroachment_value",
                               "metric_parking_encroachment_confidence_0_1"),
        "s_intersection_conflict": ("metric_intersection_conflict_value",
                                    "metric_intersection_conflict_confidence_0_1"),
        "s_traffic_control": ("metric_traffic_control_visible_value",
                              "metric_traffic_control_visible_confidence_0_1"),
        "s_crosswalk": ("metric_crosswalk_visible_value",
                        "metric_crosswalk_visible_confidence_0_1"),
    },
    "comfort": {
        "f_surface_quality": ("metric_road_surface_quality_value",
                              "metric_road_surface_quality_confidence_0_1"),
        "f_pothole": ("metric_pothole_damage_value",
                      "metric_pothole_damage_confidence_0_1"),
        "f_construction": ("metric_construction_impact_value",
                           "metric_construction_impact_confidence_0_1"),
        "f_obstacle": ("metric_obstacle_blockage_value",
                       "metric_obstacle_blockage_confidence_0_1"),
        "f_rideable_width": ("metric_effective_rideable_width_value",
                             "metric_effective_rideable_width_confidence_0_1"),
        "f_overall_comfort": ("metric_overall_cycling_comfort_value",
                              "metric_overall_cycling_comfort_confidence_0_1"),
        "f_traffic_stress": ("metric_traffic_stress_value",
                             "metric_traffic_stress_confidence_0_1"),
        "f_route_continuity": ("metric_route_continuity_value",
                               "metric_route_continuity_confidence_0_1"),
        "f_perceived_safety": ("metric_perceived_safety_value",
                               "metric_perceived_safety_confidence_0_1"),
        "f_lighting_comfort": ("metric_lighting_facility_visible_value",
                               "metric_lighting_facility_visible_confidence_0_1"),
    },
    "scenery": {
        "v_greenery": ("metric_visible_greenery_value",
                       "metric_visible_greenery_confidence_0_1"),
        "v_tree_shade": ("metric_tree_shade_potential_value",
                        "metric_tree_shade_potential_confidence_0_1"),
        "v_sky_openness": ("metric_sky_openness_value",
                          "metric_sky_openness_confidence_0_1"),
        "v_water": ("metric_water_visible_value",
                    "metric_water_visible_confidence_0_1"),
        "v_sun_exposure": ("metric_sun_exposure_value",
                          "metric_sun_exposure_confidence_0_1"),
        "v_enclosure": ("metric_enclosure_human_scale_value",
                       "metric_enclosure_human_scale_confidence_0_1"),
        "v_visual_order": ("metric_visual_order_value",
                          "metric_visual_order_confidence_0_1"),
        "v_active_frontage": ("metric_active_frontage_value",
                             "metric_active_frontage_confidence_0_1"),
        "v_shops": ("metric_shops_services_value",
                    "metric_shops_services_confidence_0_1"),
        "v_cleanliness": ("metric_street_cleanliness_value",
                         "metric_street_cleanliness_confidence_0_1"),
        "v_beauty": ("metric_beauty_value",
                     "metric_beauty_confidence_0_1"),
        "v_tranquility": ("metric_tranquility_value",
                         "metric_tranquility_confidence_0_1"),
    },
    "experience": {
        "x_perceived_safety": ("metric_perceived_safety_value",
                               "metric_perceived_safety_confidence_0_1"),
        "x_enclosure": ("metric_enclosure_human_scale_value",
                       "metric_enclosure_human_scale_confidence_0_1"),
        "x_visual_order": ("metric_visual_order_value",
                          "metric_visual_order_confidence_0_1"),
        "x_active_frontage": ("metric_active_frontage_value",
                             "metric_active_frontage_confidence_0_1"),
        "x_shops": ("metric_shops_services_value",
                    "metric_shops_services_confidence_0_1"),
        "x_cleanliness": ("metric_street_cleanliness_value",
                         "metric_street_cleanliness_confidence_0_1"),
        "x_lighting": ("metric_lighting_facility_visible_value",
                      "metric_lighting_facility_visible_confidence_0_1"),
    },
}

# 扁平化映射: 输出列名 → (value_field, conf_field)
ALL_METRICS = {}
for group in METRIC_MAPPING.values():
    ALL_METRICS.update(group)


def _weighted_avg(group: pd.DataFrame, value_col: str, conf_col: str) -> float:
    """confidence加权平均"""
    weights = group[conf_col].fillna(0).values
    values = group[value_col].fillna(0).values
    total_w = weights.sum()
    if total_w == 0:
        return values.mean() if len(values) > 0 else 0.0
    return float((values * weights).sum() / total_w)


def _normalize_values(df: pd.DataFrame) -> pd.DataFrame:
    """将非数值 metric 值标准化为 float（原 load_streetview_csv 的处理逻辑）"""
    # 分类字符串映射 (0~1)
    BIKE_LANE_MAP = {"none": 0.0, "shared": 0.5, "painted": 0.3, "uncertain": 0.1}

    value_cols = [c for c in df.columns if c.endswith("_value") and c != "quality_viewpoint_usable_value"]
    for c in value_cols:
        if df[c].dtype == "object":
            # 尝试分类映射
            if c == "metric_bike_lane_type_value":
                df[c] = df[c].map(BIKE_LANE_MAP).fillna(0).astype(float)
            else:
                try:
                    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(float)
                except Exception:
                    df[c] = 0.0
        elif df[c].dtype == "bool":
            df[c] = df[c].astype(float)
        # 将 0-5 Likert 量表归一化到 0-1
        if df[c].dtype == "float64":
            col_max = df[c].max()
            if col_max > 1.0:
                df[c] = df[c] / max(col_max, 1.0)

    # 数据库宽表列全为 TEXT：置信度列与基础坐标列需显式转数值
    conf_cols = [c for c in df.columns if c.endswith("_confidence_0_1")]
    for c in conf_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(float)
    for c in ("lon_wgs", "lat_wgs", "lon_bd09", "lat_bd09"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)

    return df


def load_streetview_csv(db_path: str = None) -> pd.DataFrame:
    """加载街景指标（优先经 database/repository 读取，回退原 CSV 文件）

    Args:
        db_path: 数据库路径；默认使用 database/bikeflow.sqlite

    Returns:
        与源 CSV 同构的 DataFrame（181 列），非数值 metric 值已标准化为 float
    """
    try:
        from database.repository import read_streetview
        df = read_streetview(db_path) if db_path else read_streetview()
        if len(df) > 0:
            return _normalize_values(df)
    except Exception:
        pass

    csv_path = DATA_DIR / STREETVIEW_CSV
    df = pd.read_csv(csv_path)
    return _normalize_values(df)


def aggregate_by_point(sv_df: pd.DataFrame) -> pd.DataFrame:
    """按point_id聚合，4方向取confidence加权平均

    Args:
        sv_df: 原始街景DataFrame，每行一个方向

    Returns:
        每个采样点一行的聚合DataFrame，含~30个核心指标列
    """
    results = []
    for pid, group in sv_df.groupby("point_id"):
        row = {"point_id": pid}
        for out_col, (val_field, conf_field) in ALL_METRICS.items():
            if val_field in group.columns and conf_field in group.columns:
                row[out_col] = _weighted_avg(group, val_field, conf_field)
            else:
                row[out_col] = 0.0
        results.append(row)

    agg_df = pd.DataFrame(results)
    return agg_df


def to_geodataframe(sv_df: pd.DataFrame, agg_df: pd.DataFrame) -> gpd.GeoDataFrame:
    """将聚合后的指标转换为GeoDataFrame

    Args:
        sv_df: 原始街景DataFrame（含lon_wgs/lat_wgs坐标）
        agg_df: aggregate_by_point输出

    Returns:
        GeoDataFrame，CRS=EPSG:4326，含obs_id列
    """
    # 取每个point_id的第一条记录获取坐标
    coords = sv_df.drop_duplicates("point_id")[["point_id", "lon_wgs", "lat_wgs"]]
    merged = agg_df.merge(coords, on="point_id", how="left")

    gdf = gpd.GeoDataFrame(
        merged,
        geometry=gpd.points_from_xy(merged["lon_wgs"], merged["lat_wgs"]),
        crs="EPSG:4326"
    )
    gdf["obs_id"] = range(len(gdf))
    return gdf


def load_and_process_streetview() -> gpd.GeoDataFrame:
    """完整流程：加载CSV → 聚合 → 转GeoDataFrame"""
    sv_df = load_streetview_csv()
    agg = aggregate_by_point(sv_df)
    obs_gdf = to_geodataframe(sv_df, agg)
    return obs_gdf
