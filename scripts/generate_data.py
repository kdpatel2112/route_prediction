"""
Synthetic Dataset Generator
Generates 1000+ trip records, 10+ drivers, 50+ locations around Ahmedabad, Gujarat
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Union
import random

random.seed(42)
np.random.seed(42)

# ── 50+ locations around Ahmedabad ─────────────────────────────────────────────
LOCATIONS = {
    "Navrangpura_Store":       (23.0395, 72.5603),
    "CG_Road_Outlet":          (23.0322, 72.5562),
    "Satellite_Branch":        (23.0258, 72.5099),
    "Vastrapur_Shop":          (23.0351, 72.5297),
    "Bodakdev_Center":         (23.0487, 72.5155),
    "Prahlad_Nagar_Store":     (23.0177, 72.5108),
    "Maninagar_Outlet":        (22.9993, 72.6010),
    "Ghatlodia_Branch":        (23.0796, 72.5611),
    "Chandkheda_Store":        (23.1146, 72.5877),
    "Motera_Shop":             (23.1014, 72.5872),
    "Naroda_Center":           (23.0715, 72.6536),
    "Odhav_Outlet":            (22.9979, 72.6460),
    "Vatva_Store":             (22.9641, 72.6385),
    "Lambha_Branch":           (22.9467, 72.5745),
    "Narol_Shop":              (22.9582, 72.6205),
    "Isanpur_Store":           (22.9754, 72.6186),
    "Nikol_Center":            (23.0286, 72.6387),
    "Vastral_Outlet":          (23.0189, 72.6607),
    "Rakhial_Branch":          (23.0494, 72.6266),
    "Bapunagar_Store":         (23.0441, 72.6204),
    "Amraiwadi_Shop":          (23.0257, 72.6216),
    "Gomtipur_Center":         (23.0415, 72.6397),
    "Khadia_Outlet":           (23.0279, 72.5952),
    "Jamalpur_Store":          (23.0220, 72.5900),
    "Dariapur_Branch":         (23.0357, 72.5840),
    "Mirzapur_Shop":           (23.0350, 72.5900),
    "Kalupur_Center":          (23.0262, 72.5963),
    "Shahpur_Outlet":          (23.0302, 72.5847),
    "Paldi_Store":             (23.0098, 72.5667),
    "Ambawadi_Branch":         (23.0329, 72.5471),
    "Ellisbridge_Shop":        (23.0240, 72.5680),
    "Memnagar_Center":         (23.0487, 72.5449),
    "Thaltej_Outlet":          (23.0566, 72.5013),
    "Shilaj_Store":            (23.0603, 72.4871),
    "Bopal_Branch":            (23.0344, 72.4618),
    "Ghuma_Shop":              (23.0152, 72.4780),
    "Manipur_Center":          (23.0050, 72.4980),
    "Sarkhej_Outlet":          (22.9965, 72.5200),
    "Juhapura_Store":          (23.0039, 72.5393),
    "Vejalpur_Branch":         (22.9939, 72.5502),
    "Jodhpur_Shop":            (23.0137, 72.5212),
    "Ambli_Center":            (23.0437, 72.4828),
    "Shela_Outlet":            (23.0269, 72.4651),
    "Bavla_Store":             (22.9346, 72.3752),
    "Sanand_Branch":           (22.9926, 72.3750),
    "Vinzol_Shop":             (22.9772, 72.6575),
    "Hathijan_Center":         (22.9540, 72.6527),
    "Aslali_Outlet":           (22.9296, 72.6364),
    "Dholka_Store":            (22.7186, 72.4683),
    "Dhandhuka_Branch":        (22.3920, 72.0100),
    "Viramgam_Shop":           (23.1169, 72.0341),
    "Detroj_Center":           (23.3182, 72.3074),
    "Mandal_Outlet":           (23.2439, 72.3021),
}

LOCATION_NAMES = list(LOCATIONS.keys())
LOCATION_META = {
    name: {"city": "Ahmedabad", "area": name.rsplit("_", 1)[0].replace("_", " ")}
    for name in LOCATIONS
}

INDIAN_CITY_AREAS = {
    "Mumbai": (19.0760, 72.8777, ["Andheri", "Bandra", "Dadar", "Powai", "Borivali", "Colaba"]),
    "Delhi": (28.6139, 77.2090, ["Connaught Place", "Saket", "Rohini", "Dwarka", "Karol Bagh", "Lajpat Nagar"]),
    "Bengaluru": (12.9716, 77.5946, ["Indiranagar", "Koramangala", "Whitefield", "Jayanagar", "Hebbal", "Electronic City"]),
    "Chennai": (13.0827, 80.2707, ["T Nagar", "Adyar", "Velachery", "Anna Nagar", "Guindy", "Mylapore"]),
    "Hyderabad": (17.3850, 78.4867, ["Banjara Hills", "Hitech City", "Secunderabad", "Gachibowli", "Kukatpally", "Charminar"]),
    "Kolkata": (22.5726, 88.3639, ["Park Street", "Salt Lake", "Howrah", "New Town", "Ballygunge", "Dum Dum"]),
    "Pune": (18.5204, 73.8567, ["Koregaon Park", "Hinjewadi", "Baner", "Kothrud", "Viman Nagar", "Hadapsar"]),
    "Jaipur": (26.9124, 75.7873, ["C Scheme", "Mansarovar", "Malviya Nagar", "Vaishali Nagar", "Tonk Road", "Bani Park"]),
    "Surat": (21.1702, 72.8311, ["Adajan", "Vesu", "Varachha", "Ring Road", "Katargam", "Udhna"]),
    "Lucknow": (26.8467, 80.9462, ["Hazratganj", "Gomti Nagar", "Aliganj", "Indira Nagar", "Aminabad", "Charbagh"]),
    "Kanpur": (26.4499, 80.3319, ["Swaroop Nagar", "Kakadeo", "Civil Lines", "Kidwai Nagar", "Govind Nagar", "Mall Road"]),
    "Nagpur": (21.1458, 79.0882, ["Sitabuldi", "Dharampeth", "Mahal", "Manish Nagar", "Sadar", "Hingna"]),
    "Indore": (22.7196, 75.8577, ["Vijay Nagar", "Palasia", "Rau", "Rajwada", "Bhawarkua", "Scheme 78"]),
    "Bhopal": (23.2599, 77.4126, ["MP Nagar", "New Market", "Arera Colony", "Kolar Road", "Bairagarh", "Shahpura"]),
    "Patna": (25.5941, 85.1376, ["Boring Road", "Kankarbagh", "Patliputra", "Fraser Road", "Bailey Road", "Danapur"]),
    "Kochi": (9.9312, 76.2673, ["Edappally", "Kakkanad", "Fort Kochi", "MG Road", "Vyttila", "Panampilly Nagar"]),
    "Coimbatore": (11.0168, 76.9558, ["RS Puram", "Gandhipuram", "Peelamedu", "Saibaba Colony", "Singanallur", "Town Hall"]),
    "Visakhapatnam": (17.6868, 83.2185, ["Dwaraka Nagar", "MVP Colony", "Gajuwaka", "Madhurawada", "Beach Road", "Akkayyapalem"]),
    "Chandigarh": (30.7333, 76.7794, ["Sector 17", "Sector 22", "Sector 35", "Manimajra", "Industrial Area", "Zirakpur"]),
    "Guwahati": (26.1445, 91.7362, ["Paltan Bazaar", "Dispur", "Ganeshguri", "Beltola", "Fancy Bazaar", "Six Mile"]),
}

AREA_OFFSETS = [
    (0.0000, 0.0000), (0.0300, -0.0250), (-0.0260, 0.0280),
    (0.0450, 0.0330), (-0.0400, -0.0350), (0.0150, 0.0520),
]

def _slug(value: str) -> str:
    """Convert string to slug format (replace spaces and special chars with underscores)."""
    return value.replace(" ", "_").replace("-", "_").replace("/", "_")

for city, (base_lat, base_lon, areas) in INDIAN_CITY_AREAS.items():
    for i, area in enumerate(areas):
        lat_offset, lon_offset = AREA_OFFSETS[i % len(AREA_OFFSETS)]
        name = f"{_slug(city)}_{_slug(area)}_Store"
        LOCATIONS[name] = (round(base_lat + lat_offset, 5), round(base_lon + lon_offset, 5))
        LOCATION_META[name] = {"city": city, "area": area}

LOCATION_NAMES = list(LOCATIONS.keys())
DRIVERS = [f"D{i}" for i in range(1, 13)]  # 12 drivers

# Driver profiles: avg_speed (km/h), daily_capacity (stores/day), efficiency_score
DRIVER_PROFILES = {
    "D1":  {"avg_speed": 32, "daily_capacity": 8,  "efficiency": 0.92},
    "D2":  {"avg_speed": 28, "daily_capacity": 7,  "efficiency": 0.85},
    "D3":  {"avg_speed": 35, "daily_capacity": 9,  "efficiency": 0.95},
    "D4":  {"avg_speed": 25, "daily_capacity": 6,  "efficiency": 0.78},
    "D5":  {"avg_speed": 30, "daily_capacity": 8,  "efficiency": 0.88},
    "D6":  {"avg_speed": 27, "daily_capacity": 7,  "efficiency": 0.82},
    "D7":  {"avg_speed": 33, "daily_capacity": 9,  "efficiency": 0.91},
    "D8":  {"avg_speed": 29, "daily_capacity": 7,  "efficiency": 0.86},
    "D9":  {"avg_speed": 31, "daily_capacity": 8,  "efficiency": 0.89},
    "D10": {"avg_speed": 26, "daily_capacity": 6,  "efficiency": 0.80},
    "D11": {"avg_speed": 34, "daily_capacity": 9,  "efficiency": 0.93},
    "D12": {"avg_speed": 28, "daily_capacity": 7,  "efficiency": 0.84},
}

DRIVER_CITIES = {
    "D1": "Ahmedabad",
    "D2": "Mumbai",
    "D3": "Delhi",
    "D4": "Bengaluru",
    "D5": "Chennai",
    "D6": "Hyderabad",
    "D7": "Kolkata",
    "D8": "Pune",
    "D9": "Jaipur",
    "D10": "Surat",
    "D11": "Lucknow",
    "D12": "Indore",
}

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in km between two coordinates using Haversine formula."""
    R = 6371
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def get_traffic_multiplier(hour: int, day_of_week: int) -> float:
    """Simulate realistic traffic patterns based on time of day and day of week."""
    if day_of_week >= 5:  # Weekend
        return random.uniform(0.8, 1.1)
    if hour in [8, 9, 10]:   # Morning rush
        return random.uniform(1.4, 1.8)
    if hour in [17, 18, 19]: # Evening rush
        return random.uniform(1.5, 2.0)
    if hour in [12, 13]:     # Lunch hour
        return random.uniform(1.1, 1.3)
    return random.uniform(0.9, 1.1)

def nearest_neighbor_route(locations_subset: List[str]) -> List[str]:
    """Generate near-optimal route using nearest neighbor heuristic (TSP approximation)."""
    if len(locations_subset) <= 1:
        return locations_subset
    
    unvisited = locations_subset.copy()
    route = [unvisited.pop(0)]
    
    while unvisited:
        last = route[-1]
        lat1, lon1 = LOCATIONS[last]
        distances = [(haversine(lat1, lon1, LOCATIONS[n][0], LOCATIONS[n][1]), n) for n in unvisited]
        distances.sort()
        next_stop = distances[0][1]
        route.append(next_stop)
        unvisited.remove(next_stop)
    
    return route

def generate_dataset() -> pd.DataFrame:
    """Generate synthetic dataset with 1000+ trip records across 10+ drivers and 50+ locations.
    
    Returns:
        DataFrame with trip records including:
        - trip_id: Unique trip identifier
        - driver_id: Driver identifier (D1-D12)
        - date: Trip date (YYYY-MM-DD format)
        - stop_name: Location name
        - latitude, longitude: Coordinates
        - visit_time: Time at stop (HH:MM format)
        - visit_duration: Minutes spent at stop
        - total_stops: Number of stops in trip
        - route_distance_km: Total trip distance
        - traffic_category: High/Medium/Low based on time
    """
    
    # Date range: 6 months of data
    start_date = datetime(2025, 11, 1)
    end_date   = datetime(2026, 4, 30)
    date_range = pd.date_range(start_date, end_date, freq='B')  # Business days only
    
    trip_id = 1
    
    for driver_id in DRIVERS:
        profile = DRIVER_PROFILES[driver_id]
        
        # Each driver works ~80% of business days
        driver_dates = random.sample(list(date_range), int(len(date_range) * 0.80))
        driver_dates.sort()
        
        # Assign a realistic city territory; drivers usually do daily routes within one city.
        home_city = DRIVER_CITIES.get(driver_id, "Ahmedabad")
        city_locs = [l for l in LOCATION_NAMES if LOCATION_META.get(l, {}).get("city") == home_city]
        if len(city_locs) < 8:
            city_locs = LOCATION_NAMES
        territory_size = min(24, len(city_locs))
        preferred_locs = city_locs[:territory_size]
        other_locs = [l for l in city_locs if l not in preferred_locs] or preferred_locs
        
        for date in driver_dates:
            daily_capacity = profile["daily_capacity"]
            # Vary stops slightly
            n_stops = random.randint(max(3, daily_capacity - 2), daily_capacity + 1)
            n_stops = min(n_stops, len(city_locs))
            
            # Pick locations (70% from territory, 30% from others)
            n_preferred = int(n_stops * 0.70)
            n_other     = n_stops - n_preferred
            
            chosen = random.sample(preferred_locs, min(n_preferred, len(preferred_locs)))
            available_other = [loc for loc in other_locs if loc not in chosen]
            chosen += random.sample(available_other, min(n_other, len(available_other)))
            if len(chosen) < n_stops:
                fill_pool = [loc for loc in city_locs if loc not in chosen]
                chosen += random.sample(fill_pool, min(n_stops - len(chosen), len(fill_pool)))
            random.shuffle(chosen)
            chosen = chosen[:n_stops]
            
            # Generate optimized route with some noise (simulate human sub-optimality)
            optimal_route = nearest_neighbor_route(chosen.copy())
            if random.random() > profile["efficiency"]:
                # Driver deviated from optimal
                i, j = random.sample(range(len(optimal_route)), 2)
                optimal_route[i], optimal_route[j] = optimal_route[j], optimal_route[i]
            
            # Build trip records
            start_hour = random.randint(8, 10)
            start_minute = random.randint(0, 30)
            current_time = date.replace(hour=start_hour, minute=start_minute)
            
            route_distance = 0.0
            
            for stop_order, location in enumerate(optimal_route):
                lat, lon = LOCATIONS[location]
                
                # Travel time from previous stop
                if stop_order > 0:
                    prev_loc = optimal_route[stop_order - 1]
                    prev_lat, prev_lon = LOCATIONS[prev_loc]
                    dist = haversine(prev_lat, prev_lon, lat, lon)
                    route_distance += dist
                    traffic_mult = get_traffic_multiplier(current_time.hour, date.dayofweek)
                    travel_mins  = (dist / profile["avg_speed"]) * 60 * traffic_mult
                    current_time += timedelta(minutes=travel_mins)
                
                visit_duration = random.randint(10, 45)
                
                records.append({
                    "trip_id":          trip_id,
                    "driver_id":        driver_id,
                    "date":             date.strftime("%Y-%m-%d"),
                    "day_of_week":      date.day_name(),
                    "day_of_week_num":  date.dayofweek,
                    "week_number":      date.isocalendar()[1],
                    "month":            date.month,
                    "is_weekend":       int(date.dayofweek >= 5),
                    "stop_order":       stop_order + 1,
                    "stop_name":        location,
                    "latitude":         lat,
                    "longitude":        lon,
                    "visit_time":       current_time.strftime("%H:%M"),
                    "visit_hour":       current_time.hour,
                    "visit_duration":   visit_duration,
                    "total_stops":      n_stops,
                    "route_distance_km": round(route_distance, 2),
                    "avg_speed_kmh":    profile["avg_speed"],
                    "driver_efficiency": profile["efficiency"],
                    "traffic_category": (
                        "high"   if current_time.hour in [8,9,10,17,18,19] else
                        "medium" if current_time.hour in [12,13] else
                        "low"
                    ),
                })
                
                current_time += timedelta(minutes=visit_duration)
            
            trip_id += 1
    
    df = pd.DataFrame(records)
    print(f"Generated {len(df)} records")
    print(f"Drivers: {df['driver_id'].nunique()}")
    print(f"Locations: {df['stop_name'].nunique()}")
    print(f"Date range: {df['date'].min()} → {df['date'].max()}")
    print(f"Unique trips: {df['trip_id'].nunique()}")
    return df

if __name__ == "__main__":
    """Generate and save synthetic trip dataset."""
    os.makedirs("data", exist_ok=True)
    df = generate_dataset()
    df.to_csv("data/trips.csv", index=False)
    
    # Save locations reference
    locs = [
        {
            "name": k,
            "latitude": v[0],
            "longitude": v[1],
            **LOCATION_META.get(k, {"city": "Unknown", "area": k}),
        }
        for k, v in LOCATIONS.items()
    ]
    with open("data/locations.json", "w") as f:
        json.dump(locs, f, indent=2)
    
    print("\nSaved: data/trips.csv, data/locations.json")
    print(df.head(5).to_string())
