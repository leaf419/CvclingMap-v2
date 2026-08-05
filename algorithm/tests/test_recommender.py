"""个性化推荐测试"""
import pytest
import networkx as nx
from algorithm.routing.recommender import UserProfile, recommend_route, compute_route_score


def test_user_profile_creation():
    """测试用户画像创建"""
    profile = UserProfile(
        user_id="user_001",
        preference_weights={"safety": 0.5, "comfort": 0.3, "scenery": 0.2},
        max_detour=1.5,
        prefer_greenery=True,
    )
    assert profile.preference_weights["safety"] == 0.5
    assert profile.max_detour == 1.5


def test_compute_route_score():
    """测试路线评分"""
    G = nx.Graph()
    G.add_edge(0, 1, length=100.0, w_safety=0.8, w_comfort=0.6,
               w_scenery=0.7, cost_composite=40.0)
    G.add_edge(1, 2, length=120.0, w_safety=0.7, w_comfort=0.5,
               w_scenery=0.8, cost_composite=50.0)

    profile = UserProfile(
        user_id="test",
        preference_weights={"safety": 0.5, "comfort": 0.3, "scenery": 0.2},
        max_detour=2.0,
    )

    score = compute_route_score([0, 1, 2], G, profile)
    assert 0 <= score <= 1


def test_recommend_route():
    """测试路线推荐"""
    G = nx.Graph()
    for i in range(5):
        G.add_edge(i, i + 1, length=100.0, w_safety=0.7, w_comfort=0.6,
                   w_scenery=0.7, cost_composite=40.0, pref_score=0.8,
                   f_traffic_stress=0.3, v_beauty=0.7)

    profile = UserProfile(
        user_id="test",
        preference_weights={"safety": 0.4, "comfort": 0.3, "scenery": 0.3},
        max_detour=2.0,
    )

    result = recommend_route([[0, 1, 2, 3, 4, 5]], G, profile)
    assert result is not None
    assert isinstance(result, list)
