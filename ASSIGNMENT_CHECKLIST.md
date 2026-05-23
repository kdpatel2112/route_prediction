# Assignment Satisfaction Checklist

This project implements the AI Developer assignment requirements.

## Mandatory Requirements

- Data collection: `data/trips.csv`
  - 8,000+ generated trip records
  - 12 drivers
  - 173 locations across Ahmedabad plus major Indian cities and areas
- Google APIs: `api/gmaps.py`
  - Distance Matrix API wrapper
  - Routes API wrapper
  - Places nearby search
  - Place details
  - Geocoding
  - SQLite caching for cost control
  - Haversine fallback when `GOOGLE_MAPS_API_KEY` is not set
- Feature engineering: `model/features.py`
  - Time, route, driver, location, density, traffic, and city-region features
- Model approach: `model/trainer.py`
  - XGBoost travel-time regressor
  - XGBoost route-rank classifier
  - K-Means area clustering
  - Nearest-neighbor plus 2-opt route optimization
- REST API: `api/main.py`
  - `POST /predict/daily`
  - `POST /predict/weekly`
  - `POST /retrain`
  - `GET /health`
- Documentation: `README.md`
- Docker: `dockerfile`
- Tests: `tests/test_api.py`

## Bonus Coverage

- Route visualization map: `web/`
- Live taxi-style route animation
- City and area selector for Indian metro locations
- Unit tests
- Google API caching
- Route confidence score
- ETA per stop
- Model/system monitoring dashboard
