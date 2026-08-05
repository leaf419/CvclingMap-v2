"""缓存命中冒烟：四画像直接搜索（均走缓存）"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from algorithm.pipeline import BikeFlowPipeline

TEMPLATES = ["commuter", "tourist", "fitness", "family"]
SOURCE = (116.36, 39.91)
TARGET = (116.46, 39.93)  # 更远 OD（西城→朝阳，~10km），验证不同长度路线

def main():
    for tmpl in TEMPLATES:
        t0 = time.time()
        p = BikeFlowPipeline()
        r = p.run(source=SOURCE, target=TARGET, user_template=tmpl, skip_gnn=True)
        dur = time.time() - t0
        print(f"[{tmpl:>9}]  {len(r.pareto_routes)} routes  {dur:.1f}s")
        for i, route in enumerate(r.pareto_routes):
            print(f"  route-{i}: {len(route)} nodes, {route[0]} → ... → {route[-1]}")
    print("CACHE SMOKE OK")

if __name__ == "__main__":
    main()
