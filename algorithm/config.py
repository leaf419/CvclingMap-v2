"""BikeFlowGNN v2 算法层全局配置"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple

# ── 路径配置 ──
# algorithm/config.py 位于 CvclingMap_new_refactor/algorithm/config.py
# BASE_DIR = CvclingMap_new_refactor/
BASE_DIR = Path(__file__).parent.parent
# 数据统一存放于数据库层 database/（raw 原始 / processed 中间 / output 产物 / cache 缓存）
DATA_DIR = BASE_DIR / "database"

# ── 原始数据文件名 (相对DATA_DIR的路径，加载时用 DATA_DIR / XXX_CSV) ──
STREETVIEW_CSV = "raw/StreetviewDirectionMetrics/streetview_direction_metrics_20260801-143827.csv"
POI_CSV = "raw/POI/北京市.csv"
STATION_FILE = "raw/SharingBikeParkingPOI/北京共享单车停车位.shp"  # Shapefile格式 (3,293个站点)

# ── 实际数据规模 (用于验证) ──
DATA_STATS = {
    "streetview_rows": 10131,       # 2,563采样点 × ~4方向
    "streetview_points": 2563,      # 唯一采样点数
    "streetview_directions": 4,     # E/N/S/W 四个方向
    "poi_total": 806960,            # 约80万POI
    "poi_categories": 14,           # 14个大类
    "station_total": 3293,          # 共享单车停车位数
    "station_format": "shapefile",  # .shp格式
}

# ── 研究区域：北京6区 ──
STUDY_DISTRICTS = [
    "Xicheng, Beijing",
    "Haidian, Beijing",
    "Dongcheng, Beijing",
    "Shijingshan, Beijing",
    "Chaoyang, Beijing",
    "Fengtai, Beijing",
]

# 6区中心点坐标 (lon, lat) 用于morphological_graph
DISTRICT_CENTERS = [
    (116.366, 39.915),   # 西城
    (116.310, 39.959),   # 海淀
    (116.418, 39.929),   # 东城
    (116.222, 39.909),   # 石景山
    (116.443, 39.921),   # 朝阳
    (116.287, 39.858),   # 丰台
]

# ── 天地图底图配置（比赛推荐底图）──
# 通过环境变量 TIANDITU_TOKEN 或 .env 配置天地图开发者 token（避免源码泄露凭据）
TIANDITU_BASE_URL = "https://t0.tianditu.gov.cn"
TIANDITU_TOKEN = os.environ.get("TIANDITU_TOKEN", "")
TIANDITU_LAYERS = {
    "vec_c": "vec_c",   # 矢量底图
    "img_c": "img_c",   # 影像底图
    "ter_c": "ter_c",   # 地形底图
}

# ── GeoScene Server配置 ──
GEOSCENE_SERVER_URL = "https://localhost:6443/arcgis"
GEOSCENE_SERVER_TOKEN = ""  # GeoScene Server token（需通过比赛组委会获取许可）
GEOSCENE_SERVICE_NAMES = {
    "segments": "BikeSegments_MapService",
    "stations": "BikeStations_MapService",
    "routes": "BikeRoutes_GeoCodeService",
    "scene3d": "Beijing3D_WebScene",
}

# ── 图构建参数 ──
@dataclass
class GraphConfig:
    morpho_distance: int = 5000           # morphological_graph搜索半径(米)
    poi_k_neighbors: int = 3              # POI→segment的k近邻
    poi_max_distance: float = 50.0        # POI最近segment最大距离(米)
    obs_max_distance: float = 100.0       # 观测点最近segment最大距离(米)
    station_max_distance: float = 100.0   # 站点最近segment最大距离(米)
    propagation_k: int = 5                # 指标传播k近邻
    propagation_max_dist: float = 150.0   # 传播最大距离(米)

# ── GNN训练参数 ──
@dataclass
class TrainConfig:
    hidden_dim: int = 64
    num_heads: int = 4
    num_layers: int = 2
    batch_size: int = 512
    epochs: int = 100
    lr: float = 1e-3
    num_neighbors_l1: dict = field(default_factory=lambda: {
        ("segment", "connected_to", "segment"): 15,
        ("observation", "observed_at", "segment"): 5,
        ("poi", "nearby", "segment"): 5,
        ("place", "faced_to", "segment"): 5,
    })
    num_neighbors_l2: dict = field(default_factory=lambda: {
        ("segment", "connected_to", "segment"): 10,
        ("observation", "observed_at", "segment"): 3,
        ("poi", "nearby", "segment"): 3,
        ("place", "faced_to", "segment"): 3,
    })
    use_compile: bool = True
    use_fp16: bool = True
    num_workers: int = 4

# ── 边权参数 ──
@dataclass
class WeightConfig:
    alpha: float = 0.30    # 安全性权重
    beta: float = 0.25     # 舒适度权重
    gamma: float = 0.25    # 风景权重
    delta: float = 0.20    # 综合体验权重

# ── NSGA-II参数 ──
@dataclass
class NSGA2Config:
    pop_size: int = 100
    n_gen: int = 50
    mutation_rate: float = 0.2
    station_buffer: float = 200.0  # 站点密度计算缓冲距离(米)

GRAPH_CFG = GraphConfig()
TRAIN_CFG = TrainConfig()
WEIGHT_CFG = WeightConfig()
NSGA2_CFG = NSGA2Config()
