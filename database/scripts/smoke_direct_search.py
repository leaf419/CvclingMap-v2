"""算法层端到端冒烟 — 四画像直接搜索 + 缓存验证"""
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from algorithm.pipeline import BikeFlowPipeline  # noqa: E402

TEMPLATES = ["commuter", "tourist", "fitness", "family"]
SOURCE = (116.36, 39.91)
TARGET = (116.42, 39.93)
CACHE_GPKG = PROJECT_ROOT / "database" / "processed" / "segments_weighted.gpkg"


def main() -> None:
    # 删除旧缓存（如有）以便验证生成
    if CACHE_GPKG.exists():
        CACHE_GPKG.unlink()
        print("old cache deleted")

    # ── 首次运行：生成缓存 ──
    t0 = time.time()
    p1 = BikeFlowPipeline()
    r1 = p1.run(source=SOURCE, target=TARGET, user_template="commuter", skip_gnn=True)
    t_first = time.time() - t0
    cache_fresh = CACHE_GPKG.exists()
    print(f"first run: {len(r1.pareto_routes)} routes, {t_first:.1f}s, cache_generated={cache_fresh}")

    # ── 第二次运行：缓存命中 ──
    t0 = time.time()
    p2 = BikeFlowPipeline()
    r2 = p2.run(source=SOURCE, target=TARGET, user_template="commuter", skip_gnn=True)
    t_cached = time.time() - t0
    print(f"cached run: {len(r2.pareto_routes)} routes, {t_cached:.1f}s")

    # ── 四画像（走缓存）──
    for tmpl in TEMPLATES:
        t1 = time.time()
        p = BikeFlowPipeline()
        result = p.run(source=SOURCE, target=TARGET, user_template=tmpl, skip_gnn=True)
        dur = time.time() - t1
        print(f"[{tmpl}] {len(result.pareto_routes)} routes, {dur:.1f}s")
        for i, r in enumerate(result.pareto_routes):
            print(f"  route-{i}: {len(r)} nodes")

    print(f"\nSMOKE OK — first={t_first:.1f}s  cached={t_cached:.1f}s")


if __name__ == "__main__":
    main()
