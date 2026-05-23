#!/usr/bin/env python
"""Check current dataset statistics."""

import pandas as pd
import json

df = pd.read_csv('data/trips.csv')
print('╔═══════════════════════════════════════════════════════════╗')
print('  CURRENT DATASET STATISTICS')
print('╠═══════════════════════════════════════════════════════════╣')
print(f'  Total Trip Records:  {len(df):,}')
print(f'  Unique Drivers:      {df["driver_id"].nunique()}')
print(f'  Unique Locations:    {df["stop_name"].nunique()}')
print(f'  Date Range:          {df["date"].min()} → {df["date"].max()}')
print(f'  Unique Trips:        {df["trip_id"].nunique()}')
print('╠═══════════════════════════════════════════════════════════╣')
meets_req = len(df) >= 1000 and df["driver_id"].nunique() >= 10 and df["stop_name"].nunique() >= 50
status = "✓ MEETS REQUIREMENTS" if meets_req else "✗ NEEDS REGENERATION"
print(f'  Status: {status}')
print('╚═══════════════════════════════════════════════════════════╝')

print('\nRequirements Check:')
print(f'  ✓ {len(df):,} records >= 1000? {len(df) >= 1000}')
print(f'  ✓ {df["driver_id"].nunique()} drivers >= 10? {df["driver_id"].nunique() >= 10}')
print(f'  ✓ {df["stop_name"].nunique()} locations >= 50? {df["stop_name"].nunique() >= 50}')
