"""GNN 独立训练入口脚本

在不改动运行时 pipeline 链路的前提下，独立完成：
    1. 数据加载与四维边权计算（复用 pipeline stage1/stage3）
    2. 构建 5类节点6类边 的 PyG HeteroData（POI 可抽样控制规模）
    3. HGT 模型训练（trainer.train_model）
    4. 导出产物至 output/models/：
        - hgt_model.pt              模型权重 + metadata
        - embeddings.npz            各节点类型嵌入
        - train_history.json        训练 loss 历史
        - segments_with_pref.geojson (--apply-pref 时)

用法（在项目根目录）:
    python -m algorithm.models.train_cli --epochs 50 --max-poi 5000
    python -m algorithm.models.train_cli --apply-pref --device cpu
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from algorithm.config import BASE_DIR, TRAIN_CFG
from algorithm.pipeline import BikeFlowPipeline
from algorithm.models.hgt_model import create_hetero_data
from algorithm.models.trainer import train_model, export_embeddings

SEG_FEAT_COLS = ["length", "w_safety", "w_comfort", "w_scenery",
                 "f_traffic_stress", "v_beauty", "v_greenery",
                 "cost_composite", "pref_score"]
PLACE_FEAT_COLS = ["height_m", "area_m2"]
POI_FEAT_COLS = ["category_code"]
STA_FEAT_COLS = ["capacity"]
OBS_FEAT_COLS = ["s_motor_pressure", "f_overall_comfort",
                 "v_greenery", "v_beauty", "f_traffic_stress"]


def _feat(gdf, cols):
    """按列取特征矩阵，缺失列填0"""
    out = []
    for c in cols:
        out.append(gdf[c].fillna(0).values if c in gdf.columns
                   else np.zeros(len(gdf)))
    return np.column_stack(out).astype(np.float32)


def _id_to_pos(ids):
    return {v: i for i, v in enumerate(ids)}


def build_segment_adjacency(segments_gdf):
    """路段级邻接：共享端点即相连 (src_pos, dst_pos)"""
    end_to_seg = {}
    for _, row in segments_gdf.iterrows():
        geom = row.geometry
        if geom is None or len(geom.coords) < 2:
            continue
        u = (round(geom.coords[0][0], 6), round(geom.coords[0][1], 6))
        v = (round(geom.coords[-1][0], 6), round(geom.coords[-1][1], 6))
        end_to_seg.setdefault(u, []).append(row["seg_id"])
        end_to_seg.setdefault(v, []).append(row["seg_id"])

    pos = _id_to_pos(segments_gdf["seg_id"])
    src, dst = [], []
    for segs in end_to_seg.values():
        idx = [pos[s] for s in segs if s in pos]
        for i in range(len(idx)):
            for j in range(i + 1, len(idx)):
                src.append(idx[i])
                dst.append(idx[j])
    return np.array(src, dtype=np.int64), np.array(dst, dtype=np.int64)


def _connect_places_to_segments(place_gdf, segments_gdf, max_distance=150.0):
    """建筑最近街道段 (faced_to 边)"""
    import geopandas as gpd
    place = place_gdf.to_crs("EPSG:32650").copy()
    if "place_id" not in place.columns:
        place["place_id"] = range(len(place))
    seg = segments_gdf.to_crs("EPSG:32650")[["seg_id", "geometry"]]
    joined = gpd.sjoin_nearest(
        place[["place_id", "geometry"]], seg,
        how="left", max_distance=max_distance,
    )
    return joined[["place_id", "seg_id"]].dropna(subset=["seg_id"])


def _pairs(src_ids, dst_ids, src_map, dst_map):
    """边索引对：仅保留两端均存在的连接"""
    src, dst = [], []
    for s, d in zip(src_ids, dst_ids):
        if s in src_map and d in dst_map:
            src.append(src_map[s])
            dst.append(dst_map[d])
    return (np.array(src, dtype=np.int64), np.array(dst, dtype=np.int64))


def build_pyg_data(segments_gdf, place_gdf, poi_gdf, station_gdf,
                   obs_gdf, max_poi=5000):
    """构建 5类节点6类边 PyG HeteroData

    Returns:
        (HeteroData, segments_gdf按seg_id排序后)
    """
    segments_gdf = segments_gdf.sort_values("seg_id").reset_index(drop=True)

    if max_poi and len(poi_gdf) > max_poi:
        poi_gdf = poi_gdf.sample(max_poi, random_state=42).reset_index(drop=True)

    nodes = {
        "segment": _feat(segments_gdf, SEG_FEAT_COLS),
        "place": _feat(place_gdf, PLACE_FEAT_COLS),
        "poi": _feat(poi_gdf, POI_FEAT_COLS),
        "station": _feat(station_gdf, STA_FEAT_COLS),
        "observation": _feat(obs_gdf, OBS_FEAT_COLS),
    }
    node_counts = {k: len(v) for k, v in nodes.items()}

    seg_src, seg_dst = build_segment_adjacency(segments_gdf)

    from algorithm.graph.hetero_builder import (
        connect_observations_to_segments,
        connect_pois_to_segments,
        connect_stations_to_segments,
    )
    obs_edges = connect_observations_to_segments(obs_gdf, segments_gdf)
    poi_edges = connect_pois_to_segments(poi_gdf, segments_gdf)
    sta_edges = connect_stations_to_segments(station_gdf, segments_gdf)
    place_edges = _connect_places_to_segments(place_gdf, segments_gdf)

    seg_pos = _id_to_pos(segments_gdf["seg_id"])
    obs_pos = _id_to_pos(obs_gdf["obs_id"])
    poi_pos = _id_to_pos(poi_gdf["poi_id"])
    sta_pos = _id_to_pos(station_gdf["station_id"])
    place_pos = ({i: i for i in range(len(place_gdf))}
                 if "place_id" not in place_gdf.columns
                 else _id_to_pos(place_gdf["place_id"]))

    edges = {
        ("segment", "connected_to", "segment"):
            (seg_src, seg_dst),
        ("place", "faced_to", "segment"):
            _pairs(place_edges["place_id"], place_edges["seg_id"],
                   place_pos, seg_pos),
        ("poi", "nearby", "segment"):
            _pairs(poi_edges["poi_id"], poi_edges["seg_id"],
                   poi_pos, seg_pos),
        ("station", "served_by", "segment"):
            _pairs(sta_edges["station_id"], sta_edges["seg_id"],
                   sta_pos, seg_pos),
        ("observation", "observed_at", "segment"):
            _pairs(obs_edges["obs_id"], obs_edges["seg_id"],
                   obs_pos, seg_pos),
    }
    edges = {k: v for k, v in edges.items() if len(v[0]) > 0}

    data = create_hetero_data(nodes, edges, node_counts,
                              hidden_dim=TRAIN_CFG.hidden_dim)

    et = ("segment", "connected_to", "segment")
    if et in data.edge_types:
        costs = segments_gdf.iloc[seg_src]["cost_composite"].values
        data[et].cost_composite = torch.tensor(costs, dtype=torch.float32)

    return data, segments_gdf


def _apply_pref_score(model, data, device):
    """用 segment 嵌入计算相邻路段偏好分，取每段均值"""
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"
    et = ("segment", "connected_to", "segment")
    if et not in data.edge_types:
        return None
    emb = export_embeddings(model, data, device)["segment"]
    ei = data[et].edge_index.numpy()
    model.eval()
    with torch.no_grad():
        e = torch.tensor(emb, dtype=torch.float32)
        pred = model.predict_preference(e, ei[0], ei[1]).numpy()

    n = ei.max() + 1
    agg = np.zeros(n)
    cnt = np.zeros(n)
    for a, b, p in zip(ei[0], ei[1], pred):
        agg[a] += p; cnt[a] += 1
        agg[b] += p; cnt[b] += 1
    return np.where(cnt > 0, agg / np.maximum(cnt, 1), 0.5)


def main():
    parser = argparse.ArgumentParser(description="BikeFlowGNN HGT 独立训练入口")
    parser.add_argument("--epochs", type=int, default=TRAIN_CFG.epochs)
    parser.add_argument("--device", default="auto", help="auto / cuda / cpu")
    parser.add_argument("--max-poi", type=int, default=5000,
                        help="POI 抽样数（控制图规模）")
    parser.add_argument("--output-dir",
                        default=str(BASE_DIR / "database" / "output" / "models"))
    parser.add_argument("--apply-pref", action="store_true",
                        help="用训练后嵌入计算 pref_score 回写并导出 GeoJSON")
    args = parser.parse_args()

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[train] device = {device}")

    t0 = time.time()
    pipeline = BikeFlowPipeline()
    obs_gdf, poi_gdf, stations_gdf, segments_gdf, buildings_gdf = \
        pipeline.stage1_load_data()
    segments = pipeline.stage3_compute_weights(segments_gdf, obs_gdf)
    print(f"[train] 数据准备完成: {time.time()-t0:.1f}s, "
          f"segments={len(segments)}, poi={len(poi_gdf)}, "
          f"obs={len(obs_gdf)}")

    data, segments = build_pyg_data(
        segments, buildings_gdf, poi_gdf, stations_gdf, obs_gdf,
        max_poi=args.max_poi,
    )
    print(f"[train] HeteroData: 节点类型={data.node_types}, "
          f"节点数={data.num_nodes}, 边数={data.num_edges}")

    if args.epochs != TRAIN_CFG.epochs:
        TRAIN_CFG.epochs = args.epochs
    model, history = train_model(data, device=device)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    torch.save({
        "state_dict": model.state_dict(),
        "metadata": list(data.metadata()),
        "hidden_dim": TRAIN_CFG.hidden_dim,
        "epochs": args.epochs,
        "device": device,
    }, out_dir / "hgt_model.pt")
    print(f"[train] 模型权重 → {out_dir / 'hgt_model.pt'}")

    embeddings = export_embeddings(model, data, device)
    np.savez_compressed(
        out_dir / "embeddings.npz",
        **{k: v for k, v in embeddings.items()},
    )
    print(f"[train] 节点嵌入 → {out_dir / 'embeddings.npz'}")

    (out_dir / "train_history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[train] 训练日志 → {out_dir / 'train_history.json'}")

    if args.apply_pref:
        pref = _apply_pref_score(model, data, device)
        if pref is not None:
            segments["pref_score"] = pref
            seg_out = out_dir / "segments_with_pref.geojson"
            segments.to_file(seg_out, driver="GeoJSON")
            print(f"[train] pref_score 回写完成 → {seg_out}")
        else:
            print("[train] 无 segment 邻接边，跳过 pref 回写")

    print("[train] 完成")


if __name__ == "__main__":
    main()
