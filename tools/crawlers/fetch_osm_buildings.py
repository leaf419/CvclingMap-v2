"""从 Overpass API 获取北京城区建筑轮廓 GeoJSON

比赛说明：此脚本用于生成 3D 演示底图。正式比赛提交时，
建筑数据来源应为 GeoScene Pro 导出的中国境内合规数据。
"""
import json
import time
import requests
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "database" / "output"

# 多端点轮转
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# 北京六区全覆盖 (海淀/朝阳/丰台/西城/东城/石景山)
# 0.055° × 0.055° tiles (~6km × 5km) to avoid timeout
QUERIES = [
    (39.79,116.17,39.845,116.225),
    (39.79,116.225,39.845,116.28),
    (39.79,116.28,39.845,116.335),
    (39.79,116.335,39.845,116.39),
    (39.79,116.39,39.845,116.445),
    (39.79,116.445,39.845,116.5),
    (39.79,116.5,39.845,116.55),
    (39.845,116.17,39.9,116.225),
    (39.845,116.225,39.9,116.28),
    (39.845,116.28,39.9,116.335),
    (39.845,116.335,39.9,116.39),
    (39.845,116.39,39.9,116.445),
    (39.845,116.445,39.9,116.5),
    (39.845,116.5,39.9,116.55),
    (39.9,116.17,39.955,116.225),
    (39.9,116.225,39.955,116.28),
    (39.9,116.28,39.955,116.335),
    (39.9,116.335,39.955,116.39),
    (39.9,116.39,39.955,116.445),
    (39.9,116.445,39.955,116.5),
    (39.9,116.5,39.955,116.55),
    (39.955,116.17,40.01,116.225),
    (39.955,116.225,40.01,116.28),
    (39.955,116.28,40.01,116.335),
    (39.955,116.335,40.01,116.39),
    (39.955,116.39,40.01,116.445),
    (39.955,116.445,40.01,116.5),
    (39.955,116.5,40.01,116.55),
    (40.01,116.17,40.02,116.225),
    (40.01,116.225,40.02,116.28),
    (40.01,116.28,40.02,116.335),
    (40.01,116.335,40.02,116.39),
    (40.01,116.39,40.02,116.445),
    (40.01,116.445,40.02,116.5),
    (40.01,116.5,40.02,116.55),
]

def fetch_buildings(south, west, north, east, label="area", endpoint_idx=0):
    """从 Overpass API 获取指定 bbox 内的建筑"""
    query = f"""[out:json][timeout:60];
(
  way["building"]({south},{west},{north},{east});
);
out body geom;
"""
    query = query.strip().replace("\n", "")
    url = f"{ENDPOINTS[endpoint_idx % len(ENDPOINTS)]}?data={requests.utils.quote(query)}"
    print(f"[OSM] 查询 {label}: ({south},{west}) -> ({north},{east})")

    try:
        resp = requests.get(url, timeout=60,
                            headers={"User-Agent": "BikeFlowGNN/3.0 (academic project)"})
        if resp.status_code == 429:
            raise Exception("429 Too Many Requests")
        resp.raise_for_status()
        data = resp.json()
        elements = data.get("elements", [])
        print(f"[OSM] {label}: {len(elements)} 个元素")
        return elements
    except Exception as e:
        if endpoint_idx + 1 < len(ENDPOINTS):
            print(f"  端点{endpoint_idx}失败({e}), 尝试备用...")
            time.sleep(5)
            return fetch_buildings(south, west, north, east, label, endpoint_idx + 1)
        raise


def osm_to_geojson(all_elements):
    """将 OSM elements 转为 GeoJSON FeatureCollection"""
    features = []
    seen = set()

    for el in all_elements:
        wid = el.get("id")
        if wid in seen:
            continue
        seen.add(wid)

        tags = el.get("tags", {})
        geom = el.get("geometry")
        if not geom:
            continue

        # OSM 格式兼容: 可能是 [{lat,lon},...] 或 [[lon,lat],...] 或 dict
        if isinstance(geom, list):
            coords = geom
            # 检查第一个元素是否是 {lat,lon} dict → 转为 [lon,lat]
            if coords and isinstance(coords[0], dict) and 'lat' in coords[0]:
                coords = [[c['lon'], c['lat']] for c in coords]
        else:
            geom_type = geom.get("type", "Polygon")
            coords = geom.get("coordinates", [])
        geom_type = "Polygon"

        # 提取高度信息
        height = None
        levels = tags.get("building:levels")
        if levels:
            try:
                height = float(levels) * 3
            except ValueError:
                pass
        if not height:
            h_tag = tags.get("height")
            if h_tag:
                try:
                    height = float(h_tag.replace("m", "").strip())
                except ValueError:
                    pass
        if not height:
            # 根据建筑类型估算
            btype = tags.get("building", "yes")
            if btype in ("apartments", "residential", "dormitory"):
                height = 18
            elif btype in ("office", "commercial", "hotel"):
                height = 30
            elif btype in ("school", "hospital", "university"):
                height = 12
            elif btype in ("house", "detached", "bungalow"):
                height = 6
            else:
                height = 9

        features.append({
            "type": "Feature",
            "properties": {
                "osm_id": wid,
                "height_m": height,
                "building": tags.get("building", "yes"),
                "name": tags.get("name", ""),
            },
            "geometry": {
                "type": geom_type,
                "coordinates": coords,
            },
        })

    return {"type": "FeatureCollection", "features": features}


def main():
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "beijing_buildings_osm.geojson"

    # ── 加载已有数据（增量累积）──
    existing_ids = set()
    existing_features = []
    if out_path.exists():
        try:
            with open(out_path) as f:
                old_geo = json.load(f)
            for feat in old_geo.get("features", []):
                oid = feat["properties"].get("osm_id")
                if oid and oid not in existing_ids:
                    existing_ids.add(oid)
                    existing_features.append(feat)
            print(f"[OSM] 已有 {len(existing_features)} 栋建筑（增量模式）")
        except Exception as e:
            print(f"[OSM] 读取已有数据失败: {e}，将重新抓取")

    # ── 本次抓取 ──
    all_elements = []
    for south, west, north, east in QUERIES:
        for attempt in range(3):  # 504 超时重试
            try:
                elements = fetch_buildings(south, west, north, east,
                                           f"({south},{west})-({north},{east})")
                all_elements.extend(elements)
                break
            except Exception as e:
                if attempt < 2:
                    wait = (attempt + 1) * 15
                    print(f"  重试 {attempt+1}/2 (等 {wait}s)...")
                    time.sleep(wait)
                else:
                    print(f"[OSM] 区域 ({south},{west}) 三次失败: {e}")
        time.sleep(12)  # rate limit

    # ── 合并新旧数据 ──
    new_geojson = osm_to_geojson(all_elements)
    added = 0
    for feat in new_geojson["features"]:
        oid = feat["properties"].get("osm_id")
        if oid and oid not in existing_ids:
            existing_ids.add(oid)
            existing_features.append(feat)
            added += 1

    merged = {"type": "FeatureCollection", "features": existing_features}

    # ── 保存 ──
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)
    print(f"[OSM] 本次新增 {added} 栋 | 累计 {len(existing_features)} 栋 | {out_path.stat().st_size / 1024:.0f} KB")

    # ── 自动同步到 buildings.geojson ──
    bld_path = OUTPUT_DIR / "buildings.geojson"
    with open(bld_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)
    print(f"[OSM] 已同步 → {bld_path}")


if __name__ == "__main__":
    main()
