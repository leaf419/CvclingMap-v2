"""抓取北京城区真实道路网络"""
import json, time, requests
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "database" / "output"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

QUERIES = [
    (39.89, 116.34, 39.92, 116.37),
    (39.89, 116.37, 39.92, 116.40),
    (39.89, 116.40, 39.92, 116.43),
    (39.92, 116.34, 39.95, 116.37),
    (39.92, 116.37, 39.95, 116.40),
    (39.92, 116.40, 39.95, 116.43),
    (39.95, 116.29, 39.98, 116.32),
    (39.95, 116.32, 39.98, 116.35),
    (39.90, 116.43, 39.93, 116.46),
]

def fetch_roads(south, west, north, east, label=""):
    query = f"""[out:json][timeout:45];
(
  way["highway"]({south},{west},{north},{east});
);
out body geom;
"""
    query = query.strip().replace("\n", "")
    url = f"{OVERPASS_URL}?data={requests.utils.quote(query)}"
    resp = requests.get(url, timeout=60, headers={"User-Agent": "BikeFlowGNN/2.0"})
    resp.raise_for_status()
    elements = resp.json().get("elements", [])
    print(f"[OSM] {label}: {len(elements)} 条道路")
    return elements

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_elements = []

    for s, w, n, e in QUERIES:
        try:
            all_elements.extend(fetch_roads(s, w, n, e, f"({s},{w})-({n},{e})"))
            time.sleep(2)
        except Exception as ex:
            print(f"[OSM] 失败: {ex}")

    # 转为 GeoJSON
    features = []
    seen = set()
    for el in all_elements:
        rid = el.get("id")
        if rid in seen: continue
        seen.add(rid)
        tags = el.get("tags", {})
        geom = el.get("geometry")
        if not geom: continue
        if isinstance(geom, list):
            coords = geom
        else:
            coords = geom.get("coordinates", [])
        features.append({
            "type": "Feature",
            "properties": {
                "osm_id": rid,
                "highway": tags.get("highway", "road"),
                "name": tags.get("name", ""),
            },
            "geometry": {"type": "LineString", "coordinates": coords},
        })

    geojson = {"type": "FeatureCollection", "features": features}
    out_path = OUTPUT_DIR / "beijing_roads_osm.geojson"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    # 同时覆盖 segments.geojson
    seg_path = OUTPUT_DIR / "segments.geojson"
    with open(seg_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    print(f"总计 {len(features)} 条道路 → {out_path} ({out_path.stat().st_size/1024:.0f} KB)")
    print(f"已同步 → {seg_path}")


if __name__ == "__main__":
    main()
