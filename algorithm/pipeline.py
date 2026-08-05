"""BikeFlowGNN v2 全流程管道编排

五阶段流水线:
    Stage 1: 多源数据加载 (街景/POI/站点/天地图底图)
    Stage 2: 5类节点6类边异构图构建 (city2graph)
    Stage 3: 街景指标传播 + 四维边权模型
    Stage 4: GNN偏好学习 (可选)
    Stage 5: 路径搜索 + 个性化推荐 + 可视化导出
"""
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

import geopandas as gpd
import networkx as nx

from algorithm.config import BASE_DIR, DATA_DIR, WEIGHT_CFG, NSGA2_CFG
from algorithm.data.streetview_loader import load_and_process_streetview
from algorithm.data.poi_loader import load_and_process_poi
from algorithm.data.station_loader import load_stations
from algorithm.data.basemap_loader import load_basemap_data
from algorithm.graph.hetero_builder import build_hetero_graph
from algorithm.graph.metric_propagation import propagate_metrics_to_segments
from algorithm.weights.edge_weights import compute_all_weights
from algorithm.weights.cost_fusion import fuse_composite_cost
from algorithm.routing.nsga2_search import build_nx_graph, nsga2_search
from algorithm.routing.direct_search import direct_search
from algorithm.routing.recommender import recommend_route, USER_TEMPLATES
from rendering.export.geoscene_export import (
    export_segments_geojson, export_stations_geojson, export_buildings_geojson, export_scene_config,
)
from rendering.export.route_overlay import export_routes_geojson

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
        pipeline = BikeFlowPipeline(data_dir="/path/to/data", output_dir="/path/to/output")
        result = pipeline.run(source=(116.36, 39.91), target=(116.42, 39.93), user_template="commuter")
    """

    def __init__(self, data_dir: str = None, output_dir: str = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.output_dir = Path(output_dir) if output_dir else (BASE_DIR / "database" / "output")
        self._segments_gdf = None
        self._obs_gdf = None
        self._poi_gdf = None
        self._stations_gdf = None
        self._buildings_gdf = None
        self._hetero_graph = None
        self._nx_graph = None
        self._cache_hit = False

    # ── 缓存路径 ──
    @property
    def _weighted_cache_path(self) -> Path:
        return BASE_DIR / "database" / "processed" / "segments_weighted.gpkg"

    def _try_load_weighted_cache(self) -> bool:
        """尝试从磁盘缓存加载 stage3 权重计算后的 segments_gdf"""
        if not self._weighted_cache_path.exists():
            return False
        try:
            self._segments_gdf = gpd.read_file(self._weighted_cache_path)
            if len(self._segments_gdf) > 0:
                logger.info(f"Cache hit: loaded {len(self._segments_gdf)} weighted segments")
                self._cache_hit = True
                return True
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")
        return False

    def _save_weighted_cache(self) -> None:
        """保存 stage3 后的 segments_gdf 到磁盘缓存"""
        if self._segments_gdf is not None:
            self._weighted_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._segments_gdf.to_file(self._weighted_cache_path, driver="GPKG")
            logger.info(f"Cached weighted segments → {self._weighted_cache_path}")

    def stage1_load_data(self) -> tuple:
        """阶段1：加载街景指标、POI、站点、天地图底图数据"""
        logger.info("=== Stage 1: Data Loading ===")
        self._obs_gdf = load_and_process_streetview()
        logger.info(f"  Streetview: {len(self._obs_gdf)} observations")
        self._poi_gdf = load_and_process_poi()
        logger.info(f"  POI: {len(self._poi_gdf)}")
        self._stations_gdf = load_stations()
        logger.info(f"  Stations: {len(self._stations_gdf)}")
        self._segments_gdf, self._buildings_gdf = load_basemap_data()
        logger.info(f"  Segments: {len(self._segments_gdf)}, Buildings: {len(self._buildings_gdf)}")

        return (self._obs_gdf, self._poi_gdf, self._stations_gdf,
                self._segments_gdf, self._buildings_gdf)

    def stage2_build_graph(
        self,
        segments_gdf: gpd.GeoDataFrame,
        obs_gdf: gpd.GeoDataFrame,
        poi_gdf: gpd.GeoDataFrame,
        station_gdf: gpd.GeoDataFrame,
        buildings_gdf: gpd.GeoDataFrame,
        max_poi: int = 10000,
    ):
        """阶段2：构建5类节点6类边异构图（POI抽样以控制规模）"""
        logger.info("=== Stage 2: Heterogeneous Graph ===")
        if max_poi and len(poi_gdf) > max_poi:
            poi_gdf = poi_gdf.sample(max_poi, random_state=42).reset_index(drop=True)
            logger.info(f"  POI sampled to {len(poi_gdf)}")
        self._hetero_graph = build_hetero_graph(
            segments_gdf, buildings_gdf, poi_gdf, station_gdf, obs_gdf,
        )
        logger.info(f"  {self._hetero_graph.summary()}")
        return self._hetero_graph

    def stage3_compute_weights(
        self,
        segments_gdf: gpd.GeoDataFrame,
        obs_gdf: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        """阶段3：街景指标传播 + 四维边权计算"""
        logger.info("=== Stage 3: Weights ===")
        segments = propagate_metrics_to_segments(obs_gdf, segments_gdf)
        obs_count = segments["has_observation"].sum() if "has_observation" in segments.columns else len(segments)
        logger.info(f"  Propagated metrics to {obs_count}/{len(segments)} segments")
        segments = compute_all_weights(segments)
        segments = fuse_composite_cost(segments)
        self._segments_gdf = segments
        logger.info("  Weights computed")
        return segments

    def stage5_search(
        self,
        segments_gdf: gpd.GeoDataFrame,
        stations_gdf: gpd.GeoDataFrame,
        source: tuple,
        target: tuple,
        user_template: str = "commuter",
        use_nsga2: bool = False,
    ) -> PipelineResult:
        """阶段5：路径搜索 + 个性化推荐 + 导出

        Args:
            use_nsga2: True 时走 NSGA-II 多目标搜索（高质量，分钟级）；
                       False 时走直接 Dijkstra 多变体搜索（秒级，commuter 点对点）
        """
        logger.info("=== Stage 5: Search & Export ===")

        G = build_nx_graph(segments_gdf)
        self._nx_graph = G
        logger.info(f"  NX graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        if use_nsga2:
            pareto_routes = nsga2_search(G, source=source, target=target)
            logger.info(f"  NSGA-II Pareto routes: {len(pareto_routes)}")
            profile = USER_TEMPLATES.get(user_template, USER_TEMPLATES["commuter"])
            best_route = recommend_route(pareto_routes, G, profile, top_k=1)
            logger.info(f"  Best route: {len(best_route) if best_route else 0} nodes")
        else:
            pareto_routes, best_route = direct_search(
                G, source=source, target=target, user_template=user_template,
            )
            logger.info(f"  Direct routes: {len(pareto_routes)} (best: {len(best_route) if best_route else 0} nodes)")

        self.save_outputs(segments_gdf, stations_gdf, G, pareto_routes, best_route,
                          source=source, target=target)

        return PipelineResult(
            segments_gdf=segments_gdf,
            stations_gdf=stations_gdf,
            hetero_graph=self._hetero_graph,
            nx_graph=G,
            pareto_routes=pareto_routes,
            best_route=best_route,
            scene_config={"center": [source[0], source[1]], "template": user_template},
        )

    def save_outputs(
        self,
        segments_gdf: gpd.GeoDataFrame,
        stations_gdf: gpd.GeoDataFrame,
        nx_graph: nx.Graph,
        pareto_routes: List[list],
        best_route: Optional[list] = None,
        source: tuple = None,
        target: tuple = None,
    ) -> None:
        """保存所有可视化输出"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        export_segments_geojson(segments_gdf, str(self.output_dir / "segments.geojson"))
        export_stations_geojson(stations_gdf, str(self.output_dir / "stations.geojson"))
        # 构建路段坐标查找表，使路线贴路网而非直线
        seg_lookup = {}
        if "seg_id" in segments_gdf.columns:
            for _, row in segments_gdf.iterrows():
                if row.geometry and hasattr(row.geometry, "coords"):
                    seg_lookup[row["seg_id"]] = [(c[0], c[1]) for c in row.geometry.coords]
        export_routes_geojson(pareto_routes, nx_graph, str(self.output_dir / "routes.geojson"),
                              seg_id_to_coords=seg_lookup, source=source, target=target)
        if self._buildings_gdf is not None:
            export_buildings_geojson(self._buildings_gdf, str(self.output_dir / "buildings.geojson"))
        export_scene_config(
            str(self.output_dir / "scene_config.json"),
            center_lon=116.40, center_lat=39.92,
        )

    def run(
        self,
        source: Tuple[float, float],
        target: Tuple[float, float],
        user_template: str = "commuter",
        skip_gnn: bool = True,
        force_nsga2: bool = False,
    ) -> PipelineResult:
        """运行完整管道（首次运行 ~100s 含缓存生成，后续命中缓存 <2s）"""
        logger.info("=" * 60)
        logger.info("BikeFlowGNN v2 Pipeline")
        logger.info("=" * 60)

        if self._try_load_weighted_cache():
            # 缓存命中：跳过 stage1/2/3，直接从数据库轻量加载 stations/buildings
            logger.info("Cache hit — skipping stage 1/2/3")
            self._stations_gdf = load_stations()
            _, self._buildings_gdf = load_basemap_data()
            segments_gdf = self._segments_gdf
        else:
            obs_gdf, poi_gdf, stations_gdf, segments_gdf, buildings_gdf = self.stage1_load_data()
            self.stage2_build_graph(segments_gdf, obs_gdf, poi_gdf, stations_gdf, buildings_gdf)
            segments_gdf = self.stage3_compute_weights(segments_gdf, obs_gdf)
            self._save_weighted_cache()

        result = self.stage5_search(segments_gdf, self._stations_gdf,
                                     source, target, user_template,
                                     use_nsga2=force_nsga2)

        logger.info("=" * 60)
        logger.info(f"Complete: {len(result.pareto_routes)} routes (cache={'hit' if self._cache_hit else 'miss'})")
        logger.info("=" * 60)
        return result
