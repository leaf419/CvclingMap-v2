"""抓取北京六区真实道路（海淀/朝阳/丰台/西城/东城/石景山）"""
import json
import time
import requests
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "database" / "output"

# 多端点轮转，避免单点限流
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# 六区全覆盖 0.06deg tiles (~6.7km) — 28 tiles
QUERIES = [
    (39.79,116.17,39.85,116.23),
    (39.79,116.23,39.85,116.29),
    (39.79,116.29,39.85,116.35),
    (39.79,116.35,39.85,116.41),
    (39.79,116.41,39.85,116.47),
    (39.79,116.47,39.85,116.53),
    (39.79,116.53,39.85,116.55),
    (39.85,116.17,39.91,116.23),
    (39.85,116.23,39.91,116.29),
    (39.85,116.29,39.91,116.35),
    (39.85,116.35,39.91,116.41),
    (39.85,116.41,39.91,116.47),
    (39.85,116.47,39.91,116.53),
    (39.85,116.53,39.91,116.55),
    (39.91,116.17,39.97,116.23),
    (39.91,116.23,39.97,116.29),
    (39.91,116.29,39.97,116.35),
    (39.91,116.35,39.97,116.41),
    (39.91,116.41,39.97,116.47),
    (39.91,116.47,39.97,116.53),
    (39.91,116.53,39.97,116.55),
    (39.97,116.17,40.02,116.23),
    (39.97,116.23,40.02,116.29),
    (39.97,116.29,40.02,116.35),
    (39.97,116.35,40.02,116.41),
    (39.97,116.41,40.02,116.47),
    (39.97,116.47,40.02,116.53),
    (39.97,116.53,40.02,116.55),
]


def normalize_coords(data):
    """递归转换 {lat,lon} dict -> [lon,lat]"""
    if isinstance(data, dict) and 'lat' in data and 'lon' in data:
        return [data['lon'], data['lat']]
    if isinstance(data, list):
        return [normalize_coords(x) for x in data]
    return data


def fetch(query_str, label="", endpoint_idx=0):
    """带端点回退的查询"""
    url = f"{ENDPOINTS[endpoint_idx % len(ENDPOINTS)]}?data={requests.utils.quote(query_str.strip().replace(chr(10), ''))}"
    try:
        resp = requests.get(url, timeout=45, headers={"User-Agent": "BikeFlowGNN/3.0"})
        if resp.status_code == 429:
            raise Exception("429 Too Many Requests")
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        print(f"[OSM] {label}: {len(elements)} 条")
        return elements
    except Exception as e:
        if endpoint_idx + 1 < len(ENDPOINTS):
            print(f"  端点{endpoint_idx}失败({e}), 尝试备用...")
            time.sleep(5)
            return fetch(query_str, label, endpoint_idx + 1)
        raise


def main():
    import sys
    sys.stdout.reconfigure(line_buffering=True)  # 实时输出
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 加载已有道路（增量累积）
    seg_path = OUTPUT_DIR / "segments.geojson"
    existing_ids = set()
    existing_features = []
    if seg_path.exists():
        try:
            with open(seg_path) as f:
                old = json.load(f)
            for feat in old.get("features", []):
                oid = feat["properties"].get("osm_id")
                if oid and oid not in existing_ids:
                    existing_ids.add(oid)
                    existing_features.append(feat)
            print(f"[OSM] 已有道路: {len(existing_features)} 条")
        except Exception as e:
            print(f"[OSM] 读取已有道路失败: {e}")

    # 抓取
    all_roads = []
    for i, (s, w, n, e) in enumerate(QUERIES):
        q = f"""[out:json][timeout:45];
(
  way["highway"]({s},{w},{n},{e});
);
out body geom;"""
        for attempt in range(2):
            try:
                all_roads.extend(fetch(q, f"道路 {i+1}/{len(QUERIES)} ({s},{w})"))
                break
            except Exception as ex:
                if attempt < 1:
                    wait = 20
                    print(f"  重试 (等{wait}s)...")
                    time.sleep(wait)
                else:
                    print(f"[OSM] 道路跳过: {ex}")
        time.sleep(15)  # 限流间隔

    # 转 GeoJSON（坐标归一化 + 去重）
    added = 0
    for el in all_roads:
        rid = el.get("id")
        if rid in existing_ids:
            continue
        existing_ids.add(rid)
        geom = el.get("geometry")
        if not geom:
            continue
        coords = geom if isinstance(geom, list) else geom.get("coordinates", [])
        coords = normalize_coords(coords)
        feat = {
            "type": "Feature",
            "properties": {"osm_id": rid, "highway": el.get("tags", {}).get("highway", "road"),
                          "name": el.get("tags", {}).get("name", "")},
            "geometry": {"type": "LineString", "coordinates": coords},
        }
        existing_features.append(feat)
        added += 1

    print(f"\n道路: 本次新增 {added} 条 | 累计 {len(existing_features)} 条")

    roads_geo = {"type": "FeatureCollection", "features": existing_features}
    for p in [OUTPUT_DIR / "beijing_roads_osm.geojson", seg_path]:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(roads_geo, f, ensure_ascii=False)
    print(f"已保存 -> {seg_path} ({seg_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
