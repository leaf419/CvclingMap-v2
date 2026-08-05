"""GeoScene Enterprise Server 客户端测试"""
from unittest.mock import patch, MagicMock

from gateway.service.geoscene_client import GeoSceneClient


def _client():
    return GeoSceneClient(server_url="https://geoscene.example.com/arcgis", token="")


def test_is_available_when_server_responds():
    resp = MagicMock()
    resp.status_code = 200
    resp.text = '{"currentVersion": 11.2}'
    with patch("gateway.service.geoscene_client.requests.get", return_value=resp) as m:
        assert _client().is_available() is True
        m.assert_called_once_with(
            "https://geoscene.example.com/arcgis/rest/info?f=json", timeout=3
        )


def test_is_available_when_server_down():
    with patch("gateway.service.geoscene_client.requests.get", side_effect=Exception("conn refused")):
        assert _client().is_available() is False


def test_status_fallback_mode_when_unavailable():
    c = _client()
    with patch.object(c, "is_available", return_value=False):
        status = c.status()
    assert status["available"] is False
    assert status["mode"] == "local-fallback"
    # 增强后始终返回 services 清单，每个服务标记不可用
    assert "services" in status
    assert all(v["available"] is False for v in status["services"].values())


def test_status_geoscene_mode_when_available():
    c = _client()
    with patch.object(c, "is_available", return_value=True):
        status = c.status()
    assert status["available"] is True
    assert status["mode"] == "geoscene"
    assert "segments" in status["services"]
    # 增强后服务条目为字典，包含 url 字段
    seg = status["services"]["segments"]
    assert seg["url"].startswith(
        "https://geoscene.example.com/arcgis/rest/services/"
    )
    assert seg["name"] == "BikeSegments_MapService"
    assert seg["type"] == "MapServer"


def test_service_url_construction():
    c = _client()
    url = c.service_url("BikeSegments_MapService", "MapServer")
    assert url == "https://geoscene.example.com/arcgis/rest/services/BikeSegments_MapService/MapServer"
