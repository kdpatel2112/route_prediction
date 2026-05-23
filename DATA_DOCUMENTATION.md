# Synthetic Dataset Documentation

## Overview

The route prediction system includes a comprehensive synthetic dataset generated from realistic field sales scenarios across India.

**Dataset Location:** `data/trips.csv` and `data/locations.json`

---

## Dataset Statistics

| Metric | Value | Requirement |
|--------|-------|-------------|
| **Trip Records** | 8,739 | ≥ 1,000 ✓ |
| **Unique Drivers** | 12 | ≥ 10 ✓ |
| **Unique Locations** | 173 | ≥ 50 ✓ |
| **Unique Trips** | 1,236 | - |
| **Date Range** | 6 months (Nov 2025 - Apr 2026) | - |
| **Business Days Covered** | ~180 | - |

---

## Data Schema

### `data/trips.csv` - Trip Records

Each row represents one stop in a route. Multiple consecutive rows with the same `trip_id` form a complete route.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `trip_id` | INT | Unique trip identifier | 1 |
| `driver_id` | STR | Driver ID (D1-D12) | D1 |
| `date` | STR | Trip date (YYYY-MM-DD) | 2025-11-03 |
| `day_of_week` | STR | Day name | Monday |
| `day_of_week_num` | INT | 0-6 (Mon-Sun) | 0 |
| `week_number` | INT | ISO week number | 45 |
| `month` | INT | Month (1-12) | 11 |
| `is_weekend` | INT | 1 if Sat/Sun, 0 otherwise | 0 |
| `stop_order` | INT | Order in route (1-N) | 1 |
| `stop_name` | STR | Location name | Naroda_Center |
| `latitude` | FLOAT | Stop latitude | 23.0715 |
| `longitude` | FLOAT | Stop longitude | 72.6536 |
| `visit_time` | STR | Arrival time (HH:MM) | 10:14 |
| `visit_hour` | INT | Hour of arrival (0-23) | 10 |
| `visit_duration` | INT | Minutes at stop | 19 |
| `total_stops` | INT | Stops in this route | 6 |
| `route_distance_km` | FLOAT | Cumulative route distance | 48.15 |
| `avg_speed_kmh` | INT | Driver's average speed | 32 |
| `driver_efficiency` | FLOAT | Driver efficiency score (0-1) | 0.92 |
| `traffic_category` | STR | Traffic level (high/medium/low) | high |

### `data/locations.json` - Location Reference

Array of location objects with metadata.

```json
[
  {
    "name": "Navrangpura_Store",
    "latitude": 23.0395,
    "longitude": 72.5603,
    "city": "Ahmedabad",
    "area": "Navrangpura"
  },
  ...
]
```

**Location Metadata:**
- **name**: Unique location identifier (slug format)
- **latitude, longitude**: Geographic coordinates
- **city**: City where location is situated
- **area**: Area/neighborhood name

---

## Geographic Distribution

### Cities Represented

The dataset covers 20+ Indian cities with realistic distribution:

| City | Drivers | Locations | Focus |
|------|---------|-----------|-------|
| **Ahmedabad** | 1 (D1) | 50 | Base territory |
| **Mumbai** | 1 (D2) | 6 | Secondary |
| **Delhi** | 1 (D3) | 6 | Secondary |
| **Bengaluru** | 1 (D4) | 6 | Secondary |
| **Chennai** | 1 (D5) | 6 | Secondary |
| And 7 more cities... | ... | ... | Distributed |

### Clustering

Locations are geographically clustered:
- Each city has 6-50 nearby stores
- Clusters represent realistic sales territories
- Drivers typically operate within one city/cluster

---

## Driver Profiles

### Drivers (D1-D12)

Each driver has realistic characteristics:

| Driver | City | Avg Speed (km/h) | Daily Capacity | Efficiency |
|--------|------|------------------|-----------------|-----------|
| D1 | Ahmedabad | 32 | 8 | 0.92 |
| D2 | Mumbai | 28 | 7 | 0.85 |
| D3 | Delhi | 35 | 9 | 0.95 |
| D4 | Bengaluru | 25 | 6 | 0.78 |
| D5 | Chennai | 30 | 8 | 0.88 |
| D6 | Hyderabad | 27 | 7 | 0.82 |
| D7 | Kolkata | 33 | 9 | 0.91 |
| D8 | Pune | 29 | 7 | 0.86 |
| D9 | Jaipur | 31 | 8 | 0.89 |
| D10 | Surat | 26 | 6 | 0.80 |
| D11 | Lucknow | 34 | 9 | 0.93 |
| D12 | Indore | 28 | 7 | 0.84 |

**Profile Attributes:**
- **avg_speed_kmh**: Average driving speed (affects travel time estimation)
- **daily_capacity**: Typical stops per day (affects route planning)
- **efficiency**: Performance score (0-1, affects route quality)

---

## Data Generation Algorithm

### Process

1. **Date Generation**: 6 months of business days (Nov 2025 - Apr 2026)
2. **Driver Assignment**: Each driver works ~80% of business days
3. **Territory Assignment**: Drivers assigned to geographic clusters (cities)
4. **Daily Route Generation**:
   - Select 3-9 stops based on driver capacity
   - 70% from preferred territory, 30% from others
   - Generate near-optimal route using nearest neighbor heuristic
   - Add realistic human error (efficiency-based deviation)
5. **Travel Time Simulation**:
   - Haversine distance calculation
   - Traffic multipliers based on time and day
   - Visit duration varies (10-45 minutes)

### Traffic Patterns

Realistic traffic multipliers:
- **Morning Rush (8-10am)**: 1.4-1.8x normal
- **Lunch Hour (12-1pm)**: 1.1-1.3x normal
- **Evening Rush (5-7pm)**: 1.5-2.0x normal
- **Normal Hours**: 0.9-1.1x normal
- **Weekends**: 0.8-1.1x normal

### Route Quality

Routes are near-optimal using:
- **Nearest Neighbor Heuristic**: O(n²) approximation
- **Human Variability**: Random deviations based on driver efficiency
- **Distance Minimization**: Drivers follow optimized paths with realistic variations

---

## Data Quality Features

✅ **Realistic Travel Patterns**
- Traffic-aware timing
- Geographic clustering
- Driver-specific characteristics

✅ **Comprehensive Coverage**
- 6 months of continuous data
- All days of week included
- Multiple cities/territories

✅ **Feature Engineering Ready**
- Time-based features (hour, day, week)
- Geographic features (distance, density)
- Traffic features (category, multiplier)
- Driver features (speed, efficiency)

✅ **Machine Learning Suitable**
- 1000+ records for training
- Multiple locations and drivers
- Temporal patterns for forecasting
- Variability for model robustness

---

## Usage Examples

### Load Dataset

```python
import pandas as pd

# Load trip records
trips = pd.read_csv('data/trips.csv')
print(f"Total records: {len(trips)}")
print(f"Date range: {trips['date'].min()} to {trips['date'].max()}")
```

### Single Trip Analysis

```python
# Get one complete trip
trip_1 = trips[trips['trip_id'] == 1]
print(f"Trip 1 for {trip_1['driver_id'].iloc[0]} on {trip_1['date'].iloc[0]}")
print(f"Stops: {len(trip_1)}")
print(f"Distance: {trip_1['route_distance_km'].iloc[-1]} km")
print(f"Total time: {trip_1['visit_time'].iloc[0]} to {trip_1['visit_time'].iloc[-1]}")
```

### Driver Statistics

```python
# Driver efficiency analysis
driver_stats = trips.groupby('driver_id').agg({
    'trip_id': 'nunique',
    'route_distance_km': ['mean', 'max'],
    'driver_efficiency': 'first',
    'total_stops': 'mean',
})
print(driver_stats)
```

### Location Popularity

```python
# Most visited locations
popular = trips['stop_name'].value_counts().head(10)
print("Top 10 most visited locations:")
print(popular)
```

---

## Regenerating Dataset

### Run Data Generator

```bash
cd d:\Ai\route_prediction
python scripts/generate_data.py
```

### Customize Generator

Edit `scripts/generate_data.py`:

```python
# Change date range
start_date = datetime(2025, 11, 1)
end_date   = datetime(2026, 4, 30)

# Add more drivers
DRIVERS = [f"D{i}" for i in range(1, 25)]  # 24 drivers instead of 12

# Adjust driver capacity
DRIVER_PROFILES = {
    "D1": {"avg_speed": 32, "daily_capacity": 10, "efficiency": 0.92},
    ...
}

# Modify date distribution
driver_dates = random.sample(list(date_range), int(len(date_range) * 0.90))
```

---

## Data Validation

### Check Dataset Integrity

```bash
python check_data.py
```

### Expected Output

```
╔═══════════════════════════════════════════════════════════╗
  CURRENT DATASET STATISTICS
╠═══════════════════════════════════════════════════════════╣
  Total Trip Records:  8,739
  Unique Drivers:      12
  Unique Locations:    173
  Date Range:          2025-11-03 → 2026-04-30
  Unique Trips:        1236
╠═══════════════════════════════════════════════════════════╣
  Status: ✓ MEETS REQUIREMENTS
╚═══════════════════════════════════════════════════════════╝
```

---

## Technical Requirements Met

| Requirement | Status | Details |
|-------------|--------|---------|
| 1000+ trip records | ✅ | 8,739 records |
| 10+ drivers | ✅ | 12 drivers (D1-D12) |
| 50+ locations | ✅ | 173 locations across India |
| Multiple cities | ✅ | 20+ cities represented |
| Real coordinates | ✅ | All coordinates in valid ranges |
| Temporal variety | ✅ | 6 months of business days |
| Traffic patterns | ✅ | Rush hour, lunch, normal hours |
| Driver variability | ✅ | Different speeds, capacities, efficiency |

---

## File Structure

```
data/
├── locations.json          # Location reference (173 locations)
├── trips.csv              # Trip records (8,739 rows)
└── [generated on run]

scripts/
├── generate_data.py       # Dataset generator (fully typed)
├── train.py              # Model training script
└── [other utilities]

check_data.py             # Data validation script
```

---

## Notes

- **Reproducibility**: Generator uses `random.seed(42)` for consistency
- **Performance**: Dataset generation takes ~5-10 seconds
- **Storage**: trips.csv is ~500KB, locations.json is ~10KB
- **Format**: CSV and JSON for portability and easy parsing
- **Type Annotations**: All code includes complete type hints for IDE support
