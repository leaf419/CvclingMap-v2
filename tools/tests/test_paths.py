"""工具库路径/可运行性测试（Phase 2-3 验收）

验证迁移到 tools/ 的脚本：
    1. 输出路径统一指向 database/output
    2. 服务发布脚本的 sys.path / SERVICES_DIR 正确
    3. 模块可正常加载（语法与顶层 import 无误）
"""
import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_OUTPUT = PROJECT_ROOT / "database" / "output"
CRAWLERS_DIR = PROJECT_ROOT / "tools" / "crawlers"
GEOSCENE_DIR = PROJECT_ROOT / "tools" / "geoscene"

CRAWLER_FILES = [
    "fetch_osm_roads.py",
    "fetch_osm_buildings.py",
    "fetch_osm_full.py",
    "download_tianditu_tiles.py",
]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("fname", CRAWLER_FILES)
def test_crawler_output_dir_points_to_database(fname):
    mod = _load_module(f"crawler_{fname[:-3]}", CRAWLERS_DIR / fname)
    assert mod.OUTPUT_DIR == DATABASE_OUTPUT, f"{fname} OUTPUT_DIR 未指向 database/output"
    assert mod.OUTPUT_DIR.exists()


def test_crawler_output_dir_is_directory():
    assert DATABASE_OUTPUT.is_dir()


def test_publish_services_paths():
    mod = _load_module("publish_services", GEOSCENE_DIR / "publish_services.py")
    assert mod.OUTPUT_DIR == DATABASE_OUTPUT
    assert mod.SERVICES_DIR == GEOSCENE_DIR / "services"
    assert mod.SERVICES_DIR.exists()
    assert (GEOSCENE_DIR / "server_config.json").exists()


def test_geoscene_services_configs_present():
    """发布配置（跟随发布工具）留在 tools/geoscene/services/"""
    names = {p.name for p in (GEOSCENE_DIR / "services").glob("*.json")}
    assert {"bike_segments_mapservice.json", "bike_stations_mapservice.json",
            "bike_routes_geocodeservice.json"} <= names
    assert "scene_3d_webscene.json" not in names  # 3D 场景定义已迁入渲染层


def test_scene_3d_webscene_in_rendering():
    """3D 场景定义归属渲染层（前端 src/rendering/scene-config/）"""
    scene = PROJECT_ROOT / "frontend" / "src" / "rendering" / "scene-config" / "scene_3d_webscene.json"
    assert scene.exists()
    import json
    cfg = json.loads(scene.read_text(encoding="utf-8"))
    assert cfg.get("type") == "WebScene"


def test_geoscene_gdb_readme_present():
    assert (GEOSCENE_DIR / "data" / "README.txt").exists()
