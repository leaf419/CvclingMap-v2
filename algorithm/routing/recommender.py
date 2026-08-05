"""个性化骑行路线推荐"""
import networkx as nx
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class UserProfile:
    """用户骑行偏好画像"""
    user_id: str
    preference_weights: Dict[str, float]
    max_detour: float = 1.5
    prefer_greenery: bool = False
    avoid_traffic: bool = False
    cycling_speed: float = 15.0
    max_duration_min: float = 60.0


def compute_route_score(
    route: list,
    G: nx.Graph,
    profile: UserProfile,
) -> float:
    """根据用户画像计算路线综合得分 [0, 1]"""
    if len(route) < 2:
        return 0.0

    edges = list(zip(route[:-1], route[1:]))

    total_dist = sum(G[u][v].get("length", 0) for u, v in edges)
    avg_safety = np.mean([G[u][v].get("w_safety", 0.5) for u, v in edges])
    avg_comfort = np.mean([G[u][v].get("w_comfort", 0.5) for u, v in edges])
    avg_scenery = np.mean([G[u][v].get("w_scenery", 0.5) for u, v in edges])
    avg_pref = np.mean([G[u][v].get("pref_score", 0.5) for u, v in edges])

    source, target = route[0], route[-1]
    if nx.has_path(G, source, target):
        shortest_dist = nx.shortest_path_length(G, source, target, weight="length")
    else:
        shortest_dist = total_dist

    detour_ratio = total_dist / max(shortest_dist, 1e-6)
    if detour_ratio > profile.max_detour:
        return 0.0

    weights = profile.preference_weights
    w_safety = weights.get("safety", 0.3)
    w_comfort = weights.get("comfort", 0.25)
    w_scenery = weights.get("scenery", 0.25)
    w_pref = max(1.0 - w_safety - w_comfort - w_scenery, 0)

    score = (
        w_safety * avg_safety +
        w_comfort * avg_comfort +
        w_scenery * avg_scenery +
        w_pref * avg_pref
    )

    if profile.prefer_greenery:
        score += avg_scenery * 0.1

    if profile.avoid_traffic:
        avg_stress = np.mean([G[u][v].get("f_traffic_stress", 0.5) for u, v in edges])
        score -= avg_stress * 0.15

    detour_penalty = max(detour_ratio - 1.0, 0) * 0.1
    score -= detour_penalty

    duration_min = (total_dist / 1000.0) / profile.cycling_speed * 60
    if duration_min > profile.max_duration_min:
        score *= 0.5

    return float(np.clip(score, 0, 1))


def recommend_route(
    pareto_routes: List[list],
    G: nx.Graph,
    profile: UserProfile,
    top_k: int = 3,
) -> Optional[list]:
    """从Pareto路线集中推荐最适合用户的路线"""
    if not pareto_routes:
        return None

    scored = [(r, compute_route_score(r, G, profile)) for r in pareto_routes]
    scored.sort(key=lambda x: x[1], reverse=True)

    if top_k == 1:
        return scored[0][0] if scored else None
    return [r for r, _ in scored[:top_k]]


USER_TEMPLATES = {
    "commuter": UserProfile(
        user_id="commuter_template",
        preference_weights={"safety": 0.5, "comfort": 0.3, "scenery": 0.1},
        max_detour=1.3, avoid_traffic=True,
        cycling_speed=18.0, max_duration_min=45.0,
    ),
    "tourist": UserProfile(
        user_id="tourist_template",
        preference_weights={"safety": 0.2, "comfort": 0.2, "scenery": 0.5},
        max_detour=2.0, prefer_greenery=True,
        cycling_speed=12.0, max_duration_min=120.0,
    ),
    "fitness": UserProfile(
        user_id="fitness_template",
        preference_weights={"safety": 0.3, "comfort": 0.2, "scenery": 0.3},
        max_detour=2.5,
        cycling_speed=22.0, max_duration_min=90.0,
    ),
    "family": UserProfile(
        user_id="family_template",
        preference_weights={"safety": 0.6, "comfort": 0.3, "scenery": 0.1},
        max_detour=1.2, prefer_greenery=True, avoid_traffic=True,
        cycling_speed=10.0, max_duration_min=30.0,
    ),
}
