"""业务逻辑层 — 调用algorithm层并管理缓存"""
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session

from gateway.core.config import settings
from gateway.db.models import RouteCache, RouteDetail

logger = logging.getLogger(__name__)


def _make_cache_key(source: list, target: list, user_template: str) -> str:
    key_str = f"{source[0]:.6f}_{source[1]:.6f}_{target[0]:.6f}_{target[1]:.6f}_{user_template}"
    return hashlib.md5(key_str.encode()).hexdigest()


async def get_cached_result(
    db: Session, source: list, target: list, user_template: str,
) -> Optional[Dict[str, Any]]:
    cache_key = _make_cache_key(source, target, user_template)
    now = datetime.utcnow()

    entry = db.query(RouteCache).filter(
        RouteCache.cache_key == cache_key, RouteCache.is_valid == True,
    ).first()

    if entry is None:
        return None
    if entry.expires_at and entry.expires_at < now:
        entry.is_valid = False
        db.commit()
        return None

    logger.info(f"Cache hit: {cache_key}")
    return json.loads(entry.result_json)


async def save_to_cache(
    db: Session, source: list, target: list, user_template: str,
    result: Dict[str, Any], duration_sec: float = 0.0,
) -> None:
    cache_key = _make_cache_key(source, target, user_template)
    now = datetime.utcnow()
    expires = now + timedelta(hours=settings.cache_ttl_hours)

    db.query(RouteCache).filter(RouteCache.cache_key == cache_key).delete()

    entry = RouteCache(
        cache_key=cache_key,
        source_lon=source[0], source_lat=source[1],
        target_lon=target[0], target_lat=target[1],
        user_template=user_template,
        result_json=json.dumps(result, ensure_ascii=False),
        created_at=now, expires_at=expires, is_valid=True,
        num_pareto_routes=len(result.get("routes", [])),
        pipeline_duration_sec=duration_sec,
    )
    db.add(entry)
    db.flush()

    for route in result.get("routes", []):
        metrics = route.get("metrics", {})
        db.add(RouteDetail(
            cache_id=entry.id, route_id=route.get("route_id", 0),
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
        ))

    db.commit()
    logger.info(f"Cached: {cache_key}")


async def run_pipeline(
    source: list, target: list, user_template: str, skip_gnn: bool = False,
) -> Dict[str, Any]:
    """运行算法管道"""
    import time
    from algorithm.pipeline import BikeFlowPipeline
    from rendering.export.route_overlay import compute_route_metrics_summary, expand_route_to_coords

    logger.info(f"Pipeline: {source} -> {target}, template={user_template}")
    start = time.time()

    pipeline = BikeFlowPipeline(data_dir=settings.data_dir, output_dir=settings.output_dir)
    result = pipeline.run(
        source=tuple(source), target=tuple(target),
        user_template=user_template, skip_gnn=skip_gnn,
    )
    duration = time.time() - start

    # 构建路段坐标查找表，使路线贴路网
    seg_lookup = {}
    if result.segments_gdf is not None and "seg_id" in result.segments_gdf.columns:
        for _, row in result.segments_gdf.iterrows():
            if row.geometry and hasattr(row.geometry, "coords"):
                seg_lookup[row["seg_id"]] = [(c[0], c[1]) for c in row.geometry.coords]

    routes = []
    for idx, route in enumerate(result.pareto_routes):
        if seg_lookup and result.nx_graph:
            coords = expand_route_to_coords(route, result.nx_graph, seg_lookup,
                                            source=tuple(source), target=tuple(target))
        else:
            coords = [[n[0], n[1]] if isinstance(n, tuple) else n for n in route]
        metrics = compute_route_metrics_summary(route, result.nx_graph) if result.nx_graph else {}
        routes.append({"route_id": idx, "coordinates": coords, "metrics": metrics})

    best_route_id = 0
    if result.best_route and result.pareto_routes:
        for idx, r in enumerate(result.pareto_routes):
            if r == result.best_route:
                best_route_id = idx
                break

    return {
        "routes": routes,
        "best_route_id": best_route_id,
        "scene_config": result.scene_config or {"center": [source[0], source[1]], "zoom": 14},
        "pipeline_duration_sec": round(duration, 2),
    }


async def search_routes(
    db: Session, source: list, target: list, user_template: str,
    use_cache: bool = True, skip_gnn: bool = False,
) -> Dict[str, Any]:
    """搜索路线（带缓存）"""
    if use_cache:
        cached = await get_cached_result(db, source, target, user_template)
        if cached is not None:
            cached["from_cache"] = True
            return cached

    result = await run_pipeline(source, target, user_template, skip_gnn)

    if use_cache:
        await save_to_cache(
            db, source, target, user_template,
            result, duration_sec=result.get("pipeline_duration_sec", 0),
        )

    result["from_cache"] = False
    return result


def get_route_detail(db: Session, route_id: int) -> Optional[Dict[str, Any]]:
    detail = db.query(RouteDetail).filter(RouteDetail.id == route_id).first()
    if detail is None:
        return None
    return {
        "route_id": detail.route_id, "is_best": detail.is_best,
        "coordinates": json.loads(detail.coordinates_json),
        "metrics": {
            "total_length": detail.total_length, "total_cost": detail.total_cost,
            "avg_safety": detail.avg_safety, "avg_comfort": detail.avg_comfort,
            "avg_scenery": detail.avg_scenery, "avg_traffic_stress": detail.avg_traffic_stress,
            "avg_beauty": detail.avg_beauty, "avg_pref_score": detail.avg_pref_score,
            "num_segments": detail.num_segments,
        },
    }
