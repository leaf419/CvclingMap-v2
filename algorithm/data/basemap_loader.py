"""天地图街道与建筑数据获取（GeoScene比赛合规，替代OSMnx）"""
import requests
import geopandas as gpd
from pathlib import Path
from shapely.geometry import shape

from algorithm.config import (
    DATA_DIR,
    STUDY_DISTRICTS,
    DISTRICT_CENTERS,
    TIANDITU_BASE_URL,
    TIANDITU_TOKEN,
    TIANDITU_LAYERS,
    GEOSCENE_SERVER_URL,
    GEOSCENE_SERVER_TOKEN,
    GEOSCENE_SERVICE_NAMES,
)


class _TiandituClient:
    """天地图矢量服务API客户端（requests封装）

    比赛合规：使用境内天地图数据源，替代境外OSMnx。
    """

    def __init__(self, base_url: str = TIANDITU_BASE_URL, token: str = TIANDITU_TOKEN):
        self.base_url = base_url
        self.token = token

    def get_street_geojson(self, bbox: tuple, layer: str = "vec_c") -> dict:
        """调用天地图矢量服务获取街道网络GeoJSON

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat) 边界框
            layer: 天地图图层名，默认矢量底图 vec_c

        Returns:
            GeoJSON FeatureCollection 字典
        """
        url = f"{self.base_url}/DataServer?T={layer}"
        params = {
            "tk": self.token,
            "bbox": ",".join(str(v) for v in bbox),
            "f": "geojson",
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()


# 全局客户端实例（测试中通过 patch('algorithm.data.basemap_loader.tianditu') 替换）
tianditu = _TiandituClient()


def _districts_to_bbox(districts: list = None) -> tuple:
    """将区域名/中心点转为bbox（用config中6区中心点合并包围盒）

    Args:
        districts: 区域名列表

    Returns:
        (min_lon, min_lat, max_lon, max_lat)
    """
    centers = DISTRICT_CENTERS
    lons = [c[0] for c in centers]
    lats = [c[1] for c in centers]
    margin = 0.05
    return (
        min(lons) - margin,
        min(lats) - margin,
        max(lons) + margin,
        max(lats) + margin,
    )


def fetch_street_network(districts: list = None) -> dict:
    """获取北京6区骑行街道网络（天地图矢量服务）

    Args:
        districts: 区域名列表，默认使用config中的6区

    Returns:
        天地图矢量服务返回的GeoJSON FeatureCollection（替代OSMnx MultiDiGraph）
    """
    if districts is None:
        districts = STUDY_DISTRICTS

    bbox = _districts_to_bbox(districts)
    geojson = tianditu.get_street_geojson(bbox, layer=TIANDITU_LAYERS["vec_c"])
    return geojson


def segments_to_gdf(geojson: dict) -> gpd.GeoDataFrame:
    """将天地图返回的街道GeoJSON转为segment GeoDataFrame

    Args:
        geojson: 天地图矢量服务返回的FeatureCollection

    Returns:
        每行一条街道段的GeoDataFrame
    """
    features = geojson.get("features", [])
    rows = []
    geoms = []
    for feat in features:
        rows.append(feat.get("properties", {}) or {})
        geoms.append(shape(feat["geometry"]))
    edges = gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:4326")
    edges = edges.reset_index(drop=True).copy()
    edges["seg_id"] = range(len(edges))
    return edges


def fetch_buildings(districts: list = None) -> gpd.GeoDataFrame:
    """获取建筑轮廓数据（GeoScene Pro建筑数据服务 / 本地File Geodatabase）

    Args:
        districts: 区域名列表

    Returns:
        建筑轮廓GeoDataFrame（比赛合规：不使用OSMnx境外建筑数据）
    """
    if districts is None:
        districts = STUDY_DISTRICTS

    # 优先从GeoScene Pro发布的建筑地图服务读取
    service_url = (
        f"{GEOSCENE_SERVER_URL}/services/"
        f"{GEOSCENE_SERVICE_NAMES['segments']}/MapServer"
    )
    params = {"f": "geojson", "token": GEOSCENE_SERVER_TOKEN}
    try:
        resp = requests.get(service_url, params=params, timeout=30)
        resp.raise_for_status()
        buildings = gpd.GeoDataFrame.from_features(
            resp.json()["features"], crs="EPSG:4326"
        )
        return buildings
    except Exception:
        # 回退：从GeoScene Pro导出的本地File Geodatabase读取
        fgdb = DATA_DIR / "raw" / "BeijingBuildings.gdb"
        if fgdb.exists():
            import fiona
            layer_name = fiona.listlayers(str(fgdb))[0]
            buildings = gpd.read_file(str(fgdb), layer=layer_name)
            return buildings
        raise RuntimeError(
            "无法获取建筑数据：GeoScene Server不可用且本地File Geodatabase不存在"
        )


def buildings_to_gdf(buildings: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """处理建筑数据：提取高度、计算面积

    Args:
        buildings: 原始建筑GeoDataFrame

    Returns:
        含height_m, area_m2, place_id列的GeoDataFrame
    """
    cols = [c for c in ["geometry", "levels", "height"] if c in buildings.columns]
    result = buildings[cols].copy()

    # 计算高度: 优先用height字段，否则用levels×3米，再否则默认3层
    if "height" in result.columns and "levels" in result.columns:
        result["height_m"] = result["height"].fillna(
            result["levels"].fillna(3).astype(float) * 3
        )
    elif "height" in result.columns:
        result["height_m"] = result["height"].fillna(9.0)
    elif "levels" in result.columns:
        result["height_m"] = result["levels"].fillna(3).astype(float) * 3
    else:
        result["height_m"] = 9.0

    # 计算面积 (投影到EPSG:32650即UTM Zone 50N)
    result_proj = result.to_crs("EPSG:32650")
    result["area_m2"] = result_proj.geometry.area

    result["place_id"] = range(len(result))
    result = result.to_crs("EPSG:4326")

    return result


def _generate_synthetic_basemap() -> tuple:
    """离线演示模式：生成类北京城区的不规则建筑 + 连通网格路网

    模拟城市特征：建筑高度随机（3-33层）、尺寸有变化、部分区域密集。
    """
    from shapely.geometry import LineString, Polygon
    import random
    rng = random.Random(42)

    lons = [c[0] for c in DISTRICT_CENTERS]
    lats = [c[1] for c in DISTRICT_CENTERS]

    grid_step = 0.005  # ~500m
    margin = grid_step * 2

    min_lon, max_lon = min(lons) - margin, max(lons) + margin
    min_lat, max_lat = min(lats) - margin, max(lats) + margin

    grid_lons = [min_lon + i * grid_step for i in range(int((max_lon - min_lon) / grid_step) + 1)]
    grid_lats = [min_lat + i * grid_step for i in range(int((max_lat - min_lat) / grid_step) + 1)]

    seg_rows, seg_geoms = [], []
    bld_rows, bld_geoms = [], []

    # 路网：短段共享端点，保证全连通
    for j in range(len(grid_lats)):
        lat = grid_lats[j]
        for i in range(len(grid_lons) - 1):
            seg_geoms.append(LineString([(grid_lons[i], lat), (grid_lons[i+1], lat)]))
            seg_rows.append({"highway": "residential", "name": "synthetic_h"})

    for i in range(len(grid_lons)):
        lon = grid_lons[i]
        for j in range(len(grid_lats) - 1):
            seg_geoms.append(LineString([(lon, grid_lats[j]), (lon, grid_lats[j+1])]))
            seg_rows.append({"highway": "residential", "name": "synthetic_v"})

    # 建筑：模拟真实城市布局
    for i in range(len(grid_lons) - 1):
        for j in range(len(grid_lats) - 1):
            cx = (grid_lons[i] + grid_lons[i + 1]) / 2
            cy = (grid_lats[j] + grid_lats[j + 1]) / 2

            # 建筑数量：模拟城区密度差异（中心更密）
            dist_from_center = ((cx - 116.37)**2 + (cy - 39.92)**2)**0.5
            density = max(1, int(3 - dist_from_center * 12))
            num_bld = rng.randint(1, density + 1)

            for _ in range(num_bld):
                # 随机偏移（避免对齐太规整）
                ox = rng.uniform(-0.0015, 0.0015)
                oy = rng.uniform(-0.0015, 0.0015)
                # 随机尺寸
                bw = rng.uniform(0.0003, 0.0012)  # ~30-130m
                bd = rng.uniform(0.0003, 0.0008)
                bx = cx + ox - bw / 2
                by = cy + oy - bd / 2
                bld_geoms.append(Polygon([
                    (bx, by), (bx + bw, by),
                    (bx + bw, by + bd), (bx, by + bd),
                ]))
                # 随机高度 3-33 层
                levels = rng.choice([3, 6, 9, 12, 18, 24, 30, 33],
                                   weights=[20, 18, 15, 12, 10, 5, 3, 2])
                bld_rows.append({"levels": levels})

    segments = gpd.GeoDataFrame(seg_rows, geometry=seg_geoms, crs="EPSG:4326")
    segments["seg_id"] = range(len(segments))
    segments["length"] = segments.geometry.to_crs("EPSG:32650").length

    buildings = gpd.GeoDataFrame(bld_rows, geometry=bld_geoms, crs="EPSG:4326")
    buildings = buildings_to_gdf(buildings)

    return segments, buildings


def load_basemap_data(save_processed: bool = True) -> tuple:
    """完整流程：获取街道+建筑数据（优先数据库，回退天地图+GeoScene/离线合成）

    Returns:
        (segments_gdf, buildings_gdf)
    """
    # 优先：database/bikeflow.sqlite 中已入库的 segments/buildings
    try:
        from database.repository import read_segments, read_buildings
        segments = read_segments()
        buildings = read_buildings()
        if len(segments) > 0 and len(buildings) > 0:
            return segments, buildings
    except Exception:
        pass

    processed_dir = DATA_DIR / "processed"
    seg_cache = processed_dir / "beijing_segments_bike.gpkg"
    bld_cache = processed_dir / "beijing_buildings_6district.gpkg"

    if save_processed and seg_cache.exists() and bld_cache.exists():
        segments = gpd.read_file(seg_cache)
        buildings = gpd.read_file(bld_cache)
        return segments, buildings

    segments, buildings = None, None

    # 优先真实数据源：天地图街道
    if TIANDITU_TOKEN:
        try:
            street_geojson = fetch_street_network()
            segments = segments_to_gdf(street_geojson)
        except Exception as e:
            print(f"[basemap] 天地图街道获取失败: {e}")

    # 真实建筑：GeoScene Server / 本地File GDB
    if segments is not None:
        try:
            raw_buildings = fetch_buildings()
            buildings = buildings_to_gdf(raw_buildings)
        except Exception as e:
            print(f"[basemap] 建筑数据获取失败: {e}")

    # 离线回退：合成数据
    if segments is None or buildings is None:
        print("[basemap] 启用离线演示模式：生成合成街道与建筑数据")
        segments, buildings = _generate_synthetic_basemap()

    if save_processed:
        processed_dir.mkdir(parents=True, exist_ok=True)
        segments.to_file(seg_cache, driver="GPKG")
        buildings.to_file(bld_cache, driver="GPKG")

    return segments, buildings
