"""
Unit Tests for Route Prediction API
====================================
Run with: pytest tests/ -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


# ── Health Check ─────────────────────────────────────────────────────────────────

def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200

def test_health_has_required_fields():
    resp = client.get("/health")
    data = resp.json()
    assert "status" in data
    assert "uptime_sec" in data
    assert "models_loaded" in data
    assert "timestamp" in data


# ── Daily Prediction ──────────────────────────────────────────────────────────────

DAILY_PAYLOAD = {
    "driver_id": "D1",
    "date": "2026-05-20",
    "locations": [
        "Navrangpura_Store",
        "CG_Road_Outlet",
        "Satellite_Branch",
        "Vastrapur_Shop",
    ]
}

def test_predict_daily_returns_200():
    resp = client.post("/predict/daily", json=DAILY_PAYLOAD)
    assert resp.status_code == 200

def test_predict_daily_has_required_fields():
    resp = client.post("/predict/daily", json=DAILY_PAYLOAD)
    data = resp.json()
    assert "recommended_route" in data
    assert "predicted_time"    in data
    assert "confidence"        in data

def test_predict_daily_route_contains_all_valid_locations():
    resp = client.post("/predict/daily", json=DAILY_PAYLOAD)
    data = resp.json()
    route = set(data["recommended_route"])
    expected = set(DAILY_PAYLOAD["locations"])
    # All valid locations should appear in the route
    assert expected.issubset(route | set(data.get("unknown_locations", [])))

def test_predict_daily_confidence_in_range():
    resp = client.post("/predict/daily", json=DAILY_PAYLOAD)
    data = resp.json()
    conf = data["confidence"]
    assert 0.0 <= conf <= 1.0

def test_predict_daily_predicted_time_format():
    resp = client.post("/predict/daily", json=DAILY_PAYLOAD)
    data = resp.json()
    pt = data["predicted_time"]
    assert "hours" in pt

def test_predict_daily_invalid_date():
    payload = {**DAILY_PAYLOAD, "date": "not-a-date"}
    resp = client.post("/predict/daily", json=payload)
    assert resp.status_code == 422

def test_predict_daily_too_few_locations():
    payload = {**DAILY_PAYLOAD, "locations": ["Navrangpura_Store"]}
    resp = client.post("/predict/daily", json=payload)
    assert resp.status_code == 422

def test_predict_daily_unknown_driver():
    payload = {**DAILY_PAYLOAD, "driver_id": "D999"}
    resp = client.post("/predict/daily", json=payload)
    # Should still return result (uses default profile)
    assert resp.status_code == 200


# ── Weekly Prediction ─────────────────────────────────────────────────────────────

WEEKLY_PAYLOAD = {"driver_id": "D1", "week": "2026-W21"}

def test_predict_weekly_returns_200():
    resp = client.post("/predict/weekly", json=WEEKLY_PAYLOAD)
    assert resp.status_code == 200

def test_predict_weekly_has_all_weekdays():
    resp = client.post("/predict/weekly", json=WEEKLY_PAYLOAD)
    data = resp.json()
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        assert day in data, f"Missing {day}"

def test_predict_weekly_has_weekly_distance():
    resp = client.post("/predict/weekly", json=WEEKLY_PAYLOAD)
    data = resp.json()
    assert "weekly_distance" in data
    assert "km" in data["weekly_distance"]

def test_predict_weekly_invalid_week_format():
    resp = client.post("/predict/weekly", json={"driver_id": "D1", "week": "2026-20"})
    assert resp.status_code == 422

def test_predict_weekly_each_day_is_list():
    resp = client.post("/predict/weekly", json=WEEKLY_PAYLOAD)
    data = resp.json()
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        assert isinstance(data[day], list)


# ── Retrain ───────────────────────────────────────────────────────────────────────

def test_retrain_without_confirm():
    resp = client.post("/retrain", json={"confirm": False})
    assert resp.status_code == 200
    assert "confirm=true" in resp.json()["message"]

def test_retrain_missing_file():
    resp = client.post("/retrain", json={"confirm": True, "data_path": "nonexistent.csv"})
    assert resp.status_code == 404


# ── Data Endpoints ────────────────────────────────────────────────────────────────

def test_list_drivers():
    resp = client.get("/drivers")
    assert resp.status_code == 200
    data = resp.json()
    assert "drivers" in data
    assert data["total"] >= 12

def test_list_locations():
    resp = client.get("/locations")
    assert resp.status_code == 200
    data = resp.json()
    assert "locations" in data
    assert data["total"] >= 53

def test_list_locations_filter_by_cluster():
    resp = client.get("/locations?cluster=0")
    assert resp.status_code == 200
    data = resp.json()
    for loc in data["locations"]:
        assert loc["cluster"] == 0


# ── System Endpoints ──────────────────────────────────────────────────────────────

def test_cache_stats():
    resp = client.get("/cache/stats")
    assert resp.status_code == 200
    assert "cached_entries" in resp.json()

def test_model_metrics():
    resp = client.get("/model/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "time_model" in data
    assert "rank_model" in data

def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "endpoints" in resp.json()


# ── Model Accuracy Threshold ──────────────────────────────────────────────────────

def test_time_model_mae_below_threshold():
    resp = client.get("/model/metrics")
    data = resp.json()
    mae = data.get("time_model", {}).get("mae", 999)
    assert mae < 5.0, f"MAE too high: {mae}"

def test_rank_model_accuracy_above_threshold():
    resp = client.get("/model/metrics")
    data = resp.json()
    acc = data.get("rank_model", {}).get("accuracy", 0)
    assert acc > 0.70, f"Accuracy too low: {acc}"
