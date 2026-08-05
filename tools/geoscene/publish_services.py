#!/usr/bin/env python
"""GeoScene Enterprise Server 服务发布脚本

将算法层产出的数据发布为 GeoScene Server 地图服务，
满足比赛"服务器端部署必须基于GeoScene"的强制要求。

前置条件:
    1. GeoScene Enterprise Server 已运行 (默认 https://localhost:6443/arcgis)
    2. 比赛组委会已提供 Server Token (填入 GEOSCENE_SERVER_TOKEN)
    3. 底图使用天地图数据（比赛推荐）

发布服务:
    - BikeSegments_MapService (街道段地图服务)
    - BikeStations_MapService (停车点地图服务)
    - BikeRoutes_GeoCodeService (路线地理编码服务)
    - Beijing3D_WebScene (3D场景服务)
"""
import os
import sys
import json
import logging
import argparse
import requests
from pathlib import Path

# 处理路径兼容: 从 tools/geoscene/ 上三级到项目根
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from algorithm.config import (
    GEOSCENE_SERVER_URL, GEOSCENE_SERVER_TOKEN, GEOSCENE_SERVICE_NAMES,
)
from rendering.export.geoscene_export import (
    export_segments_geojson, export_stations_geojson, export_scene_config,
)
from rendering.export.route_overlay import export_routes_geojson
from tools.geoscene.build_fgdb import build_fgdb, GDB_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── 配置文件路径 ──
GEO_DIR = Path(__file__).parent
SERVICES_DIR = GEO_DIR / "services"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "database" / "output"


def load_service_config(service_name: str) -> dict:
    """加载服务配置JSON"""
    cfg_path = SERVICES_DIR / f"{service_name}.json"
    if not cfg_path.exists():
        logger.warning(f"服务配置不存在: {cfg_path}, 使用默认配置")
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _headers(token: str = None):
    h = {"Content-Type": "application/x-www-form-urlencoded"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def publish_map_service(service_name: str, geo_path: str, service_type: str = "MapServer"):
    """向 GeoScene Server 发布地图服务

    参考 ArcGIS Server REST API:
    https://developers.arcgis.com/rest/enterprise-administration/server/create-service.htm

    Args:
        service_name: 服务名称 (如 BikeSegments_MapService)
        geo_path: GeoJSON 文件路径 (将作为服务的初始数据源)
        service_type: 服务类型 (MapServer / GeoCodeServer)
    """
    logger.info(f"发布服务: {service_name} ({service_type})")
    logger.info(f"  数据源: {geo_path}")

    token = GEOSCENE_SERVER_TOKEN
    server_url = GEOSCENE_SERVER_URL.rstrip("/")

    if not token:
        logger.warning("GEOSCENE_SERVER_TOKEN 未配置，将尝试匿名发布（开发环境）")

    # 1. 创建服务定义
    create_url = f"{server_url}/admin/services/createService"
    payload = {
        "serviceName": service_name,
        "type": service_type,
        "f": "json",
    }

    try:
        resp = requests.post(create_url, data=payload, headers=_headers(token), timeout=30)
        logger.info(f"  创建服务响应: {resp.status_code}")
        resp_json = resp.json()
        if "error" in resp_json:
            logger.error(f"  服务创建失败: {resp_json['error']}")
            return False
    except Exception as e:
        logger.error(f"  服务创建请求失败: {e}")
        logger.info("  [提示] 请在 GeoScene Pro 中手动发布服务，并参考 services/ 目录下的配置文件")
        return False

    logger.info(f"  ✓ 服务 {service_name} 创建成功")
    return True


def generate_all_outputs(output_dir: str = None):
    """生成所有可视化输出文件（供前端或 GeoScene Pro 导入）

    这一步运行在算法层完成之后，产出:
        - segments.geojson (街道段 → GeoScene Pro 导入 → File GDB)
        - stations.geojson (停车点 → GeoScene Pro 导入 → File GDB)
        - routes.geojson (路线叠加)
        - scene_config.json (3D场景配置)
    """
    if output_dir is None:
        output_dir = str(OUTPUT_DIR)

    logger.info(f"生成可视化输出到: {output_dir}")

    try:
        from algorithm.pipeline import BikeFlowPipeline
        logger.info("  运行全流程管道...")
        pipeline = BikeFlowPipeline(output_dir=output_dir)
        pipeline.stage1_load_data()
        pipeline.stage3_compute_weights(pipeline._segments_gdf, pipeline._obs_gdf)
        pipeline.save_outputs(
            pipeline._segments_gdf,
            pipeline._stations_gdf if hasattr(pipeline, '_stations_gdf') else None,
            None, [], None,
        )
        logger.info("  ✓ 可视化输出生成完成")
    except ImportError as e:
        logger.warning(f"  算法层不可用: {e}")
        logger.info("  [提示] 请先运行算法层 pipeline 生成 segments.geojson 等文件")


def check_services_status() -> dict:
    """检查 GeoScene Server 上各服务是否已发布（REST /rest/services）"""
    try:
        from gateway.service.geoscene_client import geoscene_client
    except ImportError:
        # 网关依赖缺失时用轻量 requests 探测
        return _check_services_lightweight()
    return geoscene_client.services_status()


def _check_services_lightweight() -> dict:
    """不依赖网关层的轻量检查"""
    server_url = GEOSCENE_SERVER_URL.rstrip("/")
    results = {}
    try:
        resp = requests.get(f"{server_url}/rest/info?f=json", timeout=5)
        available = resp.status_code == 200 and "currentVersion" in resp.text
    except Exception:
        available = False
    results["available"] = available
    results["services"] = {}
    for key, name in GEOSCENE_SERVICE_NAMES.items():
        svc_type = "SceneServer" if key == "scene3d" else (
            "GeoCodeServer" if key == "routes" else "MapServer"
        )
        url = f"{server_url}/rest/services/{name}/{svc_type}"
        results["services"][key] = {"name": name, "type": svc_type, "url": url}
        if available:
            try:
                r = requests.get(f"{url}?f=json", timeout=5)
                results["services"][key]["available"] = r.status_code == 200
            except Exception:
                results["services"][key]["available"] = False
    return results


def main():
    parser = argparse.ArgumentParser(description="GeoScene Enterprise 服务发布")
    parser.add_argument("--publish", action="store_true", help="发布服务到 GeoScene Server")
    parser.add_argument("--generate", action="store_true", help="仅生成 GeoJSON 输出文件")
    parser.add_argument("--check", action="store_true", help="检查服务发布状态")
    parser.add_argument("--build-gdb", action="store_true", help="构建 File Geodatabase（交付格式）")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="输出目录")
    parser.add_argument("--token", default=GEOSCENE_SERVER_TOKEN, help="GeoScene Server Token")

    args = parser.parse_args()

    if args.check:
        logger.info("=" * 60)
        logger.info("GeoScene Server 服务发布状态检查")
        logger.info("=" * 60)
        status = check_services_status()
        import json as _json
        logger.info(_json.dumps(status, ensure_ascii=False, indent=2))
        if not status.get("available"):
            logger.error("GeoScene Server 不可达，请先启动 GeoScene Enterprise Server")
        else:
            missing = [k for k, v in status.get("services", {}).items()
                       if not v.get("available")]
            if missing:
                logger.warning(f"未发布的服务: {missing}")
                logger.info("请运行发布流程（GeoScene Pro 手动发布或 --publish）")
            else:
                logger.info("✓ 所有 GIS 核心服务均已发布")
        return

    if args.build_gdb:
        logger.info("构建 File Geodatabase（比赛交付格式）...")
        build_fgdb(args.output_dir)
        return

    if args.generate:
        generate_all_outputs(args.output_dir)
        return

    if args.publish:
        logger.info("=" * 60)
        logger.info("GeoScene Enterprise Server 服务发布")
        logger.info("=" * 60)

        # 先确保输出文件存在
        generate_all_outputs(args.output_dir)

        # 构建 File Geodatabase（比赛推荐交付格式）
        logger.info("构建 File Geodatabase ...")
        build_fgdb(args.output_dir)

        # 发布服务
        services = [
            (GEOSCENE_SERVICE_NAMES.get("segments", "BikeSegments_MapService"),
             str(OUTPUT_DIR) + "/segments.geojson",
             "MapServer"),
            (GEOSCENE_SERVICE_NAMES.get("stations", "BikeStations_MapService"),
             str(OUTPUT_DIR) + "/stations.geojson",
             "MapServer"),
            (GEOSCENE_SERVICE_NAMES.get("routes", "BikeRoutes_GeoCodeService"),
             str(OUTPUT_DIR) + "/routes.geojson",
             "GeoCodeServer"),
        ]

        for svc_name, geo_path, svc_type in services:
            if Path(geo_path).exists():
                publish_map_service(svc_name, geo_path, svc_type)
            else:
                logger.warning(f"数据文件不存在，跳过服务 {svc_name}: {geo_path}")

        # 3D场景配置 (不需要发布到Server, 供SceneView直读)
        scene_cfg = str(OUTPUT_DIR) + "/scene_config.json"
        if Path(scene_cfg).exists():
            logger.info(f"3D场景配置已就绪: {scene_cfg}")
        else:
            export_scene_config(scene_cfg, 116.40, 39.92, zoom=14)

        logger.info("\n手动验证服务:")
        logger.info(f"  {GEOSCENE_SERVER_URL}/rest/services/BikeSegments_MapService/MapServer?f=json")
        logger.info(f"  {GEOSCENE_SERVER_URL}/rest/services/BikeStations_MapService/MapServer?f=json")

        return

    # 无参数时显示帮助
    parser.print_help()
    logger.info("\nGeoScene Pro 手动发布流程:")
    logger.info("  1. 打开 GeoScene Pro → 新建工程 → 地图")
    logger.info("  2. 添加数据 → 导入 segments.geojson 和 stations.geojson")
    logger.info("  3. 右键图层 → 共享 → 发布为 Web 图层")
    logger.info("  4. 选择 GeoScene Enterprise Server 连接")
    logger.info("  5. 配置服务参数参照 geoscene/services/ 目录下的 JSON")


if __name__ == "__main__":
    main()
