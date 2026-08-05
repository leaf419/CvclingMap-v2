"""80万POI数据加载与编码"""
import pandas as pd
import geopandas as gpd
from algorithm.config import DATA_DIR, POI_CSV

# 骑行相关POI大类 (用于预过滤降低图规模)
RIDING_RELEVANT_CATEGORIES = [
    "餐饮美食",
    "购物消费",
    "交通设施",
    "旅游景点",
    "生活服务",
    "休闲娱乐",
    "运动健身",
    "科教文化",
]

# 全部14个大类
ALL_CATEGORIES = [
    "购物消费", "餐饮美食", "生活服务", "公司企业", "交通设施",
    "商务住宅", "科教文化", "酒店住宿", "汽车相关", "医疗保健",
    "休闲娱乐", "运动健身", "金融机构", "旅游景点",
]


def load_poi_csv(db_path: str = None) -> gpd.GeoDataFrame:
    """加载北京 POI 数据（优先经 database/repository 读取，回退原 CSV 文件）

    Args:
        db_path: 数据库路径；默认使用 database/bikeflow.sqlite

    Returns:
        GeoDataFrame, CRS=EPSG:4326, 含poi_id列
        数据库模式列名为英文（name/category_big/category_mid/lon/lat/...）；
        文件回退模式列名为源 CSV 中文列名（名称/大类/中类/经度/纬度/...）
    """
    try:
        from database.repository import read_poi, to_geodataframe
        df = read_poi(db_path) if db_path else read_poi()
        if len(df) > 0:
            gdf = to_geodataframe(df, "lon", "lat")
            gdf["poi_id"] = range(len(gdf))
            return gdf
    except Exception:
        pass

    csv_path = DATA_DIR / POI_CSV
    df = pd.read_csv(csv_path)

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["经度"], df["纬度"]),
        crs="EPSG:4326"
    )
    gdf["poi_id"] = range(len(gdf))
    return gdf


def _category_col(gdf) -> str:
    """兼容中英文大类列名：文件模式用"大类"，数据库模式用"category_big"""
    return "大类" if "大类" in gdf.columns else "category_big"


def encode_categories(poi_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """将POI大类编码为整数

    Args:
        poi_gdf: 含"大类"列的GeoDataFrame

    Returns:
        添加category_code列 (0~13)
    """
    cat_type = pd.CategoricalDtype(categories=ALL_CATEGORIES, ordered=False)
    poi_gdf = poi_gdf.copy()
    poi_gdf["category_code"] = poi_gdf[_category_col(poi_gdf)].astype(cat_type).cat.codes
    return poi_gdf


def filter_riding_relevant(poi_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """过滤出骑行相关POI (降低图规模约60%)

    Args:
        poi_gdf: 含"大类"列的GeoDataFrame

    Returns:
        仅保留骑行相关大类的子集
    """
    mask = poi_gdf[_category_col(poi_gdf)].isin(RIDING_RELEVANT_CATEGORIES)
    filtered = poi_gdf[mask].copy()
    filtered["poi_id"] = range(len(filtered))
    return filtered


def load_and_process_poi(filter_relevant: bool = True) -> gpd.GeoDataFrame:
    """完整流程：加载CSV → 编码 → (可选)过滤"""
    gdf = load_poi_csv()
    gdf = encode_categories(gdf)
    if filter_relevant:
        gdf = filter_riding_relevant(gdf)
    return gdf
