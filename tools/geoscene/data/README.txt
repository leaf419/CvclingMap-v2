# File Geodatabase 占位

本目录存放 GeoScene 比赛推荐的 File Geodatabase 数据文件。

## 使用方法

在 GeoScene Pro 中执行以下步骤：

1. 新建 File Geodatabase: `BikeFlowGNN.gdb`
2. 导入要素类:
   - `StreetSegments` (线要素，来自 output/segments.geojson)
   - `BikeStations` (点要素，来自 output/stations.geojson)
   - `Observations` (点要素，来自街景观测点数据)
3. 导入要素数据集:
   - `StreetNetwork/` (包含 StreetSegments + Junctions)
   - `POI/` (包含 BikeStations + Observations)
4. 空间参考: WGS84 (EPSG:4326)

## 比赛合规

- ✅ 数据存储采用 File Geodatabase（比赛推荐格式）
- ✅ 数据组织清晰：要素类 + 要素数据集
- ✅ 中国境内数据（北京六区）
