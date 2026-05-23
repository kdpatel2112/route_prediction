"""
Google Maps API Integration (Bonus: with caching)
==================================================
Wraps:
- Distance Matrix API  → leg distances + travel durations
- Routes API           → full route polyline
- Places API           → nearby places, place details
- Geocoding API        → address → coordinates

All calls are cached in a local SQLite DB to minimise API costs.
If GOOGLE_MAPS_API_KEY is not set, falls back to haversine estimates.
"""

import os, json, sqlite3, hashlib, time, math
from typing import Optional, List, Dict, Tuple, Any
import requests

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
CACHE_DB = "data/gmaps_cache.db"

# ── Cache helpers ───────────────────────────────────────────────────────────────

def _init_cache() -> sqlite3.Connection:
    """Initialize cache SQLite database."""
    os.makedirs("data", exist_ok=True)
    con = sqlite3.connect(CACHE_DB)
    con.execute(
        "CREATE TABLE IF NOT EXISTS cache "
        "(key TEXT PRIMARY KEY, value TEXT, ts INTEGER)"
    )
    con.commit()
    return con

def _cache_get(key: str) -> Optional[dict]:
    """Get cached value by key."""
    try:
        con = _init_cache()
        row = con.execute("SELECT value FROM cache WHERE key=?", (key,)).fetchone()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return None

def _cache_set(key: str, value: dict) -> None:
    """Set cached value by key."""
    try:
        con = _init_cache()
        con.execute(
            "INSERT OR REPLACE INTO cache(key, value, ts) VALUES (?,?,?)",
            (key, json.dumps(value), int(time.time()))
        )
        con.commit()
    except Exception:
        pass

def _cache_key(*parts: Any) -> str:
    """Generate cache key from parts."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


# ── Haversine fallback ──────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two lat/lon points in km."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = math.sin(math.radians(lat2-lat1)/2)**2 + \
        math.cos(phi1)*math.cos(phi2)*math.sin(math.radians(lon2-lon1)/2)**2
    return round(2*R*math.asin(math.sqrt(a)), 3)

def _fallback_distance_matrix(
    origins: List[Tuple[float,float]],
    destinations: List[Tuple[float,float]],
    avg_speed_kmh: float = 30.0,
) -> Dict:
    """Estimate distances and durations using haversine when API key is absent."""
    rows = []
    for lat1, lon1 in origins:
        elements = []
        for lat2, lon2 in destinations:
            dist = haversine_km(lat1, lon1, lat2, lon2)
            dur  = (dist / avg_speed_kmh) * 3600  # seconds
            elements.append({
                "status":   "OK",
                "distance": {"text": f"{dist:.1f} km", "value": int(dist * 1000)},
                "duration": {"text": f"{int(dur//60)} mins", "value": int(dur)},
                "source":   "haversine_fallback",
            })
        rows.append({"elements": elements})
    return {"status": "OK", "rows": rows, "source": "haversine_fallback"}


# ── Distance Matrix API ─────────────────────────────────────────────────────────

def get_distance_matrix(
    origins: List[Tuple[float,float]],
    destinations: List[Tuple[float,float]],
    mode: str = "driving",
    departure_time: str = "now",
) -> Dict:
    """
    Get distances & durations between multiple origin/destination pairs.
    Returns Google Maps Distance Matrix response (or haversine fallback).
    """
    key = _cache_key("dm", origins, destinations, mode)
    cached = _cache_get(key)
    if cached:
        return cached

    if not GOOGLE_MAPS_API_KEY:
        result = _fallback_distance_matrix(origins, destinations)
        _cache_set(key, result)
        return result

    origin_str = "|".join(f"{lat},{lon}" for lat, lon in origins)
    dest_str   = "|".join(f"{lat},{lon}" for lat, lon in destinations)

    params = {
        "origins":      origin_str,
        "destinations": dest_str,
        "mode":         mode,
        "key":          GOOGLE_MAPS_API_KEY,
        "traffic_model": "best_guess",
    }
    if departure_time:
        params["departure_time"] = departure_time

    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            params=params, timeout=10
        )
        result = resp.json()
        if result.get("status") == "OK":
            _cache_set(key, result)
            return result
    except Exception as e:
        pass  # Fall through to haversine

    result = _fallback_distance_matrix(origins, destinations)
    _cache_set(key, result)
    return result


def get_leg_duration_minutes(
    from_coords: Tuple[float,float],
    to_coords: Tuple[float,float],
) -> float:
    """Convenience wrapper: single leg duration in minutes."""
    result = get_distance_matrix([from_coords], [to_coords])
    try:
        secs = result["rows"][0]["elements"][0]["duration"]["value"]
        return round(secs / 60, 2)
    except (KeyError, IndexError):
        dist = haversine_km(*from_coords, *to_coords)
        return round((dist / 30.0) * 60, 2)


def get_traffic_estimate(
    from_coords: Tuple[float,float],
    to_coords: Tuple[float,float],
) -> Dict:
    """Return both normal and traffic-adjusted durations."""
    result = get_distance_matrix([from_coords], [to_coords])
    el = result["rows"][0]["elements"][0]
    return {
        "duration_min":         round(el["duration"]["value"] / 60, 2),
        "duration_in_traffic":  round(el.get("duration_in_traffic", el["duration"])["value"] / 60, 2),
        "distance_km":          round(el["distance"]["value"] / 1000, 2),
        "source":               el.get("source", "google_maps"),
    }


# ── Places API ──────────────────────────────────────────────────────────────────

def get_nearby_places(
    lat: float, lon: float,
    radius_meters: int = 2000,
    place_type: str = "store",
) -> List[Dict]:
    """Search for nearby places around given coordinates."""
    key = _cache_key("nearby", lat, lon, radius_meters, place_type)
    cached = _cache_get(key)
    if cached:
        return cached

    if not GOOGLE_MAPS_API_KEY:
        return [{"note": "No API key – Places data unavailable", "source": "fallback"}]

    params = {
        "location": f"{lat},{lon}",
        "radius":   radius_meters,
        "type":     place_type,
        "key":      GOOGLE_MAPS_API_KEY,
    }
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params=params, timeout=10
        )
        data = resp.json()
        if data.get("status") == "OK":
            results = [
                {
                    "name":         p.get("name"),
                    "place_id":     p.get("place_id"),
                    "vicinity":     p.get("vicinity"),
                    "lat":          p["geometry"]["location"]["lat"],
                    "lon":          p["geometry"]["location"]["lng"],
                    "rating":       p.get("rating"),
                    "user_ratings": p.get("user_ratings_total"),
                }
                for p in data.get("results", [])[:10]
            ]
            _cache_set(key, results)
            return results
    except Exception:
        pass
    return []


def get_place_details(place_id: str) -> Dict:
    """Get detailed info for a place by its place_id."""
    key = _cache_key("place", place_id)
    cached = _cache_get(key)
    if cached:
        return cached

    if not GOOGLE_MAPS_API_KEY:
        return {"note": "No API key", "place_id": place_id}

    params = {
        "place_id": place_id,
        "fields":   "name,formatted_address,geometry,opening_hours,rating,formatted_phone_number",
        "key":      GOOGLE_MAPS_API_KEY,
    }
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params=params, timeout=10
        )
        data = resp.json()
        if data.get("status") == "OK":
            _cache_set(key, data["result"])
            return data["result"]
    except Exception:
        pass
    return {}


def geocode(address: str) -> Optional[Tuple[float,float]]:
    """Convert address string to (lat, lon) using Geocoding API."""
    key = _cache_key("geocode", address)
    cached = _cache_get(key)
    if cached:
        return tuple(cached)

    if not GOOGLE_MAPS_API_KEY:
        return None

    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params=params, timeout=10
        )
        data = resp.json()
        if data.get("status") == "OK":
            loc = data["results"][0]["geometry"]["location"]
            result = (loc["lat"], loc["lng"])
            _cache_set(key, list(result))
            return result
    except Exception:
        pass
    return None


# ── Routes API (advanced polyline) ─────────────────────────────────────────────

def get_route_polyline(waypoints: List[Tuple[float,float]]) -> Dict:
    """
    Get a full route polyline from Routes API.
    waypoints: list of (lat, lon) in visit order.
    """
    if len(waypoints) < 2:
        return {"error": "Need at least 2 waypoints"}

    key = _cache_key("route", waypoints)
    cached = _cache_get(key)
    if cached:
        return cached

    if not GOOGLE_MAPS_API_KEY:
        return {
            "note": "No API key – using haversine segments",
            "total_distance_km": sum(
                haversine_km(*waypoints[i], *waypoints[i+1])
                for i in range(len(waypoints)-1)
            ),
            "source": "haversine_fallback",
        }

    body = {
        "origin": {
            "location": {"latLng": {"latitude": waypoints[0][0], "longitude": waypoints[0][1]}}
        },
        "destination": {
            "location": {"latLng": {"latitude": waypoints[-1][0], "longitude": waypoints[-1][1]}}
        },
        "intermediates": [
            {"location": {"latLng": {"latitude": lat, "longitude": lon}}}
            for lat, lon in waypoints[1:-1]
        ],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline",
    }
    try:
        resp = requests.post(
            "https://routes.googleapis.com/directions/v2:computeRoutes",
            json=body, headers=headers, timeout=15
        )
        data = resp.json()
        if "routes" in data and data["routes"]:
            route = data["routes"][0]
            result = {
                "distance_km": round(route.get("distanceMeters", 0) / 1000, 2),
                "duration_min": round(
                    int(route.get("duration", "0s").rstrip("s")) / 60, 2
                ),
                "polyline": route.get("polyline", {}).get("encodedPolyline", ""),
                "source": "google_routes_api",
            }
            _cache_set(key, result)
            return result
    except Exception:
        pass

    # Fallback
    total = sum(haversine_km(*waypoints[i], *waypoints[i+1]) for i in range(len(waypoints)-1))
    return {
        "distance_km": round(total, 2),
        "duration_min": round((total / 30) * 60, 2),
        "source": "haversine_fallback",
    }


def cache_stats() -> Dict:
    """Return cache hit statistics."""
    try:
        con = _init_cache()
        count = con.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        return {"cached_entries": count, "cache_db": CACHE_DB}
    except Exception:
        return {"cached_entries": 0}
