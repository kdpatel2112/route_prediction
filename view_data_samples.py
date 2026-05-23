#!/usr/bin/env python
"""
Data Sample Viewer
Shows sample trip records and location data
"""

import pandas as pd
import json
from typing import Optional

def show_trip_sample() -> None:
    """Display sample trip records."""
    df = pd.read_csv('data/trips.csv')
    
    print("╔═══════════════════════════════════════════════════════════════════════════╗")
    print("  SAMPLE TRIP RECORDS (First 15 stops)")
    print("╚═══════════════════════════════════════════════════════════════════════════╝\n")
    
    # Show first trip
    first_trip_id = df['trip_id'].iloc[0]
    first_trip = df[df['trip_id'] == first_trip_id].head(15)
    
    print(f"Trip ID: {first_trip_id} | Driver: {first_trip['driver_id'].iloc[0]} | Date: {first_trip['date'].iloc[0]}")
    print(f"Total Stops: {first_trip['total_stops'].iloc[0]} | Route Distance: {first_trip['route_distance_km'].iloc[-1]} km\n")
    
    cols_to_show = ['stop_order', 'stop_name', 'latitude', 'longitude', 'visit_time', 
                    'visit_duration', 'traffic_category']
    print(first_trip[cols_to_show].to_string(index=False))
    
    print("\n" + "─" * 73 + "\n")

def show_location_sample() -> None:
    """Display sample locations."""
    with open('data/locations.json') as f:
        locs = json.load(f)
    
    print("╔═══════════════════════════════════════════════════════════════════════════╗")
    print("  SAMPLE LOCATIONS (First 10)")
    print("╚═══════════════════════════════════════════════════════════════════════════╝\n")
    
    for i, loc in enumerate(locs[:10], 1):
        print(f"{i:2}. {loc['name']:30s} | City: {loc['city']:12s} | Area: {loc['area']:20s}")
        print(f"    Lat: {loc['latitude']:.4f}, Lon: {loc['longitude']:.4f}")
    
    print(f"\n... and {len(locs) - 10} more locations")
    print("\n" + "─" * 73 + "\n")

def show_trip_breakdown() -> None:
    """Show trip composition statistics."""
    df = pd.read_csv('data/trips.csv')
    
    print("╔═══════════════════════════════════════════════════════════════════════════╗")
    print("  TRIP COMPOSITION ANALYSIS")
    print("╚═══════════════════════════════════════════════════════════════════════════╝\n")
    
    # Trips by driver
    trips_by_driver = df.groupby('driver_id')['trip_id'].nunique().sort_values(ascending=False)
    print("Trips by Driver:")
    for driver, count in trips_by_driver.items():
        print(f"  {driver}: {count:4d} trips")
    
    print("\n" + "─" * 73 + "\n")
    
    # Stops distribution
    stops_dist = df.groupby('trip_id')['stop_order'].max()
    print("Trip Stop Distribution:")
    print(f"  Min stops per trip: {stops_dist.min()}")
    print(f"  Max stops per trip: {stops_dist.max()}")
    print(f"  Avg stops per trip: {stops_dist.mean():.1f}")
    
    print("\n" + "─" * 73 + "\n")
    
    # Daily capacity analysis
    print("Driver Daily Capacity (stops per day):")
    capacity_analysis = df.groupby('driver_id')['total_stops'].agg(['min', 'max', 'mean'])
    for driver in capacity_analysis.index:
        row = capacity_analysis.loc[driver]
        print(f"  {driver}: min={row['min']:.0f}, max={row['max']:.0f}, avg={row['mean']:.1f}")

def show_data_quality() -> None:
    """Show data quality metrics."""
    df = pd.read_csv('data/trips.csv')
    
    print("╔═══════════════════════════════════════════════════════════════════════════╗")
    print("  DATA QUALITY METRICS")
    print("╚═══════════════════════════════════════════════════════════════════════════╝\n")
    
    print(f"Total Records: {len(df):,}")
    print(f"Unique Trips: {df['trip_id'].nunique():,}")
    print(f"Unique Drivers: {df['driver_id'].nunique()}")
    print(f"Unique Locations: {df['stop_name'].nunique()}")
    print(f"Unique Cities: {df.merge(pd.read_json('data/locations.json'), left_on='stop_name', right_on='name', how='left')['city'].nunique()}")
    
    print(f"\nDate Range: {df['date'].min()} to {df['date'].max()}")
    print(f"Missing Values:")
    print(f"  - latitude: {df['latitude'].isna().sum()}")
    print(f"  - longitude: {df['longitude'].isna().sum()}")
    print(f"  - visit_time: {df['visit_time'].isna().sum()}")
    
    print(f"\nDistance Stats (km):")
    dist_col = df['route_distance_km']
    print(f"  Min: {dist_col.min():.2f}")
    print(f"  Max: {dist_col.max():.2f}")
    print(f"  Mean: {dist_col.mean():.2f}")
    print(f"  Median: {dist_col.median():.2f}")
    
    print(f"\nVisit Duration Stats (minutes):")
    dur_col = df['visit_duration']
    print(f"  Min: {dur_col.min()}")
    print(f"  Max: {dur_col.max()}")
    print(f"  Mean: {dur_col.mean():.1f}")
    print(f"  Median: {dur_col.median():.1f}")

if __name__ == "__main__":
    print("\n")
    
    show_trip_sample()
    show_location_sample()
    show_trip_breakdown()
    show_data_quality()
    print("\n✓ Data sample view complete\n")
