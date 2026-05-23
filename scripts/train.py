"""
Full pipeline: generate data → engineer features → train models
Run from project root: python scripts/train.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.generate_data import generate_dataset
import pandas as pd
import json

def main() -> None:
    """Execute full training pipeline: data generation → features → models."""
    print("Step 1: Generating synthetic dataset...")
    os.makedirs("data", exist_ok=True)
    df = generate_dataset()
    df.to_csv("data/trips.csv", index=False)

    # Import locations from generator
    from scripts.generate_data import LOCATIONS, LOCATION_META
    locs_json = [
        {
            "name": k,
            "latitude": v[0],
            "longitude": v[1],
            **LOCATION_META.get(k, {"city": "Unknown", "area": k}),
        }
        for k, v in LOCATIONS.items()
    ]
    with open("data/locations.json", "w") as f:
        json.dump(locs_json, f, indent=2)
    print(f"  → {len(df)} records, {df['driver_id'].nunique()} drivers, {df['stop_name'].nunique()} locations")

    print("\nStep 2: Training ML models...")
    from model.trainer import train_all
    train_all()
    print("\nAll done! Start the API with:")
    print("  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload")

if __name__ == "__main__":
    main()
