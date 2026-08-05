"""算法层端到端冒烟：从 database/bikeflow.sqlite 加载 → 构图 → 权重 → NSGA-II 搜索 → 导出

用法: python database/scripts/smoke_pipeline.py
"""
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from algorithm.pipeline import BikeFlowPipeline  # noqa: E402


def main() -> None:
    t0 = time.time()
    pipeline = BikeFlowPipeline()  # 默认 data_dir=database/，output_dir=database/output/
    result = pipeline.run(
        source=(116.36, 39.91),
        target=(116.42, 39.93),
        user_template="commuter",
        skip_gnn=True,
    )
    print("=" * 60)
    print(f"pareto_routes: {len(result.pareto_routes)}")
    print(f"best_route nodes: {len(result.best_route) if result.best_route else 0}")
    print(f"nx_graph: {result.nx_graph.number_of_nodes()} nodes / {result.nx_graph.number_of_edges()} edges")
    print(f"scene_config: {result.scene_config}")
    print(f"output_dir: {pipeline.output_dir}")
    for name in ["segments.geojson", "stations.geojson", "routes.geojson", "buildings.geojson", "scene_config.json"]:
        p = pipeline.output_dir / name
        print(f"  {name}: exists={p.exists()}")
    print(f"elapsed: {time.time() - t0:.1f}s")
    print("SMOKE OK")


if __name__ == "__main__":
    main()
