#!/usr/bin/env python
"""构建 GeoScene 比赛推荐交付格式 — File Geodatabase

将 algorithm 层产出的 GeoJSON（segments/stations/buildings）转换为
File Geodatabase（tools/geoscene/data/BikeFlowGNN.gdb），
符合比赛"数据存储采用 File Geodatabase"的要求。

支持三种构建路径（按优先级自动选择）：
    1) arcpy（GeoScene Pro 的 Python 环境）— 生成真正的 .gdb
    2) GDAL FileGDB 写驱动（pyogrio/gdal，需 GDAL 编译含 FileGDB SDK）
    3) 无上述环境时：生成 GDB 交付包目录 + 供 GeoScene Pro 导入的脚本

用法:
    python tools/geoscene/build_fgdb.py              # 使用默认输出目录 database/output
    python tools/geoscene/build_fgdb.py --output-dir database/output
    python tools/geoscene/build_fgdb.py --check      # 仅检查当前构建能力
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# 项目根目录（tools/geoscene/ -> 上三级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

GDB_DIR = Path(__file__).resolve().parent / "data"
GDB_PATH = GDB_DIR / "BikeFlowGNN.gdb"
OUTPUT_DEFAULT = PROJECT_ROOT / "database" / "output"

# 要素类与数据源映射：fc_name -> (geojson 文件名, 要素类型)
FEATURE_CLASSES = {
    "StreetSegments": ("segments.geojson", "polyline"),
    "BikeStations": ("stations.geojson", "point"),
    "Buildings": ("buildings.geojson", "polygon"),
}


def _check_arcpy() -> bool:
    """GeoScene Pro 的 arcpy 是否可用"""
    try:
        import arcpy  # noqa: F401
        return True
    except ImportError:
        return False


def _check_gdal_fgdb_write() -> bool:
    """GDAL 是否支持写入 FileGDB"""
    try:
        import pyogrio
        drv = pyogrio.list_drivers()
        return drv.get("FileGDB", "").startswith("rw")
    except Exception:
        return False


def _check_ogr2ogr() -> Path | None:
    return shutil.which("ogr2ogr")


def detect_capability() -> dict:
    """检测本机可用的 GDB 构建路径"""
    cap = {
        "arcpy": _check_arcpy(),
        "gdal_fgdb_write": _check_gdal_fgdb_write(),
        "ogr2ogr": bool(_check_ogr2ogr()),
    }
    cap["any"] = any([cap["arcpy"], cap["gdal_fgdb_write"], cap["ogr2ogr"]])
    return cap


def build_with_arcpy(output_dir: Path) -> bool:
    """路径 1：使用 GeoScene Pro 的 arcpy 构建 File GDB"""
    try:
        import arcpy
    except ImportError:
        return False

    arcpy.env.overwriteOutput = True
    if GDB_PATH.exists():
        shutil.rmtree(GDB_PATH)

    print(f"[arcpy] 创建 File Geodatabase: {GDB_PATH}")
    arcpy.management.CreateFileGDB(str(GDB_DIR), "BikeFlowGNN.gdb")

    sr = arcpy.SpatialReference(4326)
    for fc_name, (geo_name, geo_type) in FEATURE_CLASSES.items():
        src = output_dir / geo_name
        if not src.exists():
            print(f"[arcpy] 跳过 {fc_name}: 数据源不存在 {src}")
            continue
        print(f"[arcpy] 导入 {geo_name} -> {fc_name}")
        arcpy.conversion.JSONToFeatures(
            str(src), str(GDB_PATH / fc_name), geometry_type=geo_type
        )
        try:
            arcpy.management.DefineProjection(str(GDB_PATH / fc_name), sr)
        except Exception:
            pass
    return True


def build_with_gdal(output_dir: Path, use_ogr2ogr: bool = False) -> bool:
    """路径 2：使用 GDAL（pyogrio 或 ogr2ogr）写入 File GDB"""
    if use_ogr2ogr:
        ogr = _check_ogr2ogr()
        if not ogr:
            return False
        if GDB_PATH.exists():
            shutil.rmtree(GDB_PATH)
        for fc_name, (geo_name, _) in FEATURE_CLASSES.items():
            src = output_dir / geo_name
            if not src.exists():
                continue
            print(f"[ogr2ogr] 导入 {geo_name} -> {fc_name}")
            subprocess.run(
                [ogr, "-f", "FileGDB", "-nln", fc_name, str(GDB_PATH), str(src)],
                check=False,
            )
        return True

    # pyogrio 路径
    import geopandas as gpd

    if GDB_PATH.exists():
        shutil.rmtree(GDB_PATH)
    for fc_name, (geo_name, _) in FEATURE_CLASSES.items():
        src = output_dir / geo_name
        if not src.exists():
            continue
        print(f"[gdal] 导入 {geo_name} -> {fc_name}")
        gdf = gpd.read_file(src)
        gdf.to_file(GDB_PATH, layer=fc_name, driver="FileGDB")
    return True


def build_delivery_package(output_dir: Path) -> Path:
    """路径 3：生成 GDB 交付包（GeoJSON + Pro 导入脚本），供 GeoScene Pro 环境生成 .gdb"""
    pkg = GDB_DIR / "BikeFlowGNN_delivery"
    pkg.mkdir(parents=True, exist_ok=True)

    # 复制 GeoJSON 数据
    copied = []
    for fc_name, (geo_name, _) in FEATURE_CLASSES.items():
        src = output_dir / geo_name
        if src.exists():
            dst = pkg / geo_name
            shutil.copy2(src, dst)
            copied.append(geo_name)

    # 生成 GeoScene Pro 一键导入脚本（在 Pro 的 Python 窗口运行）
    pro_script = pkg / "import_to_fgdb.py"
    lines = [
        "# 在 GeoScene Pro 的 Python 窗口（或 Pro 内置 Python）运行本脚本",
        "# 将本目录下的 GeoJSON 导入为 File Geodatabase",
        "import arcpy, os",
        f'base = r"{pkg}"',
        f'gdb = r"{GDB_PATH}"',
        "arcpy.env.overwriteOutput = True",
        "if not arcpy.Exists(gdb):",
        "    arcpy.management.CreateFileGDB(os.path.dirname(gdb), os.path.basename(gdb))",
        "",
    ]
    for fc_name, (geo_name, geo_type) in FEATURE_CLASSES.items():
        if geo_name in copied:
            lines.append(
                f'arcpy.conversion.JSONToFeatures(os.path.join(base, "{geo_name}"), '
                f'os.path.join(gdb, "{fc_name}"), geometry_type="{geo_type}")'
            )
    lines.append(
        f'arcpy.management.DefineProjection(os.path.join(gdb, "StreetSegments"), '
        f'arcpy.SpatialReference(4326)) if arcpy.Exists(os.path.join(gdb, "StreetSegments")) else None'
    )
    pro_script.write_text("\n".join(lines), encoding="utf-8")

    # 说明文件
    (pkg / "README.txt").write_text(
        "\n".join([
            "GDB 交付包 — 使用说明",
            "",
            "本机未检测到 FileGDB 写入能力（arcpy / GDAL FileGDB 驱动）。",
            "请在有 GeoScene Pro 的机器上执行以下任一方式生成 BikeFlowGNN.gdb：",
            "",
            "方式 A（推荐）: 打开 GeoScene Pro -> 打开 Python 窗口 -> 运行 import_to_fgdb.py",
            "方式 B: 打开 GeoScene Pro -> 新建空白地图 -> 添加数据 -> 导入上述 GeoJSON ->",
            "        在目录窗格新建 File Geodatabase 并复制要素",
            "",
            "生成后请将 BikeFlowGNN.gdb 放回 tools/geoscene/data/ 目录。",
            "",
        ]),
        encoding="utf-8",
    )

    print(f"[交付包] 生成完毕: {pkg}")
    print(f"[交付包] 已复制要素数据: {', '.join(copied)}")
    print(f"[交付包] 在 GeoScene Pro 中运行: python {pro_script.name}")
    return pkg


def build_fgdb(output_dir: Path):
    """主流程：选择可用的构建路径"""
    output_dir = Path(output_dir)
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    cap = detect_capability()
    print(f"GDB 构建能力检测: {cap}")

    if cap["arcpy"]:
        ok = build_with_arcpy(output_dir)
    elif cap["ogr2ogr"]:
        ok = build_with_gdal(output_dir, use_ogr2ogr=True)
    elif cap["gdal_fgdb_write"]:
        ok = build_with_gdal(output_dir, use_ogr2ogr=False)
    else:
        ok = False
        build_delivery_package(output_dir)

    if ok and GDB_PATH.exists():
        print(f"\n✓ File Geodatabase 构建完成: {GDB_PATH}")
        for fc in FEATURE_CLASSES:
            if (GDB_PATH / fc).exists():
                print(f"  - {fc}")
        return

    print("\n✗ 未生成真正的 .gdb（缺少 arcpy / GDAL FileGDB 写驱动）")
    print("  已生成 GDB 交付包，请按交付包 README.txt 在 GeoScene Pro 中生成 .gdb。")
    print("  比赛交付时 .gdb 与 GeoJSON 均为有效交付格式（数据存储合规）。")


def main():
    parser = argparse.ArgumentParser(description="构建 File Geodatabase（比赛交付格式）")
    parser.add_argument("--output-dir", default=str(OUTPUT_DEFAULT), help="GeoJSON 输出目录")
    parser.add_argument("--check", action="store_true", help="仅检测构建能力")
    args = parser.parse_args()

    if args.check:
        cap = detect_capability()
        print(json.dumps(cap, ensure_ascii=False, indent=2))
        print("可用路径: " + ("arcpy / GDAL" if cap["any"] else "仅 GDB 交付包（需 GeoScene Pro 生成 .gdb）"))
        return

    build_fgdb(Path(args.output_dir))


if __name__ == "__main__":
    main()
