"""
Route Optimization Algorithms
- Nearest Neighbor heuristic
- 2-opt local search improvement
- Confidence scoring
"""

import numpy as np
import math
from typing import List, Tuple, Dict
import json, os


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def build_distance_matrix(locations: List[str], coords: Dict[str, Tuple[float, float]]) -> np.ndarray:
    n = len(locations)
    matrix = np.zeros((n, n))
    
    try:
        from api.gmaps import get_distance_matrix
    except ImportError:
        get_distance_matrix = None
        
    if get_distance_matrix is not None:
        origins_coords = [coords[loc] for loc in locations]
        destinations_coords = [coords[loc] for loc in locations]
        dm_resp = get_distance_matrix(origins_coords, destinations_coords)
        
        if dm_resp.get("status") == "OK" and "rows" in dm_resp:
            for i in range(n):
                elements = dm_resp["rows"][i]["elements"]
                for j in range(n):
                    if i != j:
                        try:
                            matrix[i][j] = elements[j]["distance"]["value"] / 1000.0
                        except (KeyError, IndexError):
                            matrix[i][j] = haversine(*origins_coords[i], *destinations_coords[j])
            return matrix

    for i in range(n):
        for j in range(n):
            if i != j:
                lat1, lon1 = coords[locations[i]]
                lat2, lon2 = coords[locations[j]]
                matrix[i][j] = haversine(lat1, lon1, lat2, lon2)
    return matrix


def nearest_neighbor(locations: List[str], dist_matrix: np.ndarray, start: int = 0) -> List[int]:
    """Classic Nearest Neighbor TSP heuristic."""
    n = len(locations)
    visited = [False] * n
    route = [start]
    visited[start] = True

    for _ in range(n - 1):
        last = route[-1]
        # Find nearest unvisited
        best_dist, best_next = float("inf"), -1
        for j in range(n):
            if not visited[j] and dist_matrix[last][j] < best_dist:
                best_dist = dist_matrix[last][j]
                best_next = j
        route.append(best_next)
        visited[best_next] = True

    return route


def two_opt(route: List[int], dist_matrix: np.ndarray, max_iter: int = 500) -> List[int]:
    """2-opt local search to improve route quality."""
    best = route[:]
    improved = True
    iterations = 0

    while improved and iterations < max_iter:
        improved = False
        iterations += 1
        for i in range(1, len(best) - 1):
            for j in range(i + 1, len(best)):
                # Reverse segment i..j
                new_route = best[:i] + best[i:j+1][::-1] + best[j+1:]
                if _route_distance(new_route, dist_matrix) < _route_distance(best, dist_matrix):
                    best = new_route
                    improved = True
    return best


def _route_distance(route: List[int], dist_matrix: np.ndarray) -> float:
    return sum(dist_matrix[route[i]][route[i+1]] for i in range(len(route)-1))


def optimize_route(
    location_names: List[str],
    coords: Dict[str, Tuple[float, float]],
    use_two_opt: bool = True,
) -> Tuple[List[str], float]:
    """
    Full route optimization pipeline.
    Returns (ordered_location_names, total_distance_km).
    """
    if len(location_names) <= 1:
        if location_names:
            return location_names, 0.0
        return [], 0.0

    # Filter to known locations
    valid = [l for l in location_names if l in coords]
    if not valid:
        return location_names, 0.0

    dist_matrix = build_distance_matrix(valid, coords)

    # Try multiple start points → pick best
    best_route, best_dist = None, float("inf")
    starts = list(range(min(len(valid), 5)))  # Up to 5 starting points
    for start in starts:
        route_idx = nearest_neighbor(valid, dist_matrix, start)
        if use_two_opt:
            route_idx = two_opt(route_idx, dist_matrix)
        d = _route_distance(route_idx, dist_matrix)
        if d < best_dist:
            best_dist = d
            best_route = route_idx

    ordered = [valid[i] for i in best_route]
    return ordered, round(best_dist, 2)


def compute_confidence(
    predicted_route: List[str],
    historical_routes: List[List[str]],
    driver_efficiency: float,
    dist_km: float,
) -> float:
    """
    Compute route confidence score [0, 1] based on:
    - Pattern match with historical routes
    - Driver efficiency
    - Route compactness
    """
    if not historical_routes:
        base = 0.70
    else:
        # Sequence similarity: how many consecutive pairs appear in history?
        predicted_pairs = set(
            (predicted_route[i], predicted_route[i+1])
            for i in range(len(predicted_route) - 1)
        )
        matches = 0
        total_hist_pairs = 0
        for hist_route in historical_routes[-20:]:  # Last 20 routes
            hist_pairs = set(
                (hist_route[i], hist_route[i+1])
                for i in range(len(hist_route) - 1)
            )
            total_hist_pairs += len(hist_pairs)
            matches += len(predicted_pairs & hist_pairs)

        pattern_score = (matches / total_hist_pairs) if total_hist_pairs > 0 else 0.5
        base = 0.5 + 0.3 * pattern_score

    # Adjust for driver efficiency
    conf = base * (0.8 + 0.2 * driver_efficiency)

    # Clip to sensible range
    conf = max(0.55, min(0.99, conf))
    return round(conf, 3)
