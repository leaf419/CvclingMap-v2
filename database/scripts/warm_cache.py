"""生成 segments 权重缓存（供后续快速搜索）

用法: python database/scripts/warm_cache.py
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from algorithm.pipeline import BikeFlowPipeline

CACHE = Path(__file__).resolve().parent.parent / "processed" / "segments_weighted.gpkg"

def main():
    if CACHE.exists():
        print(f"cache already exists: {CACHE} ({CACHE.stat().st_size} bytes)")
        return
    print("warming cache...")
    t0 = time.time()
    p = BikeFlowPipeline()
    p.run(source=(116.36, 39.91), target=(116.42, 39.93), user_template="commuter", skip_gnn=True)
    print(f"done: {time.time()-t0:.0f}s, cache={CACHE.exists()}")
    if CACHE.exists():
        print(f"cache size: {CACHE.stat().st_size} bytes")

if __name__ == "__main__":
    main()
