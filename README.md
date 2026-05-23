# AI Route Prediction System

> **End-to-end ML system** that predicts optimal daily and weekly routes for field sales drivers using XGBoost, Google Maps APIs, and 2-opt route optimization.

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Architecture](#architecture)
- [Model Selection & Justification](#model-selection--justification)
- [Feature Engineering](#feature-engineering)
- [Google APIs Used](#google-apis-used)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Docker Deployment](#docker-deployment)
- [Running Tests](#running-tests)
- [Dataset](#dataset)
- [Evaluation Checklist](#evaluation-checklist)

---

## Problem Statement

Field sales drivers manually plan routes daily, causing:
- Extra fuel costs
- Longer travel times
- Missed store visits
- Unbalanced workloads

This system learns from **8,739 historical trip records** across **12 drivers** and **173 locations** across Ahmedabad and major Indian cities to automatically recommend optimized routes.

---

## Architecture

```
project/
├── data/
│   ├── trips.csv              # 8,739 synthetic trip records
│   ├── locations.json         # 173 locations with coordinates, city, and area
│   ├── route_pairs.csv        # Leg-level training data
│   └── gmaps_cache.db         # SQLite cache for Google API calls (bonus)
│
├── model/
│   ├── features.py            # Feature engineering pipeline
│   ├── optimizer.py           # Nearest Neighbor + 2-opt TSP solver
│   ├── trainer.py             # XGBoost + K-Means training
│   └── saved/
│       ├── time_model.pkl     # XGBoost travel time regressor
│       ├── rank_model.pkl     # XGBoost stop-order ranker
│       ├── kmeans.pkl         # K-Means location clusterer
│       ├── cluster_map.json   # Location → cluster mapping
│       ├── driver_stats.json  # Per-driver profiles
│       ├── location_history.json  # Historical route sequences
│       └── metadata.json      # Model metrics
│
├── api/
│   ├── main.py                # FastAPI application
│   ├── predictor.py           # Prediction engine
│   └── gmaps.py               # Google Maps integration + caching
│
├── scripts/
│   ├── generate_data.py       # Synthetic dataset generator
│   └── train.py               # Full training pipeline
│
├── tests/
│   └── test_api.py            # 25 unit tests (all passing)
│
├── .env.example
├── requirements.txt
├── dockerfile
└── README.md
```

---

## Model Selection & Justification

### 1. XGBoost Regressor — Travel Time Prediction
**Why XGBoost?**
- Superior performance on tabular data vs. deep learning at this scale
- Handles mixed feature types (numerical + categorical) natively
- Built-in feature importance for interpretability
- No normalization required
- Fast training (~5s) and inference (<1ms per prediction)

**Performance:**
- MAE: **0.40 minutes** on held-out test set
- R²: **0.9987** — explains 99.87% of travel time variance

### 2. XGBoost Classifier — Route Stop Ranker
**Why?**
- Ranks stops as "visit early" vs "visit late" in a route
- Combined with 2-opt optimizer for final ordering
- Accuracy: **100%** on test set (clear geometric patterns in training data)

### 3. K-Means Clustering — Weekly Schedule Builder
**Why K-Means?**
- Groups geographically close locations into daily clusters
- Ensures drivers work in one area per day (reduces cross-city travel)
- 5 clusters map naturally to 5 working days
- Fast, interpretable, no labels needed

### 4. Nearest Neighbor + 2-opt — Route Optimizer
**Why?**
- Nearest Neighbor provides a good initial solution in O(n²)
- 2-opt improvement removes crossing paths, reducing total distance 15-30%
- Multiple start points tried → best selected
- Deterministic and fast for 3-15 stop routes

---

## Feature Engineering

### Time Features
| Feature | Description |
|---------|-------------|
| `day_of_week_num` | 0=Monday ... 6=Sunday |
| `hour_sin / hour_cos` | Cyclical encoding of visit hour |
| `dow_sin / dow_cos` | Cyclical encoding of day of week |
| `month_sin / month_cos` | Cyclical encoding of month |
| `is_weekend` | Binary flag |
| `is_month_start/end` | Binary flags for sales cycle patterns |

### Route Features
| Feature | Description |
|---------|-------------|
| `stop_progress` | Position in route (0→1) |
| `dist_from_prev` | Distance from previous stop |
| `cumulative_dist` | Total distance covered so far |
| `leg_distance_km` | Haversine distance per leg |
| `route_efficiency` | Total distance per stop count |

### Driver Features
| Feature | Description |
|---------|-------------|
| `driver_avg_speed` | Historical average speed |
| `driver_avg_stops` | Historical stops per day |
| `driver_efficiency` | Past route efficiency score |
| `driver_avg_dist` | Historical daily distance |

### Location Features
| Feature | Description |
|---------|-------------|
| `dist_from_center` | Distance from each stop's own city centre |
| `store_density` | Count of stores within 3km |
| `loc_popularity` | Historical visit frequency (normalized) |
| `region` | Quadrant: North/South × East/West |
| `traffic_category` | low / medium / high |

---

## Google APIs Used

| API | Usage | Endpoint |
|-----|-------|----------|
| **Distance Matrix API** | Leg distances + travel durations | `/distancematrix/json` |
| **Routes API** | Full route polyline with traffic | `/directions/v2:computeRoutes` |
| **Places API (Nearby Search)** | Find stores near coordinates | `/place/nearbysearch/json` |
| **Places API (Details)** | Place details by ID | `/place/details/json` |
| **Geocoding API** | Address → coordinates | `/geocode/json` |

### API Caching (Bonus Feature)
All Google API calls are cached in a local SQLite database (`data/gmaps_cache.db`).
- Cache key: MD5 hash of request parameters
- Prevents redundant API calls for identical routes
- Check cache stats: `GET /cache/stats`

---

## Quick Start

### Prerequisites
```bash
python >= 3.10
pip
```

### 1. Clone and Install
```bash
git clone <repo>
cd route_prediction
pip install -r requirements.txt
```

### 2. Configure Google Maps API Key (Optional)
```bash
cp .env.example .env
# Edit .env and add your GOOGLE_MAPS_API_KEY
# Without key: haversine fallback is used (still works)
```

Enable these APIs in Google Cloud Console:
- Distance Matrix API
- Routes API
- Places API
- Geocoding API

### 3. Generate Data and Train Models
```bash
python scripts/train.py
```

Output:
```
Step 1: Generating synthetic dataset...
  → 8739 records, 12 drivers, 173 locations
Step 2: Training ML models...
[Time Model] MAE=0.40 min  R²=0.9987
[Rank Model] Accuracy=1.0000
[K-Means] 5 clusters for 173 locations
```

### 4. Start the API
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000/docs for the interactive Swagger UI.

---

## API Reference

### POST /predict/daily

Predict the optimal route for a driver on a given date.

**Request:**
```json
{
  "driver_id": "D1",
  "date": "2026-05-20",
  "locations": ["Navrangpura_Store", "CG_Road_Outlet", "Satellite_Branch", "Vastrapur_Shop"]
}
```

**Response:**
```json
{
  "driver_id": "D1",
  "date": "2026-05-20",
  "day_of_week": "Wednesday",
  "recommended_route": ["Navrangpura_Store", "CG_Road_Outlet", "Vastrapur_Shop", "Satellite_Branch"],
  "total_stops": 4,
  "predicted_time": "2.3 hours",
  "travel_time_min": 48.2,
  "visit_time_min": 90.0,
  "total_distance_km": 18.7,
  "confidence": 0.87,
  "route_score": 0.4635,
  "legs": [
    {
      "from": "Navrangpura_Store",
      "to": "CG_Road_Outlet",
      "distance_km": 1.8,
      "travel_min": 5.2,
      "traffic": "high"
    }
  ],
  "map_polyline": "..."
}
```

---

### POST /predict/weekly

Generate a full 5-day schedule for a driver.

**Request:**
```json
{
  "driver_id": "D1",
  "week": "2026-W21"
}
```

**Response:**
```json
{
  "driver_id": "D1",
  "week": "2026-W21",
  "week_start": "2026-05-18",
  "monday":    ["Naroda_Center", "Bapunagar_Store", "Rakhial_Branch"],
  "tuesday":   ["Maninagar_Outlet", "Isanpur_Store", "Narol_Shop"],
  "wednesday": ["Satellite_Branch", "Bopal_Branch", "Shela_Outlet"],
  "thursday":  ["Chandkheda_Store", "Motera_Shop", "Ghatlodia_Branch"],
  "friday":    ["Vastrapur_Shop", "Bodakdev_Center", "Memnagar_Center"],
  "weekly_distance": "187.4km",
  "weekly_hours": 38.2,
  "total_stops": 35
}
```

---

### POST /retrain

Retrain ML models on latest data.

```json
{ "confirm": true, "data_path": "data/trips.csv" }
```

---

### GET /health

```json
{
  "status": "ok",
  "uptime_sec": 142.5,
  "models_loaded": true,
  "model_metrics": { "time_model": {"mae": 0.40, "r2": 0.9987} }
}
```

---

### Bonus Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /drivers` | List all drivers with profiles |
| `GET /locations` | All locations with cluster assignments |
| `POST /places/nearby` | Google Places nearby search |
| `GET /places/{place_id}` | Google Place details |
| `GET /geocode?address=...` | Address to coordinates |
| `GET /cache/stats` | Google API cache statistics |
| `GET /model/metrics` | All model performance metrics |

---

## Docker Deployment (Bonus)

```bash
# Build image
docker build -f dockerfile -t route-prediction .

# Run with Google Maps API key
docker run -p 8000:8000 \
  -e GOOGLE_MAPS_API_KEY=your_key_here \
  route-prediction

# Or with docker-compose
docker-compose up
```

---

## Running Tests

```bash
pytest tests/ -v
```

Expected output: **25 passed** covering:
- Health check fields and status
- Daily prediction schema, route completeness, confidence range
- Weekly prediction all 5 weekdays present
- Input validation (invalid dates, bad week format)
- Model accuracy thresholds (MAE < 5 min, accuracy > 70%)
- Data endpoints (drivers, locations, filtering)

---

## Dataset

### Generated Synthetic Data
- **8,739** trip records  
- **12** drivers (D1-D12)  
- **173** locations across Ahmedabad and major Indian cities  
- **6 months** of business days (Nov 2025 – Apr 2026)  
- **1,236** unique trip days  

### Schema
| Column | Type | Description |
|--------|------|-------------|
| `trip_id` | int | Unique trip identifier |
| `driver_id` | str | Driver (D1-D12) |
| `date` | date | Visit date |
| `stop_order` | int | Position in daily route |
| `stop_name` | str | Location name |
| `latitude` | float | Latitude |
| `longitude` | float | Longitude |
| `visit_time` | str | HH:MM arrival time |
| `visit_duration` | int | Minutes spent at stop |
| `traffic_category` | str | low/medium/high |
| `route_distance_km` | float | Total trip distance so far |

---

## Evaluation Checklist

| Criterion | Weight | Implementation |
|-----------|--------|----------------|
| Code quality | 15% | Modular structure, type hints, docstrings |
| Google API integration | 20% | Distance Matrix, Routes, Places, Geocoding + caching |
| Feature engineering | 15% | 20+ features: time, route, driver, location |
| Model approach | 20% | XGBoost (justified) + K-Means + 2-opt optimizer |
| API implementation | 15% | FastAPI with all 4 mandatory + bonus endpoints |
| Documentation | 5% | This README + Swagger UI at /docs |
| Scalability | 10% | Caching, background retrain, modular pipeline |

### Bonus Features Implemented
- ✅ Docker deployment (`dockerfile`)
- ✅ Unit tests (25 tests, all passing)
- ✅ Caching Google API calls (SQLite cache)
- ✅ Route confidence score
- ✅ ETA prediction (per-leg and total)
- ✅ Route score (efficiency metric)
