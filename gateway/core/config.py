"""FastAPI后端配置（含GeoScene Server连接配置）

环境变量前缀: BIKEFLOW_
示例: 复制项目根目录 .env.example 为 .env 后按需修改。
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

# 项目根目录（gateway/core/ -> 上三级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """后端应用配置"""

    # ── 应用配置 ──
    app_name: str = "BikeFlowGNN API"
    version: str = "2.0.0"
    debug: bool = False
    testing: bool = False

    # ── 网关监听配置（部署用）──
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000

    # ── 数据库配置（数据库层 database/cache/）──
    database_url: str = f"sqlite:///{(Path(__file__).resolve().parent.parent.parent / 'database' / 'cache' / 'bikeflow.db').as_posix()}"

    # ── CORS配置 ──
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    # ── 数据库层目录配置 ──
    data_dir: str = str(Path(__file__).resolve().parent.parent.parent / "database")
    output_dir: str = str(Path(__file__).resolve().parent.parent.parent / "database" / "output")

    # ── GeoScene Server配置（比赛合规：GIS核心服务）──
    geoscene_server_url: str = "https://localhost:6443/arcgis"
    geoscene_server_token: str = ""
    geoscene_service_segments: str = "BikeSegments_MapService"
    geoscene_service_stations: str = "BikeStations_MapService"
    geoscene_service_routes: str = "BikeRoutes_GeoCodeService"
    geoscene_service_scene3d: str = "Beijing3D_WebScene"

    # ── 天地图底图配置 ──
    tianditu_token: str = ""

    # ── 缓存配置 ──
    cache_ttl_hours: int = 24

    class Config:
        env_prefix = "BIKEFLOW_"
        # 优先读取项目根目录 .env（与 .env.example 模板对应）
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
