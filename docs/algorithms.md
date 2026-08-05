# 算法说明

## 概述

BikeFlowGNN v2 的路径推荐算法分为三层：**边权模型**（四维指标融合）、**搜索策略**（Dijkstra 多变体 / NSGA-II）、**画像推荐**（偏好评分排序）。全链通过磁盘缓存将首次 131s 的权重计算压缩到后续 <1s。

## 1. 四维边权模型

每条街道段 `e` 有四维指标（来自街景 VLM 指标经 KD-Tree 空间传播）：

| 维度 | 边属性 | 含义 |
|---|---|---|
| 安全性 | `w_safety` | 骑行道类型、物理隔离、机动车压力等 8 项加权 |
| 舒适度 | `w_comfort` | 路面质量、坑洼、障碍、骑行宽度等 10 项加权 |
| 风景 | `w_scenery` | 绿视率、树荫、开阔度、水景、美观度等 12 项加权 |
| 综合成本 | `cost_composite` | 安全/舒适/风景/体验 加权融合（0.30/0.25/0.25/0.20）|

```
cost_composite(e) = α·(1−w_safety) + β·(1−w_comfort) + γ·(1−w_scenery) + δ·(1−pref_score)
```
所有指标已归一化到 `[0,1]`，`cost_composite` 越低越好。

## 2. 画像定义

四种用户画像（`recommender.py` 中 `USER_TEMPLATES`）：

| 画像 | 安全权重 | 舒适权重 | 风景权重 | 最大绕行 | 特色 |
|---|---|---|---|---|---|
| commuter 通勤 | 0.5 | 0.3 | 0.1 | 1.3× | avoid_traffic |
| tourist 游客 | 0.2 | 0.2 | 0.5 | 2.0× | prefer_greenery |
| fitness 健身 | 0.3 | 0.2 | 0.3 | 2.5× | 高速 22km/h |
| family 家庭 | 0.6 | 0.3 | 0.1 | 1.2× | avoid_traffic + greenery |

## 3. 点对点直接搜索（direct_search）

对于每种画像，运行多个**加权变体**的 Dijkstra，去重后按画像偏好得分排序。

### 3.1 变体设计

每条边根据变体标签计算自定义权重 `w(e)`，越低越优先走该边：

```
w(e, "shortest")      = cost_composite
w(e, "shortest_len")  = length                    （纯距离最短）
w(e, "safe")          = cost * max(0.25, 2.5 − w_safety × 2.5)
w(e, "safety_first")  = cost * max(0.15, 3.5 − w_safety × 4.0)
w(e, "ultra_safe")    = cost * max(0.10, 4.0 − w_safety × 5.0)
w(e, "scenic")        = cost * max(0.25, 2.5 − w_scenery × 2.5)
w(e, "scenic_first")  = cost * max(0.15, 3.5 − w_scenery × 4.0)
w(e, "moderate_scenic") = cost * max(0.20, 2.8 − w_scenery × 3.0)    （中等绕行）
w(e, "long_scenic")   = cost * max(0.08, 4.0 − w_scenery × 5.0)     （大幅绕行）
w(e, "comfort")       = cost * max(0.25, 2.5 − w_comfort × 2.5)
w(e, "long_comfort")  = cost * max(0.10, 3.5 − w_comfort × 4.0)
w(e, "balance")       = cost * (1.8 − Σw_i·p_i)   （按画像权重线性平衡）
w(e, "leisure")       = cost * max(0.20, 3.0 − w_comfort×3.0 − w_scenery×1.5)
w(e, "long_ride")     = cost * max(0.30, 1.5 − w_comfort×0.8 − w_scenery×0.6)
w(e, "any_path")      = cost * 0.3                 （最大绕行，探索全图）
```

核心思想：某项指标得分越高，边的权重系数越小，Dijkstra 自然优先经过该类路段。系数范围 `[0.08, 2.5]` 可产生从最短路径到大幅绕行的连续变化。

### 3.2 各画像变体分配

| 画像 | 变体列表（按运行顺序） | 预期路线数 |
|---|---|---|
| commuter | `shortest`, `shortest_len` | 2 |
| tourist | `scenic_first`, `moderate_scenic`, `long_scenic`, `balance`, `shortest_len` | 5 |
| fitness | `long_ride`, `long_scenic`, `long_comfort`, `comfort`, `scenic`, `any_path` | 5 |
| family | `ultra_safe`, `safety_first`, `safe`, `shortest_len` | 4 |

### 3.3 去重与排序

1. 每个变体跑一次 Dijkstra（`networkx.shortest_path`），收集全部路线
2. 路线按节点数降序排列，若两路线共享边 ≥ 55% 则视为重复，保留较长的
3. 对去重后的路线调用 `compute_route_score(r, G, profile)`（画像偏好加权得分 + 绕行惩罚 + 骑行时长折扣），降序排序取 Top-K

### 3.4 坐标吸附

source/target 为地理坐标 `(lon, lat)` 时，调用 `_find_nearest_node(G, coord)` 吸附到最近图节点：
```python
if coord in G:                    # 已是节点键（int 或 tuple）→ 直接返回
    return coord
key = (round(lon, 6), round(lat, 6))
if key in G: return key           # 精确匹配
# 否则欧氏距离最近邻
```

### 3.5 复杂度

- 每个变体：O(E log V)（Dijkstra）
- 总复杂度：O(K × E log V)，K = 变体数（2~6）
- 2376 条边、1225 个节点，单变体 < 0.1s，全画像 < 0.5s

## 4. NSGA-II 多目标搜索（可选）

通过 `pipeline.run(force_nsga2=True)` 启用。NSGA-II 同时优化四个目标：

```
f1: 总距离       （最小化）
f2: 总交通压力    （最小化）
f3: −总风景      （风景最大化 → 取负最小化）
f4: −总偏好得分   （偏好最大化 → 取负最小化）
```

参数：种群 100、50 代、变异率 0.2。产生 Pareto 最优路线集，再经 `recommend_route` 按画像偏好评分选出最优路线。

NSGA-II 约 2~5s（不含权重计算），路线质量更高但非实时（≈137s 含全链）。默认关闭，推荐用 direct_search。

## 5. 磁盘缓存

首次运行 pipeline 时自动将 Stage3（权重计算后的 segments GeoDataFrame）保存为 GPKG：

```
database/processed/segments_weighted.gpkg  (1.3MB)
```

后续 `pipeline.run()` 检测到缓存存在时跳过 Stage 1/2/3，直接加载加权 segments 并进入 Stage5 搜索。

| 阶段 | 缓存未命中 | 缓存命中 |
|---|---|---|
| Stage 1 数据加载 | ~5s | 跳过 |
| Stage 2 异构图构建 | ~30s | 跳过 |
| Stage 3 权重计算 | ~95s | 跳过 |
| Stage 5 路径搜索 | <1s | <1s |
| **合计** | **~131s** | **<1s** |

缓存预热：`python database/scripts/warm_cache.py`（只需一次）。缓存失效：删除 `segments_weighted.gpkg` 后下次运行自动重建。

## 6. 数据流总览

```
database/bikeflow.sqlite
  │ read_streetview / read_poi / read_stations / read_segments / read_buildings
  ▼
algorithm/data/*_loader.py           ← 数据库优先，文件回退
  │
  ▼
algorithm/graph/hetero_builder.py    ← 5类节点6类边异构图（可选）
algorithm/weights/edge_weights.py    ← 四维边权计算
  │
  ▼  save → database/processed/segments_weighted.gpkg
  │  load ← (缓存命中跳过前两步)
  ▼
algorithm/routing/direct_search.py   ← Dijkstra 多变体搜索
  │
  ▼
gateway/api/routes.py                ← REST API (/api/routes/search)
  │
  ▼
frontend/src/rendering/Scene3DView   ← Three.js 管状路线渲染
```
