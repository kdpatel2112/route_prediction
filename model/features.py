"""
Feature Engineering for Route Prediction
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from typing import Dict, Tuple
import json, os

# ── Location coordinates (loaded once) ─────────────────────────────────────────
_LOC_COORDS: Dict[str, Tuple[float, float]] = {}

def _load_coords(path: str = "data/locations.json") -> Dict[str, Tuple[float, float]]:
    """Load location coordinates from JSON file."""
    global _LOC_COORDS
    if not _LOC_COORDS:
        with open(path) as f:
            locs = json.load(f)
        _LOC_COORDS = {l["name"]: (l["latitude"], l["longitude"]) for l in locs}
    return _LOC_COORDS

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two lat/lon points in km."""
    R = 6371
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

# ─────────────────────────────────────────────────────────────────────────────
def engineer_features(df: pd.DataFrame, coords_path="data/locations.json") -> pd.DataFrame:
    """
    Build all model features from raw trip data.
    Returns enriched DataFrame ready for ML.
    """
    coords = _load_coords(coords_path)
    df = df.copy()

    # ── Time features ──────────────────────────────────────────────────────────
    df["date"] = pd.to_datetime(df["date"])
    df["day_of_week_num"] = df["date"].dt.dayofweek
    df["day_of_week"]     = df["date"].dt.day_name()
    df["week_number"]     = df["date"].dt.isocalendar().week.astype(int)
    df["month"]           = df["date"].dt.month
    df["quarter"]         = df["date"].dt.quarter
    df["is_weekend"]      = (df["day_of_week_num"] >= 5).astype(int)
    df["is_month_start"]  = (df["date"].dt.day <= 5).astype(int)
    df["is_month_end"]    = (df["date"].dt.day >= 25).astype(int)

    # Cyclical encoding for time
    df["hour_sin"]    = np.sin(2 * np.pi * df["visit_hour"] / 24)
    df["hour_cos"]    = np.cos(2 * np.pi * df["visit_hour"] / 24)
    df["dow_sin"]     = np.sin(2 * np.pi * df["day_of_week_num"] / 7)
    df["dow_cos"]     = np.cos(2 * np.pi * df["day_of_week_num"] / 7)
    df["month_sin"]   = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"]   = np.cos(2 * np.pi * df["month"] / 12)

    # ── Traffic category encoding ──────────────────────────────────────────────
    traffic_map = {"low": 0, "medium": 1, "high": 2}
    df["traffic_num"] = df["traffic_category"].map(traffic_map).fillna(0).astype(int)

    # ── Route-level features ───────────────────────────────────────────────────
    df["stop_progress"]  = df["stop_order"] / df["total_stops"]  # 0→1

    # Compute distance from previous stop per trip
    df = df.sort_values(["trip_id", "stop_order"]).reset_index(drop=True)
    df["prev_lat"] = df.groupby("trip_id")["latitude"].shift(1)
    df["prev_lon"] = df.groupby("trip_id")["longitude"].shift(1)
    df["dist_from_prev"] = df.apply(
        lambda r: haversine(r["prev_lat"], r["prev_lon"], r["latitude"], r["longitude"])
        if pd.notna(r["prev_lat"]) else 0.0, axis=1
    )

    # Cumulative distance along the route
    df["cumulative_dist"] = df.groupby("trip_id")["dist_from_prev"].cumsum()

    # ── Location features ──────────────────────────────────────────────────────
    with open(coords_path) as f:
        loc_rows = json.load(f)
    loc_df = pd.DataFrame(loc_rows)
    if "city" not in loc_df:
        loc_df["city"] = "Ahmedabad"
    city_centers = loc_df.groupby("city")[["latitude", "longitude"]].mean().to_dict(orient="index")
    loc_city = loc_df.set_index("name")["city"].to_dict()
    df["city"] = df["stop_name"].map(loc_city).fillna("Ahmedabad")
    df["center_lat"] = df["city"].map(lambda city: city_centers.get(city, {}).get("latitude", 23.0225))
    df["center_lon"] = df["city"].map(lambda city: city_centers.get(city, {}).get("longitude", 72.5714))

    # Distance from each stop to its own city centre.
    df["dist_from_center"] = df.apply(
        lambda r: haversine(r["center_lat"], r["center_lon"], r["latitude"], r["longitude"]),
        axis=1
    )

    # Region labelling (quadrant-based)
    df["region"] = df.apply(_assign_region, axis=1)

    # Store density — count of locations within 3 km
    location_list = list(coords.values())
    df["store_density"] = df.apply(
        lambda r: sum(
            1 for (la, lo) in location_list
            if haversine(r["latitude"], r["longitude"], la, lo) <= 3.0
        ),
        axis=1
    )

    # ── Driver features ────────────────────────────────────────────────────────
    driver_stats = df.groupby("driver_id").agg(
        driver_avg_stops  = ("total_stops", "mean"),
        driver_avg_speed  = ("avg_speed_kmh", "mean"),
        driver_avg_dist   = ("route_distance_km", "mean"),
        driver_efficiency_agg = ("driver_efficiency", "first"),
    ).reset_index()
    df = df.merge(driver_stats, on="driver_id", how="left")

    # Historical visit frequency per location
    loc_freq = df.groupby("stop_name").size().reset_index(name="loc_visit_count")
    df = df.merge(loc_freq, on="stop_name", how="left")
    df["loc_popularity"] = df["loc_visit_count"] / df["loc_visit_count"].max()

    # ── Label encode categoricals ──────────────────────────────────────────────
    for col in ["driver_id", "stop_name", "region"]:
        le = LabelEncoder()
        df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))

    # ── Route efficiency score (target-like feature) ───────────────────────────
    # Lower score = more efficient (normalized total distance per stop)
    df["route_efficiency"] = df.groupby("trip_id")["dist_from_prev"].transform("sum") / df["total_stops"]

    return df


def _assign_region(row: pd.Series) -> str:
    """Assign geographic region based on latitude/longitude."""
    lat, lon = row["latitude"], row["longitude"]
    CENTER_LAT = row.get("center_lat", 23.0225)
    CENTER_LON = row.get("center_lon", 72.5714)
    ns = "North" if lat >= CENTER_LAT else "South"
    ew = "East"  if lon >= CENTER_LON else "West"
    return f"{ns}_{ew}"


def build_route_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build pairwise (from→to) records for the route-ranking model.
    Each row represents one leg of a trip.
    """
    pairs = []
    for trip_id, group in df.groupby("trip_id"):
        group = group.sort_values("stop_order").reset_index(drop=True)
        for i in range(len(group) - 1):
            cur  = group.iloc[i]
            nxt  = group.iloc[i + 1]
            dist = haversine(cur["latitude"], cur["longitude"],
                             nxt["latitude"], nxt["longitude"])
            pairs.append({
                "trip_id":          trip_id,
                "driver_id":        cur["driver_id"],
                "date":             cur["date"],
                "from_stop":        cur["stop_name"],
                "to_stop":          nxt["stop_name"],
                "from_lat":         cur["latitude"],
                "from_lon":         cur["longitude"],
                "to_lat":           nxt["latitude"],
                "to_lon":           nxt["longitude"],
                "leg_distance_km":  round(dist, 3),
                "expected_leg_min": round(
                    (dist / cur["avg_speed_kmh"]) * 60 * (1 + 0.3 * cur["traffic_num"] / 2),
                    2
                ),
                "from_hour":        cur["visit_hour"],
                "traffic_num":      cur["traffic_num"],
                "day_of_week_num":  cur["day_of_week_num"],
                "is_weekend":       cur["is_weekend"],
                "driver_efficiency": cur.get("driver_efficiency", cur.get("driver_avg_speed", 0.85)),
                "driver_avg_speed": cur.get("driver_avg_speed", cur.get("avg_speed_kmh", 30)),
                "from_dist_center": cur["dist_from_center"],
                "to_dist_center":   nxt["dist_from_center"],
                "from_store_density": cur["store_density"],
                "to_store_density":   nxt["store_density"],
                # Target: actual travel time in minutes
                "actual_travel_min": round(
                    (dist / cur["avg_speed_kmh"]) * 60 * (1 + 0.3 * cur["traffic_num"] / 2),
                    2
                ),
            })
    return pd.DataFrame(pairs)


if __name__ == "__main__":
    df_raw = pd.read_csv("data/trips.csv")
    df_feat = engineer_features(df_raw)
    df_feat.to_csv("data/trips_features.csv", index=False)

    df_pairs = build_route_pairs(df_feat)
    df_pairs.to_csv("data/route_pairs.csv", index=False)

    print(f"Feature-engineered records: {len(df_feat)}")
    print(f"Route-pair records:         {len(df_pairs)}")
    print(f"Features: {[c for c in df_feat.columns]}")
