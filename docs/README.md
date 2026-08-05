# BikeFlowGNN v2 — 北京骑行路线智能分析系统

## 系统概述

BikeFlowGNN v2 是基于 GeoScene Enterprise 与异构图神经网络（HGT-GNN）的北京骑行路线智能分析系统。系统融合 2,563 个街景采样点的视觉指标、80 万 POI、3,293 个共享单车停车点，构建 5 类节点 6 类边的异构图模型，通过 city2graph 形态分析与 GNN 偏好学习，利用 NSGA-II 多目标遗传算法同时优化安全性、舒适度、风景和综合体验四个维度，生成 Pareto 最优骑行路线推荐。

## 六层架构

```
CvclingMap_new_refactor/
├── database/       # 数据库层：全量数据分门别类存储
│   ├── raw/            # 原始数据（poi/ stations/ streetview/）
│   ├── processed/      # 中间处理结果（GeoPackage）
│   ├── output/         # 运行产物（GeoJSON/场景配置，/data 静态挂载源）
│   ├── cache/          # SQLite 路线缓存（bikeflow.db）
│   ├── bikeflow.sqlite # 真实数据库系统（SQLite，全量数据已入库）
│   ├── schema.py       # 数据库 schema 定义与建库入口
│   ├── repository/     # 统一访问层（read_* 只读 API）
│   ├── scripts/        # 入库脚本（ingest_all.py）、冒烟脚本
│   └── tests/          # 数据库层测试
├── algorithm/      # 算法层（纯算法引擎，零 Web 依赖）
│   ├── data/           # 数据加载器（经 database/repository 读取）
│   ├── graph/          # 5类节点6类边异构图构建 + 指标传播
│   ├── weights/        # 四维边权模型（安全/舒适/风景/综合体验）
│   ├── models/         # HGT-GNN 模型与训练
│   ├── routing/        # NSGA-II 多目标搜索 + 个性化推荐
│   └── pipeline.py     # 五阶段流水线编排
├── gateway/        # 网关层（FastAPI 网关 + GeoScene Server 集成）
│   ├── app.py          # 应用入口（/data 静态挂载 → database/output）
│   ├── api/            # REST 路由（health/geoscene/user-templates/routes）
│   ├── service/        # 业务逻辑 + geoscene_client（GIS 能力代理）
│   ├── db/             # SQLAlchemy 缓存模型（database/cache/bikeflow.db）
│   └── tests/
├── interaction/    # 交互层（前端单工程内模块，控制面板与 UI）
│   └── frontend/src/interaction/   # Sidebar、RouteCompare、MetricsPanel
├── rendering/      # 渲染层
│   ├── frontend/src/rendering/     # Scene3DView（Three.js 3D 场景）
│   │   └── scene-config/           # GeoScene WebScene 3D 场景定义
│   ├── export/                     # 渲染数据导出（GeoJSON/场景配置）
│   └── frontend/public/data/       # 静态渲染数据
├── tools/          # 工具库（与平台运行相对无关）
│   ├── crawlers/        # OSM/天地图爬虫脚本
│   ├── geoscene/        # GeoScene 服务发布脚本 + 服务配置 + GDB 说明
│   └── notebooks/       # 研究分析笔记本
└── docs/           # 文档
```

数据流：`database/`（SQLite 全量数据）→ `algorithm/`（纯算法引擎）→ `gateway/`（FastAPI 网关，GeoScene Server 集成）→ `interaction/`（控制面板）+ `rendering/`（3D 场景）。

## 快速开始

```bash
# 1) 初始化数据库并入库（全量数据 → database/bikeflow.sqlite）
python database/scripts/ingest_all.py

# 2) 网关
cd gateway
pip install -r requirements.txt
uvicorn gateway.app:app --reload --port 8000

# 3) 前端
cd frontend
npm install
npm run dev

# 4) GeoScene 服务发布（需 GeoScene Enterprise Server 运行）
python tools/geoscene/publish_services.py --publish
```

## 数据库层

- 存储：`database/bikeflow.sqlite`（SQLite 空间库，几何以 WKT 存储，点数据含 lon/lat 列）
- 表：`streetview_observations`（10,131 行 × 181 列）、`poi`（806,960）、`stations`（3,293）、`segments`（2,376）、`buildings`（1,152）、`districts`（16）、`routes`、`dataset_meta`
- 访问：`database/repository` 提供 `read_streetview/read_poi/read_stations/read_segments/read_buildings/...` 统一只读 API
- 入库：`python database/scripts/ingest_all.py [--dataset poi]`，幂等可重复执行

## 比赛合规（GeoScene 杯 C 组 GIS 应用开发组）

- **服务器端 GIS 核心基于 GeoScene Enterprise Server**：网关层 `geoscene_client` 负责探测与代理地图/场景服务（`/api/geoscene/status`）；GeoScene 不可达时回退本地 `/data` 静态数据（开发模式）
- **底图**：天地图数据（`tools/crawlers/download_tianditu_tiles.py` 可下载影像底图）
- **数据存储**：File Geodatabase（`.gdb`，见 `tools/geoscene/data/README.txt` 导入步骤）+ SQLite（真实数据库系统）
- **数据源**：中国境内数据（北京六区），无境外数据
- **Algorithm 层**：开源技术（city2graph、PyTorch、PyG），零 Web 依赖，可独立运行

## 运行环境

- Python 3.11+（开发机实测 3.13）、Node.js 20+
- GeoScene Enterprise Server（比赛组委会提供，可选：本地开发自动回退）
- RTX 4060 8GB（GPU 训练，可选）
- Windows 10/11 或 Linux

## 测试

```bash
python -m pytest database/tests algorithm/tests gateway/tests tools/tests -q   # 后端/算法/工具全量测试
cd frontend && npm run build                                                    # 前端 TypeScript 零错误构建
```
