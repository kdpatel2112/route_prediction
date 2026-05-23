"""
Prediction Engine
=================
Loads trained models and provides:
- predict_daily()  → optimized route for a given day
- predict_weekly() → 5-day schedule for a given week
"""

import json, os, math
import numpy as np
import pandas as pd
import joblib
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

from model.optimizer import optimize_route, compute_confidence
from api.gmaps import (
    get_distance_matrix, get_leg_duration_minutes,
    get_traffic_estimate, get_route_polyline, haversine_km,
)

MODEL_DIR   = "model/saved"
DATA_DIR    = "data"

# ── Load models once at import ──────────────────────────────────────────────────
_time_model   = None
_rank_model   = None
_kmeans_model = None
_cluster_map  = None
_driver_stats = None
_loc_history  = None
_loc_coords   = None
_loc_meta     = None
_city_centers = None


def _load_models() -> None:
    """Load all trained models and data from disk into global variables."""
    global _time_model, _rank_model, _kmeans_model, _cluster_map
    global _driver_stats, _loc_history, _loc_coords, _loc_meta, _city_centers

    if _time_model is None:
        _time_model   = joblib.load(f"{MODEL_DIR}/time_model.pkl")
        _rank_model   = joblib.load(f"{MODEL_DIR}/rank_model.pkl")
        _kmeans_model = joblib.load(f"{MODEL_DIR}/kmeans.pkl")

        with open(f"{MODEL_DIR}/cluster_map.json")    as f: _cluster_map  = json.load(f)
        with open(f"{MODEL_DIR}/driver_stats.json")   as f: _driver_stats = json.load(f)
        with open(f"{MODEL_DIR}/location_history.json") as f: _loc_history = json.load(f)
        with open(f"{DATA_DIR}/locations.json")       as f:
            locs = json.load(f)
            _loc_coords = {l["name"]: (l["latitude"], l["longitude"]) for l in locs}
            _loc_meta = {
                l["name"]: {
                    "city": l.get("city", "Ahmedabad"),
                    "area": l.get("area", l["name"].replace("_", " ")),
                }
                for l in locs
            }
            city_groups = {}
            for loc in locs:
                city_groups.setdefault(loc.get("city", "Ahmedabad"), []).append((loc["latitude"], loc["longitude"]))
            _city_centers = {
                city: (
                    sum(lat for lat, _ in coords) / len(coords),
                    sum(lon for _, lon in coords) / len(coords),
                )
                for city, coords in city_groups.items()
            }


def _get_driver_profile(driver_id: str) -> Dict[str, float]:
    """Retrieve driver profile with default values if not found."""
    _load_models()
    return _driver_stats.get(driver_id, {
        "avg_speed": 30.0, "avg_stops": 7, "avg_dist": 40.0,
        "efficiency": 0.85, "avg_visit_dur": 20.0,
    })


def _predict_leg_time(
    from_lat: float, from_lon: float,
    to_lat: float, to_lon: float,
    hour: int, dow: int, traffic_num: int,
    driver: Dict,
) -> float:
    """Use XGBoost to predict leg travel time in minutes."""
    dist = haversine_km(from_lat, from_lon, to_lat, to_lon)
    from_city_center = min(
        _city_centers.values(),
        key=lambda c: haversine_km(c[0], c[1], from_lat, from_lon),
    )
    to_city_center = min(
        _city_centers.values(),
        key=lambda c: haversine_km(c[0], c[1], to_lat, to_lon),
    )
    from_center = haversine_km(from_city_center[0], from_city_center[1], from_lat, from_lon)
    to_center = haversine_km(to_city_center[0], to_city_center[1], to_lat, to_lon)

    # Simple store density proxy
    from_density = sum(
        1 for (la, lo) in _loc_coords.values()
        if haversine_km(from_lat, from_lon, la, lo) <= 3.0
    )
    to_density = sum(
        1 for (la, lo) in _loc_coords.values()
        if haversine_km(to_lat, to_lon, la, lo) <= 3.0
    )

    X = pd.DataFrame([{
        "leg_distance_km":    dist,
        "expected_leg_min":   (dist / max(driver.get("avg_speed", 30.0), 1.0)) * 60 * (1 + 0.3 * traffic_num / 2),
        "from_hour":          hour,
        "traffic_num":        traffic_num,
        "day_of_week_num":    dow,
        "is_weekend":         int(dow >= 5),
        "driver_efficiency":  driver.get("efficiency", 0.85),
        "driver_avg_speed":   driver.get("avg_speed", 30.0),
        "from_dist_center":   from_center,
        "to_dist_center":     to_center,
        "from_store_density": from_density,
        "to_store_density":   to_density,
    }])
    return max(1.0, float(_time_model.predict(X)[0]))


# ─────────────────────────────────────────────────────────────────────────────
# Daily Prediction
# ─────────────────────────────────────────────────────────────────────────────

def predict_daily(
    driver_id: str,
    date: str,
    locations: List[str],
) -> Dict:
    """
    Predict optimal daily route for a driver.
    
    Business Scenario Implementation:
    - Learns from historical movement patterns (location_history)
    - Recommends optimized route to reduce: fuel cost, travel time, missed visits
    - Balances efficiency with driver capabilities
    
    Input:  driver_id, date (YYYY-MM-DD), locations list
    Output: recommended_route, predicted_time, confidence, legs, route score
    """
    _load_models()

    dt = datetime.strptime(date, "%Y-%m-%d")
    dow = dt.weekday()
    hour = 9  # Start of day assumption

    driver = _get_driver_profile(driver_id)

    # ── Resolve all locations to coordinates ────────────────────────────────────
    valid_locs = [l for l in locations if l in _loc_coords]
    unknown    = [l for l in locations if l not in _loc_coords]

    if not valid_locs:
        return {
            "error": f"None of the provided locations are in the system: {locations}",
            "known_locations": list(_loc_coords.keys())[:10],
        }

    # ── Optimize route using NN + 2-opt ─────────────────────────────────────────
    ordered_route, total_dist_km = optimize_route(valid_locs, _loc_coords, use_two_opt=True)

    # ── Build leg details using Google Maps + XGBoost ───────────────────────────
    legs = []
    total_travel_min = 0.0
    total_visit_min  = float(driver.get("avg_visit_dur", 20)) * len(ordered_route)
    visit_minutes = float(driver.get("avg_visit_dur", 20))
    current_clock = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    stop_etas = [{
        "stop": ordered_route[0],
        "eta": current_clock.strftime("%H:%M"),
        "latitude": _loc_coords[ordered_route[0]][0],
            "longitude": _loc_coords[ordered_route[0]][1],
            "cluster": _cluster_map.get(ordered_route[0], -1),
            **_loc_meta.get(ordered_route[0], {}),
        }] if ordered_route else []

    for i in range(len(ordered_route) - 1):
        frm = ordered_route[i]
        to  = ordered_route[i + 1]
        lat1, lon1 = _loc_coords[frm]
        lat2, lon2 = _loc_coords[to]

        current_hour = current_clock.hour
        traffic_num = 2 if current_hour in [8,9,10,17,18,19] else (1 if current_hour in [12,13] else 0)

        # XGBoost time prediction
        xgb_min = _predict_leg_time(lat1, lon1, lat2, lon2,
                                    current_hour, dow, traffic_num, driver)

        # Google Maps traffic estimate (or fallback)
        gm = get_traffic_estimate((lat1, lon1), (lat2, lon2))

        # Blend model and map estimates. If Google traffic is available, lean harder on it.
        map_weight = 0.65 if gm.get("source") == "google_maps" else 0.30
        model_weight = 1.0 - map_weight
        blended_min = round(model_weight * xgb_min + map_weight * gm["duration_in_traffic"], 2)
        total_travel_min += blended_min
        depart_at = current_clock.strftime("%H:%M")
        current_clock = current_clock + timedelta(minutes=blended_min + visit_minutes)

        legs.append({
            "from":           frm,
            "to":             to,
            "distance_km":    gm["distance_km"],
            "travel_min_xgb": round(xgb_min, 2),
            "travel_min_gm":  gm["duration_in_traffic"],
            "travel_min":     blended_min,
            "traffic":        "high" if traffic_num == 2 else ("medium" if traffic_num == 1 else "low"),
            "source":         gm.get("source", "google_maps"),
            "depart_at":      depart_at,
            "arrive_by":      current_clock.strftime("%H:%M"),
        })
        stop_etas.append({
            "stop": to,
            "eta": current_clock.strftime("%H:%M"),
            "latitude": lat2,
            "longitude": lon2,
            "cluster": _cluster_map.get(to, -1),
            **_loc_meta.get(to, {}),
        })

    # ── Total predicted time ─────────────────────────────────────────────────────
    total_hours = (total_travel_min + total_visit_min) / 60

    # ── Confidence score ─────────────────────────────────────────────────────────
    history = _loc_history.get(driver_id, [])
    conf = compute_confidence(ordered_route, history, driver.get("efficiency", 0.85), total_dist_km)

    # ── Route polyline (for map display) ────────────────────────────────────────
    waypoints = [_loc_coords[l] for l in ordered_route]
    route_map = get_route_polyline(waypoints)
    route_points = [
        {
            "name": loc,
            "latitude": _loc_coords[loc][0],
            "longitude": _loc_coords[loc][1],
            "cluster": _cluster_map.get(loc, -1),
            **_loc_meta.get(loc, {}),
        }
        for loc in ordered_route
    ]

    return {
        "driver_id":         driver_id,
        "date":              date,
        "day_of_week":       dt.strftime("%A"),
        "recommended_route": ordered_route,
        "unknown_locations": unknown,
        "total_stops":       len(ordered_route),
        "predicted_time":    f"{total_hours:.1f} hours",
        "travel_time_min":   round(total_travel_min, 1),
        "visit_time_min":    round(total_visit_min, 1),
        "total_distance_km": round(total_dist_km, 2),
        "confidence":        conf,
        "route_score":       round(conf * (1 / max(1, total_dist_km / 10)), 4),
        "legs":              legs,
        "stop_etas":         stop_etas,
        "route_points":      route_points,
        "map_polyline":      route_map.get("polyline", ""),
        "map_source":        route_map.get("source", ""),
        "prediction_basis": {
            "model": "XGBoost leg-time model + nearest-neighbor/2-opt routing",
            "map_estimate": legs[0]["source"] if legs else route_map.get("source", "none"),
            "blend": "65% map traffic / 35% ML when Google Maps is available, otherwise 30% fallback map / 70% ML",
            "start_time": "09:00",
            "visit_minutes_per_stop": round(visit_minutes, 1),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Weekly Prediction
# ─────────────────────────────────────────────────────────────────────────────

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

def predict_weekly(driver_id: str, week: str) -> Dict:
    """
    Generate a 5-day optimized schedule for a driver (ISO week).
    
    Business Scenario Implementation:
    - Learns from historical patterns and location preferences
    - Distributes visits across 5 days (Mon-Fri)
    - Balances daily workload based on driver profile and location clustering
    - Reduces unbalanced workload distribution
    
    Input:  driver_id, week in ISO format "YYYY-WNN"
    Output: per-day location lists, weekly_distance, total_time, optimization metrics
    """
    _load_models()

    # Parse ISO week → Monday date
    year, wnum = week.split("-W")
    monday = datetime.fromisocalendar(int(year), int(wnum), 1)

    driver = _get_driver_profile(driver_id)
    history = _loc_history.get(driver_id, [])

    # ── Assign all locations to clusters ─────────────────────────────────────────
    all_locs = list(_loc_coords.keys())

    # Use historical preference: pick locations this driver has visited most
    if history:
        hist_flat = [l for route in history for l in route]
        hist_counts = pd.Series(hist_flat).value_counts()
        # Score locations: frequency + cluster variety
        scored = []
        for loc in all_locs:
            freq = hist_counts.get(loc, 0)
            cluster = _cluster_map.get(loc, 0)
            scored.append((loc, freq, cluster))
        # Sort by frequency (desc)
        scored.sort(key=lambda x: -x[1])
        # Pick top ~35-40 locations
        n_locs = min(40, int(driver.get("avg_stops", 7) * 5))
        selected = [x[0] for x in scored[:n_locs]]
    else:
        n_locs = min(35, len(all_locs))
        selected = all_locs[:n_locs]

    # ── Split locations across weekdays by cluster ────────────────────────────────
    # Cluster-based assignment: group nearby stores together per day
    cluster_groups: Dict[int, List[str]] = {i: [] for i in range(5)}
    for loc in selected:
        c = _cluster_map.get(loc, 0) % 5
        cluster_groups[c].append(loc)

    # Assign clusters to days (balance load)
    daily_stops = int(driver.get("avg_stops", 7))
    schedule: Dict[str, List[str]] = {day: [] for day in WEEKDAYS}
    assigned_locs: set = set()

    all_selected = selected.copy()
    np.random.seed(42)
    np.random.shuffle(all_selected)

    for i, day in enumerate(WEEKDAYS):
        # Prefer cluster i for day i
        day_locs = [l for l in cluster_groups.get(i, []) if l not in assigned_locs][:daily_stops]
        # Top up from remaining if needed
        remaining = [l for l in all_selected if l not in assigned_locs and l not in day_locs]
        day_locs += remaining[:max(0, daily_stops - len(day_locs))]
        # Mark as assigned
        assigned_locs.update(day_locs)
        # Optimize order within day
        if day_locs:
            optimized, _ = optimize_route(day_locs, _loc_coords, use_two_opt=True)
            schedule[day] = optimized[:daily_stops]

    # ── Compute weekly totals ────────────────────────────────────────────────────
    total_dist = 0.0
    total_time_min = 0.0
    day_summaries = {}

    for i, day in enumerate(WEEKDAYS):
        date_str = (monday + timedelta(days=i)).strftime("%Y-%m-%d")
        locs = schedule[day]

        day_dist = 0.0
        for j in range(len(locs) - 1):
            lat1, lon1 = _loc_coords.get(locs[j], (0, 0))
            lat2, lon2 = _loc_coords.get(locs[j+1], (0, 0))
            day_dist += haversine_km(lat1, lon1, lat2, lon2)

        day_travel = (day_dist / driver.get("avg_speed", 30)) * 60
        day_visit  = driver.get("avg_visit_dur", 20) * len(locs)
        day_total  = day_travel + day_visit

        total_dist     += day_dist
        total_time_min += day_total

        day_summaries[day] = {
            "date":             date_str,
            "locations":        locs,
            "stop_count":       len(locs),
            "estimated_dist_km": round(day_dist, 2),
            "estimated_hours":  round(day_total / 60, 2),
        }

    return {
        "driver_id":            driver_id,
        "week":                 week,
        "week_start":           monday.strftime("%Y-%m-%d"),
        **{day: day_summaries[day]["locations"] for day in WEEKDAYS},
        "day_details":          day_summaries,
        "weekly_distance":      f"{total_dist:.1f}km",
        "weekly_distance_km":   round(total_dist, 2),
        "weekly_hours":         round(total_time_min / 60, 2),
        "total_stops":          sum(len(schedule[d]) for d in WEEKDAYS),
        "driver_profile": {
            "avg_speed_kmh":  driver.get("avg_speed", 30),
            "efficiency":     driver.get("efficiency", 0.85),
        },
    }
