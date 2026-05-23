"""
Route Prediction API
====================
FastAPI application exposing all required endpoints.

Endpoints:
  POST /predict/daily    → Predict optimal daily route
  POST /predict/weekly   → Predict weekly schedule
  POST /retrain          → Retrain models on latest data
  GET  /health           → Health check

Bonus:
  GET  /drivers          → List all known drivers
  GET  /locations        → List all known locations
  GET  /cache/stats      → Google API cache statistics
  GET  /model/metrics    → Model performance metrics
"""

import os, sys, json, time
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.predictor import predict_daily, predict_weekly
from api.gmaps import cache_stats, get_nearby_places, get_place_details, geocode

# ── App Setup ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Route Prediction System",
    description=(
        "Predicts optimized routes for field sales drivers using "
        "XGBoost ML models, Google Maps APIs, and 2-opt route optimization."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
if os.path.isdir(WEB_DIR):
    app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="web")

_start_time = time.time()


# ── Request / Response Schemas ───────────────────────────────────────────────────

class DailyPredictRequest(BaseModel):
    driver_id: str = Field(..., example="D1", description="Driver identifier")
    date: str = Field(..., example="2026-05-20", description="Date in YYYY-MM-DD format")
    locations: List[str] = Field(..., min_items=2, example=["Navrangpura_Store","CG_Road_Outlet","Satellite_Branch","Vastrapur_Shop"])

    @validator("date")
    def validate_date(cls, v: str) -> str:
        """Validate date format YYYY-MM-DD."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be YYYY-MM-DD")
        return v


class WeeklyPredictRequest(BaseModel):
    driver_id: str = Field(..., example="D1", description="Driver identifier")
    week: str = Field(..., example="2026-W21", description="ISO week in YYYY-WNN format")

    @validator("week")
    def validate_week(cls, v: str) -> str:
        """Validate ISO week format YYYY-WNN."""
        parts = v.split("-W")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ValueError("week must be YYYY-WNN, e.g. 2026-W21")
        try:
            datetime.fromisocalendar(int(parts[0]), int(parts[1]), 1)
        except ValueError:
            raise ValueError("week must be a valid ISO week, e.g. 2026-W21")
        return v


class RetrainRequest(BaseModel):
    data_path: Optional[str] = Field(
        default="data/trips.csv",
        description="Path to trips CSV for retraining"
    )
    confirm: bool = Field(default=False, description="Set True to confirm retraining")


class NearbyPlacesRequest(BaseModel):
    lat: float = Field(..., example=23.0395)
    lon: float = Field(..., example=72.5603)
    radius_meters: int = Field(default=2000, ge=100, le=50000)
    place_type: str = Field(default="store")


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _load_metadata() -> Dict:
    """Load model training metadata from saved JSON."""
    path = "model/saved/metadata.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def _load_driver_list() -> List[str]:
    """Load list of known driver IDs from driver statistics."""
    path = "model/saved/driver_stats.json"
    if os.path.exists(path):
        with open(path) as f:
            return list(json.load(f).keys())
    return []

def _load_locations() -> List[Dict]:
    """Load location data from JSON file."""
    path = "data/locations.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


# ── Endpoints ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check")
def health_check() -> Dict:
    """Returns API status, uptime, and model readiness."""
    meta = _load_metadata()
    models_ready = os.path.exists("model/saved/time_model.pkl")
    return {
        "status": "ok" if models_ready else "degraded",
        "uptime_sec": round(time.time() - _start_time, 1),
        "models_loaded": models_ready,
        "model_metrics": meta,
        "google_api_key_set": bool(os.getenv("GOOGLE_MAPS_API_KEY", "")),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/predict/daily", tags=["Predictions"], summary="Predict optimal daily route")
def predict_daily_route(req: DailyPredictRequest) -> Dict:
    """
    Predict the best stop order for a driver on a given date.

    - Uses XGBoost + Google Maps to estimate travel times
    - Applies Nearest Neighbor + 2-opt optimization
    - Returns confidence score and route score
    """
    try:
        result = predict_daily(req.driver_id, req.date, req.locations)
        if "error" in result:
            raise HTTPException(status_code=422, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/weekly", tags=["Predictions"], summary="Predict weekly schedule")
def predict_weekly_route(req: WeeklyPredictRequest) -> Dict:
    """
    Generate a 5-day optimized schedule for a driver for a given ISO week.

    - Groups locations by geographic cluster (K-Means)
    - Balances daily workload based on driver profile
    - Returns per-day location lists and weekly totals
    """
    try:
        result = predict_weekly(req.driver_id, req.week)
        if "error" in result:
            raise HTTPException(status_code=422, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retrain", tags=["Model"], summary="Retrain ML models")
def retrain_model(req: RetrainRequest, background_tasks: BackgroundTasks) -> Dict:
    """
    Retrain all ML models on latest trip data.
    Set confirm=true to execute. Runs in background.
    """
    if not req.confirm:
        return {
            "message": "Set confirm=true to proceed with retraining.",
            "warning": "Retraining will overwrite existing models.",
            "data_path": req.data_path,
        }

    if not os.path.exists(req.data_path):
        raise HTTPException(
            status_code=404,
            detail=f"Data file not found: {req.data_path}"
        )

    def _run_retrain() -> None:
        """Background task to retrain models."""
        from model.trainer import train_all
        train_all(trips_csv=req.data_path)

    background_tasks.add_task(_run_retrain)
    return {
        "status": "retraining_started",
        "message": "Models are being retrained in the background.",
        "data_path": req.data_path,
        "check_status": "/health",
    }


@app.get("/drivers", tags=["Data"], summary="List all known drivers")
def list_drivers() -> Dict:
    """Returns all driver IDs in the system with their profiles."""
    path = "model/saved/driver_stats.json"
    if not os.path.exists(path):
        raise HTTPException(status_code=503, detail="Models not trained yet")
    with open(path) as f:
        stats = json.load(f)
    return {
        "drivers": [
            {"driver_id": k, **v} for k, v in stats.items()
        ],
        "total": len(stats),
    }


@app.get("/locations", tags=["Data"], summary="List all known locations")
def list_locations(
    cluster: Optional[int] = Query(default=None, description="Filter by cluster (0-4)"),
    city: Optional[str] = Query(default=None, description="Filter by city name"),
) -> Dict:
    """Returns all location names with coordinates and cluster assignments."""
    locs = _load_locations()
    cluster_path = "model/saved/cluster_map.json"
    cluster_map = {}
    if os.path.exists(cluster_path):
        with open(cluster_path) as f:
            cluster_map = json.load(f)

    result = [
        {
            "name":      l["name"],
            "latitude":  l["latitude"],
            "longitude": l["longitude"],
            "city":      l.get("city", "Ahmedabad"),
            "area":      l.get("area", l["name"].replace("_", " ")),
            "cluster":   cluster_map.get(l["name"], -1),
        }
        for l in locs
    ]

    if cluster is not None:
        result = [r for r in result if r["cluster"] == cluster]
    if city is not None:
        result = [r for r in result if r["city"].lower() == city.lower()]

    return {"locations": result, "total": len(result)}


@app.post("/places/nearby", tags=["Google Maps"], summary="Search nearby places")
def nearby_places(req: NearbyPlacesRequest) -> Dict:
    """Search for nearby stores/businesses using Google Places API."""
    results = get_nearby_places(req.lat, req.lon, req.radius_meters, req.place_type)
    return {"results": results, "count": len(results)}


@app.get("/places/{place_id}", tags=["Google Maps"], summary="Get place details")
def place_details(place_id: str) -> Dict:
    """Get detailed information about a place by Google Place ID."""
    result = get_place_details(place_id)
    if not result:
        raise HTTPException(status_code=404, detail="Place not found")
    return result


@app.get("/geocode", tags=["Google Maps"], summary="Geocode an address")
def geocode_address(address: str = Query(..., description="Address to geocode")) -> Dict:
    """Convert an address string to lat/lon coordinates."""
    coords = geocode(address)
    if coords:
        return {"address": address, "latitude": coords[0], "longitude": coords[1]}
    return {"address": address, "latitude": None, "longitude": None,
            "note": "Not found or API key not set"}


@app.get("/cache/stats", tags=["System"], summary="Google API cache statistics")
def api_cache_stats() -> Dict:
    """Returns cached API call count (bonus: caching feature)."""
    return cache_stats()


@app.get("/model/metrics", tags=["Model"], summary="Model performance metrics")
def model_metrics() -> Dict:
    """Returns training metrics for all models."""
    meta = _load_metadata()
    if not meta:
        raise HTTPException(status_code=503, detail="No model metadata found")
    return meta


@app.get("/", tags=["System"])
def root() -> Dict:
    """API root endpoint - returns service info and available endpoints."""
    return {
        "service": "AI Route Prediction System",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "predict_daily":  "POST /predict/daily",
            "predict_weekly": "POST /predict/weekly",
            "retrain":        "POST /retrain",
            "health":         "GET  /health",
            "drivers":        "GET  /drivers",
            "locations":      "GET  /locations",
        },
    }
