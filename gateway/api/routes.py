"""REST API路由"""
import logging
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, field_validator
from typing import List, Optional

from gateway.core.config import settings
from gateway.service.route_service import search_routes, get_route_detail
from gateway.service.geoscene_client import (
    geoscene_client, SERVICE_NAMES, SERVICE_TYPES,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["bikesearch"])

# ── 请求/响应模型 ──

VALID_TEMPLATES = {"commuter", "tourist", "fitness", "family"}

class RouteSearchRequest(BaseModel):
    source: List[float]
    target: List[float]
    user_template: str = "commuter"
    use_cache: bool = True
    skip_gnn: bool = False

    @field_validator("source", "target")
    @classmethod
    def validate_coords(cls, v):
        if len(v) != 2:
            raise ValueError("坐标必须是 [lon, lat] 格式")
        lon, lat = v
        if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
            raise ValueError("经纬度超出范围")
        return v

    @field_validator("user_template")
    @classmethod
    def validate_template(cls, v):
        if v not in VALID_TEMPLATES:
            raise ValueError(f"无效的用户模板: {v}")
        return v


class RouteMetrics(BaseModel):
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
    route_id: int
    coordinates: List[List[float]]
    metrics: RouteMetrics


class RouteSearchResponse(BaseModel):
    routes: List[RouteResult]
    best_route_id: int
    scene_config: dict
    from_cache: bool = False
    pipeline_duration_sec: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    version: str


TEMPLATE_INFO = {
    "commuter": {"name": "通勤者", "description": "高效安全，最短路径优先"},
    "tourist": {"name": "游客", "description": "风景优先，享受城市景观"},
    "fitness": {"name": "健身者", "description": "长距离骑行，适度绕路"},
    "family": {"name": "家庭", "description": "安全第一，低速慢骑"},
}


@router.get("/geoscene/status")
async def geoscene_status():
    """GeoScene Enterprise Server 集成状态（服务器端 GIS 能力代理）"""
    return geoscene_client.status()


@router.get("/geoscene/services")
async def geoscene_services():
    """已配置的 GeoScene 服务发布状态清单（供渲染层决定回退策略）"""
    return geoscene_client.services_status()


@router.get("/geoscene/proxy/{service}/{path:path}")
async def geoscene_proxy(service: str, path: str, request: Request):
    """反向代理 GeoScene 服务请求

    前端统一经网关加载 GeoScene 地图/场景服务，规避跨域与内网端口暴露问题。
    例如: /api/geoscene/proxy/segments/export?bbox=...&f=json
           → https://<server>/rest/services/BikeSegments_MapService/MapServer/export?...
    服务不可达时返回 503，前端据此回退本地 /data 数据。

    Args:
        service: 服务键名（segments / stations / routes / scene3d）
        path: 服务子路径（export / query / find / legend 等）
    """
    if service not in SERVICE_NAMES:
        raise HTTPException(status_code=404, detail=f"未知服务: {service}")

    service_name = SERVICE_NAMES[service]
    service_type = SERVICE_TYPES.get(service, "MapServer")
    base = f"{geoscene_client.server_url}/rest/services/{service_name}/{service_type}"

    if not geoscene_client.is_available():
        raise HTTPException(status_code=503, detail="GeoScene Server 不可达")

    # 组装目标 URL：透传请求参数并附加 token
    params = dict(request.query_params)
    if geoscene_client.token and "token" not in params:
        params["token"] = geoscene_client.token
    target = f"{base}/{path}?{urlencode(params)}"

    try:
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            resp = await client.request(
                request.method,
                target,
                headers={k: v for k, v in request.headers.items()
                         if k.lower() in {"accept", "content-type", "user-agent"}},
                content=await request.body() if request.method in {"POST", "PUT"} else None,
            )
    except httpx.HTTPError as e:
        logger.error(f"GeoScene 代理失败 {service}/{path}: {e}")
        raise HTTPException(status_code=502, detail=f"GeoScene 代理失败: {e}")

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", version=settings.version)


@router.get("/user-templates")
async def get_user_templates():
    return {
        "templates": [
            {"key": k, "name": v["name"], "description": v["description"]}
            for k, v in TEMPLATE_INFO.items()
        ]
    }


@router.post("/routes/search", response_model=RouteSearchResponse)
async def search_routes_endpoint(req: RouteSearchRequest, request: Request):
    db = request.app.state.db_session

    try:
        result = await search_routes(
            db=db, source=req.source, target=req.target,
            user_template=req.user_template,
            use_cache=req.use_cache, skip_gnn=req.skip_gnn,
        )
        return RouteSearchResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/routes/{route_id}")
async def get_route_endpoint(route_id: int, request: Request):
    db = request.app.state.db_session
    detail = get_route_detail(db, route_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="路线不存在")
    return detail
