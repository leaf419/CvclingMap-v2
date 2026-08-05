# BikeFlowGNN v2 — 骑行路线智能推荐系统

融合 GeoScene Enterprise GIS + 异构图神经网络（HGT-GNN）+ 街景 VLM 指标的北京骑行路线智能分析平台。

## 六层架构

```
├── database/    SQLite 真实数据库（80万POI / 3293停车点 / 10131街景观测 / 道路与建筑全量入库）
├── algorithm/   纯算法引擎（零Web依赖：异构图构建 → 四维边权 → GNN训练 → 路径搜索）
├── gateway/     FastAPI 网关 + GeoScene Enterprise Server 集成（比赛合规核心）
├── interaction/ 控制面板（Sidebar / RouteCompare / MetricsPanel）
├── rendering/   3D 场景渲染（Three.js 管状路线 + 光晕高亮 + 建筑白模）
└── tools/       爬虫 / GeoScene 服务发布 / notebooks
```

## 快速开始

```bash
# 1) 入库（只需一次，131s）
python database/scripts/warm_cache.py

# 2) 启动网关
uvicorn gateway.app:app --port 8000

# 3) 前端
cd frontend && npm install && npm run dev
```

## 部署（比赛规则第 5 条合规）

> 规则第 5 条强制要求"服务器端部署必须基于 GeoScene 服务器端产品"。
> 本项目服务器端 GIS 核心基于 **GeoScene Enterprise Server**（网关层 REST 集成与地图服务代理），
> 前端三维渲染采用 Three.js（开源仅用于可视化部分功能）。

```powershell
copy .env.example .env        # 填写 GeoScene Server URL / Token / 天地图 Token
deploy\deploy_geoscene.ps1    # 检查连接 → 生成数据 → File GDB 交付包 → 服务状态
deploy\start_gateway.ps1      # 启动网关（:8000，含 /api/geoscene/proxy 服务代理）
deploy\start_frontend.ps1     # 启动前端（:5173，Three.js 3D 场景）
```

详细步骤见 [`docs/部署文档.md`](docs/部署文档.md)（GeoScene 安装、服务发布、验证清单）。

## 路线推荐

| 画像 | 策略 | 路线数 | 速度 |
|---|---|---|---|
| 🚴 commuter 通勤 | cost_composite Dijkstra 点对点 | 2 | <1s |
| 🗺️ tourist 游客 | 5 变体加权（风景优先多档绕行） | 5 | <1s |
| 💪 fitness 健身 | 6 变体加权（长距离舒适/风景） | 5 | <1s |
| 👨‍👩‍👧 family 家庭 | 4 变体加权（安全优先） | 4 | <1s |

磁盘缓存 (`segments_weighted.gpkg`) 将首次 131s 压缩到后续 <1s。
NSGA-II 多目标搜索保留可选 (`force_nsga2=True`)。

## 测试

```bash
python -m pytest database/tests algorithm/tests gateway/tests tools/tests -q
```

## 比赛合规（GeoScene 杯 C 组）

- **服务器端 GIS 核心基于 GeoScene Enterprise Server**（`gateway/service/geoscene_client.py`）
- 底图：天地图数据（token 经环境变量注入）
- 数据存储：SQLite 空间库 + File Geodatabase（`tools/geoscene/data/README.txt`）
- Algorithm 层零 Web 依赖，开源技术（city2graph / PyTorch / PyG）

---

> 📖 详细架构与开发文档见 [`docs/README.md`](docs/README.md)
