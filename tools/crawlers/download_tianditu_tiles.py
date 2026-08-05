"""下载天地图卫星影像瓦片，拼接为北京区域地面纹理

需通过环境变量 TIANDITU_TOKEN 配置天地图开发者 token。
"""
import math
import os
import requests
from PIL import Image
from io import BytesIO
from pathlib import Path

TOKEN = os.environ.get("TIANDITU_TOKEN", "")  # 天地图开发者 token（环境变量注入，避免源码泄露）
OUTPUT_DIR = Path(__file__).parent.parent.parent / "database" / "output"

# 北京六区范围
MIN_LON, MAX_LON = 116.19, 116.48
MIN_LAT, MAX_LAT = 39.83, 39.99
ZOOM = 12
TILE_SIZE = 256


def lon2tile(lon, zoom):
    return math.floor((lon + 180) / 360 * (2 ** zoom))


def lat2tile(lat, zoom):
    lat_rad = math.radians(lat)
    return math.floor((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * (2 ** zoom))


def tile2lon(x, z):
    return x / (2 ** z) * 360 - 180


def tile2lat(y, z):
    n = math.pi - 2 * math.pi * y / (2 ** z)
    return math.degrees(math.atan(math.sinh(n)))


def main():
    if not TOKEN:
        print("[tianditu] 未配置 TIANDITU_TOKEN 环境变量，请先设置天地图开发者 token")
        return
    x0 = lon2tile(MIN_LON, ZOOM)
    x1 = lon2tile(MAX_LON, ZOOM)
    y0 = lat2tile(MAX_LAT, ZOOM)  # 注意：y 越大越靠南
    y1 = lat2tile(MIN_LAT, ZOOM)

    cols = x1 - x0 + 1
    rows = y1 - y0 + 1
    print(f"北京区域 ZOOM={ZOOM}: {cols}×{rows} = {cols*rows} 张瓦片")

    canvas = Image.new("RGB", (cols * TILE_SIZE, rows * TILE_SIZE))
    base_url = "https://t0.tianditu.gov.cn/img_w/wmts"

    for ri in range(rows):
        for ci in range(cols):
            tx = x0 + ci
            ty = y0 + ri
            url = (f"{base_url}?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
                   f"&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles"
                   f"&TILEMATRIX={ZOOM}&TILEROW={ty}&TILECOL={tx}&tk={TOKEN}")
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200 and len(resp.content) > 100:
                    tile = Image.open(BytesIO(resp.content))
                    canvas.paste(tile, (ci * TILE_SIZE, ri * TILE_SIZE))
                    print(f"  [{ri+1}/{rows},{ci+1}/{cols}] OK", end="\r")
                else:
                    print(f"  [{ri+1},{ci+1}] HTTP {resp.status_code}")
            except Exception as e:
                print(f"  [{ri+1},{ci+1}] 失败: {e}")

    # 保存
    out_path = OUTPUT_DIR / "beijing_satellite.png"
    canvas.save(out_path)
    print(f"\n已保存 → {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")

    # 计算实际地理范围（瓦片覆盖的精确bbox）
    actual_min_lon = tile2lon(x0, ZOOM)
    actual_max_lon = tile2lon(x1 + 1, ZOOM)
    actual_min_lat = tile2lat(y1 + 1, ZOOM)
    actual_max_lat = tile2lat(y0, ZOOM)
    print(f"影像覆盖: lon [{actual_min_lon:.4f}, {actual_max_lon:.4f}], lat [{actual_min_lat:.4f}, {actual_max_lat:.4f}]")
    print(f"图片尺寸: {canvas.size[0]}×{canvas.size[1]} px")


if __name__ == "__main__":
    main()
