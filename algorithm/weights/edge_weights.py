"""街景指标驱动的四维边权模型"""
import numpy as np
import geopandas as gpd


def safety_from_streetview(metrics: dict) -> float:
    """从街景指标计算安全性 (0=危险, 1=安全)

    8项指标: 自行车道类型、物理隔离、机动车压力(反转)、大型车暴露(反转)、
             停车侵占(反转)、路口冲突(反转)、交通控制设施、斑马线
    """
    s_lane = metrics.get("s_bike_lane_type", 0.2)
    s_sep = metrics.get("s_physical_separation", 0.0)
    s_traffic = 1.0 - metrics.get("s_motor_pressure", 0.5)
    s_heavy = 1.0 - metrics.get("s_heavy_vehicle", 0.3)
    s_parking = 1.0 - metrics.get("s_parking_encroach", 0.2)
    s_intersection = 1.0 - metrics.get("s_intersection_conflict", 0.3)
    s_control = metrics.get("s_traffic_control", 0.5)
    s_crosswalk = metrics.get("s_crosswalk", 0.5)

    return float(np.average(
        [s_lane, s_sep, s_traffic, s_heavy,
         s_parking, s_intersection, s_control, s_crosswalk],
        weights=[0.25, 0.20, 0.15, 0.10, 0.10, 0.10, 0.05, 0.05]
    ))


def comfort_from_streetview(metrics: dict) -> float:
    """从街景指标计算舒适度 (0=差, 1=好)

    10项指标: 路面质量、坑洼(反转)、施工(反转)、障碍物(反转)、
             有效骑行宽度、整体舒适度、交通压力(反转)、路线连续性、
             感知安全、照明设施
    """
    f_surface = metrics.get("f_surface_quality", 0.5)
    f_pothole = 1.0 - metrics.get("f_pothole", 0.2)
    f_construction = 1.0 - metrics.get("f_construction", 0.0)
    f_obstacle = 1.0 - metrics.get("f_obstacle", 0.0)
    f_width = min(1.0, metrics.get("f_rideable_width", 2.0) / 4.0)
    f_overall = metrics.get("f_overall_comfort", 0.5)
    f_stress = 1.0 - metrics.get("f_traffic_stress", 0.4)
    f_continuity = metrics.get("f_route_continuity", 0.5)
    f_perceived = metrics.get("f_perceived_safety", 0.5)
    f_lighting = metrics.get("f_lighting_comfort", 0.5)

    return float(np.average(
        [f_surface, f_pothole, f_construction, f_obstacle,
         f_width, f_overall, f_stress, f_continuity,
         f_perceived, f_lighting],
        weights=[0.20, 0.15, 0.10, 0.10, 0.15, 0.20, 0.10, 0.05, 0.03, 0.02]
    ))


def scenery_from_streetview(metrics: dict) -> float:
    """从街景指标计算风景指数 (0=差, 1=好)

    12项指标: 可见绿植、树荫潜力、天空开阔度、水体可见、日照暴露、
             围合感、视觉秩序、活跃底界面、商铺服务、整洁度、美感、宁静度
    """
    v_green = metrics.get("v_greenery", 0.5)
    v_shade = metrics.get("v_tree_shade", 0.5)
    v_sky = metrics.get("v_sky_openness", 0.5)
    v_water = metrics.get("v_water", 0.0)
    v_sun = metrics.get("v_sun_exposure", 0.5)
    v_enclosure = metrics.get("v_enclosure", 0.5)
    v_order = metrics.get("v_visual_order", 0.5)
    v_frontage = metrics.get("v_active_frontage", 0.5)
    v_shops = metrics.get("v_shops", 0.5)
    v_clean = metrics.get("v_cleanliness", 0.5)
    v_beauty = metrics.get("v_beauty", 0.5)
    v_tranquil = metrics.get("v_tranquility", 0.5)

    return float(np.average(
        [v_green, v_shade, v_sky, v_water, v_sun,
         v_enclosure, v_order, v_frontage, v_shops,
         v_clean, v_beauty, v_tranquil],
        weights=[0.15, 0.10, 0.08, 0.08, 0.05,
                 0.08, 0.08, 0.08, 0.08,
                 0.08, 0.10, 0.04]
    ))


def experience_from_streetview(metrics: dict) -> float:
    """综合体验维度 (0=差, 1=好)

    7项指标: 感知安全、围合感/人尺度、视觉秩序、活跃底界面、
             商铺服务、街道整洁、照明设施
    """
    x_safety = metrics.get("x_perceived_safety", 0.5)
    x_enclosure = metrics.get("x_enclosure", 0.5)
    x_order = metrics.get("x_visual_order", 0.5)
    x_frontage = metrics.get("x_active_frontage", 0.5)
    x_shops = metrics.get("x_shops", 0.5)
    x_clean = metrics.get("x_cleanliness", 0.5)
    x_light = metrics.get("x_lighting", 0.5)

    return float(np.average(
        [x_safety, x_enclosure, x_order, x_frontage,
         x_shops, x_clean, x_light],
        weights=[0.25, 0.10, 0.10, 0.15, 0.15, 0.15, 0.10]
    ))


def compute_all_weights(segments_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """批量计算所有街道段的四维边权

    Args:
        segments_gdf: 含传播后街景指标列的街道段GeoDataFrame

    Returns:
        添加 w_safety, w_comfort, w_scenery, w_experience 列
    """
    result = segments_gdf.copy()

    weights_list = []
    for _, row in result.iterrows():
        metrics = row.to_dict()
        weights_list.append({
            "w_safety": safety_from_streetview(metrics),
            "w_comfort": comfort_from_streetview(metrics),
            "w_scenery": scenery_from_streetview(metrics),
            "w_experience": experience_from_streetview(metrics),
        })

    weights_df = gpd.GeoDataFrame(weights_list, index=result.index)

    for col in ["w_safety", "w_comfort", "w_scenery", "w_experience"]:
        result[col] = weights_df[col]

    return result
