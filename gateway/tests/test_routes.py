"""FastAPI后端API测试"""
import pytest
from fastapi.testclient import TestClient
from gateway.app import create_app


@pytest.fixture
def client():
    app = create_app(testing=True)
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_get_user_templates(client):
    resp = client.get("/api/user-templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    keys = [t["key"] for t in data["templates"]]
    assert "commuter" in keys
    assert "tourist" in keys
    assert "fitness" in keys
    assert "family" in keys


def test_search_routes_validation_error(client):
    resp = client.post("/api/routes/search", json={
        "user_template": "commuter",
    })
    assert resp.status_code == 422


def test_search_routes_invalid_template(client):
    resp = client.post("/api/routes/search", json={
        "source": [116.36, 39.91],
        "target": [116.42, 39.93],
        "user_template": "invalid_template",
    })
    assert resp.status_code == 422


def test_get_route_by_id_not_found(client):
    resp = client.get("/api/routes/99999")
    assert resp.status_code == 404


def test_root_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "BikeFlowGNN API"
    assert data["version"] == "2.0.0"


def test_search_routes_mock(client, monkeypatch):
    """测试路线搜索（mock管道）"""
    async def mock_search(*args, **kwargs):
        return {
            "routes": [{
                "route_id": 0,
                "coordinates": [[116.36, 39.91], [116.37, 39.92]],
                "metrics": {
                    "total_length": 1000.0, "total_cost": 100.0,
                    "avg_safety": 0.72, "avg_comfort": 0.65,
                    "avg_scenery": 0.58, "avg_traffic_stress": 0.3,
                    "avg_beauty": 0.6, "avg_pref_score": 0.7,
                    "num_segments": 5,
                },
            }],
            "best_route_id": 0,
            "scene_config": {"center": [116.39, 39.92], "zoom": 14},
            "pipeline_duration_sec": 1.5,
            "from_cache": False,
        }

    # 必须 monkeypatch routes.py 中的本地引用
    monkeypatch.setattr(
        "gateway.api.routes.search_routes", mock_search
    )

    resp = client.post("/api/routes/search", json={
        "source": [116.36, 39.91],
        "target": [116.42, 39.93],
        "user_template": "commuter",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["routes"]) > 0
    assert data["best_route_id"] == 0
    assert "scene_config" in data
