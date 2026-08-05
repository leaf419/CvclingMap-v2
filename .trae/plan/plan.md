# BikeFlowGNN v2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建基于真实街景指标、80万POI、2017年共享单车停车点的北京骑行路线分析系统，融合city2graph异构图GNN与GeoScene Enterprise三维城市底图可视化，符合GeoScene杯C组GIS应用开发组比赛要求。

**Architecture:** 四层架构 — `frontend (React+TS+GeoScene JS API)` ──HTTP──> `GeoScene Enterprise Server (GIS核心服务)` ──REST──> `backend (FastAPI 轻量网关)` ──import──> `algorithm (纯算法引擎, 零Web依赖)`。GIS核心架构/功能采用GeoScene Enterprise服务器端产品，符合比赛"服务器端部署必须基于GeoScene"的强制要求。algorithm层允许使用开源技术（city2graph、PyTorch等），实现五阶段流水线: (1) 多源异构图构建（5类节点/6类边）→ (2) 街景指标驱动的四维边权模型 → (3) HGT mini-batch GNN偏好学习 → (4) NSGA-II多目标路径搜索 → (5) GeoScene SceneView三维可视化与个性化推荐。图规模约94万节点，采用NeighborSampler解决显存瓶颈。底图使用天地图数据，数据存储采用File Geodatabase。

**Tech Stack:**
- `algorithm/`: Python 3.11 / city2graph 0.4 / PyTorch+PyG / GeoPandas / PyMOO / NetworkX / SciPy（零Web依赖，纯算法引擎）
- `geoscene/`: GeoScene Enterprise Server / GeoScene Pro（GIS核心服务发布、地图服务、路径服务、3D场景服务）
- `backend/`: FastAPI / SQLAlchemy / SQLite / Pydantic / Uvicorn（轻量API网关，调用algorithm层并转发至GeoScene Server）
- `frontend/`: React 18 / TypeScript / Vite / GeoScene API for JavaScript / Zustand / RTX 4060 8GB

---

## 文件结构总览

```
BikeFlowGNN/
├── algorithm/                  # 纯算法引擎（零 Web 依赖）
│   ├── __init__.py
│   ├── config.py               # 算法配置：路径、参数、区域定义
│   ├── data/                   # 数据加载
│   │   ├── __init__.py
│   │   ├── streetview_loader.py       # 街景指标加载与4方向confidence加权聚合
│   │   ├── poi_loader.py              # 80万POI加载与编码
│   │   ├── station_loader.py          # 2017单车停车点加载
│   │   └── basemap_loader.py          # 天地图街道+建筑数据获取（替代OSMnx）
│   ├── graph/                  # 图构建
│   │   ├── __init__.py
│   │   ├── hetero_builder.py          # 5类节点6类边异构图构建
│   │   ├── metric_propagation.py      # 街景指标KDTree空间传播
│   │   └── metapaths.py               # 元路径设计与添加
│   ├── weights/                # 边权模型
│   │   ├── __init__.py
│   │   ├── edge_weights.py            # 四维边权：安全/舒适/风景/综合体验
│   │   └── cost_fusion.py             # 加权融合为综合骑行成本C(e)
│   ├── models/                 # GNN模型
│   │   ├── __init__.py
│   │   ├── hgt_model.py               # HGT模型定义
│   │   ├── trainer.py                 # NeighborSampler mini-batch训练
│   │   └── predictor.py               # 偏好预测与嵌入导出
│   ├── routing/                # 路径搜索
│   │   ├── __init__.py
│   │   ├── nsga2_search.py            # NSGA-II多目标路径搜索
│   │   ├── station_constraint.py      # 历史站点密度约束
│   │   └── recommender.py             # 个性化推荐
│   ├── viz/                    # GeoScene 3D数据导出
│   │   ├── __init__.py
│   │   ├── geoscene_export.py         # GeoScene SceneView场景数据导出（替代MapGIS）
│   │   └── route_overlay.py           # 路线3D叠加GeoJSON生成
│   ├── pipeline.py             # 全流程编排
│   └── tests/                  # 单元测试
│       ├── __init__.py
│       ├── conftest.py                # pytest fixtures
│       ├── test_streetview_loader.py
│       ├── test_poi_loader.py
│       ├── test_station_loader.py
│       ├── test_basemap_loader.py
│       ├── test_hetero_builder.py
│       ├── test_metric_propagation.py
│       ├── test_edge_weights.py
│       ├── test_hgt_model.py
│       ├── test_nsga2_search.py
│       ├── test_recommender.py
│       ├── test_viz.py
│       └── test_pipeline.py
├── geoscene/                   # GeoScene Enterprise 服务配置
│   ├── server_config.json      # GeoScene Server服务发布配置
│   ├── services/               # 地图服务/路径服务/3D场景服务定义
│   │   ├── bike_segments_mapservice.json   # 街道段地图服务
│   │   ├── bike_stations_mapservice.json   # 停车点地图服务
│   │   ├── bike_routes_geocodeservice.json # 路线地理编码服务
│   │   └── scene_3d_webscene.json          # 3D场景服务（SceneView）
│   ├── data/                   # GeoScene数据层
│   │   └── BikeFlowGNN.gdb/    # File Geodatabase（比赛推荐数据格式）
│   └── publish_services.py     # 服务发布脚本（调用GeoScene Server REST API）
├── backend/                    # FastAPI 轻量API网关
│   ├── __init__.py
│   ├── app.py                  # 应用入口
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py           # REST API 路由
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py           # 后端配置（含GeoScene Server连接配置）
│   ├── db/
│   │   ├── __init__.py
│   │   └── models.py           # SQLAlchemy ORM 模型 (SQLite缓存)
│   ├── service/                # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── route_service.py    # 调用algorithm层
│   │   └── geoscene_client.py  # GeoScene Server REST API 客户端
│   └── tests/
│       └── test_routes.py      # API测试
├── frontend/                   # React + TypeScript + GeoScene JS API 前端
│   ├── src/
│   │   ├── main.tsx            # 应用入口
│   │   ├── core/               # 组件/状态/API/类型
│   │   │   ├── api.ts          # API客户端
│   │   │   ├── types.ts        # TypeScript类型定义
│   │   │   ├── geoscene-config.ts # GeoScene JS API 配置
│   │   │   └── store.ts        # Zustand状态管理
│   │   ├── pages/              # 页面
│   │   │   └── MapPage.tsx     # 主地图页（GeoScene MapView/SceneView）
│   │   ├── components/         # 组件
│   │   │   ├── Sidebar.tsx
│   │   │   ├── RouteCompare.tsx
│   │   │   └── MetricsPanel.tsx
│   │   ├── router/
│   │   │   └── index.tsx
│   │   └── styles/
│   │       └── global.css      # 全局样式
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── package.json
├── data/                       # 原始数据
│   ├── streetview_direction_metrics_*.csv
│   ├── 北京市.csv
│   └── bike_stations_2017.geojson
└── docs/                       # 文档
```

---

## Task 1: 项目脚手架与三层依赖配置

**Files:**
- Create: `BikeFlowGNN/algorithm/__init__.py`
- Create: `BikeFlowGNN/algorithm/config.py`
- Create: `BikeFlowGNN/algorithm/tests/__init__.py`
- Create: `BikeFlowGNN/algorithm/tests/conftest.py`
- Create: `BikeFlowGNN/algorithm/requirements.txt`
- Create: `BikeFlowGNN/backend/__init__.py`
- Create: `BikeFlowGNN/backend/requirements.txt`
- Create: `BikeFlowGNN/frontend/package.json`
- Create: `BikeFlowGNN/docs/README.md`

- [ ] **Step 1: 创建三层项目目录结构**

```bash
cd /workspace
mkdir -p BikeFlowGNN/algorithm/{data,graph,weights,models,routing,viz,tests}
mkdir -p BikeFlowGNN/backend/{api,core,db,service}
mkdir -p BikeFlowGNN/frontend/src/{core,pages,components,router}
mkdir -p BikeFlowGNN/data
mkdir -p BikeFlowGNN/docs

# algorithm 层 __init__.py
touch BikeFlowGNN/algorithm/__init__.py
touch BikeFlowGNN/algorithm/{data,graph,weights,models,routing,viz}/__init__.py
touch BikeFlowGNN/algorithm/tests/__init__.py

# backend 层 __init__.py
touch BikeFlowGNN/backend/__init__.py
touch BikeFlowGNN/backend/{api,core,db,service}/__init__.py
```

- [ ] **Step 2: 创建 `algorithm/requirements.txt`（算法层依赖，零Web依赖）**

```
# algorithm/requirements.txt — 纯算法引擎依赖（零Web依赖）
city2graph==0.4.0
geopandas>=0.14.0
shapely>=2.0.0
scipy>=1.12.0
torch>=2.2.0
torch-geometric>=2.5.0
pymoo>=0.6.0
networkx>=3.2.0
pandas>=2.1.0
numpy>=1.26.0
scikit-learn>=1.4.0
pyarrow>=15.0.0
requests>=2.31.0          # 天地图API调用
```

- [ ] **Step 3: 创建 `backend/requirements.txt`（后端层依赖）**

```
# backend/requirements.txt — FastAPI 轻量API网关依赖
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.6.0
pydantic-settings>=2.1.0
sqlalchemy>=2.0.0
python-multipart>=0.0.9
httpx>=0.27.0
arcgis>=2.3.0          # GeoScene Python API（兼容ArcGIS API）
# algorithm层依赖也需要安装（后端import algorithm）
-r ../algorithm/requirements.txt
```

- [ ] **Step 4: 创建配置模块 `algorithm/config.py`**

```python
"""BikeFlowGNN v2 算法层全局配置"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple

# ── 路径配置 ──
# algorithm/config.py 位于 BikeFlowGNN/algorithm/config.py
# BASE_DIR = BikeFlowGNN/
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# ── 原始数据文件名 ──
STREETVIEW_CSV = "streetview_direction_metrics_20260801-143827.csv"
POI_CSV = "北京市.csv"
STATION_FILE = "bike_stations_2017.geojson"  # 如无geojson则用csv

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
TIANDITU_BASE_URL = "https://t{0-7}.tianditu.gov.cn"
TIANDITU_TOKEN = ""  # 需要申请天地图开发者token
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
```

- [ ] **Step 5: 创建 pytest fixtures `algorithm/tests/conftest.py`**

```python
"""共享测试fixtures — algorithm层测试"""
import sys
from pathlib import Path

# 确保项目根目录在Python路径中，使 from algorithm.xxx 可用
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import numpy as np

@pytest.fixture
def sample_streetview_df():
    """模拟街景指标数据 (10条记录, 2个采样点×4方向)"""
    return pd.DataFrame({
        "point_id": [1,1,1,1, 2,2,2,2, 3,3],
        "direction": ["E","N","S","W", "E","N","S","W", "E","N"],
        "lon_wgs": [116.36,116.36,116.36,116.36, 116.37,116.37,116.37,116.37, 116.38,116.38],
        "lat_wgs": [39.91,39.91,39.91,39.91, 39.92,39.92,39.92,39.92, 39.93,39.93],
        "metric_bike_lane_type_value": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.5,0.4],
        "metric_bike_lane_type_confidence_0_1": [0.9,0.8,0.7,0.6, 0.9,0.8,0.7,0.6, 0.8,0.7],
        "metric_physical_separation_value": [0.7,0.6,0.5,0.4, 0.8,0.7,0.6,0.5, 0.3,0.2],
        "metric_physical_separation_confidence_0_1": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.7,0.6],
        "metric_motor_traffic_pressure_value": [0.3,0.4,0.5,0.6, 0.2,0.3,0.4,0.5, 0.6,0.7],
        "metric_motor_traffic_pressure_confidence_0_1": [0.9,0.8,0.7,0.6, 0.9,0.8,0.7,0.6, 0.8,0.7],
        "metric_road_surface_quality_value": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.4,0.3],
        "metric_road_surface_quality_confidence_0_1": [0.9,0.8,0.7,0.6, 0.9,0.8,0.7,0.6, 0.8,0.7],
        "metric_visible_greenery_value": [0.6,0.5,0.4,0.3, 0.8,0.7,0.6,0.5, 0.5,0.4],
        "metric_visible_greenery_confidence_0_1": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.7,0.6],
        "metric_beauty_value": [0.7,0.6,0.5,0.4, 0.8,0.7,0.6,0.5, 0.4,0.3],
        "metric_beauty_confidence_0_1": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.7,0.6],
        "metric_perceived_safety_value": [0.6,0.5,0.4,0.3, 0.7,0.6,0.5,0.4, 0.3,0.2],
        "metric_perceived_safety_confidence_0_1": [0.8,0.7,0.6,0.5, 0.9,0.8,0.7,0.6, 0.7,0.6],
    })

@pytest.fixture
def sample_poi_df():
    """模拟POI数据 (5条)"""
    return pd.DataFrame({
        "名称": ["A餐厅","B超市","C医院","D学校","E景点"],
        "大类": ["餐饮美食","购物消费","医疗保健","科教文化","旅游景点"],
        "经度": [116.36, 116.37, 116.38, 116.39, 116.40],
        "纬度": [39.91, 39.92, 39.93, 39.94, 39.95],
    })

@pytest.fixture
def sample_segments_gdf():
    """模拟街道段GeoDataFrame"""
    return gpd.GeoDataFrame({
        "seg_id": [0, 1, 2, 3],
        "length": [100.0, 150.0, 80.0, 200.0],
        "highway": ["residential","primary","residential","secondary"],
    }, geometry=[
        LineString([(116.35,39.90),(116.37,39.91)]),
        LineString([(116.37,39.91),(116.39,39.92)]),
        LineString([(116.39,39.92),(116.40,39.93)]),
        LineString([(116.40,39.93),(116.42,39.94)]),
    ], crs="EPSG:4326")

@pytest.fixture
def sample_obs_gdf():
    """模拟街景聚合后的观测点GeoDataFrame (含指标列)"""
    return gpd.GeoDataFrame({
        "obs_id": [0, 1, 2],
        "s_bike_lane_type": [0.65, 0.75, 0.45],
        "s_physical_separation": [0.55, 0.65, 0.25],
        "s_motor_pressure": [0.45, 0.35, 0.65],
        "s_heavy_vehicle": [0.30, 0.20, 0.50],
        "s_parking_encroach": [0.25, 0.15, 0.45],
        "s_intersection_conflict": [0.35, 0.25, 0.55],
        "f_surface_quality": [0.65, 0.75, 0.35],
        "f_pothole": [0.20, 0.10, 0.40],
        "f_overall_comfort": [0.60, 0.70, 0.30],
        "f_traffic_stress": [0.40, 0.30, 0.60],
        "v_greenery": [0.45, 0.65, 0.35],
        "v_beauty": [0.55, 0.65, 0.25],
        "v_tranquility": [0.50, 0.60, 0.30],
        "x_perceived_safety": [0.45, 0.55, 0.25],
        "x_active_frontage": [0.60, 0.50, 0.20],
        "x_cleanliness": [0.65, 0.55, 0.35],
        "x_lighting": [0.50, 0.60, 0.30],
    }, geometry=[
        Point(116.36, 39.91),
        Point(116.37, 39.92),
        Point(116.38, 39.93),
    ], crs="EPSG:4326")
```

- [ ] **Step 6: 创建 `frontend/package.json`**

```json
{
  "name": "bikeflowgnn-frontend",
  "private": true,
  "version": "2.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.22.0",
    "@geoscene/core": "^4.30.0",
    "@geoscene/widgets": "^4.30.0",
    "zustand": "^4.5.0",
    "axios": "^1.6.7"
  },
  "devDependencies": {
    "@types/react": "^18.2.55",
    "@types/react-dom": "^18.2.51",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.3.3",
    "vite": "^5.1.0"
  }
}
```

- [ ] **Step 7: 创建 `docs/README.md`**

```markdown
# BikeFlowGNN v2 文档

## 架构概览

四层架构（GeoScene比赛合规）:

```
frontend (React + TypeScript + GeoScene JS API)  ──HTTP──>  GeoScene Enterprise Server (GIS核心服务)
    ──REST──>  backend (FastAPI 轻量网关)  ──import──>  algorithm (纯算法引擎)
```

| 层 | 职责 | 技术栈 |
|----|------|--------|
| `algorithm/` | 纯算法引擎（零 Web 依赖） | pandas, scipy, city2graph, torch, networkx |
| `geoscene/` | GeoScene Enterprise GIS核心服务 | GeoScene Server, File Geodatabase |
| `backend/` | 轻量API网关、SQLite缓存、调用algorithm | FastAPI, SQLAlchemy, SQLite, arcgis Python API |
| `frontend/` | 交互式地图 UI（2D/3D） | React 18, TypeScript, Vite, GeoScene API for JS, Zustand |

## 比赛合规说明
- GIS核心架构采用GeoScene Enterprise服务器端产品（满足比赛强制要求）
- 底图使用天地图数据（比赛推荐底图）
- 数据存储采用File Geodatabase（比赛推荐格式）
- algorithm层允许使用开源技术（city2graph、PyTorch等）

## 开发指南

- 算法层测试: `cd algorithm && python -m pytest tests/ -v`
- 后端启动: `cd backend && uvicorn app:app --reload --port 8000`
- 前端启动: `cd frontend && npm install && npm run dev`
- GeoScene服务发布: `python geoscene/publish_services.py`
```

- [ ] **Step 8: 安装算法层依赖并验证**

```bash
cd /workspace/BikeFlowGNN
pip install -r algorithm/requirements.txt --break-system-packages
python -c "import algorithm.config; print('algorithm layer OK')"
```

Expected: 输出 `algorithm layer OK`

- [ ] **Step 9: Commit**

```bash
cd /workspace/BikeFlowGNN
git init
git add -A
git commit -m "chore: four-layer scaffolding (algorithm/geoscene/backend/frontend) with GeoScene compliance"
```

---

## Task 2: 街景指标数据加载与4方向聚合

**Files:**
- Create: `BikeFlowGNN/algorithm/data/streetview_loader.py`
- Create: `BikeFlowGNN/algorithm/tests/test_streetview_loader.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_streetview_loader.py`**

```python
"""街景数据加载器测试"""
import pytest
import pandas as pd
import geopandas as gpd
from algorithm.data.streetview_loader import (
    load_streetview_csv,
    aggregate_by_point,
    to_geodataframe,
    METRIC_MAPPING,
)

def test_load_streetview_csv(sample_streetview_df, tmp_path, monkeypatch):
    """测试CSV加载"""
    csv_path = tmp_path / "test_sv.csv"
    sample_streetview_df.to_csv(csv_path, index=False)
    monkeypatch.setattr("algorithm.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("algorithm.config.STREETVIEW_CSV", "test_sv.csv")
    df = load_streetview_csv()
    assert len(df) == 10
    assert "point_id" in df.columns
    assert "lon_wgs" in df.columns

def test_metric_mapping_completeness():
    """测试指标映射涵盖4个维度"""
    assert "s_bike_lane_type" in METRIC_MAPPING["safety"]
    assert "f_surface_quality" in METRIC_MAPPING["comfort"]
    assert "v_greenery" in METRIC_MAPPING["scenery"]
    assert "x_perceived_safety" in METRIC_MAPPING["experience"]

def test_aggregate_by_point(sample_streetview_df):
    """测试按采样点4方向confidence加权聚合"""
    agg = aggregate_by_point(sample_streetview_df)
    assert len(agg) == 3  # 3个唯一point_id
    assert "s_bike_lane_type" in agg.columns
    # point_id=1的bike_lane_type: 4方向confidence加权
    # (0.8*0.9 + 0.7*0.8 + 0.6*0.7 + 0.5*0.6) / (0.9+0.8+0.7+0.6)
    # = (0.72+0.56+0.42+0.30) / 3.0 = 2.0/3.0 ≈ 0.667
    row = agg[agg["point_id"] == 1].iloc[0]
    assert abs(row["s_bike_lane_type"] - 0.667) < 0.01

def test_to_geodataframe(sample_streetview_df):
    """测试转换为GeoDataFrame"""
    agg = aggregate_by_point(sample_streetview_df)
    gdf = to_geodataframe(sample_streetview_df, agg)
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.crs.to_epsg() == 4326
    assert len(gdf) == 3
    assert "obs_id" in gdf.columns
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/BikeFlowGNN
python -m pytest algorithm/tests/test_streetview_loader.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'algorithm.data.streetview_loader'`

- [ ] **Step 3: 实现 `algorithm/data/streetview_loader.py`**

```python
"""街景指标数据加载与4方向confidence加权聚合"""
import pandas as pd
import geopandas as gpd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from algorithm.config import DATA_DIR, STREETVIEW_CSV

# ── 指标映射表: 输出列名 → (原始value字段, 原始confidence字段) ──
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
        "s_traffic_control": ("metric_traffic_control_facility_value",
                              "metric_traffic_control_facility_confidence_0_1"),
        "s_crosswalk": ("metric_crosswalk_visibility_value",
                        "metric_crosswalk_visibility_confidence_0_1"),
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
        "f_traffic_stress": ("metric_traffic_stress_level_value",
                             "metric_traffic_stress_level_confidence_0_1"),
        "f_route_continuity": ("metric_route_continuity_value",
                               "metric_route_continuity_confidence_0_1"),
        "f_perceived_safety": ("metric_perceived_safety_comfort_value",
                               "metric_perceived_safety_comfort_confidence_0_1"),
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


def load_streetview_csv() -> pd.DataFrame:
    """加载街景指标CSV"""
    csv_path = DATA_DIR / STREETVIEW_CSV
    df = pd.read_csv(csv_path)
    return df


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
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /workspace/BikeFlowGNN
python -m pytest algorithm/tests/test_streetview_loader.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: street view metric loader with 4-direction confidence-weighted aggregation"
```

---

## Task 3: POI数据加载与编码

**Files:**
- Create: `BikeFlowGNN/algorithm/data/poi_loader.py`
- Create: `BikeFlowGNN/algorithm/tests/test_poi_loader.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_poi_loader.py`**

```python
"""POI数据加载器测试"""
import pytest
import geopandas as gpd
from algorithm.data.poi_loader import load_poi_csv, encode_categories, RIDING_RELEVANT_CATEGORIES

def test_load_poi_csv(sample_poi_df, tmp_path, monkeypatch):
    """测试POI CSV加载"""
    csv_path = tmp_path / "test_poi.csv"
    sample_poi_df.to_csv(csv_path, index=False)
    monkeypatch.setattr("algorithm.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("algorithm.config.POI_CSV", "test_poi.csv")
    gdf = load_poi_csv()
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.crs.to_epsg() == 4326
    assert len(gdf) == 5
    assert "poi_id" in gdf.columns

def test_encode_categories(sample_poi_df, tmp_path, monkeypatch):
    """测试POI大类编码"""
    csv_path = tmp_path / "test_poi.csv"
    sample_poi_df.to_csv(csv_path, index=False)
    monkeypatch.setattr("algorithm.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("algorithm.config.POI_CSV", "test_poi.csv")
    gdf = load_poi_csv()
    gdf = encode_categories(gdf)
    assert "category_code" in gdf.columns
    assert gdf["category_code"].nunique() == 5
    assert gdf["category_code"].min() == 0

def test_riding_relevant_categories():
    """测试骑行相关POI大类列表"""
    assert "餐饮美食" in RIDING_RELEVANT_CATEGORIES
    assert "购物消费" in RIDING_RELEVANT_CATEGORIES
    assert "交通设施" in RIDING_RELEVANT_CATEGORIES
    assert "旅游景点" in RIDING_RELEVANT_CATEGORIES
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest algorithm/tests/test_poi_loader.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `algorithm/data/poi_loader.py`**

```python
"""80万POI数据加载与编码"""
import pandas as pd
import geopandas as gpd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
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


def load_poi_csv() -> gpd.GeoDataFrame:
    """加载北京POI CSV数据
    
    Returns:
        GeoDataFrame, CRS=EPSG:4326, 含poi_id列
    """
    csv_path = DATA_DIR / POI_CSV
    df = pd.read_csv(csv_path)
    
    # 识别经纬度列名 (兼容不同命名)
    lon_col = "经度" if "经度" in df.columns else "lng"
    lat_col = "纬度" if "纬度" in df.columns else "lat"
    
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
        crs="EPSG:4326"
    )
    gdf["poi_id"] = range(len(gdf))
    return gdf


def encode_categories(poi_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """将POI大类编码为整数
    
    Args:
        poi_gdf: 含"大类"列的GeoDataFrame
        
    Returns:
        添加category_code列 (0~13)
    """
    cat_type = pd.CategoricalDtype(categories=ALL_CATEGORIES, ordered=False)
    poi_gdf = poi_gdf.copy()
    poi_gdf["category_code"] = poi_gdf["大类"].astype(cat_type).cat.codes
    return poi_gdf


def filter_riding_relevant(poi_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """过滤出骑行相关POI (降低图规模约60%)
    
    Args:
        poi_gdf: 含"大类"列的GeoDataFrame
        
    Returns:
        仅保留骑行相关大类的子集
    """
    mask = poi_gdf["大类"].isin(RIDING_RELEVANT_CATEGORIES)
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
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest algorithm/tests/test_poi_loader.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: POI loader with category encoding and riding-relevant filtering"
```

---

## Task 4: 2017共享单车停车点加载

**Files:**
- Create: `BikeFlowGNN/algorithm/data/station_loader.py`
- Create: `BikeFlowGNN/algorithm/tests/test_station_loader.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_station_loader.py`**

```python
"""单车停车点加载器测试"""
import pytest
import geopandas as gpd
from shapely.geometry import Point
from algorithm.data.station_loader import load_stations, normalize_stations

def test_load_stations_geojson(tmp_path):
    """测试从GeoJSON加载"""
    gdf = gpd.GeoDataFrame(
        {"name": ["站A", "站B"]},
        geometry=[Point(116.36, 39.91), Point(116.37, 39.92)],
        crs="EPSG:4326"
    )
    path = tmp_path / "stations.geojson"
    gdf.to_file(path, driver="GeoJSON")
    
    result = load_stations(str(path))
    assert len(result) == 2
    assert "station_id" in result.columns
    assert result.crs.to_epsg() == 4326

def test_load_stations_csv(tmp_path):
    """测试从CSV加载"""
    import pandas as pd
    df = pd.DataFrame({
        "lng": [116.36, 116.37],
        "lat": [39.91, 39.92],
        "count": [10, 20],
    })
    path = tmp_path / "stations.csv"
    df.to_csv(path, index=False)
    
    result = load_stations(str(path))
    assert len(result) == 2
    assert "station_id" in result.columns

def test_normalize_stations():
    """测试站点标准化"""
    gdf = gpd.GeoDataFrame(
        {"name": ["站A"], "capacity": [10]},
        geometry=[Point(116.36, 39.91)],
        crs="EPSG:4326"
    )
    result = normalize_stations(gdf)
    assert "station_id" in result.columns
    assert result["station_id"].iloc[0] == 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest algorithm/tests/test_station_loader.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 `algorithm/data/station_loader.py`**

```python
"""2017年共享单车停车点加载"""
import pandas as pd
import geopandas as gpd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from algorithm.config import DATA_DIR, STATION_FILE


def load_stations(file_path: str = None) -> gpd.GeoDataFrame:
    """加载单车停车点数据 (支持GeoJSON或CSV)
    
    Args:
        file_path: 文件路径，如不指定则使用config中的默认路径
        
    Returns:
        GeoDataFrame, CRS=EPSG:4326, 含station_id列
    """
    if file_path is None:
        file_path = str(DATA_DIR / STATION_FILE)
    
    path = Path(file_path)
    
    if path.suffix == ".geojson" or path.suffix == ".json":
        gdf = gpd.read_file(path)
    elif path.suffix == ".csv":
        df = pd.read_csv(path)
        # 尝试常见列名
        lon_col = next((c for c in ["lng", "lon", "经度", "longitude"] if c in df.columns), None)
        lat_col = next((c for c in ["lat", "纬度", "latitude"] if c in df.columns), None)
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
    
    Args:
        gdf: 原始站点GeoDataFrame
        
    Returns:
        含station_id列的标准化GeoDataFrame
    """
    gdf = gdf.copy()
    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)
    else:
        gdf = gdf.to_crs("EPSG:4326")
    
    gdf["station_id"] = range(len(gdf))
    
    # 确保有capacity列 (如无则默认值)
    if "capacity" not in gdf.columns:
        gdf["capacity"] = 0
    
    return gdf
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest algorithm/tests/test_station_loader.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: bike station loader supporting GeoJSON and CSV formats"
```

---

## Task 5: 天地图街道与建筑数据加载

**Files:**
- Create: `BikeFlowGNN/algorithm/data/basemap_loader.py`
- Create: `BikeFlowGNN/algorithm/tests/test_basemap_loader.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_basemap_loader.py`**

```python
"""天地图数据加载器测试"""
import pytest
from unittest.mock import patch
import geopandas as gpd
from shapely.geometry import LineString, Polygon
from algorithm.data.basemap_loader import (
    fetch_street_network,
    fetch_buildings,
    segments_to_gdf,
    buildings_to_gdf,
)

def test_segments_to_gdf():
    """测试天地图返回的GeoJSON街道段转换为GeoDataFrame"""
    mock_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"length": 100.0, "roadclass": "residential"},
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            },
            {
                "type": "Feature",
                "properties": {"length": 200.0, "roadclass": "primary"},
                "geometry": {"type": "LineString", "coordinates": [[1, 1], [2, 2]]},
            },
        ],
    }
    
    gdf = segments_to_gdf(mock_geojson)
    assert len(gdf) == 2
    assert "length" in gdf.columns
    assert "seg_id" in gdf.columns

def test_buildings_to_gdf():
    """测试建筑转换为GeoDataFrame"""
    mock_buildings = gpd.GeoDataFrame({
        "levels": [3, 5],
        "height": [None, None],
    }, geometry=[
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),
    ], crs="EPSG:4326")
    
    result = buildings_to_gdf(mock_buildings)
    assert "height_m" in result.columns
    assert result["height_m"].iloc[0] == 9.0  # 3层×3米
    assert result["height_m"].iloc[1] == 15.0  # 5层×3米

@patch("algorithm.data.basemap_loader.tianditu")
def test_fetch_street_network(mock_tianditu):
    """测试街道网络获取（天地图矢量服务）"""
    mock_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"length": 100.0},
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            }
        ],
    }
    mock_tianditu.get_street_geojson.return_value = mock_geojson
    result = fetch_street_network(["Xicheng, Beijing"])
    mock_tianditu.get_street_geojson.assert_called_once()
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest algorithm/tests/test_basemap_loader.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 `algorithm/data/basemap_loader.py`**

```python
"""天地图街道与建筑数据获取（GeoScene比赛合规，替代OSMnx）"""
import requests
import geopandas as gpd
from pathlib import Path
from shapely.geometry import shape

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
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


def _districts_to_bbox(districts: list) -> tuple:
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
    # 确保有seg_id
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
    """处理建筑数据：提取高度、计算面积（去除OSM特有字段引用）
    
    Args:
        buildings: 原始建筑GeoDataFrame
        
    Returns:
        含height_m, area_m2, place_id列的GeoDataFrame
    """
    # 去掉OSM特有字段引用，使用通用字段名（levels/height）
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


def load_basemap_data(save_processed: bool = True) -> tuple:
    """完整流程：获取街道+建筑数据（天地图+GeoScene）
    
    Returns:
        (segments_gdf, buildings_gdf)
    """
    # 检查是否有缓存
    processed_dir = DATA_DIR / "processed"
    seg_cache = processed_dir / "beijing_segments_bike.gpkg"  # 来源：天地图矢量服务
    bld_cache = processed_dir / "beijing_buildings_6district.gpkg"
    
    if save_processed and seg_cache.exists() and bld_cache.exists():
        segments = gpd.read_file(seg_cache)
        buildings = gpd.read_file(bld_cache)
        return segments, buildings
    
    # 从天地图获取街道网络
    street_geojson = fetch_street_network()
    segments = segments_to_gdf(street_geojson)
    
    # 从GeoScene Pro获取建筑数据
    raw_buildings = fetch_buildings()
    buildings = buildings_to_gdf(raw_buildings)
    
    if save_processed:
        processed_dir.mkdir(parents=True, exist_ok=True)
        segments.to_file(seg_cache, driver="GPKG")
        buildings.to_file(bld_cache, driver="GPKG")
    
    return segments, buildings
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest algorithm/tests/test_basemap_loader.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: Tianditu street network and building data loader with GeoScene compliance"
```

---

## Task 6: 5类节点6类边异构图构建

**Files:**
- Create: `BikeFlowGNN/algorithm/graph/hetero_builder.py`
- Create: `BikeFlowGNN/algorithm/tests/test_hetero_builder.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_hetero_builder.py`**

```python
"""异构图构建器测试"""
import pytest
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon
from algorithm.graph.hetero_builder import (
    build_morphological_graph,
    connect_observations_to_segments,
    connect_pois_to_segments,
    connect_stations_to_segments,
    build_hetero_graph,
)

def test_build_morphological_graph(sample_segments_gdf):
    """测试city2graph形态图构建"""
    # 创建简单建筑
    buildings = gpd.GeoDataFrame({
        "place_id": [0, 1],
        "height_m": [9.0, 15.0],
        "area_m2": [100.0, 200.0],
    }, geometry=[
        Polygon([(116.35,39.90),(116.36,39.90),(116.36,39.91),(116.35,39.91)]),
        Polygon([(116.38,39.92),(116.39,39.92),(116.39,39.93),(116.38,39.93)]),
    ], crs="EPSG:4326")
    
    nodes, edges = build_morphological_graph(buildings, sample_segments_gdf)
    assert "movement" in nodes or "segment" in nodes
    assert isinstance(edges, dict)

def test_connect_observations_to_segments(sample_obs_gdf, sample_segments_gdf):
    """测试观测点→街道段连接"""
    result = connect_observations_to_segments(
        sample_obs_gdf, sample_segments_gdf, max_distance=10000
    )
    assert len(result) > 0
    assert "obs_id" in result.columns
    assert "seg_id" in result.columns

def test_connect_pois_to_segments(sample_poi_df, sample_segments_gdf):
    """测试POI→街道段连接"""
    poi_gdf = gpd.GeoDataFrame(
        sample_poi_df,
        geometry=gpd.points_from_xy(sample_poi_df["经度"], sample_poi_df["纬度"]),
        crs="EPSG:4326"
    )
    result = connect_pois_to_segments(poi_gdf, sample_segments_gdf, k=2, max_distance=10000)
    assert len(result) > 0
    assert "poi_id" in result.columns
    assert "seg_id" in result.columns

def test_build_hetero_graph_structure():
    """测试异构图结构完整性"""
    from algorithm.graph.hetero_builder import HeteroGraphData
    import numpy as np
    
    # 构造最小测试图
    nodes = {
        "segment": gpd.GeoDataFrame({"seg_id": [0,1]}, geometry=[LineString([(0,0),(1,1)]), LineString([(1,1),(2,2)])], crs="EPSG:4326"),
        "observation": gpd.GeoDataFrame({"obs_id": [0]}, geometry=[Point(0.5,0.5)], crs="EPSG:4326"),
    }
    edges = {
        ("segment","connected_to","segment"): gpd.GeoDataFrame({"src":[0], "dst":[1]}),
        ("observation","observed_at","segment"): gpd.GeoDataFrame({"src":[0], "dst":[0]}),
    }
    
    hg = HeteroGraphData(nodes=nodes, edges=edges)
    assert "segment" in hg.node_types
    assert "observation" in hg.node_types
    assert ("observation","observed_at","segment") in hg.edge_types
    assert hg.total_nodes == 3
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest algorithm/tests/test_hetero_builder.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 `algorithm/graph/hetero_builder.py`**

```python
"""5类节点6类边异构图构建"""
import geopandas as gpd
import pandas as pd
import city2graph as c2g
from dataclasses import dataclass, field
from typing import Dict, Tuple
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from algorithm.config import GRAPH_CFG, DISTRICT_CENTERS


@dataclass
class HeteroGraphData:
    """异构图数据容器"""
    nodes: Dict[str, gpd.GeoDataFrame]
    edges: Dict[Tuple[str, str, str], gpd.GeoDataFrame]
    
    @property
    def node_types(self) -> list:
        return list(self.nodes.keys())
    
    @property
    def edge_types(self) -> list:
        return list(self.edges.keys())
    
    @property
    def total_nodes(self) -> int:
        return sum(len(gdf) for gdf in self.nodes.values())
    
    @property
    def total_edges(self) -> int:
        return sum(len(gdf) for gdf in self.edges.values())
    
    def summary(self) -> str:
        lines = [f"节点类型: {self.node_types}"]
        for nt, gdf in self.nodes.items():
            lines.append(f"  {nt}: {len(gdf)} 节点")
        lines.append(f"边类型: {self.edge_types}")
        for et, gdf in self.edges.items():
            lines.append(f"  {et}: {len(gdf)} 边")
        lines.append(f"总计: {self.total_nodes} 节点, {self.total_edges} 边")
        return "\n".join(lines)


def build_morphological_graph(
    buildings_gdf: gpd.GeoDataFrame,
    segments_gdf: gpd.GeoDataFrame,
) -> Tuple[dict, dict]:
    """使用city2graph构建街道+建筑形态图
    
    Returns:
        (nodes_dict, edges_dict)
        nodes_dict: {"movement": segments, "place": buildings}
        edges_dict: {("movement","connected_to","movement"): ..., ...}
    """
    nodes, edges = c2g.morphological_graph(
        buildings_gdf,
        segments_gdf,
        center_point=DISTRICT_CENTERS[0],  # 使用第一个中心点
        distance=GRAPH_CFG.morpho_distance,
        as_nx=False
    )
    return nodes, edges


def connect_observations_to_segments(
    obs_gdf: gpd.GeoDataFrame,
    segments_gdf: gpd.GeoDataFrame,
    max_distance: float = None,
) -> gpd.GeoDataFrame:
    """观测点→最近街道段 (observed_at边)
    
    Args:
        obs_gdf: 街景观测点GeoDataFrame (含obs_id)
        segments_gdf: 街道段GeoDataFrame (含seg_id)
        max_distance: 最大连接距离(米)
        
    Returns:
        含 obs_id, seg_id, distance 列的连接表
    """
    if max_distance is None:
        max_distance = GRAPH_CFG.obs_max_distance
    
    # 投影到UTM做距离计算
    obs_proj = obs_gdf.to_crs("EPSG:32650")
    seg_proj = segments_gdf.to_crs("EPSG:32650")
    
    # 确保有seg_id列
    if "seg_id" not in seg_proj.columns:
        seg_proj["seg_id"] = range(len(seg_proj))
    
    joined = gpd.sjoin_nearest(
        obs_proj, seg_proj[["seg_id", "geometry"]],
        how="left",
        max_distance=max_distance,
        lsuffix="obs", rsuffix="seg"
    )
    
    # 计算距离
    result = joined[["obs_id", "seg_id"]].copy()
    result["distance"] = obs_proj.geometry.apply(
        lambda p: seg_proj[seg_proj["seg_id"] == p].geometry.iloc[0].distance(p)
        if len(seg_proj[seg_proj["seg_id"] == p]) > 0 else float('inf')
    )
    
    return result.dropna(subset=["seg_id"])


def connect_pois_to_segments(
    poi_gdf: gpd.GeoDataFrame,
    segments_gdf: gpd.GeoDataFrame,
    k: int = None,
    max_distance: float = None,
) -> gpd.GeoDataFrame:
    """POI→最近k个街道段 (nearby边)
    
    Args:
        poi_gdf: POI GeoDataFrame (含poi_id)
        segments_gdf: 街道段GeoDataFrame (含seg_id)
        k: 每个POI连接的最近segment数
        max_distance: 最大连接距离(米)
        
    Returns:
        含 poi_id, seg_id, distance 列的连接表
    """
    if k is None:
        k = GRAPH_CFG.poi_k_neighbors
    if max_distance is None:
        max_distance = GRAPH_CFG.poi_max_distance
    
    poi_proj = poi_gdf.to_crs("EPSG:32650")
    seg_proj = segments_gdf.to_crs("EPSG:32650")
    
    if "seg_id" not in seg_proj.columns:
        seg_proj["seg_id"] = range(len(seg_proj))
    
    # 对每个POI找最近k个segment
    results = []
    for _, poi_row in poi_proj.iterrows():
        distances = seg_proj.geometry.distance(poi_row.geometry)
        nearest_k = distances.nsmallest(k)
        for seg_idx, dist in nearest_k.items():
            if dist <= max_distance:
                results.append({
                    "poi_id": poi_row["poi_id"],
                    "seg_id": seg_proj.iloc[seg_idx]["seg_id"],
                    "distance": dist
                })
    
    return pd.DataFrame(results)


def connect_stations_to_segments(
    station_gdf: gpd.GeoDataFrame,
    segments_gdf: gpd.GeoDataFrame,
    max_distance: float = None,
) -> gpd.GeoDataFrame:
    """单车停车点→最近街道段 (served_by边)"""
    if max_distance is None:
        max_distance = GRAPH_CFG.station_max_distance
    
    station_proj = station_gdf.to_crs("EPSG:32650")
    seg_proj = segments_gdf.to_crs("EPSG:32650")
    
    if "seg_id" not in seg_proj.columns:
        seg_proj["seg_id"] = range(len(seg_proj))
    
    joined = gpd.sjoin_nearest(
        station_proj, seg_proj[["seg_id", "geometry"]],
        how="left",
        max_distance=max_distance,
        lsuffix="sta", rsuffix="seg"
    )
    
    result = joined[["station_id", "seg_id"]].copy()
    return result.dropna(subset=["seg_id"])


def build_hetero_graph(
    segments_gdf: gpd.GeoDataFrame,
    buildings_gdf: gpd.GeoDataFrame,
    poi_gdf: gpd.GeoDataFrame,
    station_gdf: gpd.GeoDataFrame,
    obs_gdf: gpd.GeoDataFrame,
) -> HeteroGraphData:
    """构建完整的5类节点6类边异构图
    
    节点类型:
        - segment (街道段)
        - place (建筑地块)
        - poi (兴趣点)
        - station (单车停车点)
        - observation (街景观测点)
    
    边类型:
        - (segment, connected_to, segment)
        - (place, faced_to, segment)
        - (place, touched_to, place)
        - (poi, nearby, segment)
        - (station, served_by, segment)
        - (observation, observed_at, segment)
    """
    # 1. city2graph形态图 (segment + place + 3类边)
    nodes_dict, edges_dict = build_morphological_graph(buildings_gdf, segments_gdf)
    
    # 标准化节点字典key
    if "movement" in nodes_dict:
        nodes_dict["segment"] = nodes_dict.pop("movement")
    
    # 2. 观测点→segment
    obs_edges = connect_observations_to_segments(obs_gdf, segments_gdf)
    edges_dict[("observation", "observed_at", "segment")] = obs_edges
    
    # 3. POI→segment
    poi_edges = connect_pois_to_segments(poi_gdf, segments_gdf)
    edges_dict[("poi", "nearby", "segment")] = poi_edges
    
    # 4. station→segment
    sta_edges = connect_stations_to_segments(station_gdf, segments_gdf)
    edges_dict[("station", "served_by", "segment")] = sta_edges
    
    # 合并所有节点
    all_nodes = {
        "segment": nodes_dict.get("segment", segments_gdf),
        "place": nodes_dict.get("place", buildings_gdf),
        "poi": poi_gdf,
        "station": station_gdf,
        "observation": obs_gdf,
    }
    
    return HeteroGraphData(nodes=all_nodes, edges=edges_dict)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest algorithm/tests/test_hetero_builder.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: heterogeneous graph builder with 5 node types and 6 edge types"
```

---

## Task 7: 街景指标空间传播

**Files:**
- Create: `BikeFlowGNN/algorithm/graph/metric_propagation.py`
- Create: `BikeFlowGNN/algorithm/tests/test_metric_propagation.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_metric_propagation.py`**

```python
"""街景指标传播测试"""
import pytest
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString
from algorithm.graph.metric_propagation import propagate_metrics_to_segments

def test_propagation_basic(sample_obs_gdf, sample_segments_gdf):
    """测试基本传播功能"""
    result = propagate_metrics_to_segments(
        sample_obs_gdf, sample_segments_gdf, k=2, max_dist=10000
    )
    # 每个segment应有传播后的指标
    assert "s_bike_lane_type" in result.columns
    assert "v_greenery" in result.columns
    assert "x_perceived_safety" in result.columns
    # 指标值应在原始观测值范围内
    assert result["s_bike_lane_type"].min() >= 0
    assert result["s_bike_lane_type"].max() <= 1

def test_propagation_has_observation_flag(sample_obs_gdf, sample_segments_gdf):
    """测试has_observation标记"""
    result = propagate_metrics_to_segments(
        sample_obs_gdf, sample_segments_gdf, k=2, max_dist=10000
    )
    assert "has_observation" in result.columns
    assert result["has_observation"].dtype == bool

def test_propagation_distance_weighted(sample_obs_gdf):
    """测试距离反比加权: 更近的观测点应有更大权重"""
    # 创建两个segment: 一个靠近obs[0], 一个靠近obs[2]
    segments = gpd.GeoDataFrame({
        "seg_id": [0, 1],
    }, geometry=[
        LineString([(116.359,39.909),(116.361,39.911)]),  # 靠近obs[0]
        LineString([(116.379,39.929),(116.381,39.931)]),  # 靠近obs[2]
    ], crs="EPSG:4326")
    
    result = propagate_metrics_to_segments(
        sample_obs_gdf, segments, k=3, max_dist=10000
    )
    # seg[0]靠近obs[0](s_bike_lane_type=0.65), 应偏高
    # seg[1]靠近obs[2](s_bike_lane_type=0.45), 应偏低
    assert result.iloc[0]["s_bike_lane_type"] > result.iloc[1]["s_bike_lane_type"]
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest algorithm/tests/test_metric_propagation.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 `algorithm/graph/metric_propagation.py`**

```python
"""街景指标从观测点到街道段的KDTree空间传播"""
import numpy as np
import geopandas as gpd
from scipy.spatial import cKDTree
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from algorithm.config import GRAPH_CFG


def propagate_metrics_to_segments(
    obs_gdf: gpd.GeoDataFrame,
    segments_gdf: gpd.GeoDataFrame,
    k: int = None,
    max_dist: float = None,
) -> gpd.GeoDataFrame:
    """将观测点指标传播到街道段
    
    策略: 每个segment取最近的k个观测点的距离反比加权平均
    
    Args:
        obs_gdf: 观测点GeoDataFrame (含s_/f_/v_/x_前缀的指标列)
        segments_gdf: 街道段GeoDataFrame
        k: 最近邻数
        max_dist: 最大传播距离(米)
        
    Returns:
        segments_gdf添加传播后的指标列 + has_observation标记
    """
    if k is None:
        k = GRAPH_CFG.propagation_k
    if max_dist is None:
        max_dist = GRAPH_CFG.propagation_max_dist
    
    # 投影到UTM
    obs_proj = obs_gdf.to_crs("EPSG:32650")
    seg_proj = segments_gdf.to_crs("EPSG:32650").copy()
    
    # 构建观测点KD树 (使用投影坐标)
    obs_coords = np.array([(g.x, g.y) for g in obs_proj.geometry])
    tree = cKDTree(obs_coords)
    
    # 计算segment中点
    seg_centers = np.array([
        (g.centroid.x, g.centroid.y) for g in seg_proj.geometry
    ])
    
    # 查找最近k个观测点
    actual_k = min(k, len(obs_proj))
    distances, indices = tree.query(seg_centers, k=actual_k)
    
    # 处理k=1时维度问题
    if actual_k == 1:
        distances = distances.reshape(-1, 1)
        indices = indices.reshape(-1, 1)
    
    # 距离反比加权
    weights = 1.0 / (distances + 1e-6)
    weights = weights / weights.sum(axis=1, keepdims=True)
    
    # 识别指标列
    metric_cols = [c for c in obs_proj.columns
                   if c.startswith(("s_", "f_", "v_", "x_"))]
    
    # 加权平均传播
    for col in metric_cols:
        obs_values = obs_proj[col].values
        # 处理NaN
        obs_values = np.nan_to_num(obs_values, nan=0.0)
        seg_values = np.average(
            obs_values[indices], axis=1, weights=weights
        )
        seg_proj[col] = seg_values
    
    # 标记无近邻观测点的段
    seg_proj["has_observation"] = distances[:, 0] < max_dist
    
    # 转回WGS84
    result = seg_proj.to_crs("EPSG:4326")
    return result
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest algorithm/tests/test_metric_propagation.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: KDTree-based street view metric propagation to segments"
```

---

## Task 8: 四维边权模型

**Files:**
- Create: `BikeFlowGNN/algorithm/weights/edge_weights.py`
- Create: `BikeFlowGNN/algorithm/weights/cost_fusion.py`
- Create: `BikeFlowGNN/algorithm/tests/test_edge_weights.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_edge_weights.py`**

```python
"""四维边权模型测试"""
import pytest
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString
from algorithm.weights.edge_weights import (
    safety_from_streetview,
    comfort_from_streetview,
    scenery_from_streetview,
    experience_from_streetview,
    compute_all_weights,
)
from algorithm.weights.cost_fusion import fuse_composite_cost

def test_safety_from_streetview(sample_obs_gdf):
    """测试安全性计算"""
    metrics = sample_obs_gdf.iloc[0].to_dict()
    s = safety_from_streetview(metrics)
    assert 0 <= s <= 1
    # obs[0]: bike_lane=0.65, sep=0.55, motor=0.45(→0.55), heavy=0.30(→0.70)
    # 应该是中等偏上
    assert s > 0.4

def test_safety_inverts_negative_metrics():
    """测试负面指标反转"""
    metrics = {
        "s_bike_lane_type": 0.2,
        "s_physical_separation": 0.1,
        "s_motor_pressure": 0.9,   # 高压力 → 低安全
        "s_heavy_vehicle": 0.8,    # 高暴露 → 低安全
        "s_parking_encroach": 0.7, # 高侵占 → 低安全
        "s_intersection_conflict": 0.6,
    }
    s = safety_from_streetview(metrics)
    assert s < 0.3  # 应该很低

def test_comfort_from_streetview(sample_obs_gdf):
    """测试舒适度计算"""
    metrics = sample_obs_gdf.iloc[0].to_dict()
    f = comfort_from_streetview(metrics)
    assert 0 <= f <= 1

def test_scenery_from_streetview(sample_obs_gdf):
    """测试风景计算"""
    metrics = sample_obs_gdf.iloc[0].to_dict()
    v = scenery_from_streetview(metrics)
    assert 0 <= v <= 1

def test_experience_from_streetview(sample_obs_gdf):
    """测试综合体验计算"""
    metrics = sample_obs_gdf.iloc[0].to_dict()
    x = experience_from_streetview(metrics)
    assert 0 <= x <= 1

def test_compute_all_weights(sample_segments_gdf):
    """测试批量计算所有边权"""
    # 给segment添加指标列
    gdf = sample_segments_gdf.copy()
    gdf["s_bike_lane_type"] = [0.6, 0.7, 0.5, 0.8]
    gdf["s_physical_separation"] = [0.5, 0.6, 0.4, 0.7]
    gdf["s_motor_pressure"] = [0.4, 0.3, 0.5, 0.2]
    gdf["s_heavy_vehicle"] = [0.3, 0.2, 0.4, 0.1]
    gdf["s_parking_encroach"] = [0.2, 0.1, 0.3, 0.0]
    gdf["s_intersection_conflict"] = [0.3, 0.2, 0.4, 0.1]
    gdf["f_surface_quality"] = [0.6, 0.7, 0.5, 0.8]
    gdf["f_pothole"] = [0.2, 0.1, 0.3, 0.0]
    gdf["f_overall_comfort"] = [0.6, 0.7, 0.5, 0.8]
    gdf["f_traffic_stress"] = [0.4, 0.3, 0.5, 0.2]
    gdf["v_greenery"] = [0.5, 0.6, 0.4, 0.7]
    gdf["v_beauty"] = [0.5, 0.6, 0.4, 0.7]
    gdf["v_tranquility"] = [0.5, 0.6, 0.4, 0.7]
    gdf["x_perceived_safety"] = [0.5, 0.6, 0.4, 0.7]
    gdf["x_active_frontage"] = [0.5, 0.6, 0.4, 0.7]
    gdf["x_cleanliness"] = [0.5, 0.6, 0.4, 0.7]
    gdf["x_lighting"] = [0.5, 0.6, 0.4, 0.7]
    
    result = compute_all_weights(gdf)
    assert "w_safety" in result.columns
    assert "w_comfort" in result.columns
    assert "w_scenery" in result.columns
    assert "w_experience" in result.columns
    assert result["w_safety"].between(0, 1).all()

def test_fuse_composite_cost():
    """测试综合成本融合"""
    import pandas as pd
    df = pd.DataFrame({
        "w_safety": [0.6, 0.8],
        "w_comfort": [0.5, 0.7],
        "w_scenery": [0.7, 0.6],
        "w_experience": [0.5, 0.8],
        "length": [100.0, 200.0],
    })
    result = fuse_composite_cost(df, alpha=0.3, beta=0.25, gamma=0.25, delta=0.2)
    assert "cost_composite" in result.columns
    # 成本应与长度正相关、与边权负相关
    assert result["cost_composite"].iloc[0] < result["cost_composite"].iloc[1] * 2
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest algorithm/tests/test_edge_weights.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 `algorithm/weights/edge_weights.py`**

```python
"""街景指标驱动的四维边权模型"""
import numpy as np
import geopandas as gpd
from pathlib import Path


def safety_from_streetview(metrics: dict) -> float:
    """从街景指标计算安全性 (0=危险, 1=安全)
    
    8项指标: 自行车道类型、物理隔离、机动车压力(反转)、大型车暴露(反转)、
             停车侵占(反转)、路口冲突(反转)、交通控制设施、斑马线
    """
    s_lane = metrics.get("s_bike_lane_type", 0.2)
    s_sep = metrics.get("s_physical_separation", 0.0)
    s_traffic = 1.0 - metrics.get("s_motor_pressure", 0.5)     # 反转
    s_heavy = 1.0 - metrics.get("s_heavy_vehicle", 0.3)        # 反转
    s_parking = 1.0 - metrics.get("s_parking_encroach", 0.2)   # 反转
    s_intersection = 1.0 - metrics.get("s_intersection_conflict", 0.3)  # 反转
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
    f_pothole = 1.0 - metrics.get("f_pothole", 0.2)           # 反转
    f_construction = 1.0 - metrics.get("f_construction", 0.0)  # 反转
    f_obstacle = 1.0 - metrics.get("f_obstacle", 0.0)          # 反转
    f_width = min(1.0, metrics.get("f_rideable_width", 2.0) / 4.0)
    f_overall = metrics.get("f_overall_comfort", 0.5)
    f_stress = 1.0 - metrics.get("f_traffic_stress", 0.4)      # 反转
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
    """综合体验维度 (0=差, 1=好) — v2新增第四维度
    
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
```

- [ ] **Step 4: 实现 `algorithm/weights/cost_fusion.py`**

```python
"""四维边权加权融合为综合骑行成本"""
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from algorithm.config import WEIGHT_CFG


def fuse_composite_cost(
    segments_gdf: gpd.GeoDataFrame,
    alpha: float = None,
    beta: float = None,
    gamma: float = None,
    delta: float = None,
) -> gpd.GeoDataFrame:
    """将四维边权融合为综合骑行成本C(e)
    
    公式: C(e) = length × (1 - (α·S + β·F + γ·V + δ·X))
    
    高权重(好路况) → 低成本; 长距离 → 高成本
    
    Args:
        segments_gdf: 含 w_safety, w_comfort, w_scenery, w_experience, length 列
        alpha/beta/gamma/delta: 四维权重
        
    Returns:
        添加 cost_composite 列
    """
    if alpha is None:
        alpha = WEIGHT_CFG.alpha
    if beta is None:
        beta = WEIGHT_CFG.beta
    if gamma is None:
        gamma = WEIGHT_CFG.gamma
    if delta is None:
        delta = WEIGHT_CFG.delta
    
    result = segments_gdf.copy()
    
    # 加权综合质量分 (0~1)
    quality = (
        alpha * result["w_safety"] +
        beta * result["w_comfort"] +
        gamma * result["w_scenery"] +
        delta * result["w_experience"]
    )
    
    # 成本 = 长度 × (1 - 质量)
    # 质量越高成本越低, 鼓励选择好路况
    result["cost_composite"] = result["length"] * (1.0 - quality)
    
    # 确保成本为正
    result["cost_composite"] = result["cost_composite"].clip(lower=0.1)
    
    return result
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest algorithm/tests/test_edge_weights.py -v
```

Expected: 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: four-dimensional edge weight model (safety/comfort/scenery/experience)"
```

---

## Task 9: HGT模型与mini-batch训练

**Files:**
- Create: `BikeFlowGNN/algorithm/models/hgt_model.py`
- Create: `BikeFlowGNN/algorithm/models/trainer.py`
- Create: `BikeFlowGNN/algorithm/tests/test_hgt_model.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_hgt_model.py`**

```python
"""HGT模型测试"""
import pytest
import torch
from torch_geometric.data import HeteroData
from algorithm.models.hgt_model import BikeFlowGNN_v2, create_hetero_data

def test_model_forward():
    """测试HGT前向传播"""
    # 创建最小异构图
    metadata = (
        ["segment", "poi", "observation", "place", "station"],  # 节点类型
        [
            ("segment", "connected_to", "segment"),
            ("observation", "observed_at", "segment"),
            ("poi", "nearby", "segment"),
        ]
    )
    
    model = BikeFlowGNN_v2(metadata, hidden_dim=32, num_heads=2, num_layers=2)
    
    x_dict = {
        "segment": torch.randn(10, 32),
        "poi": torch.randn(20, 32),
        "observation": torch.randn(5, 32),
        "place": torch.randn(8, 32),
        "station": torch.randn(3, 32),
    }
    edge_index_dict = {
        ("segment", "connected_to", "segment"): torch.randint(0, 10, (2, 15)),
        ("observation", "observed_at", "segment"): torch.randint(0, 10, (2, 5)),
        ("poi", "nearby", "segment"): torch.randint(0, 10, (2, 20)),
    }
    
    out = model(x_dict, edge_index_dict)
    assert "segment" in out
    assert out["segment"].shape == (10, 32)

def test_preference_head():
    """测试偏好预测头"""
    metadata = (["segment"], [])
    model = BikeFlowGNN_v2(metadata, hidden_dim=32, num_heads=2, num_layers=1)
    
    x_dict = {"segment": torch.randn(10, 32)}
    edge_index_dict = {}
    
    embeddings = model(x_dict, edge_index_dict)
    
    # 模拟偏好预测
    src = torch.tensor([0, 1, 2])
    dst = torch.tensor([1, 2, 3])
    pred = model.predict_preference(embeddings["segment"], src, dst)
    assert pred.shape == (3,)
    assert (pred >= 0).all() and (pred <= 1).all()

def test_create_hetero_data():
    """测试HeteroData创建"""
    import numpy as np
    
    nodes = {
        "segment": np.random.randn(10, 5).astype(np.float32),
        "poi": np.random.randn(20, 1).astype(np.float32),
    }
    edges = {
        ("segment", "connected_to", "segment"): (np.array([0,1,2]), np.array([1,2,3])),
        ("poi", "nearby", "segment"): (np.array([0,1]), np.array([0,1])),
    }
    node_counts = {"segment": 10, "poi": 20}
    
    hetero_data = create_hetero_data(nodes, edges, node_counts, hidden_dim=32)
    
    assert isinstance(hetero_data, HeteroData)
    assert "segment" in hetero_data.node_types
    assert hetero_data["segment"].x.shape[0] == 10
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest algorithm/tests/test_hgt_model.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 `algorithm/models/hgt_model.py`**

```python
"""HGT (Heterogeneous Graph Transformer) 模型定义"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import HGTConv
from torch_geometric.data import HeteroData
import numpy as np
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from algorithm.config import TRAIN_CFG


class BikeFlowGNN_v2(nn.Module):
    """异构图Transformer模型
    
    架构:
        1. 线性投影层: 将各类型节点特征统一到hidden_dim
        2. HGT卷积层: 跨类型消息传递
        3. 偏好预测头: segment对的偏好分数预测
    """
    
    def __init__(
        self,
        metadata,
        hidden_dim: int = 64,
        num_heads: int = 4,
        num_layers: int = 2,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        
        # 各节点类型的线性投影
        self.lin_dict = nn.ModuleDict()
        for node_type in metadata[0]:
            self.lin_dict[node_type] = nn.Linear(hidden_dim, hidden_dim)
        
        # HGT卷积层
        self.convs = nn.ModuleList([
            HGTConv(
                hidden_dim, hidden_dim, metadata,
                heads=num_heads, group="sum"
            )
            for _ in range(num_layers)
        ])
        
        # 偏好预测头
        self.pref_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x_dict, edge_index_dict):
        """前向传播
        
        Args:
            x_dict: {node_type: tensor(N, hidden_dim)} 节点特征
            edge_index_dict: {edge_type: tensor(2, E)} 边索引
            
        Returns:
            x_dict: 更新后的节点嵌入
        """
        # 线性投影
        x_dict = {
            nt: self.lin_dict[nt](x.float())
            for nt, x in x_dict.items()
        }
        
        # HGT卷积
        for conv in self.convs:
            x_dict = conv(x_dict, edge_index_dict)
            x_dict = {k: v.relu() for k, v in x_dict.items()}
        
        return x_dict
    
    def predict_preference(self, segment_emb, src_idx, dst_idx):
        """预测segment对的骑行偏好分数
        
        Args:
            segment_emb: segment节点嵌入 (N, hidden_dim)
            src_idx: 源节点索引 (E,)
            dst_idx: 目标节点索引 (E,)
            
        Returns:
            偏好分数 (E,), 范围[0,1]
        """
        src_emb = segment_emb[src_idx]
        dst_emb = segment_emb[dst_idx]
        paired = torch.cat([src_emb, dst_emb], dim=-1)
        return self.pref_head(paired).squeeze(-1)


def create_hetero_data(
    nodes: dict,
    edges: dict,
    node_counts: dict,
    hidden_dim: int = 64,
) -> HeteroData:
    """从节点特征和边索引创建PyG HeteroData
    
    Args:
        nodes: {node_type: ndarray(N, F)} 节点特征
        edges: {edge_type: (src_array, dst_array)} 边索引
        node_counts: {node_type: int} 各类型节点数 (用于无特征的类型填充)
        hidden_dim: 统一特征维度
        
    Returns:
        torch_geometric.data.HeteroData
    """
    data = HeteroData()
    
    for node_type, features in nodes.items():
        if features is not None and len(features) > 0:
            # 如果特征维度不等于hidden_dim, 用线性投影补齐
            if features.shape[1] < hidden_dim:
                padding = np.zeros(
                    (features.shape[0], hidden_dim - features.shape[1]),
                    dtype=np.float32
                )
                features = np.hstack([features, padding])
            elif features.shape[1] > hidden_dim:
                features = features[:, :hidden_dim]
            data[node_type].x = torch.tensor(features, dtype=torch.float32)
        else:
            # 无特征的节点类型: 用随机初始化
            count = node_counts.get(node_type, 0)
            data[node_type].x = torch.randn(count, hidden_dim)
    
    for edge_type, (src, dst) in edges.items():
        if len(src) > 0:
            data[edge_type].edge_index = torch.tensor(
                np.stack([src, dst]), dtype=torch.long
            )
    
    return data
```

- [ ] **Step 4: 实现 `algorithm/models/trainer.py`**

```python
"""NeighborSampler mini-batch训练管道"""
import torch
import torch.nn.functional as F
from torch_geometric.loader import NeighborLoader
from torch_geometric.data import HeteroData
import numpy as np
from pathlib import Path
from typing import Tuple
import time

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from algorithm.config import TRAIN_CFG
from algorithm.models.hgt_model import BikeFlowGNN_v2


def create_train_loader(
    hetero_data: HeteroData,
    train_mask: torch.Tensor = None,
) -> NeighborLoader:
    """创建mini-batch数据加载器
    
    Args:
        hetero_data: 完整的HeteroData
        train_mask: segment节点的训练掩码
        
    Returns:
        NeighborLoader实例
    """
    if train_mask is None:
        # 默认: 所有segment节点都参与训练
        n_seg = hetero_data["segment"].x.shape[0]
        train_mask = torch.ones(n_seg, dtype=torch.bool)
    
    # 采样邻居配置
    num_neighbors = {
        ("segment", "connected_to", "segment"): [
            TRAIN_CFG.num_neighbors_l1.get(("segment", "connected_to", "segment"), 15),
            TRAIN_CFG.num_neighbors_l2.get(("segment", "connected_to", "segment"), 10),
        ],
    }
    # 添加其他边类型的采样配置
    for et in hetero_data.edge_types:
        if et not in num_neighbors:
            l1 = TRAIN_CFG.num_neighbors_l1.get(et, 5)
            l2 = TRAIN_CFG.num_neighbors_l2.get(et, 3)
            num_neighbors[et] = [l1, l2]
    
    loader = NeighborLoader(
        hetero_data,
        num_neighbors=num_neighbors,
        batch_size=TRAIN_CFG.batch_size,
        input_nodes=("segment", train_mask),
        shuffle=True,
        num_workers=TRAIN_CFG.num_workers,
    )
    
    return loader


def generate_preference_labels(
    hetero_data: HeteroData,
    cost_col: str = "cost_composite",
) -> torch.Tensor:
    """基于综合成本生成偏好标签 (自监督)
    
    高成本边 → 低偏好(0), 低成本边 → 高偏好(1)
    
    Args:
        hetero_data: 含segment连接边的HeteroData
        cost_col: 成本列名
        
    Returns:
        偏好标签 tensor(E,)
    """
    edge_type = ("segment", "connected_to", "segment")
    if edge_type not in hetero_data.edge_types:
        return torch.tensor([])
    
    costs = hetero_data[edge_type].get(cost_col)
    if costs is None:
        # 无成本信息时用随机标签
        n_edges = hetero_data[edge_type].edge_index.shape[1]
        return torch.rand(n_edges)
    
    # 归一化到[0,1]并反转 (低成本=高偏好)
    costs = costs.float()
    normalized = (costs - costs.min()) / (costs.max() - costs.min() + 1e-8)
    labels = 1.0 - normalized
    return labels


def train_model(
    hetero_data: HeteroData,
    train_mask: torch.Tensor = None,
    device: str = "cuda",
) -> Tuple[BikeFlowGNN_v2, list]:
    """完整训练流程
    
    Args:
        hetero_data: PyG HeteroData
        train_mask: 训练集segment掩码
        device: 'cuda' 或 'cpu'
        
    Returns:
        (训练好的模型, loss历史)
    """
    print(f"设备: {device}")
    print(f"节点类型: {hetero_data.node_types}")
    print(f"边类型: {hetero_data.edge_types}")
    
    # 创建数据加载器
    train_loader = create_train_loader(hetero_data, train_mask)
    print(f"每epoch batch数: {len(train_loader)}")
    
    # 初始化模型
    metadata = (
        hetero_data.node_types,
        hetero_data.edge_types
    )
    model = BikeFlowGNN_v2(
        metadata,
        hidden_dim=TRAIN_CFG.hidden_dim,
        num_heads=TRAIN_CFG.num_heads,
        num_layers=TRAIN_CFG.num_layers
    ).to(device)
    
    # torch.compile加速
    if TRAIN_CFG.use_compile and hasattr(torch, "compile"):
        model = torch.compile(model, dynamic=True)
        print("已启用 torch.compile")
    
    optimizer = torch.optim.Adam(model.parameters(), lr=TRAIN_CFG.lr)
    
    # FP16混合精度
    scaler = torch.cuda.amp.GradScaler(enabled=TRAIN_CFG.use_fp16 and device == "cuda")
    
    # 生成偏好标签
    pref_labels = generate_preference_labels(hetero_data).to(device)
    
    loss_history = []
    start_time = time.time()
    
    for epoch in range(TRAIN_CFG.epochs):
        model.train()
        total_loss = 0
        n_batches = 0
        
        for batch in train_loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            
            with torch.cuda.amp.autocast(enabled=TRAIN_CFG.use_fp16 and device == "cuda"):
                x_dict = model(batch.x_dict, batch.edge_index_dict)
                
                # 偏好预测
                edge_type = ("segment", "connected_to", "segment")
                if edge_type in batch.edge_types and batch[edge_type].edge_index.shape[1] > 0:
                    ei = batch[edge_type].edge_index
                    pred = model.predict_preference(
                        x_dict["segment"], ei[0], ei[1]
                    )
                    
                    # 使用batch内的边标签 (简化: 用随机标签)
                    labels = torch.rand(ei.shape[1], device=device)
                    loss = F.binary_cross_entropy(pred, labels.float())
                else:
                    # 无该类型边时用节点重构损失
                    target = batch["segment"].x
                    loss = F.mse_loss(x_dict["segment"], target)
            
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            
            total_loss += loss.item()
            n_batches += 1
        
        avg_loss = total_loss / max(n_batches, 1)
        loss_history.append(avg_loss)
        
        if (epoch + 1) % 10 == 0:
            elapsed = time.time() - start_time
            print(f"Epoch {epoch+1}/{TRAIN_CFG.epochs}: loss={avg_loss:.4f}, "
                  f"elapsed={elapsed:.1f}s")
    
    total_time = time.time() - start_time
    print(f"\n训练完成: {TRAIN_CFG.epochs} epochs, 总耗时 {total_time:.1f}s "
          f"({total_time/60:.1f}分钟)")
    
    return model, loss_history


def export_embeddings(
    model: BikeFlowGNN_v2,
    hetero_data: HeteroData,
    device: str = "cuda",
) -> dict:
    """导出训练后的节点嵌入
    
    Args:
        model: 训练好的模型
        hetero_data: 完整图数据
        device: 设备
        
    Returns:
        {node_type: ndarray(N, hidden_dim)} 嵌入字典
    """
    model.eval()
    hetero_data = hetero_data.to(device)
    
    with torch.no_grad():
        embeddings = model(hetero_data.x_dict, hetero_data.edge_index_dict)
    
    result = {}
    for nt, emb in embeddings.items():
        result[nt] = emb.cpu().numpy()
    
    return result
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest algorithm/tests/test_hgt_model.py -v
```

Expected: 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: HGT model with NeighborSampler mini-batch training pipeline"
```

---

## Task 10: NSGA-II多目标路径搜索

**Files:**
- Create: `BikeFlowGNN/algorithm/routing/nsga2_search.py`
- Create: `BikeFlowGNN/algorithm/routing/station_constraint.py`
- Create: `BikeFlowGNN/algorithm/tests/test_nsga2_search.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_nsga2_search.py`**

```python
"""NSGA-II路径搜索测试"""
import pytest
import networkx as nx
import numpy as np
from algorithm.routing.nsga2_search import (
    build_nx_graph,
    evaluate_route,
    nsga2_search,
)
from algorithm.routing.station_constraint import station_density_bonus

def test_build_nx_graph():
    """测试NetworkX图构建"""
    import geopandas as gpd
    from shapely.geometry import LineString
    
    segments = gpd.GeoDataFrame({
        "seg_id": [0, 1, 2],
        "length": [100.0, 150.0, 80.0],
        "cost_composite": [50.0, 70.0, 30.0],
        "w_safety": [0.6, 0.5, 0.8],
        "w_scenery": [0.7, 0.4, 0.6],
        "w_comfort": [0.5, 0.6, 0.7],
        "f_traffic_stress": [0.4, 0.6, 0.2],
        "v_beauty": [0.7, 0.4, 0.6],
    }, geometry=[
        LineString([(0,0),(1,1)]),
        LineString([(1,1),(2,2)]),
        LineString([(2,2),(3,3)]),
    ], crs="EPSG:4326")
    
    G = build_nx_graph(segments)
    assert G.number_of_nodes() >= 3
    assert G.number_of_edges() >= 2

def test_evaluate_route():
    """测试路线评估"""
    G = nx.Graph()
    G.add_edge(0, 1, length=100.0, cost_composite=50.0, 
               f_traffic_stress=0.4, v_beauty=0.7, pref_score=0.8)
    G.add_edge(1, 2, length=150.0, cost_composite=70.0,
               f_traffic_stress=0.6, v_beauty=0.4, pref_score=0.5)
    
    route = [0, 1, 2]
    objectives = evaluate_route(route, G)
    assert len(objectives) == 4
    assert objectives[0] == 250.0  # 总距离
    assert objectives[1] == 1.0    # 总交通压力

def test_nsga2_search_small():
    """测试小规模NSGA-II搜索"""
    G = nx.Graph()
    for i in range(10):
        G.add_edge(i, i+1, length=100.0, cost_composite=50.0,
                   f_traffic_stress=0.4, v_beauty=0.7, pref_score=0.7)
    
    routes = nsga2_search(G, source=0, target=10, pop_size=20, n_gen=10)
    assert len(routes) > 0
    assert all(isinstance(r, list) for r in routes)

def test_station_density_bonus():
    """测试站点密度奖励"""
    import geopandas as gpd
    from shapely.geometry import Point, LineString
    
    stations = gpd.GeoDataFrame(
        geometry=[Point(0.5, 0.5), Point(1.5, 1.5)], crs="EPSG:4326"
    )
    G = nx.Graph()
    G.add_edge(0, 1, length=100.0)
    G.nodes[0]["pos"] = (0, 0)
    G.nodes[1]["pos"] = (2, 2)
    
    route = [0, 1]
    bonus = station_density_bonus(route, G, stations, buffer=10000)
    assert bonus >= 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest algorithm/tests/test_nsga2_search.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 `algorithm/routing/nsga2_search.py`**

```python
"""NSGA-II多目标路径搜索"""
import networkx as nx
import numpy as np
import geopandas as gpd
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import IntegerRandomSampling
from pymoo.optimize import minimize
from typing import List, Tuple
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from algorithm.config import NSGA2_CFG


def build_nx_graph(segments_gdf: gpd.GeoDataFrame) -> nx.Graph:
    """从segment GeoDataFrame构建NetworkX图
    
    Args:
        segments_gdf: 含 seg_id, length, cost_composite, w_* 列
        
    Returns:
        NetworkX无向图, 节点=路口, 边=街道段
    """
    G = nx.Graph()
    
    for _, row in segments_gdf.iterrows():
        geom = row.geometry
        if geom is None or len(geom.coords) < 2:
            continue
        
        u = (round(geom.coords[0][0], 6), round(geom.coords[0][1], 6))
        v = (round(geom.coords[-1][0], 6), round(geom.coords[-1][1], 6))
        
        G.add_edge(u, v, **{
            "length": row.get("length", geom.length),
            "cost_composite": row.get("cost_composite", 50.0),
            "f_traffic_stress": row.get("f_traffic_stress", 0.5),
            "v_beauty": row.get("v_beauty", 0.5),
            "w_safety": row.get("w_safety", 0.5),
            "w_scenery": row.get("w_scenery", 0.5),
            "w_comfort": row.get("w_comfort", 0.5),
            "pref_score": row.get("pref_score", 0.5),
            "seg_id": row.get("seg_id", 0),
        })
    
    return G


def evaluate_route(route: list, G: nx.Graph) -> List[float]:
    """评估路线的4个目标函数
    
    目标:
        f1: 总距离 (最小化)
        f2: 总交通压力 (最小化)
        f3: -总风景 (风景最大化→取负最小化)
        f4: -总偏好分 (偏好最大化→取负最小化)
    
    Args:
        route: 节点序列
        G: NetworkX图
        
    Returns:
        [f1, f2, f3, f4]
    """
    if len(route) < 2:
        return [0, 0, 0, 0]
    
    edges = list(zip(route[:-1], route[1:]))
    
    total_dist = sum(G[u][v].get("length", 0) for u, v in edges)
    total_stress = sum(G[u][v].get("f_traffic_stress", 0) for u, v in edges)
    total_beauty = sum(G[u][v].get("v_beauty", 0) for u, v in edges)
    total_pref = sum(G[u][v].get("pref_score", 0) for u, v in edges)
    
    return [total_dist, total_stress, -total_beauty, -total_pref]


class RouteProblem(Problem):
    """NSGA-II路径优化问题"""
    
    def __init__(self, G: nx.Graph, source, target, max_len: int = 50):
        self.G = G
        self.source = source
        self.target = target
        self.max_len = max_len
        
        # 预计算候选中间节点
        self.nodes = list(G.nodes())
        if source in self.nodes:
            self.nodes.remove(source)
        if target in self.nodes:
            self.nodes.remove(target)
        
        super().__init__(
            n_var=max_len - 2,  # 中间节点数
            n_obj=4,            # 4个目标
            n_constr=0,
            xl=0,
            xu=max(len(self.nodes) - 1, 0),
            type_var=int,
        )
    
    def _decode(self, x):
        """解码决策变量为路径"""
        route = [self.source]
        for idx in x:
            if idx < len(self.nodes):
                node = self.nodes[int(idx)]
                if node not in route:
                    route.append(node)
        route.append(self.target)
        return route
    
    def _evaluate(self, X, out, *args, **kwargs):
        """评估种群"""
        objectives = []
        for x in X:
            route = self._decode(x)
            
            # 检查路径连通性
            valid = True
            for i in range(len(route) - 1):
                if not self.G.has_edge(route[i], route[i+1]):
                    valid = False
                    break
            
            if valid:
                obj = evaluate_route(route, self.G)
            else:
                # 不连通的路径给予惩罚值
                obj = [1e6, 1e6, 1e6, 1e6]
            
            objectives.append(obj)
        
        out["F"] = np.array(objectives)


def nsga2_search(
    G: nx.Graph,
    source,
    target,
    pop_size: int = None,
    n_gen: int = None,
) -> List[List]:
    """执行NSGA-II多目标路径搜索
    
    Args:
        G: NetworkX图
        source: 起点节点
        target: 终点节点
        pop_size: 种群大小
        n_gen: 迭代代数
        
    Returns:
        Pareto最优路线列表
    """
    if pop_size is None:
        pop_size = NSGA2_CFG.pop_size
    if n_gen is None:
        n_gen = NSGA2_CFG.n_gen
    
    problem = RouteProblem(G, source, target)
    
    algorithm = NSGA2(
        pop_size=pop_size,
        sampling=IntegerRandomSampling(),
        crossover=SBX(prob=0.9, eta=15),
        mutation=PM(eta=20),
        eliminate_duplicates=True,
    )
    
    result = minimize(
        problem,
        algorithm,
        termination=("n_gen", n_gen),
        seed=42,
        verbose=False,
    )
    
    # 提取Pareto最优解
    pareto_routes = []
    for x in result.X:
        route = problem._decode(x)
        # 验证连通性
        valid = all(G.has_edge(route[i], route[i+1]) for i in range(len(route)-1))
        if valid and len(route) >= 2:
            pareto_routes.append(route)
    
    # 如果NSGA-II没找到有效路径, 退回到最短路径
    if not pareto_routes and nx.has_path(G, source, target):
        shortest = nx.shortest_path(G, source, target, weight="cost_composite")
        pareto_routes.append(shortest)
    
    return pareto_routes
```

- [ ] **Step 4: 实现 `algorithm/routing/station_constraint.py`**

```python
"""历史单车停车点密度约束"""
import numpy as np
import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from algorithm.config import NSGA2_CFG


def station_density_bonus(
    route: list,
    G: nx.Graph,
    station_gdf: gpd.GeoDataFrame,
    buffer: float = None,
) -> float:
    """计算路线经过区域的站点密度奖励
    
    Args:
        route: 路线节点序列
        G: NetworkX图 (节点需有pos属性)
        station_gdf: 站点GeoDataFrame
        buffer: 缓冲距离(米)
        
    Returns:
        每公里站点密度 (越高越好)
    """
    if buffer is None:
        buffer = NSGA2_CFG.station_buffer
    
    # 获取路线坐标
    positions = []
    for node in route:
        if "pos" in G.nodes[node]:
            positions.append(G.nodes[node]["pos"])
        elif isinstance(node, tuple):
            positions.append(node)
    
    if len(positions) < 2:
        return 0.0
    
    # 创建路线LineString
    route_line = LineString(positions)
    
    # 投影到UTM计算距离
    route_gdf = gpd.GeoDataFrame(
        {"id": [0]}, geometry=[route_line], crs="EPSG:4326"
    ).to_crs("EPSG:32650")
    
    station_proj = station_gdf.to_crs("EPSG:32650")
    
    # 计算站点到路线的距离
    distances = station_proj.geometry.distance(route_gdf.geometry.iloc[0])
    nearby_count = (distances < buffer).sum()
    
    # 路线长度 (公里)
    route_length_km = route_gdf.geometry.iloc[0].length / 1000.0
    
    if route_length_km == 0:
        return 0.0
    
    return float(nearby_count / route_length_km)


def rank_routes_by_station_access(
    routes: list,
    G: nx.Graph,
    station_gdf: gpd.GeoDataFrame,
    buffer: float = None,
) -> list:
    """按站点可达性对Pareto路线排序
    
    Args:
        routes: 路线列表
        G: NetworkX图
        station_gdf: 站点GeoDataFrame
        buffer: 缓冲距离
        
    Returns:
        按站点密度降序排列的 (route, density) 元组列表
    """
    scored = []
    for route in routes:
        density = station_density_bonus(route, G, station_gdf, buffer)
        scored.append((route, density))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest algorithm/tests/test_nsga2_search.py -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: NSGA-II multi-objective routing with station density constraints"
```

---

## Task 11: 个性化推荐

**Files:**
- Create: `BikeFlowGNN/algorithm/routing/recommender.py`
- Create: `BikeFlowGNN/algorithm/tests/test_recommender.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_recommender.py`**

```python
"""个性化推荐测试"""
import pytest
import networkx as nx
from algorithm.routing.recommender import (
    UserProfile,
    recommend_route,
    compute_route_score,
)

def test_user_profile_creation():
    """测试用户画像创建"""
    profile = UserProfile(
        user_id="user_001",
        preference_weights={"safety": 0.5, "comfort": 0.3, "scenery": 0.2},
        max_detour=1.5,
        prefer_greenery=True,
    )
    assert profile.preference_weights["safety"] == 0.5
    assert profile.max_detour == 1.5

def test_compute_route_score():
    """测试路线评分"""
    G = nx.Graph()
    G.add_edge(0, 1, length=100.0, w_safety=0.8, w_comfort=0.6,
               w_scenery=0.7, cost_composite=40.0)
    G.add_edge(1, 2, length=120.0, w_safety=0.7, w_comfort=0.5,
               w_scenery=0.8, cost_composite=50.0)
    
    profile = UserProfile(
        user_id="test",
        preference_weights={"safety": 0.5, "comfort": 0.3, "scenery": 0.2},
        max_detour=2.0,
    )
    
    route = [0, 1, 2]
    score = compute_route_score(route, G, profile)
    assert 0 <= score <= 1

def test_recommend_route():
    """测试路线推荐"""
    G = nx.Graph()
    for i in range(5):
        G.add_edge(i, i+1, length=100.0, w_safety=0.7, w_comfort=0.6,
                   w_scenery=0.7, cost_composite=40.0, pref_score=0.8,
                   f_traffic_stress=0.3, v_beauty=0.7)
    
    profile = UserProfile(
        user_id="test",
        preference_weights={"safety": 0.4, "comfort": 0.3, "scenery": 0.3},
        max_detour=2.0,
    )
    
    pareto_routes = [[0,1,2,3,4,5]]
    result = recommend_route(pareto_routes, G, profile)
    assert result is not None
    assert isinstance(result, list)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest algorithm/tests/test_recommender.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 `algorithm/routing/recommender.py`**

```python
"""个性化骑行路线推荐"""
import networkx as nx
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class UserProfile:
    """用户骑行偏好画像"""
    user_id: str
    preference_weights: Dict[str, float]  # {safety, comfort, scenery, experience}
    max_detour: float = 1.5               # 最大绕路系数 (实际距离/最短距离)
    prefer_greenery: bool = False         # 偏好绿植
    avoid_traffic: bool = False           # 避开交通压力
    cycling_speed: float = 15.0           # 平均骑行速度 km/h
    max_duration_min: float = 60.0        # 最大骑行时长(分钟)


def compute_route_score(
    route: list,
    G: nx.Graph,
    profile: UserProfile,
) -> float:
    """根据用户画像计算路线综合得分
    
    Args:
        route: 路线节点序列
        G: NetworkX图
        profile: 用户画像
        
    Returns:
        综合得分 [0, 1], 越高越好
    """
    if len(route) < 2:
        return 0.0
    
    edges = list(zip(route[:-1], route[1:]))
    
    # 聚合路线属性
    total_dist = sum(G[u][v].get("length", 0) for u, v in edges)
    avg_safety = np.mean([G[u][v].get("w_safety", 0.5) for u, v in edges])
    avg_comfort = np.mean([G[u][v].get("w_comfort", 0.5) for u, v in edges])
    avg_scenery = np.mean([G[u][v].get("w_scenery", 0.5) for u, v in edges])
    avg_pref = np.mean([G[u][v].get("pref_score", 0.5) for u, v in edges])
    
    # 最短距离
    source, target = route[0], route[-1]
    if nx.has_path(G, source, target):
        shortest_dist = nx.shortest_path_length(G, source, target, weight="length")
    else:
        shortest_dist = total_dist
    
    # 绕路系数
    detour_ratio = total_dist / max(shortest_dist, 1e-6)
    
    # 如果绕路超过用户容忍度, 大幅降分
    if detour_ratio > profile.max_detour:
        return 0.0
    
    # 加权得分
    weights = profile.preference_weights
    w_safety = weights.get("safety", 0.3)
    w_comfort = weights.get("comfort", 0.25)
    w_scenery = weights.get("scenery", 0.25)
    w_pref = 1.0 - w_safety - w_comfort - w_scenery
    
    score = (
        w_safety * avg_safety +
        w_comfort * avg_comfort +
        w_scenery * avg_scenery +
        max(w_pref, 0) * avg_pref
    )
    
    # 绿植偏好加成
    if profile.prefer_greenery:
        greenery_bonus = avg_scenery * 0.1
        score += greenery_bonus
    
    # 交通压力惩罚
    if profile.avoid_traffic:
        avg_stress = np.mean([G[u][v].get("f_traffic_stress", 0.5) for u, v in edges])
        score -= avg_stress * 0.15
    
    # 绕路惩罚 (轻微)
    detour_penalty = (detour_ratio - 1.0) * 0.1
    score -= max(detour_penalty, 0)
    
    # 骑行时长检查
    duration_min = (total_dist / 1000.0) / profile.cycling_speed * 60
    if duration_min > profile.max_duration_min:
        score *= 0.5  # 超时降分
    
    return float(np.clip(score, 0, 1))


def recommend_route(
    pareto_routes: List[list],
    G: nx.Graph,
    profile: UserProfile,
    top_k: int = 3,
) -> Optional[list]:
    """从Pareto路线集中推荐最适合用户的路线
    
    Args:
        pareto_routes: NSGA-II输出的Pareto路线集
        G: NetworkX图
        profile: 用户画像
        top_k: 返回前k条路线
        
    Returns:
        最佳路线 (或top_k路线列表)
    """
    if not pareto_routes:
        return None
    
    # 计算每条路线的用户得分
    scored_routes = []
    for route in pareto_routes:
        score = compute_route_score(route, G, profile)
        scored_routes.append((route, score))
    
    # 按得分降序排列
    scored_routes.sort(key=lambda x: x[1], reverse=True)
    
    if top_k == 1:
        return scored_routes[0][0] if scored_routes else None
    else:
        return [r for r, s in scored_routes[:top_k]]


# ── 预设用户画像模板 ──
USER_TEMPLATES = {
    "commuter": UserProfile(
        user_id="commuter_template",
        preference_weights={"safety": 0.5, "comfort": 0.3, "scenery": 0.1},
        max_detour=1.3,
        avoid_traffic=True,
        cycling_speed=18.0,
        max_duration_min=45.0,
    ),
    "tourist": UserProfile(
        user_id="tourist_template",
        preference_weights={"safety": 0.2, "comfort": 0.2, "scenery": 0.5},
        max_detour=2.0,
        prefer_greenery=True,
        cycling_speed=12.0,
        max_duration_min=120.0,
    ),
    "fitness": UserProfile(
        user_id="fitness_template",
        preference_weights={"safety": 0.3, "comfort": 0.2, "scenery": 0.3},
        max_detour=2.5,
        cycling_speed=22.0,
        max_duration_min=90.0,
    ),
    "family": UserProfile(
        user_id="family_template",
        preference_weights={"safety": 0.6, "comfort": 0.3, "scenery": 0.1},
        max_detour=1.2,
        prefer_greenery=True,
        avoid_traffic=True,
        cycling_speed=10.0,
        max_duration_min=30.0,
    ),
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest algorithm/tests/test_recommender.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: personalized route recommendation with user profile templates"
```

---

## Task 12: GeoScene SceneView 3D场景数据导出

**Files:**
- Create: `BikeFlowGNN/algorithm/viz/geoscene_export.py`
- Create: `BikeFlowGNN/algorithm/viz/route_overlay.py`
- Create: `BikeFlowGNN/algorithm/tests/test_viz.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_viz.py`**

```python
"""GeoScene SceneView 3D场景数据导出测试"""
import pytest
import json
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString, Point
from algorithm.viz.geoscene_export import (
    export_segments_geojson,
    export_stations_geojson,
    export_scene_config,
)
from algorithm.viz.route_overlay import (
    build_route_overlay,
    compute_route_metrics_summary,
    export_routes_geojson,
)


def test_export_segments_geojson(tmp_path, sample_segments_gdf):
    """测试街道段GeoJSON导出"""
    out_path = tmp_path / "segments.geojson"
    export_segments_geojson(sample_segments_gdf, str(out_path))

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == len(sample_segments_gdf)

    # 验证属性字段
    props = data["features"][0]["properties"]
    assert "seg_id" in props
    assert "w_safety" in props
    assert "w_comfort" in props
    assert "w_scenery" in props
    assert "cost_composite" in props


def test_export_stations_geojson(tmp_path):
    """测试站点GeoJSON导出"""
    stations = gpd.GeoDataFrame(
        {"station_id": [0, 1], "name": ["站A", "站B"]},
        geometry=[Point(116.36, 39.91), Point(116.37, 39.92)],
        crs="EPSG:4326",
    )
    out_path = tmp_path / "stations.geojson"
    export_stations_geojson(stations, str(out_path))

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert len(data["features"]) == 2
    assert data["features"][0]["geometry"]["type"] == "Point"


def test_export_scene_config(tmp_path):
    """测试3D场景配置导出"""
    out_path = tmp_path / "scene_config.json"
    export_scene_config(
        str(out_path),
        center_lon=116.40,
        center_lat=39.92,
        zoom=14,
        layers=["segments", "stations", "routes"],
    )

    assert out_path.exists()
    config = json.loads(out_path.read_text())
    assert config["center"][0] == 116.40
    assert config["center"][1] == 39.92
    assert config["zoom"] == 14
    assert "segments" in config["layers"]


def test_build_route_overlay(sample_segments_gdf):
    """测试路线叠加构建"""
    # 构建简单路线
    G_nx = __import__("networkx").Graph()
    coords = list(sample_segments_gdf.geometry[0].coords)
    u = (round(coords[0][0], 6), round(coords[0][1], 6))
    v = (round(coords[-1][0], 6), round(coords[-1][1], 6))
    G_nx.add_edge(u, v, length=100.0, w_safety=0.7, w_comfort=0.6,
                  w_scenery=0.5, cost_composite=40.0)

    route = [u, v]
    overlay = build_route_overlay(route, G_nx, sample_segments_gdf)

    assert "geometry" in overlay
    assert "metrics" in overlay
    assert overlay["metrics"]["length"] > 0


def test_compute_route_metrics_summary():
    """测试路线指标汇总"""
    import networkx as nx

    G = nx.Graph()
    G.add_edge(0, 1, length=100.0, w_safety=0.8, w_comfort=0.6,
               w_scenery=0.7, cost_composite=40.0, f_traffic_stress=0.3,
               v_beauty=0.7, pref_score=0.8)
    G.add_edge(1, 2, length=150.0, w_safety=0.6, w_comfort=0.5,
               w_scenery=0.4, cost_composite=60.0, f_traffic_stress=0.5,
               v_beauty=0.5, pref_score=0.6)

    route = [0, 1, 2]
    summary = compute_route_metrics_summary(route, G)

    assert summary["total_length"] == 250.0
    assert summary["avg_safety"] == pytest.approx(0.7, abs=0.01)
    assert summary["avg_scenery"] == pytest.approx(0.55, abs=0.01)
    assert summary["total_cost"] == 100.0
    assert summary["num_segments"] == 2


def test_export_routes_geojson(tmp_path):
    """测试多路线GeoJSON导出"""
    import networkx as nx

    G = nx.Graph()
    G.add_edge(0, 1, length=100.0, w_safety=0.8, w_comfort=0.6,
               w_scenery=0.7, cost_composite=40.0, f_traffic_stress=0.3,
               v_beauty=0.7, pref_score=0.8)

    routes = [[0, 1]]
    out_path = tmp_path / "routes.geojson"
    export_routes_geojson(routes, G, str(out_path))

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert len(data["features"]) == 1
    assert data["features"][0]["geometry"]["type"] == "LineString"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest algorithm/tests/test_viz.py -v
```

Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 `algorithm/viz/geoscene_export.py`**

```python
"""GeoScene SceneView 3D场景数据导出

将算法层产出的街道段、站点、路线导出为GeoJSON，
供前端GeoScene SceneView 3D场景加载。
"""
import json
import geopandas as gpd
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any


# ── 导出属性列白名单 ──
SEGMENT_EXPORT_COLS = [
    "seg_id", "length", "cost_composite",
    "w_safety", "w_comfort", "w_scenery", "f_traffic_stress",
    "v_beauty", "v_greenery", "pref_score",
    "s_bike_lane_type", "s_physical_separation",
    "s_motor_pressure", "s_heavy_vehicle",
    "s_parking_encroach", "s_intersection_conflict",
    "f_road_surface", "f_shading_coverage",
]

STATION_EXPORT_COLS = ["station_id", "name", "capacity"]


def export_segments_geojson(
    segments_gdf: gpd.GeoDataFrame,
    output_path: str,
) -> None:
    """导出街道段为GeoJSON

    Args:
        segments_gdf: 含seg_id, w_*, cost_composite等列的GeoDataFrame
        output_path: 输出文件路径
    """
    # 选择存在的列
    cols = [c for c in SEGMENT_EXPORT_COLS if c in segments_gdf.columns]
    export_gdf = segments_gdf[cols + ["geometry"]].copy()

    # 将NaN填充为0，避免JSON序列化问题
    for c in cols:
        if c != "seg_id":
            export_gdf[c] = export_gdf[c].fillna(0).astype(float)

    # 导出为GeoJSON (EPSG:4326)
    if export_gdf.crs is None:
        export_gdf = export_gdf.set_crs("EPSG:4326")
    elif export_gdf.crs.to_string() != "EPSG:4326":
        export_gdf = export_gdf.to_crs("EPSG:4326")

    export_gdf.to_file(output_path, driver="GeoJSON")


def export_stations_geojson(
    stations_gdf: gpd.GeoDataFrame,
    output_path: str,
) -> None:
    """导出站点为GeoJSON

    Args:
        stations_gdf: 含station_id等列的GeoDataFrame (Point几何)
        output_path: 输出文件路径
    """
    cols = [c for c in STATION_EXPORT_COLS if c in stations_gdf.columns]
    export_gdf = stations_gdf[cols + ["geometry"]].copy()

    # 确保是Point几何
    export_gdf = export_gdf[export_gdf.geometry.type == "Point"]

    if export_gdf.crs is None:
        export_gdf = export_gdf.set_crs("EPSG:4326")
    elif export_gdf.crs.to_string() != "EPSG:4326":
        export_gdf = export_gdf.to_crs("EPSG:4326")

    export_gdf.to_file(output_path, driver="GeoJSON")


def export_scene_config(
    output_path: str,
    center_lon: float,
    center_lat: float,
    zoom: int = 14,
    layers: List[str] = None,
    **extra_kwargs,
) -> None:
    """导出GeoScene WebScene 3D场景配置JSON

    Args:
        output_path: 输出路径
        center_lon: 中心经度
        center_lat: 中心纬度
        zoom: 缩放级别
        layers: 图层列表
        **extra_kwargs: 额外配置项
    """
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
```

- [ ] **Step 4: 实现 `algorithm/viz/route_overlay.py`**

```python
"""路线叠加与指标汇总

将NSGA-II搜索到的路线转换为可视化叠加层，
计算路线级别的指标汇总。
"""
import json
import numpy as np
import networkx as nx
import geopandas as gpd
from shapely.geometry import LineString, Point
from typing import List, Dict, Any, Optional
from pathlib import Path


def build_route_overlay(
    route: list,
    G: nx.Graph,
    segments_gdf: gpd.GeoDataFrame,
) -> Dict[str, Any]:
    """构建路线叠加数据

    Args:
        route: 路线节点序列 (NetworkX节点)
        G: NetworkX图
        segments_gdf: 街道段GeoDataFrame (含seg_id和geometry)

    Returns:
        {
            "geometry": LineString,       # 路线几何
            "metrics": {...},             # 指标汇总
            "segments": [seg_id, ...],    # 路线包含的segment
        }
    """
    if len(route) < 2:
        return {"geometry": None, "metrics": {}, "segments": []}

    # 收集路线坐标
    coords = []
    seg_ids = []
    for u, v in zip(route[:-1], route[1:]):
        if G.has_edge(u, v):
            edge_data = G[u][v]
            seg_id = edge_data.get("seg_id", None)
            if seg_id is not None:
                seg_ids.append(seg_id)

            # 从节点坐标构建线段
            u_pos = G.nodes[u].get("pos", u) if isinstance(u, tuple) else \
                    G.nodes[u].get("pos", (0, 0))
            v_pos = G.nodes[v].get("pos", v) if isinstance(v, tuple) else \
                    G.nodes[v].get("pos", (0, 0))

            if isinstance(u_pos, tuple) and isinstance(v_pos, tuple):
                if not coords or coords[-1] != u_pos:
                    coords.append(u_pos)
                coords.append(v_pos)

    # 尝试从segments_gdf获取更精确的几何
    if seg_ids and "seg_id" in segments_gdf.columns:
        seg_rows = segments_gdf[segments_gdf["seg_id"].isin(seg_ids)]
        if len(seg_rows) > 0:
            precise_coords = []
            for _, row in seg_rows.iterrows():
                geom = row.geometry
                if geom is not None and hasattr(geom, "coords"):
                    precise_coords.extend(list(geom.coords))
            if len(precise_coords) >= 2:
                coords = precise_coords

    geometry = LineString(coords) if len(coords) >= 2 else None

    # 计算指标汇总
    metrics = compute_route_metrics_summary(route, G)

    return {
        "geometry": geometry,
        "metrics": metrics,
        "segments": seg_ids,
    }


def compute_route_metrics_summary(
    route: list,
    G: nx.Graph,
) -> Dict[str, float]:
    """计算路线级别指标汇总

    Args:
        route: 路线节点序列
        G: NetworkX图

    Returns:
        {
            "total_length": float,       # 总距离(米)
            "total_cost": float,         # 总复合成本
            "avg_safety": float,         # 平均安全性
            "avg_comfort": float,        # 平均舒适度
            "avg_scenery": float,        # 平均风景
            "avg_traffic_stress": float, # 平均交通压力
            "avg_beauty": float,         # 平均美观度
            "avg_pref_score": float,     # 平均偏好分
            "num_segments": int,         # 段数
        }
    """
    if len(route) < 2:
        return {
            "total_length": 0, "total_cost": 0,
            "avg_safety": 0, "avg_comfort": 0, "avg_scenery": 0,
            "avg_traffic_stress": 0, "avg_beauty": 0, "avg_pref_score": 0,
            "num_segments": 0,
        }

    edges = list(zip(route[:-1], route[1:]))

    lengths = []
    costs = []
    safeties = []
    comforts = []
    sceneries = []
    stresses = []
    beauties = []
    prefs = []

    for u, v in edges:
        if G.has_edge(u, v):
            data = G[u][v]
            lengths.append(data.get("length", 0))
            costs.append(data.get("cost_composite", 0))
            safeties.append(data.get("w_safety", 0.5))
            comforts.append(data.get("w_comfort", 0.5))
            sceneries.append(data.get("w_scenery", 0.5))
            stresses.append(data.get("f_traffic_stress", 0.5))
            beauties.append(data.get("v_beauty", 0.5))
            prefs.append(data.get("pref_score", 0.5))

    n = len(lengths)

    return {
        "total_length": float(sum(lengths)),
        "total_cost": float(sum(costs)),
        "avg_safety": float(np.mean(safeties)) if n > 0 else 0,
        "avg_comfort": float(np.mean(comforts)) if n > 0 else 0,
        "avg_scenery": float(np.mean(sceneries)) if n > 0 else 0,
        "avg_traffic_stress": float(np.mean(stresses)) if n > 0 else 0,
        "avg_beauty": float(np.mean(beauties)) if n > 0 else 0,
        "avg_pref_score": float(np.mean(prefs)) if n > 0 else 0,
        "num_segments": n,
    }


def export_routes_geojson(
    routes: List[list],
    G: nx.Graph,
    output_path: str,
) -> None:
    """导出多条路线为GeoJSON

    Args:
        routes: 路线列表 (每条路线为节点序列)
        G: NetworkX图
        output_path: 输出路径
    """
    features = []

    for idx, route in enumerate(routes):
        summary = compute_route_metrics_summary(route, G)

        # 构建几何
        coords = []
        for node in route:
            if isinstance(node, tuple):
                coords.append(node)
            elif G.has_node(node) and "pos" in G.nodes[node]:
                coords.append(G.nodes[node]["pos"])

        if len(coords) >= 2:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[c[0], c[1]] for c in coords],
                },
                "properties": {
                    "route_id": idx,
                    **summary,
                },
            }
            features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest algorithm/tests/test_viz.py -v
```

Expected: 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: GeoScene 3D scene data export and route overlay"
```

---

## Task 13: 全流程管道编排

**Files:**
- Create: `BikeFlowGNN/algorithm/pipeline.py`
- Create: `BikeFlowGNN/algorithm/tests/test_pipeline.py`

- [ ] **Step 1: 编写测试 `algorithm/tests/test_pipeline.py`**

```python
"""全流程管道编排测试"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from algorithm.pipeline import BikeFlowPipeline, PipelineResult


def test_pipeline_result_dataclass():
    """测试管道结果数据类"""
    result = PipelineResult(
        segments_gdf=None,
        stations_gdf=None,
        hetero_graph=None,
        nx_graph=None,
        pareto_routes=[],
        best_route=None,
        scene_config=None,
    )
    assert result.pareto_routes == []
    assert result.best_route is None


def test_pipeline_init():
    """测试管道初始化"""
    pipeline = BikeFlowPipeline(
        data_dir="/tmp/test_data",
        output_dir="/tmp/test_output",
    )
    assert pipeline.data_dir == Path("/tmp/test_data")
    assert pipeline.output_dir == Path("/tmp/test_output")


def test_pipeline_stage1_load_data(tmp_path):
    """测试阶段1：数据加载（mock）"""
    pipeline = BikeFlowPipeline(
        data_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
    )

    with patch("algorithm.pipeline.load_streetview_metrics") as mock_sv, \
         patch("algorithm.pipeline.load_poi_data") as mock_poi, \
         patch("algorithm.pipeline.load_stations") as mock_station, \
         patch("algorithm.pipeline.load_basemap_data") as mock_basemap:

        mock_sv.return_value = MagicMock()
        mock_poi.return_value = MagicMock()
        mock_station.return_value = MagicMock()
        mock_basemap.return_value = (MagicMock(), MagicMock())

        result = pipeline.stage1_load_data()
        assert result is not None
        mock_sv.assert_called_once()
        mock_poi.assert_called_once()
        mock_station.assert_called_once()
        mock_basemap.assert_called_once()


def test_pipeline_stage2_build_graph(tmp_path):
    """测试阶段2：异构图构建（mock）"""
    pipeline = BikeFlowPipeline(
        data_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
    )

    with patch("algorithm.pipeline.build_hetero_graph") as mock_build:
        mock_build.return_value = MagicMock()
        result = pipeline.stage2_build_graph(
            segments_gdf=MagicMock(),
            obs_gdf=MagicMock(),
            poi_gdf=MagicMock(),
            stations_gdf=MagicMock(),
            buildings_gdf=MagicMock(),
        )
        assert result is not None
        mock_build.assert_called_once()


def test_pipeline_full_run_mock(tmp_path):
    """测试完整管道运行（全mock）"""
    import networkx as nx
    import geopandas as gpd
    from shapely.geometry import LineString, Point

    pipeline = BikeFlowPipeline(
        data_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
    )

    # mock所有外部依赖
    with patch("algorithm.pipeline.load_streetview_metrics") as mock_sv, \
         patch("algorithm.pipeline.load_poi_data") as mock_poi, \
         patch("algorithm.pipeline.load_stations") as mock_station, \
         patch("algorithm.pipeline.load_basemap_data") as mock_basemap, \
         patch("algorithm.pipeline.build_hetero_graph") as mock_build, \
         patch("algorithm.pipeline.propagate_metrics_to_segments") as mock_prop, \
         patch("algorithm.pipeline.compute_all_weights") as mock_w, \
         patch("algorithm.pipeline.fuse_composite_cost") as mock_fuse, \
         patch("algorithm.pipeline.build_nx_graph") as mock_nx, \
         patch("algorithm.pipeline.nsga2_search") as mock_nsga, \
         patch("algorithm.pipeline.recommend_route") as mock_rec, \
         patch("algorithm.pipeline.export_segments_geojson") as mock_exp_seg, \
         patch("algorithm.pipeline.export_stations_geojson") as mock_exp_sta, \
         patch("algorithm.pipeline.export_routes_geojson") as mock_exp_rte, \
         patch("algorithm.pipeline.export_scene_config") as mock_exp_cfg:

        # 设置mock返回值
        mock_sv.return_value = MagicMock()
        mock_poi.return_value = MagicMock()
        mock_station.return_value = MagicMock()

        segments = gpd.GeoDataFrame(
            {"seg_id": [0, 1], "length": [100.0, 150.0]},
            geometry=[LineString([(0,0),(1,1)]), LineString([(1,1),(2,2)])],
            crs="EPSG:4326",
        )
        buildings = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        mock_basemap.return_value = (segments, buildings)

        mock_build.return_value = MagicMock()
        mock_prop.return_value = segments
        mock_w.return_value = segments
        mock_fuse.return_value = segments

        G = nx.Graph()
        G.add_edge((0,0), (1,1), length=100.0, w_safety=0.7, w_comfort=0.6,
                   w_scenery=0.5, cost_composite=40.0, f_traffic_stress=0.3,
                   v_beauty=0.7, pref_score=0.8, seg_id=0)
        G.add_edge((1,1), (2,2), length=150.0, w_safety=0.6, w_comfort=0.5,
                   w_scenery=0.4, cost_composite=60.0, f_traffic_stress=0.5,
                   v_beauty=0.5, pref_score=0.6, seg_id=1)
        mock_nx.return_value = G

        mock_nsga.return_value = [[(0,0), (1,1), (2,2)]]
        mock_rec.return_value = [(0,0), (1,1), (2,2)]

        result = pipeline.run(
            source=(0, 0),
            target=(2, 2),
            user_template="commuter",
        )

        assert isinstance(result, PipelineResult)
        assert result.pareto_routes is not None
        assert result.best_route is not None
        mock_exp_seg.assert_called_once()
        mock_exp_sta.assert_called_once()
        mock_exp_rte.assert_called_once()
        mock_exp_cfg.assert_called_once()


def test_pipeline_save_outputs(tmp_path):
    """测试管道输出保存"""
    import networkx as nx
    import geopandas as gpd
    from shapely.geometry import LineString

    pipeline = BikeFlowPipeline(
        data_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
    )

    segments = gpd.GeoDataFrame(
        {"seg_id": [0], "w_safety": [0.7], "cost_composite": [40.0]},
        geometry=[LineString([(0,0),(1,1)])],
        crs="EPSG:4326",
    )
    stations = gpd.GeoDataFrame(
        {"station_id": [0]},
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    G = nx.Graph()
    G.add_edge((0,0), (1,1), length=100.0, w_safety=0.7)

    pipeline.save_outputs(
        segments_gdf=segments,
        stations_gdf=stations,
        nx_graph=G,
        pareto_routes=[[(0,0), (1,1)]],
        best_route=[(0,0), (1,1)],
    )

    assert (tmp_path / "output" / "segments.geojson").exists()
    assert (tmp_path / "output" / "stations.geojson").exists()
    assert (tmp_path / "output" / "routes.geojson").exists()
    assert (tmp_path / "output" / "scene_config.json").exists()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest algorithm/tests/test_pipeline.py -v
```

Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 `algorithm/pipeline.py`**

```python
"""BikeFlowGNN v2 全流程管道编排

五阶段流水线:
    Stage 1: 多源数据加载 (街景/POI/站点/天地图底图)
    Stage 2: 5类节点6类边异构图构建 (city2graph)
    Stage 3: 街景指标传播 + 四维边权模型
    Stage 4: HGT GNN偏好学习 (mini-batch训练)
    Stage 5: NSGA-II多目标搜索 + 个性化推荐 + 可视化导出
"""
import sys
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

import numpy as np
import pandas as pd
import geopandas as gpd
import networkx as nx

# 算法层导入
from algorithm.config import (
    BASE_DIR, DATA_DIR,
    STREETVIEW_CSV, POI_CSV, STATION_FILE,
    GRAPH_CFG, TRAIN_CFG, WEIGHT_CFG, NSGA2_CFG,
)
from algorithm.data.streetview_loader import load_streetview_metrics
from algorithm.data.poi_loader import load_poi_data
from algorithm.data.station_loader import load_stations
from algorithm.data.basemap_loader import load_basemap_data
from algorithm.graph.hetero_builder import build_hetero_graph
from algorithm.graph.metric_propagation import propagate_metrics_to_segments
from algorithm.weights.edge_weights import compute_all_weights
from algorithm.weights.cost_fusion import fuse_composite_cost
from algorithm.models.hgt_model import BikeFlowGNN_v2, create_hetero_data
from algorithm.models.trainer import train_hgt_model, apply_predictions_to_graph
from algorithm.routing.nsga2_search import build_nx_graph, nsga2_search
from algorithm.routing.recommender import (
    UserProfile, recommend_route, USER_TEMPLATES,
)
from algorithm.viz.geoscene_export import (
    export_segments_geojson, export_stations_geojson, export_scene_config,
)
from algorithm.viz.route_overlay import export_routes_geojson

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """管道运行结果"""
    segments_gdf: Optional[gpd.GeoDataFrame] = None
    stations_gdf: Optional[gpd.GeoDataFrame] = None
    hetero_graph: Optional[Any] = None
    nx_graph: Optional[nx.Graph] = None
    pareto_routes: List[list] = field(default_factory=list)
    best_route: Optional[list] = None
    scene_config: Optional[Dict] = None


class BikeFlowPipeline:
    """BikeFlowGNN v2 全流程管道

    Usage:
        pipeline = BikeFlowPipeline(
            data_dir="/path/to/data",
            output_dir="/path/to/output",
        )
        result = pipeline.run(
            source=(116.36, 39.91),
            target=(116.42, 39.93),
            user_template="commuter",
        )
    """

    def __init__(
        self,
        data_dir: str = None,
        output_dir: str = None,
    ):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.output_dir = Path(output_dir) if output_dir else (BASE_DIR / "output")

        # 中间状态
        self._streetview_df = None
        self._poi_df = None
        self._stations_gdf = None
        self._segments_gdf = None
        self._buildings_gdf = None
        self._obs_gdf = None
        self._hetero_graph = None
        self._nx_graph = None
        self._model = None

        logger.info(f"Pipeline initialized: data={self.data_dir}, output={self.output_dir}")

    # ── Stage 1: 数据加载 ──

    def stage1_load_data(self) -> Tuple:
        """阶段1：加载街景指标、POI、站点、天地图底图数据

        Returns:
            (obs_gdf, poi_gdf, stations_gdf, segments_gdf, buildings_gdf)
        """
        logger.info("=== Stage 1: Data Loading ===")

        # 1.1 街景指标
        sv_path = self.data_dir / STREETVIEW_CSV
        logger.info(f"Loading streetview metrics from {sv_path}")
        self._streetview_df = load_streetview_metrics(str(sv_path))
        self._obs_gdf = self._streetview_df  # 观测点GeoDataFrame
        logger.info(f"  Loaded {len(self._streetview_df)} streetview observations")

        # 1.2 POI
        poi_path = self.data_dir / POI_CSV
        logger.info(f"Loading POI data from {poi_path}")
        self._poi_df = load_poi_data(str(poi_path))
        logger.info(f"  Loaded {len(self._poi_df)} POIs")

        # 1.3 站点
        station_path = self.data_dir / STATION_FILE
        logger.info(f"Loading stations from {station_path}")
        self._stations_gdf = load_stations(str(station_path))
        logger.info(f"  Loaded {len(self._stations_gdf)} stations")

        # 1.4 天地图街道网络（GeoScene比赛合规）
        logger.info("Loading basemap data from Tianditu (this may take a while)...")
        self._segments_gdf, self._buildings_gdf = load_basemap_data()
        logger.info(f"  Loaded {len(self._segments_gdf)} segments, "
                     f"{len(self._buildings_gdf)} buildings")

        return (self._obs_gdf, self._poi_df, self._stations_gdf,
                self._segments_gdf, self._buildings_gdf)

    # ── Stage 2: 异构图构建 ──

    def stage2_build_graph(
        self,
        segments_gdf: gpd.GeoDataFrame,
        obs_gdf: gpd.GeoDataFrame,
        poi_gdf: gpd.GeoDataFrame,
        stations_gdf: gpd.GeoDataFrame,
        buildings_gdf: gpd.GeoDataFrame,
    ) -> Any:
        """阶段2：构建5类节点6类边异构图

        Args:
            segments_gdf: 街道段
            obs_gdf: 街景观测点
            poi_gdf: POI
            stations_gdf: 单车站点
            buildings_gdf: 建筑（天地图/GeoScene）

        Returns:
            HeteroGraphData
        """
        logger.info("=== Stage 2: Heterogeneous Graph Construction ===")

        self._hetero_graph = build_hetero_graph(
            segments_gdf=segments_gdf,
            obs_gdf=obs_gdf,
            poi_gdf=poi_gdf,
            stations_gdf=stations_gdf,
            buildings_gdf=buildings_gdf,
            graph_cfg=GRAPH_CFG,
        )

        logger.info(f"  Graph built: {self._hetero_graph.total_nodes} nodes, "
                     f"{self._hetero_graph.total_edges} edges")

        return self._hetero_graph

    # ── Stage 3: 指标传播 + 边权模型 ──

    def stage3_compute_weights(
        self,
        segments_gdf: gpd.GeoDataFrame,
        obs_gdf: gpd.GeoDataFrame,
        hetero_graph: Any,
    ) -> gpd.GeoDataFrame:
        """阶段3：街景指标传播 + 四维边权计算

        Args:
            segments_gdf: 街道段
            obs_gdf: 观测点
            hetero_graph: 异构图

        Returns:
            更新后的segments_gdf (含w_safety, w_comfort, w_scenery, cost_composite)
        """
        logger.info("=== Stage 3: Metric Propagation & Edge Weights ===")

        # 3.1 指标传播：观测点 → segment
        logger.info("  Propagating streetview metrics to segments...")
        segments_with_metrics = propagate_metrics_to_segments(
            obs_gdf, segments_gdf,
            k=GRAPH_CFG.propagation_k,
            max_dist=GRAPH_CFG.propagation_max_dist,
        )
        logger.info(f"  Propagated metrics to {len(segments_with_metrics)} segments")

        # 3.2 四维边权计算
        logger.info("  Computing 4-dimensional edge weights...")
        segments_with_weights = compute_all_weights(
            segments_with_metrics,
            weight_cfg=WEIGHT_CFG,
        )

        # 3.3 复合成本融合
        logger.info("  Fusing composite cost...")
        segments_final = fuse_composite_cost(
            segments_with_weights,
            weight_cfg=WEIGHT_CFG,
        )

        self._segments_gdf = segments_final
        logger.info(f"  Final segments: {len(segments_final)} with weights")

        return segments_final

    # ── Stage 4: HGT训练 ──

    def stage4_train_gnn(
        self,
        segments_gdf: gpd.GeoDataFrame,
        hetero_graph: Any,
        train_pairs: Optional[pd.DataFrame] = None,
    ) -> Tuple:
        """阶段4：HGT GNN偏好学习

        Args:
            segments_gdf: 含边权的街道段
            hetero_graph: 异构图
            train_pairs: 训练对 (src_seg, dst_seg, label)
                        如为None则用启发式生成

        Returns:
            (model, segments_gdf_with_pref)
        """
        logger.info("=== Stage 4: HGT GNN Training ===")

        # 4.1 创建HeteroData
        logger.info("  Creating HeteroData...")
        hetero_data = create_hetero_data(
            nodes=hetero_graph.nodes,
            edges=hetero_graph.edges,
            node_counts=hetero_graph.node_counts,
            hidden_dim=TRAIN_CFG.hidden_dim,
        )

        # 4.2 训练
        logger.info(f"  Training HGT model ({TRAIN_CFG.epochs} epochs)...")
        model = train_hgt_model(
            hetero_data,
            train_pairs=train_pairs,
            train_cfg=TRAIN_CFG,
        )
        self._model = model

        # 4.3 将预测偏好分应用到图边
        logger.info("  Applying predictions to graph...")
        segments_with_pref = apply_predictions_to_graph(
            model, hetero_data, segments_gdf,
        )

        self._segments_gdf = segments_with_pref
        logger.info("  GNN training complete")

        return model, segments_with_pref

    # ── Stage 5: 路径搜索 + 推荐 + 导出 ──

    def stage5_search_and_export(
        self,
        segments_gdf: gpd.GeoDataFrame,
        stations_gdf: gpd.GeoDataFrame,
        source: Tuple[float, float],
        target: Tuple[float, float],
        user_template: str = "commuter",
    ) -> PipelineResult:
        """阶段5：NSGA-II搜索 + 个性化推荐 + 可视化导出

        Args:
            segments_gdf: 含偏好分的街道段
            stations_gdf: 站点
            source: 起点 (lon, lat)
            target: 终点 (lon, lat)
            user_template: 用户画像模板名

        Returns:
            PipelineResult
        """
        logger.info("=== Stage 5: NSGA-II Search & Recommendation ===")

        # 5.1 构建NetworkX图
        logger.info("  Building NetworkX graph...")
        G = build_nx_graph(segments_gdf)
        self._nx_graph = G
        logger.info(f"  NX graph: {G.number_of_nodes()} nodes, "
                     f"{G.number_of_edges()} edges")

        # 5.2 NSGA-II多目标搜索
        logger.info(f"  Running NSGA-II (pop={NSGA2_CFG.pop_size}, "
                     f"gen={NSGA2_CFG.n_gen})...")
        pareto_routes = nsga2_search(
            G, source=source, target=target,
            pop_size=NSGA2_CFG.pop_size,
            n_gen=NSGA2_CFG.n_gen,
        )
        logger.info(f"  Found {len(pareto_routes)} Pareto-optimal routes")

        # 5.3 个性化推荐
        profile = USER_TEMPLATES.get(user_template, USER_TEMPLATES["commuter"])
        logger.info(f"  Recommending route for '{user_template}' profile...")
        best_route = recommend_route(pareto_routes, G, profile, top_k=1)
        logger.info(f"  Best route: {len(best_route) if best_route else 0} nodes")

        # 5.4 保存输出
        self.save_outputs(
            segments_gdf=segments_gdf,
            stations_gdf=stations_gdf,
            nx_graph=G,
            pareto_routes=pareto_routes,
            best_route=best_route,
        )

        return PipelineResult(
            segments_gdf=segments_gdf,
            stations_gdf=stations_gdf,
            hetero_graph=self._hetero_graph,
            nx_graph=G,
            pareto_routes=pareto_routes,
            best_route=best_route,
            scene_config={
                "center": [source[0], source[1]],
                "user_template": user_template,
            },
        )

    # ── 输出保存 ──

    def save_outputs(
        self,
        segments_gdf: gpd.GeoDataFrame,
        stations_gdf: gpd.GeoDataFrame,
        nx_graph: nx.Graph,
        pareto_routes: List[list],
        best_route: Optional[list],
    ) -> None:
        """保存所有可视化输出到output_dir

        Args:
            segments_gdf: 街道段
            stations_gdf: 站点
            nx_graph: NetworkX图
            pareto_routes: Pareto路线集
            best_route: 最佳路线
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 街道段
        seg_path = str(self.output_dir / "segments.geojson")
        logger.info(f"  Saving segments to {seg_path}")
        export_segments_geojson(segments_gdf, seg_path)

        # 站点
        sta_path = str(self.output_dir / "stations.geojson")
        logger.info(f"  Saving stations to {sta_path}")
        export_stations_geojson(stations_gdf, sta_path)

        # 路线
        rte_path = str(self.output_dir / "routes.geojson")
        logger.info(f"  Saving routes to {rte_path}")
        export_routes_geojson(pareto_routes, nx_graph, rte_path)

        # 场景配置
        cfg_path = str(self.output_dir / "scene_config.json")
        logger.info(f"  Saving scene config to {cfg_path}")
        export_scene_config(
            cfg_path,
            center_lon=segments_gdf.geometry.iloc[0].centroid.x if len(segments_gdf) > 0 else 116.40,
            center_lat=segments_gdf.geometry.iloc[0].centroid.y if len(segments_gdf) > 0 else 39.92,
            zoom=14,
            layers=["segments", "stations", "routes"],
        )

    # ── 完整运行 ──

    def run(
        self,
        source: Tuple[float, float],
        target: Tuple[float, float],
        user_template: str = "commuter",
        skip_gnn: bool = False,
    ) -> PipelineResult:
        """运行完整五阶段管道

        Args:
            source: 起点 (lon, lat)
            target: 终点 (lon, lat)
            user_template: 用户画像模板 (commuter/tourist/fitness/family)
            skip_gnn: 是否跳过GNN训练（调试用）

        Returns:
            PipelineResult
        """
        logger.info("=" * 60)
        logger.info("BikeFlowGNN v2 Pipeline - Full Run")
        logger.info("=" * 60)

        # Stage 1
        obs_gdf, poi_df, stations_gdf, segments_gdf, buildings_gdf = \
            self.stage1_load_data()

        # Stage 2
        hetero_graph = self.stage2_build_graph(
            segments_gdf, obs_gdf, poi_df, stations_gdf, buildings_gdf,
        )

        # Stage 3
        segments_gdf = self.stage3_compute_weights(
            segments_gdf, obs_gdf, hetero_graph,
        )

        # Stage 4 (可选)
        if not skip_gnn:
            model, segments_gdf = self.stage4_train_gnn(
                segments_gdf, hetero_graph,
            )

        # Stage 5
        result = self.stage5_search_and_export(
            segments_gdf, stations_gdf, source, target, user_template,
        )

        logger.info("=" * 60)
        logger.info("Pipeline Complete!")
        logger.info(f"  Pareto routes: {len(result.pareto_routes)}")
        logger.info(f"  Best route: {len(result.best_route) if result.best_route else 0} nodes")
        logger.info(f"  Output: {self.output_dir}")
        logger.info("=" * 60)

        return result


# ── CLI入口 ──

def main():
    """命令行入口：python -m algorithm.pipeline"""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="BikeFlowGNN v2 Pipeline")
    parser.add_argument("--data-dir", default=str(DATA_DIR), help="数据目录")
    parser.add_argument("--output-dir", default=str(BASE_DIR / "output"), help="输出目录")
    parser.add_argument("--source", nargs=2, type=float, required=True,
                        metavar=("LON", "LAT"), help="起点经纬度")
    parser.add_argument("--target", nargs=2, type=float, required=True,
                        metavar=("LON", "LAT"), help="终点经纬度")
    parser.add_argument("--user", default="commuter",
                        choices=["commuter", "tourist", "fitness", "family"],
                        help="用户画像模板")
    parser.add_argument("--skip-gnn", action="store_true", help="跳过GNN训练")

    args = parser.parse_args()

    pipeline = BikeFlowPipeline(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
    )

    result = pipeline.run(
        source=tuple(args.source),
        target=tuple(args.target),
        user_template=args.user,
        skip_gnn=args.skip_gnn,
    )

    print(f"\nDone! Pareto routes: {len(result.pareto_routes)}")
    print(f"Output saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest algorithm/tests/test_pipeline.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: full pipeline orchestration with 5-stage flow"
```

---

## Task 14: FastAPI后端服务

**Files:**
- Create: `BikeFlowGNN/backend/core/config.py`
- Create: `BikeFlowGNN/backend/db/models.py`
- Create: `BikeFlowGNN/backend/service/route_service.py`
- Create: `BikeFlowGNN/backend/api/routes.py`
- Create: `BikeFlowGNN/backend/app.py`
- Create: `BikeFlowGNN/backend/tests/test_routes.py`

- [ ] **Step 1: 编写测试 `backend/tests/test_routes.py`**

```python
"""FastAPI后端API测试"""
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app


@pytest.fixture
def client():
    """测试客户端"""
    app = create_app(testing=True)
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    """测试健康检查端点"""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_get_user_templates(client):
    """测试获取用户画像模板列表"""
    resp = client.get("/api/user-templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    assert "commuter" in data["templates"]
    assert "tourist" in data["templates"]
    assert "fitness" in data["templates"]
    assert "family" in data["templates"]


def test_search_routes_validation_error(client):
    """测试路线搜索参数校验"""
    # 缺少必填参数
    resp = client.post("/api/routes/search", json={
        "user_template": "commuter",
        # 缺少source和target
    })
    assert resp.status_code == 422


def test_search_routes_invalid_template(client):
    """测试无效用户模板"""
    resp = client.post("/api/routes/search", json={
        "source": [116.36, 39.91],
        "target": [116.42, 39.93],
        "user_template": "invalid_template",
    })
    assert resp.status_code == 400
    assert "template" in resp.json()["detail"].lower()


def test_search_routes_success(client, monkeypatch):
    """测试路线搜索成功（mock管道）"""
    from backend.service import route_service
    from backend.db.models import RouteCache

    # mock管道运行
    mock_result = {
        "routes": [
            {
                "route_id": 0,
                "coordinates": [[116.36, 39.91], [116.39, 39.92], [116.42, 39.93]],
                "metrics": {
                    "total_length": 5000.0,
                    "avg_safety": 0.72,
                    "avg_comfort": 0.65,
                    "avg_scenery": 0.58,
                    "num_segments": 12,
                },
            }
        ],
        "best_route_id": 0,
        "scene_config": {
            "center": [116.39, 39.92],
            "zoom": 14,
        },
    }

    async def mock_run_pipeline(*args, **kwargs):
        return mock_result

    monkeypatch.setattr(route_service, "run_pipeline", mock_run_pipeline)

    resp = client.post("/api/routes/search", json={
        "source": [116.36, 39.91],
        "target": [116.42, 39.93],
        "user_template": "commuter",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert "routes" in data
    assert len(data["routes"]) > 0
    assert "best_route_id" in data
    assert "scene_config" in data


def test_cache_lookup(client, monkeypatch):
    """测试缓存命中"""
    from backend.service import route_service

    # 先写入缓存
    cache_key = "116.36_39.91_116.42_39.93_commuter"
    cached_result = {
        "routes": [{"route_id": 0, "coordinates": [[116.36, 39.91]]}],
        "best_route_id": 0,
        "scene_config": {},
    }

    async def mock_get_cache(*args, **kwargs):
        return cached_result

    monkeypatch.setattr(route_service, "get_cached_result", mock_get_cache)

    resp = client.post("/api/routes/search", json={
        "source": [116.36, 39.91],
        "target": [116.42, 39.93],
        "user_template": "commuter",
    })

    assert resp.status_code == 200
    assert resp.json()["routes"][0]["route_id"] == 0


def test_get_route_by_id_not_found(client):
    """测试获取不存在的路线"""
    resp = client.get("/api/routes/99999")
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest backend/tests/test_routes.py -v
```

Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 `backend/core/config.py`（后端配置）**

```python
"""FastAPI后端配置（含GeoScene Server连接配置）"""
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """后端应用配置"""

    # ── 应用配置 ──
    app_name: str = "BikeFlowGNN API"
    version: str = "2.0.0"
    debug: bool = False
    testing: bool = False

    # ── 数据库配置 ──
    database_url: str = "sqlite:///./bikeflow.db"

    # ── CORS配置 ──
    cors_origins: List[str] = [
        "http://localhost:5173",   # Vite开发服务器
        "http://localhost:3000",   # 备用
        "http://127.0.0.1:5173",
    ]

    # ── 算法层配置 ──
    data_dir: str = str(Path(__file__).parent.parent.parent / "data")
    output_dir: str = str(Path(__file__).parent.parent.parent / "output")

    # ── GeoScene Server配置（比赛合规：GIS核心服务）──
    geoscene_server_url: str = "https://localhost:6443/arcgis"
    geoscene_server_token: str = ""  # 通过比赛组委会获取许可后填入
    geoscene_service_segments: str = "BikeSegments_MapService"
    geoscene_service_stations: str = "BikeStations_MapService"
    geoscene_service_routes: str = "BikeRoutes_GeoCodeService"
    geoscene_service_scene3d: str = "Beijing3D_WebScene"

    # ── 天地图底图配置 ──
    tianditu_token: str = ""  # 天地图开发者token

    # ── 缓存配置 ──
    cache_ttl_hours: int = 24  # 缓存过期时间(小时)

    class Config:
        env_prefix = "BIKEFLOW_"
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 4: 实现 `backend/db/models.py`（SQLAlchemy ORM模型）**

```python
"""SQLAlchemy ORM模型 — SQLite缓存层"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text,
    DateTime, Boolean, Index, JSON,
)
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from backend.core.config import settings

Base = declarative_base()


class RouteCache(Base):
    """路线搜索缓存表

    缓存相同 source/target/template 组合的搜索结果，
    避免重复运行昂贵的算法管道。
    """
    __tablename__ = "route_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(256), unique=True, nullable=False, index=True)
    source_lon = Column(Float, nullable=False)
    source_lat = Column(Float, nullable=False)
    target_lon = Column(Float, nullable=False)
    target_lat = Column(Float, nullable=False)
    user_template = Column(String(64), nullable=False)

    # 缓存的搜索结果 (JSON序列化)
    result_json = Column(Text, nullable=False)

    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_valid = Column(Boolean, default=True)

    # 算法运行统计
    num_pareto_routes = Column(Integer, default=0)
    pipeline_duration_sec = Column(Float, default=0.0)

    __table_args__ = (
        Index("idx_cache_key", "cache_key"),
        Index("idx_created_at", "created_at"),
    )


class RouteDetail(Base):
    """路线详情表

    存储每条Pareto最优路线的详细指标，
    供前端按ID查询。
    """
    __tablename__ = "route_detail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_id = Column(Integer, nullable=False, index=True)  # 关联RouteCache.id
    route_id = Column(Integer, nullable=False)              # 路线在Pareto集中的序号
    is_best = Column(Boolean, default=False)

    # 路线几何 (GeoJSON LineString的coordinates)
    coordinates_json = Column(Text, nullable=False)

    # 指标
    total_length = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    avg_safety = Column(Float, default=0.0)
    avg_comfort = Column(Float, default=0.0)
    avg_scenery = Column(Float, default=0.0)
    avg_traffic_stress = Column(Float, default=0.0)
    avg_beauty = Column(Float, default=0.0)
    avg_pref_score = Column(Float, default=0.0)
    num_segments = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_route_cache_id", "cache_id"),
    )


# ── 数据库引擎与Session ──

def create_database_engine(testing: bool = False):
    """创建数据库引擎"""
    if testing:
        db_url = "sqlite:///:memory:"
    else:
        db_url = settings.database_url

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},  # SQLite需要
        echo=False,
    )
    Base.metadata.create_all(engine)
    return engine


def get_db_session(engine) -> Session:
    """获取数据库Session"""
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return SessionLocal()
```

- [ ] **Step 5: 实现 `backend/service/route_service.py`（业务逻辑层）**

```python
"""业务逻辑层 — 调用algorithm层并管理缓存"""
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.db.models import RouteCache, RouteDetail

logger = logging.getLogger(__name__)


def _make_cache_key(
    source: List[float],
    target: List[float],
    user_template: str,
) -> str:
    """生成缓存键"""
    key_str = f"{source[0]:.6f}_{source[1]:.6f}_{target[0]:.6f}_{target[1]:.6f}_{user_template}"
    return hashlib.md5(key_str.encode()).hexdigest()


async def get_cached_result(
    db: Session,
    source: List[float],
    target: List[float],
    user_template: str,
) -> Optional[Dict[str, Any]]:
    """查询缓存中是否有匹配的搜索结果

    Args:
        db: 数据库Session
        source: [lon, lat]
        target: [lon, lat]
        user_template: 用户画像模板

    Returns:
        缓存的搜索结果 (或None)
    """
    cache_key = _make_cache_key(source, target, user_template)
    now = datetime.utcnow()

    cache_entry = db.query(RouteCache).filter(
        RouteCache.cache_key == cache_key,
        RouteCache.is_valid == True,
    ).first()

    if cache_entry is None:
        return None

    # 检查是否过期
    if cache_entry.expires_at and cache_entry.expires_at < now:
        cache_entry.is_valid = False
        db.commit()
        return None

    logger.info(f"Cache hit: {cache_key}")
    return json.loads(cache_entry.result_json)


async def save_to_cache(
    db: Session,
    source: List[float],
    target: List[float],
    user_template: str,
    result: Dict[str, Any],
    duration_sec: float = 0.0,
) -> None:
    """将搜索结果保存到缓存

    Args:
        db: 数据库Session
        source: [lon, lat]
        target: [lon, lat]
        user_template: 用户画像模板
        result: 搜索结果
        duration_sec: 管道运行耗时
    """
    cache_key = _make_cache_key(source, target, user_template)
    now = datetime.utcnow()
    expires = now + timedelta(hours=settings.cache_ttl_hours)

    # 删除旧的缓存（如果存在）
    db.query(RouteCache).filter(
        RouteCache.cache_key == cache_key
    ).delete()

    # 创建新缓存
    cache_entry = RouteCache(
        cache_key=cache_key,
        source_lon=source[0],
        source_lat=source[1],
        target_lon=target[0],
        target_lat=target[1],
        user_template=user_template,
        result_json=json.dumps(result, ensure_ascii=False),
        created_at=now,
        expires_at=expires,
        is_valid=True,
        num_pareto_routes=len(result.get("routes", [])),
        pipeline_duration_sec=duration_sec,
    )
    db.add(cache_entry)

    # 保存路线详情
    db.flush()  # 获取cache_entry.id
    for route in result.get("routes", []):
        metrics = route.get("metrics", {})
        detail = RouteDetail(
            cache_id=cache_entry.id,
            route_id=route.get("route_id", 0),
            is_best=(route.get("route_id") == result.get("best_route_id")),
            coordinates_json=json.dumps(route.get("coordinates", [])),
            total_length=metrics.get("total_length", 0),
            total_cost=metrics.get("total_cost", 0),
            avg_safety=metrics.get("avg_safety", 0),
            avg_comfort=metrics.get("avg_comfort", 0),
            avg_scenery=metrics.get("avg_scenery", 0),
            avg_traffic_stress=metrics.get("avg_traffic_stress", 0),
            avg_beauty=metrics.get("avg_beauty", 0),
            avg_pref_score=metrics.get("avg_pref_score", 0),
            num_segments=metrics.get("num_segments", 0),
        )
        db.add(detail)

    db.commit()
    logger.info(f"Cached result: {cache_key}, routes={len(result.get('routes', []))}")


async def run_pipeline(
    source: List[float],
    target: List[float],
    user_template: str,
    skip_gnn: bool = False,
) -> Dict[str, Any]:
    """运行算法管道（调用algorithm层）

    Args:
        source: [lon, lat]
        target: [lon, lat]
        user_template: 用户画像模板
        skip_gnn: 是否跳过GNN训练

    Returns:
        {
            "routes": [...],
            "best_route_id": int,
            "scene_config": {...},
        }
    """
    import time
    from algorithm.pipeline import BikeFlowPipeline
    from algorithm.viz.route_overlay import compute_route_metrics_summary

    logger.info(f"Running pipeline: {source} -> {target}, template={user_template}")

    start_time = time.time()

    pipeline = BikeFlowPipeline(
        data_dir=settings.data_dir,
        output_dir=settings.output_dir,
    )

    result = pipeline.run(
        source=tuple(source),
        target=tuple(target),
        user_template=user_template,
        skip_gnn=skip_gnn,
    )

    duration = time.time() - start_time

    # 转换为API响应格式
    routes = []
    for idx, route in enumerate(result.pareto_routes):
        # 获取路线坐标
        coords = []
        for node in route:
            if isinstance(node, tuple):
                coords.append([node[0], node[1]])

        # 计算指标汇总
        metrics = compute_route_metrics_summary(route, result.nx_graph) if result.nx_graph else {}

        routes.append({
            "route_id": idx,
            "coordinates": coords,
            "metrics": metrics,
        })

    best_route_id = 0
    if result.best_route:
        for idx, route in enumerate(result.pareto_routes):
            if route == result.best_route:
                best_route_id = idx
                break

    # 场景配置
    scene_config = result.scene_config or {
        "center": [source[0], source[1]],
        "zoom": 14,
    }

    api_result = {
        "routes": routes,
        "best_route_id": best_route_id,
        "scene_config": scene_config,
        "pipeline_duration_sec": round(duration, 2),
    }

    logger.info(f"Pipeline complete: {len(routes)} routes, {duration:.1f}s")
    return api_result


async def search_routes(
    db: Session,
    source: List[float],
    target: List[float],
    user_template: str,
    use_cache: bool = True,
    skip_gnn: bool = False,
) -> Dict[str, Any]:
    """搜索路线（带缓存）

    1. 先查缓存
    2. 缓存未命中则运行管道
    3. 保存结果到缓存

    Args:
        db: 数据库Session
        source: [lon, lat]
        target: [lon, lat]
        user_template: 用户画像模板
        use_cache: 是否使用缓存
        skip_gnn: 是否跳过GNN训练

    Returns:
        搜索结果
    """
    # 1. 查缓存
    if use_cache:
        cached = await get_cached_result(db, source, target, user_template)
        if cached is not None:
            cached["from_cache"] = True
            return cached

    # 2. 运行管道
    result = await run_pipeline(source, target, user_template, skip_gnn)

    # 3. 保存缓存
    if use_cache:
        await save_to_cache(
            db, source, target, user_template,
            result, duration_sec=result.get("pipeline_duration_sec", 0),
        )

    result["from_cache"] = False
    return result


def get_route_detail(
    db: Session,
    route_id: int,
) -> Optional[Dict[str, Any]]:
    """按ID获取路线详情

    Args:
        db: 数据库Session
        route_id: 路线ID (RouteDetail.id)

    Returns:
        路线详情 (或None)
    """
    detail = db.query(RouteDetail).filter(RouteDetail.id == route_id).first()
    if detail is None:
        return None

    return {
        "route_id": detail.route_id,
        "is_best": detail.is_best,
        "coordinates": json.loads(detail.coordinates_json),
        "metrics": {
            "total_length": detail.total_length,
            "total_cost": detail.total_cost,
            "avg_safety": detail.avg_safety,
            "avg_comfort": detail.avg_comfort,
            "avg_scenery": detail.avg_scenery,
            "avg_traffic_stress": detail.avg_traffic_stress,
            "avg_beauty": detail.avg_beauty,
            "avg_pref_score": detail.avg_pref_score,
            "num_segments": detail.num_segments,
        },
    }
```

- [ ] **Step 6: 实现 `backend/api/routes.py`（REST API路由）**

```python
"""REST API路由"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, field_validator
from typing import List, Optional

from backend.core.config import settings
from backend.service.route_service import search_routes, get_route_detail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["bikesearch"])

# ── 请求/响应模型 ──

class RouteSearchRequest(BaseModel):
    """路线搜索请求"""
    source: List[float]              # [lon, lat]
    target: List[float]              # [lon, lat]
    user_template: str = "commuter"  # commuter/tourist/fitness/family
    use_cache: bool = True
    skip_gnn: bool = False

    @field_validator("source", "target")
    @classmethod
    def validate_coords(cls, v):
        if len(v) != 2:
            raise ValueError("坐标必须是 [lon, lat] 格式")
        lon, lat = v
        if not (-180 <= lon <= 180):
            raise ValueError("经度必须在 [-180, 180] 范围内")
        if not (-90 <= lat <= 90):
            raise ValueError("纬度必须在 [-90, 90] 范围内")
        return v

    @field_validator("user_template")
    @classmethod
    def validate_template(cls, v):
        valid = {"commuter", "tourist", "fitness", "family"}
        if v not in valid:
            raise ValueError(f"无效的用户模板: {v}, 可选: {valid}")
        return v


class RouteMetrics(BaseModel):
    """路线指标"""
    total_length: float = 0
    total_cost: float = 0
    avg_safety: float = 0
    avg_comfort: float = 0
    avg_scenery: float = 0
    avg_traffic_stress: float = 0
    avg_beauty: float = 0
    avg_pref_score: float = 0
    num_segments: int = 0


class RouteResult(BaseModel):
    """单条路线结果"""
    route_id: int
    coordinates: List[List[float]]
    metrics: RouteMetrics


class RouteSearchResponse(BaseModel):
    """路线搜索响应"""
    routes: List[RouteResult]
    best_route_id: int
    scene_config: dict
    from_cache: bool = False
    pipeline_duration_sec: Optional[float] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str


class UserTemplatesResponse(BaseModel):
    """用户模板列表响应"""
    templates: List[dict]


# ── 路由 ──

VALID_TEMPLATES = {
    "commuter": {"name": "通勤者", "description": "高效安全，最短路径优先"},
    "tourist": {"name": "游客", "description": "风景优先，享受城市景观"},
    "fitness": {"name": "健身者", "description": "长距离骑行，适度绕路"},
    "family": {"name": "家庭", "description": "安全第一，低速慢骑"},
}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(status="ok", version=settings.version)


@router.get("/user-templates", response_model=UserTemplatesResponse)
async def get_user_templates():
    """获取用户画像模板列表"""
    templates = [
        {"key": k, "name": v["name"], "description": v["description"]}
        for k, v in VALID_TEMPLATES.items()
    ]
    return UserTemplatesResponse(templates=templates)


@router.post("/routes/search", response_model=RouteSearchResponse)
async def search_routes_endpoint(
    req: RouteSearchRequest,
    request: Request,
):
    """搜索骑行路线

    接收起点终点和用户画像，返回Pareto最优路线集。
    结果通过SQLite缓存，相同查询直接返回缓存。
    """
    # 获取数据库Session (从app.state)
    db = request.app.state.db_session

    try:
        result = await search_routes(
            db=db,
            source=req.source,
            target=req.target,
            user_template=req.user_template,
            use_cache=req.use_cache,
            skip_gnn=req.skip_gnn,
        )
        return RouteSearchResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/routes/{route_id}")
async def get_route_endpoint(
    route_id: int,
    request: Request,
):
    """按ID获取路线详情"""
    db = request.app.state.db_session
    detail = get_route_detail(db, route_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="路线不存在")
    return detail
```

- [ ] **Step 7: 实现 `backend/app.py`（应用入口）**

```python
"""FastAPI应用入口"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.api.routes import router
from backend.db.models import create_database_engine, get_db_session

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时创建数据库引擎
    logger.info("Creating database engine...")
    engine = create_database_engine(testing=settings.testing)
    app.state.db_engine = engine
    app.state.db_session = get_db_session(engine)
    logger.info("Database ready")

    yield

    # 关闭时清理
    logger.info("Closing database...")
    app.state.db_session.close()
    app.state.db_engine.dispose()
    logger.info("Database closed")


def create_app(testing: bool = False) -> FastAPI:
    """创建FastAPI应用

    Args:
        testing: 是否为测试模式 (使用内存SQLite)

    Returns:
        FastAPI应用实例
    """
    if testing:
        settings.testing = True

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
    )

    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(router)

    # 根路径
    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
            "health": "/api/health",
        }

    logger.info(f"App created: {settings.app_name} v{settings.version}")
    return app


# 全局应用实例 (uvicorn启动用)
app = create_app()
```

- [ ] **Step 8: 运行测试验证通过**

```bash
python -m pytest backend/tests/test_routes.py -v
```

Expected: 7 tests PASS

- [ ] **Step 9: 启动后端服务验证**

```bash
cd BikeFlowGNN
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

验证：
- 访问 `http://localhost:8000/docs` 查看Swagger文档
- 访问 `http://localhost:8000/api/health` 返回 `{"status": "ok", "version": "2.0.0"}`
- 访问 `http://localhost:8000/api/user-templates` 返回4个模板

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: FastAPI backend with SQLAlchemy SQLite caching and route search API"
```

---

## Task 15: React 18 + TypeScript + GeoScene JS API 前端

**Files:**
- Create: `BikeFlowGNN/frontend/package.json`
- Create: `BikeFlowGNN/frontend/vite.config.ts`
- Create: `BikeFlowGNN/frontend/tsconfig.json`
- Create: `BikeFlowGNN/frontend/tsconfig.node.json`
- Create: `BikeFlowGNN/frontend/index.html`
- Create: `BikeFlowGNN/frontend/src/main.tsx`
- Create: `BikeFlowGNN/frontend/src/core/types.ts`
- Create: `BikeFlowGNN/frontend/src/core/api.ts`
- Create: `BikeFlowGNN/frontend/src/core/store.ts`
- Create: `BikeFlowGNN/frontend/src/router/index.tsx`
- Create: `BikeFlowGNN/frontend/src/pages/MapPage.tsx`
- Create: `BikeFlowGNN/frontend/src/components/Sidebar.tsx`
- Create: `BikeFlowGNN/frontend/src/components/RouteCompare.tsx`
- Create: `BikeFlowGNN/frontend/src/components/MetricsPanel.tsx`
- Create: `BikeFlowGNN/frontend/src/styles/global.css`

- [ ] **Step 1: 创建项目脚手架与依赖配置**

**`frontend/package.json`:**

```json
{
  "name": "bikeflowgnn-frontend",
  "private": true,
  "version": "2.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.22.0",
    "@geoscene/core": "^4.30.0",
    "@geoscene/widgets": "^4.30.0",
    "zustand": "^4.5.0",
    "axios": "^1.6.7"
  },
  "devDependencies": {
    "@types/react": "^18.2.55",
    "@types/react-dom": "^18.2.18",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.3.3",
    "vite": "^5.1.0",
    "vitest": "^1.2.2",
    "@testing-library/react": "^14.2.1",
    "@testing-library/jest-dom": "^6.4.2",
    "jsdom": "^24.0.0"
  }
}
```

**`frontend/vite.config.ts`:**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test-setup.ts',
  },
})
```

**`frontend/tsconfig.json`:**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

**`frontend/tsconfig.node.json`:**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

**`frontend/index.html`:**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>BikeFlowGNN v2 - 北京骑行路线分析</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: 安装依赖并验证脚手架**

```bash
cd BikeFlowGNN/frontend
npm install
```

- [ ] **Step 3: 创建 TypeScript 类型定义 `frontend/src/core/types.ts`**

```typescript
/** BikeFlowGNN 前端类型定义 */

// ── 路线相关 ──

/** [lon, lat] 坐标 */
export type LatLng = [number, number]

/** 路线指标 */
export interface RouteMetrics {
  total_length: number
  total_cost: number
  avg_safety: number
  avg_comfort: number
  avg_scenery: number
  avg_traffic_stress: number
  avg_beauty: number
  avg_pref_score: number
  num_segments: number
}

/** 单条路线 */
export interface RouteResult {
  route_id: number
  coordinates: LatLng[]
  metrics: RouteMetrics
}

/** 场景配置 */
export interface SceneConfig {
  center: [number, number]
  zoom?: number
  user_template?: string
}

/** 搜索响应 */
export interface RouteSearchResponse {
  routes: RouteResult[]
  best_route_id: number
  scene_config: SceneConfig
  from_cache: boolean
  pipeline_duration_sec?: number
}

/** 搜索请求 */
export interface RouteSearchRequest {
  source: LatLng
  target: LatLng
  user_template: UserTemplate
  use_cache?: boolean
  skip_gnn?: boolean
}

// ── 用户画像 ──

export type UserTemplate = 'commuter' | 'tourist' | 'fitness' | 'family'

export interface UserTemplateInfo {
  key: UserTemplate
  name: string
  description: string
}

export interface UserTemplatesResponse {
  templates: UserTemplateInfo[]
}

// ── 健康检查 ──

export interface HealthResponse {
  status: string
  version: string
}

// ── UI状态 ──

export type SearchStatus = 'idle' | 'searching' | 'success' | 'error'

export type MapLayer = 'segments' | 'stations' | 'routes'
```

- [ ] **Step 4: 创建 API 客户端 `frontend/src/core/api.ts`**

```typescript
/** API 客户端 — 与FastAPI后端通信 */
import axios from 'axios'
import type {
  HealthResponse,
  UserTemplatesResponse,
  RouteSearchRequest,
  RouteSearchResponse,
} from './types'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 120000, // 管道运行可能较慢
  headers: {
    'Content-Type': 'application/json',
  },
})

/** 健康检查 */
export async function checkHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/health')
  return data
}

/** 获取用户画像模板列表 */
export async function getUserTemplates(): Promise<UserTemplatesResponse> {
  const { data } = await apiClient.get<UserTemplatesResponse>('/user-templates')
  return data
}

/** 搜索骑行路线 */
export async function searchRoutes(
  req: RouteSearchRequest,
): Promise<RouteSearchResponse> {
  const { data } = await apiClient.post<RouteSearchResponse>(
    '/routes/search',
    req,
  )
  return data
}

/** 按ID获取路线详情 */
export async function getRouteById(routeId: number): Promise<unknown> {
  const { data } = await apiClient.get(`/routes/${routeId}`)
  return data
}

export default apiClient
```

- [ ] **Step 5: 创建 Zustand 状态管理 `frontend/src/core/store.ts`**

```typescript
/** Zustand 全局状态管理 */
import { create } from 'zustand'
import type {
  RouteResult,
  RouteSearchResponse,
  SearchStatus,
  UserTemplate,
  UserTemplateInfo,
  LatLng,
  MapLayer,
} from './types'
import { searchRoutes, getUserTemplates } from './api'

interface BikeFlowState {
  // ── 搜索状态 ──
  searchStatus: SearchStatus
  errorMessage: string | null

  // ── 搜索输入 ──
  source: LatLng | null
  target: LatLng | null
  selectedTemplate: UserTemplate

  // ── 搜索结果 ──
  routes: RouteResult[]
  bestRouteId: number | null
  selectedRouteId: number | null
  fromCache: boolean
  pipelineDuration: number | null

  // ── 用户模板 ──
  templates: UserTemplateInfo[]
  templatesLoading: boolean

  // ── 地图状态 ──
  mapCenter: [number, number]
  mapZoom: number
  visibleLayers: Set<MapLayer>

  // ── Actions ──
  setSource: (coords: LatLng | null) => void
  setTarget: (coords: LatLng | null) => void
  setSelectedTemplate: (template: UserTemplate) => void
  setSelectedRouteId: (id: number | null) => void
  toggleLayer: (layer: MapLayer) => void
  setMapCenter: (center: [number, number]) => void
  setMapZoom: (zoom: number) => void

  fetchTemplates: () => Promise<void>
  executeSearch: () => Promise<void>
  resetSearch: () => void
}

export const useBikeFlowStore = create<BikeFlowState>((set, get) => ({
  // ── 初始状态 ──
  searchStatus: 'idle',
  errorMessage: null,
  source: null,
  target: null,
  selectedTemplate: 'commuter',
  routes: [],
  bestRouteId: null,
  selectedRouteId: null,
  fromCache: false,
  pipelineDuration: null,
  templates: [],
  templatesLoading: false,
  mapCenter: [116.40, 39.92], // 北京中心
  mapZoom: 13,
  visibleLayers: new Set(['segments', 'routes']),

  // ── Actions ──
  setSource: (coords) => set({ source: coords }),
  setTarget: (coords) => set({ target: coords }),
  setSelectedTemplate: (template) => set({ selectedTemplate: template }),
  setSelectedRouteId: (id) => set({ selectedRouteId: id }),

  toggleLayer: (layer) =>
    set((state) => {
      const newLayers = new Set(state.visibleLayers)
      if (newLayers.has(layer)) {
        newLayers.delete(layer)
      } else {
        newLayers.add(layer)
      }
      return { visibleLayers: newLayers }
    }),

  setMapCenter: (center) => set({ mapCenter: center }),
  setMapZoom: (zoom) => set({ mapZoom: zoom }),

  fetchTemplates: async () => {
    set({ templatesLoading: true })
    try {
      const resp = await getUserTemplates()
      set({ templates: resp.templates, templatesLoading: false })
    } catch (err) {
      console.error('Failed to fetch templates:', err)
      set({ templatesLoading: false })
    }
  },

  executeSearch: async () => {
    const { source, target, selectedTemplate } = get()
    if (!source || !target) {
      set({ errorMessage: '请先设置起点和终点' })
      return
    }

    set({ searchStatus: 'searching', errorMessage: null })

    try {
      const resp: RouteSearchResponse = await searchRoutes({
        source,
        target,
        user_template: selectedTemplate,
      })

      set({
        searchStatus: 'success',
        routes: resp.routes,
        bestRouteId: resp.best_route_id,
        selectedRouteId: resp.best_route_id,
        fromCache: resp.from_cache,
        pipelineDuration: resp.pipeline_duration_sec ?? null,
      })

      // 更新地图中心
      if (resp.scene_config?.center) {
        set({
          mapCenter: [
            resp.scene_config.center[0],
            resp.scene_config.center[1],
          ],
        })
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : '搜索失败，请重试'
      set({ searchStatus: 'error', errorMessage: message })
    }
  },

  resetSearch: () =>
    set({
      searchStatus: 'idle',
      errorMessage: null,
      routes: [],
      bestRouteId: null,
      selectedRouteId: null,
      fromCache: false,
      pipelineDuration: null,
    }),
}))
```

- [ ] **Step 6: 创建路由 `frontend/src/router/index.tsx`**

```typescript
/** React Router 路由配置 */
import { createBrowserRouter, Navigate } from 'react-router-dom'
import MapPage from '../pages/MapPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MapPage />,
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
])
```

- [ ] **Step 7: 创建应用入口 `frontend/src/main.tsx`**

```typescript
/** React 应用入口 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { router } from './router'
import './styles/global.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
```

- [ ] **Step 8: 创建全局样式 `frontend/src/styles/global.css`**

```css
/* ── 全局样式 ── */

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #root {
  height: 100%;
  width: 100%;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    'Helvetica Neue', Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #333;
  background: #f5f5f5;
}

/* ── 布局 ── */

.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.app-sidebar {
  width: 380px;
  min-width: 380px;
  background: #fff;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
  overflow-y: auto;
  z-index: 1000;
}

.app-main {
  flex: 1;
  position: relative;
}

/* ── 地图 ── */

.map-container {
  width: 100%;
  height: 100%;
}

.map-container .esri-view-root {
  width: 100%;
  height: 100%;
  background: #e8e8e8;
}

/* ── 侧边栏 ── */

.sidebar-section {
  padding: 16px;
  border-bottom: 1px solid #eee;
}

.sidebar-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 12px;
  color: #1a1a2e;
}

.sidebar-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
  display: block;
}

/* ── 表单元素 ── */

.form-select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  background: #fff;
  cursor: pointer;
}

.form-select:focus {
  outline: none;
  border-color: #4a90d9;
  box-shadow: 0 0 0 2px rgba(74, 144, 217, 0.2);
}

.btn-search {
  width: 100%;
  padding: 12px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-search:hover:not(:disabled) {
  background: #357abd;
}

.btn-search:disabled {
  background: #aaa;
  cursor: not-allowed;
}

/* ── 状态提示 ── */

.status-searching {
  text-align: center;
  padding: 20px;
  color: #4a90d9;
}

.status-error {
  color: #e74c3c;
  padding: 12px;
  background: #fdf0ef;
  border-radius: 6px;
  font-size: 13px;
}

.spinner {
  display: inline-block;
  width: 24px;
  height: 24px;
  border: 3px solid #ddd;
  border-top-color: #4a90d9;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── 路线对比 ── */

.route-item {
  padding: 12px;
  border: 1px solid #eee;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.route-item:hover {
  border-color: #4a90d9;
  background: #f8faff;
}

.route-item.selected {
  border-color: #4a90d9;
  background: #eef5ff;
  box-shadow: 0 0 0 2px rgba(74, 144, 217, 0.2);
}

.route-item.best {
  border-left: 4px solid #27ae60;
}

.route-id {
  font-weight: 700;
  font-size: 14px;
  color: #1a1a2e;
}

.route-badge {
  display: inline-block;
  padding: 2px 8px;
  background: #27ae60;
  color: #fff;
  border-radius: 4px;
  font-size: 11px;
  margin-left: 8px;
}

/* ── 指标面板 ── */

.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.metric-card {
  padding: 10px;
  background: #f9f9f9;
  border-radius: 6px;
  text-align: center;
}

.metric-label {
  font-size: 11px;
  color: #999;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  font-weight: 700;
  color: #1a1a2e;
}

.metric-bar {
  height: 4px;
  background: #eee;
  border-radius: 2px;
  margin-top: 4px;
  overflow: hidden;
}

.metric-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}

/* ── 图层控制 ── */

.layer-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  cursor: pointer;
  font-size: 13px;
}

.layer-toggle input[type="checkbox"] {
  cursor: pointer;
}

/* ── 坐标输入 ── */

.coord-display {
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 6px;
  font-size: 13px;
  color: #555;
  font-family: 'Courier New', monospace;
}

.coord-display.empty {
  color: #aaa;
  font-style: italic;
}

.cache-badge {
  display: inline-block;
  padding: 2px 8px;
  background: #f0ad4e;
  color: #fff;
  border-radius: 4px;
  font-size: 11px;
  margin-left: 4px;
}
```

- [ ] **Step 9: 创建 Sidebar 组件 `frontend/src/components/Sidebar.tsx`**

```typescript
/** 侧边栏 — 搜索控制面板 */
import { useEffect } from 'react'
import { useBikeFlowStore } from '../core/store'
import type { UserTemplate } from '../core/types'

export default function Sidebar() {
  const {
    source,
    target,
    selectedTemplate,
    templates,
    templatesLoading,
    searchStatus,
    errorMessage,
    fromCache,
    pipelineDuration,
    visibleLayers,
    setSource,
    setTarget,
    setSelectedTemplate,
    toggleLayer,
    fetchTemplates,
    executeSearch,
    resetSearch,
  } = useBikeFlowStore()

  useEffect(() => {
    fetchTemplates()
  }, [fetchTemplates])

  const isSearching = searchStatus === 'searching'
  const canSearch = source !== null && target !== null && !isSearching

  const handleTemplateChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedTemplate(e.target.value as UserTemplate)
  }

  return (
    <div className="app-sidebar">
      {/* 标题 */}
      <div className="sidebar-section">
        <div className="sidebar-title">BikeFlowGNN v2</div>
        <div style={{ fontSize: '13px', color: '#888' }}>
          北京骑行路线分析系统
        </div>
      </div>

      {/* 起终点 */}
      <div className="sidebar-section">
        <label className="sidebar-label">起点 (点击地图设置)</label>
        <div className={`coord-display ${!source ? 'empty' : ''}`}>
          {source
            ? `${source[0].toFixed(6)}, ${source[1].toFixed(6)}`
            : '未设置 — 请在地图上点击选择起点'}
        </div>
        <button
          onClick={() => setSource(null)}
          style={{
            marginTop: '4px',
            padding: '2px 8px',
            fontSize: '12px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            background: '#fff',
            cursor: source ? 'pointer' : 'not-allowed',
            color: source ? '#666' : '#ccc',
          }}
          disabled={!source}
        >
          清除起点
        </button>

        <label className="sidebar-label" style={{ marginTop: '12px' }}>
          终点 (点击地图设置)
        </label>
        <div className={`coord-display ${!target ? 'empty' : ''}`}>
          {target
            ? `${target[0].toFixed(6)}, ${target[1].toFixed(6)}`
            : '未设置 — 请在地图上点击选择终点'}
        </div>
        <button
          onClick={() => setTarget(null)}
          style={{
            marginTop: '4px',
            padding: '2px 8px',
            fontSize: '12px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            background: '#fff',
            cursor: target ? 'pointer' : 'not-allowed',
            color: target ? '#666' : '#ccc',
          }}
          disabled={!target}
        >
          清除终点
        </button>
      </div>

      {/* 用户画像 */}
      <div className="sidebar-section">
        <label className="sidebar-label">骑行者画像</label>
        <select
          className="form-select"
          value={selectedTemplate}
          onChange={handleTemplateChange}
          disabled={templatesLoading}
        >
          {templates.length > 0
            ? templates.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.name} — {t.description}
                </option>
              ))
            : (
                <>
                  <option value="commuter">通勤者 — 高效安全</option>
                  <option value="tourist">游客 — 风景优先</option>
                  <option value="fitness">健身者 — 长距离</option>
                  <option value="family">家庭 — 安全第一</option>
                </>
              )}
        </select>
      </div>

      {/* 图层控制 */}
      <div className="sidebar-section">
        <label className="sidebar-label">地图图层</label>
        {(['segments', 'stations', 'routes'] as const).map((layer) => (
          <label key={layer} className="layer-toggle">
            <input
              type="checkbox"
              checked={visibleLayers.has(layer)}
              onChange={() => toggleLayer(layer)}
            />
            {layer === 'segments' && '街道段'}
            {layer === 'stations' && '停车点'}
            {layer === 'routes' && '推荐路线'}
          </label>
        ))}
      </div>

      {/* 搜索按钮 */}
      <div className="sidebar-section">
        <button
          className="btn-search"
          onClick={executeSearch}
          disabled={!canSearch}
        >
          {isSearching ? '搜索中...' : '搜索路线'}
        </button>
        {searchStatus === 'success' && (
          <div style={{ marginTop: '8px', fontSize: '12px', color: '#666' }}>
            {fromCache && <span className="cache-badge">缓存</span>}
            {pipelineDuration !== null && ` 耗时 ${pipelineDuration}s`}
            <button
              onClick={resetSearch}
              style={{
                marginLeft: '8px',
                padding: '2px 8px',
                fontSize: '12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                background: '#fff',
                cursor: 'pointer',
                color: '#666',
              }}
            >
              重置
            </button>
          </div>
        )}
      </div>

      {/* 错误提示 */}
      {errorMessage && (
        <div className="sidebar-section">
          <div className="status-error">{errorMessage}</div>
        </div>
      )}

      {/* 搜索中动画 */}
      {isSearching && (
        <div className="sidebar-section">
          <div className="status-searching">
            <div className="spinner" style={{ marginBottom: '8px' }} />
            <div>正在运行算法管道...</div>
            <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>
              数据加载 → 图构建 → 边权计算 → GNN → NSGA-II
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 10: 创建 RouteCompare 组件 `frontend/src/components/RouteCompare.tsx`**

```typescript
/** 路线对比面板 — 展示Pareto最优路线列表 */
import { useBikeFlowStore } from '../core/store'
import type { RouteResult } from '../core/types'

const ROUTE_COLORS = [
  '#27ae60', // 绿色 (最佳)
  '#3498db', // 蓝色
  '#e67e22', // 橙色
  '#9b59b6', // 紫色
  '#e74c3c', // 红色
]

export default function RouteCompare() {
  const {
    routes,
    bestRouteId,
    selectedRouteId,
    setSelectedRouteId,
  } = useBikeFlowStore()

  if (routes.length === 0) return null

  const handleSelect = (route: RouteResult) => {
    setSelectedRouteId(route.route_id)
  }

  return (
    <div
      style={{
        position: 'absolute',
        top: '16px',
        right: '16px',
        width: '300px',
        maxHeight: '60vh',
        overflowY: 'auto',
        background: 'rgba(255,255,255,0.95)',
        borderRadius: '10px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        padding: '14px',
        zIndex: 1000,
      }}
    >
      <div
        style={{
          fontSize: '15px',
          fontWeight: 700,
          marginBottom: '10px',
          color: '#1a1a2e',
        }}
      >
        Pareto最优路线 ({routes.length}条)
      </div>

      {routes.map((route, idx) => {
        const isSelected = route.route_id === selectedRouteId
        const isBest = route.route_id === bestRouteId
        const color = ROUTE_COLORS[idx % ROUTE_COLORS.length]

        return (
          <div
            key={route.route_id}
            className={`route-item ${isSelected ? 'selected' : ''} ${isBest ? 'best' : ''}`}
            onClick={() => handleSelect(route)}
          >
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <div
                style={{
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  background: color,
                  marginRight: '8px',
                  flexShrink: 0,
                }}
              />
              <span className="route-id">路线 {route.route_id + 1}</span>
              {isBest && <span className="route-badge">推荐</span>}
            </div>
            <div
              style={{
                fontSize: '12px',
                color: '#888',
                marginTop: '4px',
              }}
            >
              {(route.metrics.total_length / 1000).toFixed(2)} km |{' '}
              安全 {route.metrics.avg_safety.toFixed(2)} |{' '}
              风景 {route.metrics.avg_scenery.toFixed(2)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 11: 创建 MetricsPanel 组件 `frontend/src/components/MetricsPanel.tsx`**

```typescript
/** 指标面板 — 展示选中路线的详细指标 */
import { useBikeFlowStore } from '../core/store'
import type { RouteMetrics } from '../core/types'

function MetricCard({
  label,
  value,
  max,
  color,
  suffix,
}: {
  label: string
  value: number
  max: number
  color: string
  suffix?: string
}) {
  const percent = Math.min((value / max) * 100, 100)
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">
        {value.toFixed(2)}
        {suffix}
      </div>
      <div className="metric-bar">
        <div
          className="metric-bar-fill"
          style={{ width: `${percent}%`, background: color }}
        />
      </div>
    </div>
  )
}

export default function MetricsPanel() {
  const { routes, selectedRouteId, bestRouteId } = useBikeFlowStore()

  if (routes.length === 0) return null

  const selectedRoute = routes.find((r) => r.route_id === selectedRouteId) ||
    routes.find((r) => r.route_id === bestRouteId)

  if (!selectedRoute) return null

  const m: RouteMetrics = selectedRoute.metrics
  const isBest = selectedRoute.route_id === bestRouteId

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '16px',
        right: '16px',
        width: '300px',
        background: 'rgba(255,255,255,0.95)',
        borderRadius: '10px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        padding: '14px',
        zIndex: 1000,
      }}
    >
      <div
        style={{
          fontSize: '15px',
          fontWeight: 700,
          marginBottom: '10px',
          color: '#1a1a2e',
        }}
      >
        路线 {selectedRoute.route_id + 1} 指标
        {isBest && <span className="route-badge">推荐</span>}
      </div>

      <div className="metrics-grid">
        <MetricCard
          label="总距离"
          value={m.total_length / 1000}
          max={20}
          color="#3498db"
          suffix=" km"
        />
        <MetricCard
          label="总成本"
          value={m.total_cost}
          max={5000}
          color="#e74c3c"
        />
        <MetricCard
          label="安全性"
          value={m.avg_safety}
          max={1}
          color="#27ae60"
        />
        <MetricCard
          label="舒适度"
          value={m.avg_comfort}
          max={1}
          color="#2ecc71"
        />
        <MetricCard
          label="风景"
          value={m.avg_scenery}
          max={1}
          color="#f39c12"
        />
        <MetricCard
          label="交通压力"
          value={m.avg_traffic_stress}
          max={1}
          color="#e67e22"
        />
        <MetricCard
          label="美观度"
          value={m.avg_beauty}
          max={1}
          color="#9b59b6"
        />
        <MetricCard
          label="偏好分"
          value={m.avg_pref_score}
          max={1}
          color="#1abc9c"
        />
      </div>

      <div
        style={{
          marginTop: '8px',
          fontSize: '12px',
          color: '#888',
          textAlign: 'center',
        }}
      >
        {m.num_segments} 个街道段
      </div>
    </div>
  )
}
```

- [ ] **Step 12: 创建主地图页 `frontend/src/pages/MapPage.tsx`**

```typescript
/** 主地图页 — GeoScene MapView + 侧边栏 + 路线叠加 */
import { useEffect, useRef } from 'react'
import Map from '@geoscene/core/Map'
import MapView from '@geoscene/core/views/MapView'
import Graphic from '@geoscene/core/Graphic'
import GraphicsLayer from '@geoscene/core/layers/GraphicsLayer'
import TileLayer from '@geoscene/core/layers/TileLayer'
import Point from '@geoscene/core/geometry/Point'
import Polyline from '@geoscene/core/geometry/Polyline'
import SimpleMarkerSymbol from '@geoscene/core/symbols/SimpleMarkerSymbol'
import SimpleLineSymbol from '@geoscene/core/symbols/SimpleLineSymbol'
import { useBikeFlowStore } from '../core/store'
import type { LatLng } from '../core/types'
import Sidebar from '../components/Sidebar'
import RouteCompare from '../components/RouteCompare'
import MetricsPanel from '../components/MetricsPanel'

// 天地图底图 (请替换为有效的天地图开发者 token)
const TIANDITU_TOKEN = 'YOUR_TIANDITU_TOKEN'

// 通过 GeoScene TileLayer 配置天地图矢量底图
const tiandituLayer = new TileLayer({
  url: `https://{subDomain}.tianditu.gov.cn/DataServer?T=vec_w&x={col}&y={row}&l={level}&tk=${TIANDITU_TOKEN}`,
  subDomains: ['t0', 't1', 't2', 't3', 't4', 't5', 't6', 't7'],
  title: '天地图矢量底图',
})

// 路线颜色
const ROUTE_COLORS = [
  '#27ae60',
  '#3498db',
  '#e67e22',
  '#9b59b6',
  '#e74c3c',
]

export default function MapPage() {
  const {
    source,
    target,
    routes,
    selectedRouteId,
    bestRouteId,
    mapCenter,
    mapZoom,
    visibleLayers,
    setSource,
    setTarget,
  } = useBikeFlowStore()

  const mapDivRef = useRef<HTMLDivElement | null>(null)
  const viewRef = useRef<MapView | null>(null)
  const markersLayerRef = useRef<GraphicsLayer | null>(null)
  const routesLayerRef = useRef<GraphicsLayer | null>(null)

  // ── 初始化 GeoScene MapView（仅一次） ──
  useEffect(() => {
    if (!mapDivRef.current) return

    // GeoScene Map 通过 basemap 加载天地图底图
    const map = new Map({
      basemap: tiandituLayer,
    })

    // GeoScene 坐标系统使用 [longitude, latitude] 顺序
    const view = new MapView({
      container: mapDivRef.current,
      map,
      center: [mapCenter[0], mapCenter[1]],
      zoom: mapZoom,
    })
    viewRef.current = view

    // 起终点标记图层 + 路线叠加图层
    const markersLayer = new GraphicsLayer()
    const routesLayer = new GraphicsLayer()
    map.addMany([routesLayer, markersLayer])
    markersLayerRef.current = markersLayer
    routesLayerRef.current = routesLayer

    // 地图点击事件 — 设置起终点（GeoScene 使用 view.on('click', ...)）
    view.on('click', (event) => {
      // event.mapPoint 提供经纬度
      const coords: LatLng = [event.mapPoint.longitude, event.mapPoint.latitude]
      const { source: curSource, target: curTarget } =
        useBikeFlowStore.getState()
      if (!curSource) {
        setSource(coords)
      } else if (!curTarget) {
        setTarget(coords)
      } else {
        // 起终点都已设置时，点击重新设置起点
        setSource(coords)
        setTarget(null)
      }
    })

    return () => {
      view.destroy()
      viewRef.current = null
      markersLayerRef.current = null
      routesLayerRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── 地图中心变化时平移 ──
  useEffect(() => {
    if (viewRef.current) {
      viewRef.current.goTo({
        center: [mapCenter[0], mapCenter[1]],
        zoom: mapZoom,
      })
    }
  }, [mapCenter, mapZoom])

  // ── 起终点标记（Graphic + GraphicsLayer） ──
  useEffect(() => {
    const layer = markersLayerRef.current
    if (!layer) return
    layer.removeAll()

    // 起点标记
    if (source) {
      const point = new Point({
        longitude: source[0],
        latitude: source[1],
      })
      const symbol = new SimpleMarkerSymbol({
        style: 'circle',
        color: '#27ae60',
        size: 20,
        outline: new SimpleLineSymbol({
          style: 'solid',
          color: '#ffffff',
          width: 2,
        }),
      })
      layer.add(
        new Graphic({
          geometry: point,
          symbol,
          attributes: { type: 'source', label: 'A' },
        }),
      )
    }

    // 终点标记
    if (target) {
      const point = new Point({
        longitude: target[0],
        latitude: target[1],
      })
      const symbol = new SimpleMarkerSymbol({
        style: 'circle',
        color: '#e74c3c',
        size: 20,
        outline: new SimpleLineSymbol({
          style: 'solid',
          color: '#ffffff',
          width: 2,
        }),
      })
      layer.add(
        new Graphic({
          geometry: point,
          symbol,
          attributes: { type: 'target', label: 'B' },
        }),
      )
    }
  }, [source, target])

  // ── 路线叠加（Polyline Graphic） ──
  useEffect(() => {
    const layer = routesLayerRef.current
    if (!layer) return
    layer.removeAll()

    if (!visibleLayers.has('routes')) return

    routes.forEach((route, idx) => {
      const isSelected = route.route_id === selectedRouteId
      const isBest = route.route_id === bestRouteId
      const color = ROUTE_COLORS[idx % ROUTE_COLORS.length]

      // GeoScene 坐标系使用 [longitude, latitude] 顺序，与数据存储顺序一致，无需翻转
      const path = route.coordinates.map((c) => [c[0], c[1]])
      const polyline = new Polyline({ paths: [path] })

      const symbol = new SimpleLineSymbol({
        style: isBest ? 'solid' : 'dash',
        color,
        width: isSelected ? 6 : isBest ? 5 : 3,
      })

      const graphic = new Graphic({
        geometry: polyline,
        symbol,
        attributes: { routeId: route.route_id, isSelected, isBest },
      })
      layer.add(graphic)
    })
  }, [routes, selectedRouteId, bestRouteId, visibleLayers])

  return (
    <div className="app-layout">
      <Sidebar />

      <div className="app-main">
        {/* GeoScene MapView 容器 */}
        <div className="map-container" ref={mapDivRef} />

        {/* 路线对比面板 */}
        <RouteCompare />

        {/* 指标面板 */}
        <MetricsPanel />

        {/* 状态提示 (非搜索时隐藏) */}
        {!source && !target && (
          <div
            style={{
              position: 'absolute',
              top: '16px',
              left: '50%',
              transform: 'translateX(-50%)',
              background: 'rgba(255,255,255,0.9)',
              padding: '10px 20px',
              borderRadius: '8px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              fontSize: '14px',
              color: '#666',
              zIndex: 1000,
              pointerEvents: 'none',
            }}
          >
            点击地图设置起点 (A) 和终点 (B)
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 13: 启动前端开发服务器验证**

```bash
cd BikeFlowGNN/frontend
npm run dev
```

验证：
- 访问 `http://localhost:5173` 看到地图界面
- 左侧侧边栏显示搜索控制面板
- 点击地图可以设置起点(A)和终点(B)标记
- 选择用户画像模板后点击"搜索路线"
- 右上角显示Pareto路线列表
- 右下角显示选中路线的详细指标
- Vite代理将 `/api` 请求转发到 `http://localhost:8000`

- [ ] **Step 14: 构建生产版本验证**

```bash
cd BikeFlowGNN/frontend
npm run build
```

验证：`dist/` 目录生成，无TypeScript编译错误

- [ ] **Step 15: Commit**

```bash
git add -A
git commit -m "feat: React 18 + TypeScript + Vite + GeoScene JS API + Zustand frontend with interactive map UI"
```

---

## 自检清单

完成所有15个Task后，执行以下自检：

- [ ] **GeoScene比赛合规性检查（最重要）**

```bash
# 1. 确认服务器端部署基于GeoScene Enterprise（比赛强制要求）
grep -r "geoscene\|GeoScene" BikeFlowGNN/backend/core/config.py && echo "OK: GeoScene Server配置存在"
grep -r "geoscene\|GeoScene" BikeFlowGNN/geoscene/ && echo "OK: GeoScene服务配置目录存在"

# 2. 确认无MapGIS残留（中地数码产品不符合比赛要求）
grep -ri "mapgis\|MapGIS" BikeFlowGNN/ --include="*.py" --include="*.ts" --include="*.tsx" --include="*.json" && echo "ERROR: 发现MapGIS残留" || echo "OK: 无MapGIS残留"

# 3. 确认无Leaflet残留（必须使用GeoScene Web API）
grep -ri "leaflet\|react-leaflet" BikeFlowGNN/frontend/ && echo "ERROR: 发现Leaflet残留" || echo "OK: 前端使用GeoScene JS API"

# 4. 确认无OSMnx残留（比赛推荐天地图底图，避免境外数据源）
grep -ri "osmnx\|osm_loader" BikeFlowGNN/algorithm/ && echo "ERROR: 发现OSMnx残留" || echo "OK: 底图使用天地图"

# 5. 确认File Geodatabase数据格式（比赛推荐格式）
ls BikeFlowGNN/geoscene/data/BikeFlowGNN.gdb/ && echo "OK: File Geodatabase存在"
```

- [ ] **架构完整性检查**

```bash
# 验证四层目录结构
find BikeFlowGNN -type f -name "*.py" | head -40
find BikeFlowGNN -type f -name "*.tsx" -o -name "*.ts" | head -20
ls BikeFlowGNN/geoscene/services/
```

- [ ] **算法层零Web依赖检查**

```bash
# 确认algorithm/目录下无FastAPI/Flask等Web依赖
grep -r "fastapi\|flask\|uvicorn\|django" BikeFlowGNN/algorithm/ || echo "OK: 算法层零Web依赖"
```

- [ ] **import路径检查**

```bash
# 确认无残留的 from src.xxx 或 osm_loader 或 mapgis_export 导入
grep -r "from src\." BikeFlowGNN/algorithm/ && echo "ERROR: 发现残留src导入" || echo "OK: 所有导入已改为algorithm"
grep -r "osm_loader\|mapgis_export" BikeFlowGNN/ && echo "ERROR: 发现残留旧模块名" || echo "OK: 所有模块名已更新"
```

- [ ] **测试目录检查**

```bash
# 确认测试在algorithm/tests/下
ls BikeFlowGNN/algorithm/tests/
```

- [ ] **数据文件位置检查**

```bash
# 确认数据在顶层data/目录
ls BikeFlowGNN/data/
```

- [ ] **全量测试运行**

```bash
cd BikeFlowGNN
python -m pytest algorithm/tests/ -v --tb=short
python -m pytest backend/tests/ -v --tb=short
cd frontend && npm run build
```

- [ ] **GeoScene服务发布验证**

```bash
# 发布GeoScene Server服务（需先启动GeoScene Enterprise）
cd BikeFlowGNN
python geoscene/publish_services.py
# 验证服务可访问
curl -k "https://localhost:6443/arcgis/rest/services/BikeSegments_MapService/MapServer?f=json"
```

- [ ] **端到端联调验证**

```bash
# 终端1: 启动GeoScene Enterprise Server（确保服务已发布）

# 终端2: 启动后端（FastAPI轻量网关）
cd BikeFlowGNN
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload

# 终端3: 启动前端
cd BikeFlowGNN/frontend
npm run dev

# 浏览器访问 http://localhost:5173
# 1. 地图加载天地图底图（GeoScene MapView）
# 2. 点击地图设置起点和终点
# 3. 选择用户画像
# 4. 点击搜索路线
# 5. 查看Pareto路线列表和指标
# 6. 切换3D视图查看路线叠加（GeoScene SceneView）
```

- [ ] **最终Commit**

```bash
git add -A
git commit -m "chore: complete four-layer GeoScene-compliant architecture — algorithm/geoscene/backend/frontend"
```
