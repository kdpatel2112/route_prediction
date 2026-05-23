"""
ML Model Trainer
================
Models:
1. XGBoostRegressor  → Travel time prediction per leg (minutes)
2. XGBoostClassifier → Stop-order preference (route ranking signal)
3. K-Means           → Location clustering for weekly schedule

Justification:
- XGBoost chosen for: tabular data superiority, handles mixed features,
  built-in feature importance, fast inference, no normalisation needed.
- K-Means for area clustering: groups locations into regions for balanced
  weekly schedule assignment.
"""

import pandas as pd
import numpy as np
import joblib
import os
import json
from typing import Dict, List, Tuple
from sklearn.cluster import KMeans
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score, accuracy_score
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb

from model.features import engineer_features, build_route_pairs

# ── Paths ───────────────────────────────────────────────────────────────────────
MODEL_DIR = "model/saved"
os.makedirs(MODEL_DIR, exist_ok=True)

class TravelTimeResidualModel:
    """Predict travel time as a baseline plus an XGBoost residual."""

    def __init__(self, residual_model):
        self.residual_model = residual_model

    def predict(self, X):
        baseline = X["expected_leg_min"].to_numpy()
        residual = self.residual_model.predict(X)
        return np.maximum(1.0, baseline + residual)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Travel-time Regression Model
# ─────────────────────────────────────────────────────────────────────────────
TIME_FEATURES = [
    "leg_distance_km", "expected_leg_min", "from_hour", "traffic_num",
    "day_of_week_num", "is_weekend", "driver_efficiency",
    "driver_avg_speed",
    "from_dist_center", "to_dist_center",
    "from_store_density", "to_store_density",
]

def train_time_model(df_pairs: pd.DataFrame) -> Tuple[TravelTimeResidualModel, Dict[str, float]]:
    """XGBoost regressor: predict leg travel time (minutes)."""
    df = df_pairs.dropna(subset=TIME_FEATURES + ["actual_travel_min"])
    X = df[TIME_FEATURES]
    y = df["actual_travel_min"] - df["expected_leg_min"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        tree_method="hist",
    )
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)],
              verbose=False)

    wrapped_model = TravelTimeResidualModel(model)
    y_test_actual = df.loc[X_test.index, "actual_travel_min"]
    y_pred = wrapped_model.predict(X_test)
    mae = mean_absolute_error(y_test_actual, y_pred)
    r2  = r2_score(y_test_actual, y_pred)

    print(f"[Time Model] MAE={mae:.2f} min  R²={r2:.4f}")

    joblib.dump(wrapped_model, f"{MODEL_DIR}/time_model.pkl")
    return wrapped_model, {"mae": round(mae, 4), "r2": round(r2, 4)}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Route-Order Ranking Model
# ─────────────────────────────────────────────────────────────────────────────
RANK_FEATURES = [
    "stop_progress", "dist_from_prev", "cumulative_dist",
    "visit_hour", "traffic_num", "day_of_week_num", "is_weekend",
    "dist_from_center", "store_density", "loc_popularity",
    "driver_avg_speed", "driver_avg_stops", "driver_efficiency",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "stop_order",
]

def train_rank_model(df_feat: pd.DataFrame) -> Tuple[xgb.XGBClassifier, Dict[str, float]]:
    """
    XGBoost classifier: predict stop order bucket (early/mid/late).
    Used as a scoring function to re-rank candidate routes.
    """
    df = df_feat.dropna(subset=RANK_FEATURES).copy()

    # Target: is this stop in the first half of the route?
    df["early_stop"] = (df["stop_order"] <= df["total_stops"] / 2).astype(int)

    X = df[RANK_FEATURES]
    y = df["early_stop"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
        tree_method="hist",
        eval_metric="logloss",
    )
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)],
              verbose=False)

    acc = accuracy_score(y_test, model.predict(X_test))
    print(f"[Rank Model] Accuracy={acc:.4f}")

    joblib.dump(model, f"{MODEL_DIR}/rank_model.pkl")
    return model, {"accuracy": round(acc, 4)}


# ─────────────────────────────────────────────────────────────────────────────
# 3. K-Means Clustering for Weekly Schedule
# ─────────────────────────────────────────────────────────────────────────────
def train_kmeans(locations_path: str = "data/locations.json", n_clusters: int = 5) -> Tuple[KMeans, Dict[str, int]]:
    """K-Means on geographic coordinates for region clustering."""
    with open(locations_path) as f:
        locs = json.load(f)

    names  = [l["name"] for l in locs]
    coords = np.array([[l["latitude"], l["longitude"]] for l in locs])

    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = model.fit_predict(coords)

    cluster_map = {name: int(label) for name, label in zip(names, labels)}

    joblib.dump(model, f"{MODEL_DIR}/kmeans.pkl")
    with open(f"{MODEL_DIR}/cluster_map.json", "w") as f:
        json.dump(cluster_map, f, indent=2)

    print(f"[K-Means] {n_clusters} clusters for {len(names)} locations")
    return model, cluster_map


# ─────────────────────────────────────────────────────────────────────────────
# 4. Driver Statistics (used at inference)
# ─────────────────────────────────────────────────────────────────────────────
def build_driver_stats(df_feat: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Build and save driver profile statistics from features."""
    stats = df_feat.groupby("driver_id").agg(
        avg_speed        = ("avg_speed_kmh", "mean"),
        avg_stops        = ("total_stops", "mean"),
        avg_dist         = ("route_distance_km", "mean"),
        efficiency       = ("driver_efficiency", "first"),
        avg_visit_dur    = ("visit_duration", "mean"),
    ).reset_index()

    result = stats.set_index("driver_id").to_dict(orient="index")
    with open(f"{MODEL_DIR}/driver_stats.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"[Driver Stats] Saved stats for {len(result)} drivers")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5. Location History Index (for confidence scoring)
# ─────────────────────────────────────────────────────────────────────────────
def build_location_history(df_feat: pd.DataFrame) -> Dict[str, List[List[str]]]:
    """Save per-driver historical route sequences."""
    history = {}
    for driver_id, grp in df_feat.groupby("driver_id"):
        driver_routes = []
        for trip_id, trip in grp.groupby("trip_id"):
            trip_sorted = trip.sort_values("stop_order")
            driver_routes.append(trip_sorted["stop_name"].tolist())
        history[driver_id] = driver_routes[-50:]  # Keep last 50 routes

    with open(f"{MODEL_DIR}/location_history.json", "w") as f:
        json.dump(history, f, indent=2)
    print(f"[History] Saved route history for {len(history)} drivers")
    return history


# ─────────────────────────────────────────────────────────────────────────────
# Master Training Function
# ─────────────────────────────────────────────────────────────────────────────
def train_all(trips_csv: str = "data/trips.csv", locations_json: str = "data/locations.json") -> Dict:
    """Master training function - trains all ML models end-to-end."""
    print("=" * 60)
    print("  TRAINING ROUTE PREDICTION MODELS")
    print("=" * 60)

    # Load & engineer features
    df_raw = pd.read_csv(trips_csv)
    print(f"\nLoaded {len(df_raw)} raw records from {trips_csv}")

    df_feat = engineer_features(df_raw, locations_json)
    df_pairs = build_route_pairs(df_feat)

    print(f"Feature matrix shape: {df_feat.shape}")
    print(f"Route pairs shape:    {df_pairs.shape}\n")

    # Train models
    time_model, time_metrics  = train_time_model(df_pairs)
    rank_model, rank_metrics  = train_rank_model(df_feat)
    kmeans_model, cluster_map = train_kmeans(locations_json, n_clusters=5)
    driver_stats              = build_driver_stats(df_feat)
    location_history          = build_location_history(df_feat)

    # Save metadata
    metadata = {
        "time_model":   time_metrics,
        "rank_model":   rank_metrics,
        "n_clusters":   5,
        "n_drivers":    len(driver_stats),
        "n_locations":  len(cluster_map),
        "features": {
            "time": TIME_FEATURES,
            "rank": RANK_FEATURES,
        },
    }
    with open(f"{MODEL_DIR}/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print("\n" + "=" * 60)
    print("  TRAINING COMPLETE")
    print(f"  Models saved to: {MODEL_DIR}/")
    print(f"  Time MAE : {time_metrics['mae']} min")
    print(f"  Rank Acc : {rank_metrics['accuracy']}")
    print("=" * 60)

    return {
        "time_model": time_model,
        "rank_model": rank_model,
        "kmeans":     kmeans_model,
        "metadata":   metadata,
    }


if __name__ == "__main__":
    train_all()
