"""验证 bikeflow.sqlite 的表结构与索引（Phase 1-2 验收）

用法: python database/scripts/verify_schema.py
"""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "bikeflow.sqlite"

EXPECTED_TABLES = {
    "dataset_meta": None,
    "streetview_observations": None,  # 列数动态，单独断言
    "poi": ["poi_id", "name", "category_big", "category_mid", "lon", "lat", "province", "district"],
    "stations": ["station_id", "code", "name", "location", "capacity", "lon_wgs", "lat_wgs"],
    "segments": ["seg_id", "highway", "name", "length", "geometry_wkt"],
    "buildings": ["place_id", "levels", "height_m", "area_m2", "geometry_wkt"],
    "districts": ["name", "admin_level", "geometry_wkt"],
    "routes": ["route_id", "total_length", "total_cost", "avg_safety", "avg_comfort",
               "avg_scenery", "avg_traffic_stress", "avg_beauty", "avg_pref_score",
               "num_segments", "geometry_wkt"],
}
EXPECTED_INDEXES = ["idx_poi_category", "idx_poi_lonlat", "idx_stations_lonlat"]

failures = []


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"  [FAIL] {msg}")


conn = sqlite3.connect(DB)
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
).fetchall()]

print(f"database: {DB}")
for t, cols in EXPECTED_TABLES.items():
    if t not in tables:
        fail(f"missing table: {t}")
        continue
    actual = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")').fetchall()]
    if cols is None:
        print(f"  [OK]   {t}: columns={len(actual)}")
    else:
        missing = [c for c in cols if c not in actual]
        if missing:
            fail(f"{t} missing columns: {missing}")
        else:
            print(f"  [OK]   {t}: {len(actual)} columns, required present")

sv_cols = len([r for r in conn.execute('PRAGMA table_info("streetview_observations")').fetchall()])
print(f"  [INFO] streetview_observations total columns: {sv_cols} (expect 181 source + 1 id = 182)")
if sv_cols < 100:
    fail(f"streetview_observations looks truncated: {sv_cols} columns")

indexes = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
).fetchall()]
for idx in EXPECTED_INDEXES:
    if idx not in indexes:
        fail(f"missing index: {idx}")
    else:
        print(f"  [OK]   index: {idx}")

conn.close()
print()
if failures:
    print(f"RESULT: FAIL ({len(failures)} problem(s))")
    sys.exit(1)
print("RESULT: PASS")
