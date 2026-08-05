"""GeoScene Enterprise Server 客户端 — 网关层 GIS 能力代理

比赛合规核心（C 组 GIS 应用开发组，规则第 5 条）：
服务器端部署必须基于 GeoScene 服务器端产品。
本客户端负责：
    - 探测 GeoScene Enterprise Server 可用性（REST /rest/info）
    - 校验地图/场景/地理编码服务是否已发布（REST /rest/services）
    - 暴露服务端点供渲染层（前端）加载
    - GeoScene 不可用时回退本地静态数据（开发模式），保证开发环境可运行

渲染层加载策略：
    - GeoScene 可用：前端经网关 /api/geoscene/proxy 代理加载已发布服务（GIS 核心服务）
    - 不可用：前端加载 /data/*.geojson（本地回退，开发模式）
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

from gateway.core.config import settings

logger = logging.getLogger(__name__)

# 服务类型映射（key -> REST 服务类型，供渲染层加载）
SERVICE_TYPES = {
    "segments": "MapServer",
    "stations": "MapServer",
    "routes": "GeoCodeServer",
    "scene3d": "SceneServer",
}

# 渲染层可能引用的 GeoScene 服务清单（对应 tools/geoscene/ 发布配置）
SERVICE_NAMES = {
    "segments": settings.geoscene_service_segments,
    "stations": settings.geoscene_service_stations,
    "routes": settings.geoscene_service_routes,
    "scene3d": settings.geoscene_service_scene3d,
}


class GeoSceneClient:
    """GeoScene Enterprise Server REST 客户端"""

    def __init__(self, server_url: Optional[str] = None, token: Optional[str] = None):
        self.server_url = (server_url or settings.geoscene_server_url).rstrip("/")
        self.token = token if token is not None else settings.geoscene_server_token
        self._cache_available: Optional[bool] = None

    def is_available(self, force: bool = False) -> bool:
        """GeoScene Server 是否可达（结果缓存，force 时重新探测）"""
        if self._cache_available is not None and not force:
            return self._cache_available
        try:
            resp = requests.get(f"{self.server_url}/rest/info?f=json", timeout=3)
            ok = resp.status_code == 200 and "currentVersion" in resp.text
        except Exception:
            ok = False
        self._cache_available = ok
        logger.info(f"GeoScene Server {'available' if ok else 'unavailable'}: {self.server_url}")
        return ok

    def service_url(self, service_name: str, service_type: str = "MapServer") -> str:
        """构造服务 REST URL（供渲染层直接加载）"""
        return f"{self.server_url}/rest/services/{service_name}/{service_type}"

    def check_service(self, name: str, service_type: str = "MapServer") -> dict:
        """校验单个服务是否已发布（REST /rest/services/<name>/<type>）

        Returns:
            {"name", "type", "url", "available", "error"}
        """
        url = self.service_url(name, service_type)
        if not self.is_available():
            return {
                "name": name, "type": service_type, "url": url,
                "available": False,
                "error": "GeoScene Server 不可达",
            }
        try:
            resp = requests.get(
                f"{url}?f=json",
                params={"token": self.token} if self.token else None,
                timeout=5,
            )
            payload = resp.json()
            ok = resp.status_code == 200 and "error" not in payload
            return {
                "name": name, "type": service_type, "url": url,
                "available": ok,
                "error": None if ok else "服务未发布或需要 Token",
                "serviceType": payload.get("serviceDescription", "") if ok else "",
            }
        except Exception as e:
            return {
                "name": name, "type": service_type, "url": url,
                "available": False,
                "error": str(e),
            }

    def services_status(self) -> dict:
        """全部服务发布状态（供 /api/geoscene/status 与渲染层回退判断）"""
        results = {}
        for key, name in SERVICE_NAMES.items():
            svc_type = SERVICE_TYPES.get(key, "MapServer")
            results[key] = self.check_service(name, svc_type)
        return results

    def status(self) -> dict:
        """GeoScene 集成状态（供 /api/geoscene/status 端点）"""
        available = self.is_available()
        base = {
            "available": available,
            "mode": "geoscene" if available else "local-fallback",
            "server": self.server_url,
            "tiandituToken": settings.tianditu_token or "",
            "note": (
                "GeoScene Enterprise Server 可达：渲染层经 GIS 服务加载"
                if available else
                "GeoScene 不可达：渲染层回退本地 /data 静态数据（开发模式）"
            ),
        }
        base["services"] = self.services_status()
        return base


geoscene_client = GeoSceneClient()
