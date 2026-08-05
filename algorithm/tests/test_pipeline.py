"""全流程管道编排测试"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from algorithm.pipeline import BikeFlowPipeline, PipelineResult


def test_pipeline_result_dataclass():
    """测试管道结果数据类"""
    result = PipelineResult(
        segments_gdf=None,
        stations_gdf=None,
        hetero_graph=None,
        nx_graph=None,
        pareto_routes=[],
        best_route=None,
        scene_config=None,
    )
    assert result.pareto_routes == []
    assert result.best_route is None


def test_pipeline_init():
    """测试管道初始化"""
    pipeline = BikeFlowPipeline(
        data_dir="/tmp/test_data",
        output_dir="/tmp/test_output",
    )
    assert pipeline.data_dir == Path("/tmp/test_data")
    assert pipeline.output_dir == Path("/tmp/test_output")


def test_pipeline_stage1_load_data(tmp_path):
    """测试阶段1：数据加载（mock）"""
    pipeline = BikeFlowPipeline(
        data_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
    )

    with patch("algorithm.pipeline.load_and_process_streetview") as mock_sv, \
         patch("algorithm.pipeline.load_and_process_poi") as mock_poi, \
         patch("algorithm.pipeline.load_stations") as mock_sta, \
         patch("algorithm.pipeline.load_basemap_data") as mock_bm:

        mock_sv.return_value = MagicMock()
        mock_poi.return_value = MagicMock()
        mock_sta.return_value = MagicMock()
        mock_bm.return_value = (MagicMock(), MagicMock())

        result = pipeline.stage1_load_data()
        assert result is not None
        mock_sv.assert_called_once()
        mock_poi.assert_called_once()
        mock_sta.assert_called_once()
        mock_bm.assert_called_once()


def test_pipeline_stage2_build_graph(tmp_path):
    """测试阶段2：异构图构建（mock）"""
    pipeline = BikeFlowPipeline(
        data_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
    )

    with patch("algorithm.pipeline.build_hetero_graph") as mock_build:
        mock_build.return_value = MagicMock()
        result = pipeline.stage2_build_graph(
            segments_gdf=MagicMock(),
            obs_gdf=MagicMock(),
            poi_gdf=MagicMock(),
            station_gdf=MagicMock(),
            buildings_gdf=MagicMock(),
        )
        assert result is not None
        mock_build.assert_called_once()


def test_pipeline_full_run_mock(tmp_path):
    """测试完整管道运行（全mock）"""
    import geopandas as gpd
    import networkx as nx
    from shapely.geometry import LineString, Point

    pipeline = BikeFlowPipeline(
        data_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
    )

    segments = gpd.GeoDataFrame(
        {"seg_id": [0, 1], "length": [100.0, 150.0]},
        geometry=[LineString([(0,0),(1,1)]), LineString([(1,1),(2,2)])],
        crs="EPSG:4326",
    )

    with patch("algorithm.pipeline.load_and_process_streetview") as mock_sv, \
         patch("algorithm.pipeline.load_and_process_poi") as mock_poi, \
         patch("algorithm.pipeline.load_stations") as mock_sta, \
         patch("algorithm.pipeline.load_basemap_data") as mock_bm, \
         patch("algorithm.pipeline.build_hetero_graph") as mock_build, \
         patch("algorithm.pipeline.propagate_metrics_to_segments") as mock_prop, \
         patch("algorithm.pipeline.compute_all_weights") as mock_w, \
         patch("algorithm.pipeline.fuse_composite_cost") as mock_fuse, \
         patch("algorithm.pipeline.build_nx_graph") as mock_nx, \
         patch("algorithm.pipeline.recommend_route") as mock_rec, \
         patch("algorithm.pipeline.export_segments_geojson") as mock_exp_seg, \
         patch("algorithm.pipeline.export_stations_geojson") as mock_exp_sta, \
         patch("algorithm.pipeline.export_routes_geojson") as mock_exp_rte, \
         patch("algorithm.pipeline.export_scene_config") as mock_exp_cfg:

        mock_sv.return_value = MagicMock()
        mock_poi.return_value = MagicMock()
        mock_sta.return_value = MagicMock()
        mock_bm.return_value = (segments, MagicMock())
        mock_build.return_value = MagicMock()
        mock_prop.return_value = segments
        mock_w.return_value = segments
        mock_fuse.return_value = segments

        G = nx.Graph()
        G.add_edge((0,0), (1,1), length=100.0, w_safety=0.7)
        G.add_edge((1,1), (2,2), length=150.0, w_safety=0.6)
        mock_nx.return_value = G

        mock_rec.return_value = [(0,0), (1,1), (2,2)]

        result = pipeline.run(
            source=(0, 0),
            target=(2, 2),
            user_template="commuter",
            skip_gnn=True,
        )

        assert isinstance(result, PipelineResult)
        assert result.best_route is not None
        mock_exp_seg.assert_called_once()
        mock_exp_sta.assert_called_once()
        mock_exp_rte.assert_called_once()


def test_pipeline_save_outputs(tmp_path):
    """测试管道输出保存"""
    import geopandas as gpd
    import networkx as nx
    from shapely.geometry import LineString, Point

    pipeline = BikeFlowPipeline(
        data_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
    )

    segments = gpd.GeoDataFrame(
        {"seg_id": [0], "w_safety": [0.7], "cost_composite": [40.0]},
        geometry=[LineString([(0,0),(1,1)])],
        crs="EPSG:4326",
    )
    stations = gpd.GeoDataFrame(
        {"station_id": [0]},
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    G = nx.Graph()
    G.add_edge((0,0), (1,1), length=100.0, w_safety=0.7)

    pipeline.save_outputs(
        segments_gdf=segments,
        stations_gdf=stations,
        nx_graph=G,
        pareto_routes=[[(0,0), (1,1)]],
        best_route=[(0,0), (1,1)],
    )

    assert (tmp_path / "output" / "segments.geojson").exists()
    assert (tmp_path / "output" / "stations.geojson").exists()
    assert (tmp_path / "output" / "routes.geojson").exists()
    assert (tmp_path / "output" / "scene_config.json").exists()
