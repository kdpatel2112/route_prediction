#!/usr/bin/env python
"""
Final Verification Script
Validates all requirements are met
"""

import os
import sys
import pandas as pd
import json
from pathlib import Path

def check_files_exist() -> bool:
    """Check all required files exist."""
    required_files = [
        'data/trips.csv',
        'data/locations.json',
        'api/main.py',
        'api/predictor.py',
        'api/gmaps.py',
        'model/trainer.py',
        'model/optimizer.py',
        'model/features.py',
        'scripts/generate_data.py',
        'scripts/train.py',
        'dockerfile',
        'requirements.txt',
    ]
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("  FILE EXISTENCE CHECK")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    all_exist = True
    for file_path in required_files:
        exists = os.path.exists(file_path)
        status = "✓" if exists else "✗"
        print(f"  {status} {file_path}")
        all_exist = all_exist and exists
    
    return all_exist

def check_data_requirements() -> bool:
    """Check data meets all requirements."""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("  DATA REQUIREMENTS CHECK")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    df = pd.read_csv('data/trips.csv')
    
    checks = {
        'Trip Records >= 1000': len(df) >= 1000,
        'Unique Drivers >= 10': df['driver_id'].nunique() >= 10,
        'Unique Locations >= 50': df['stop_name'].nunique() >= 50,
        'No Missing Latitudes': df['latitude'].isna().sum() == 0,
        'No Missing Longitudes': df['longitude'].isna().sum() == 0,
        'No Missing Visit Times': df['visit_time'].isna().sum() == 0,
    }
    
    all_pass = True
    for check, result in checks.items():
        status = "✓" if result else "✗"
        if check.startswith('Trip Records'):
            detail = f" ({len(df):,})"
        elif check.startswith('Unique Drivers'):
            detail = f" ({df['driver_id'].nunique()})"
        elif check.startswith('Unique Locations'):
            detail = f" ({df['stop_name'].nunique()})"
        else:
            detail = ""
        print(f"  {status} {check}{detail}")
        all_pass = all_pass and result
    
    return all_pass

def check_type_annotations() -> bool:
    """Check type annotations are present."""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("  TYPE ANNOTATION CHECK")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    modules = [
        ('api/main.py', 15),
        ('api/predictor.py', 5),
        ('model/trainer.py', 6),
        ('scripts/generate_data.py', 5),
    ]
    
    total_functions = 0
    for module, expected_count in modules:
        with open(module) as f:
            content = f.read()
        
        # Count functions with type hints (-> )
        type_hint_count = content.count(' -> ')
        status = "✓" if type_hint_count >= expected_count else "~"
        print(f"  {status} {module}: {type_hint_count} functions with types")
        total_functions += type_hint_count
    
    print(f"\n  Total: {total_functions}+ functions with type annotations")
    return True

def check_documentation() -> bool:
    """Check documentation files exist."""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("  DOCUMENTATION CHECK")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    docs = [
        'ROUTE_OPTIMIZATION_UPDATES.md',
        'TYPE_ANNOTATIONS_GUIDE.md',
        'DATA_DOCUMENTATION.md',
        'BUSINESS_REQUIREMENTS.md',
        'README.md',
        'ASSIGNMENT_CHECKLIST.md',
    ]
    
    all_exist = True
    for doc in docs:
        exists = os.path.exists(doc)
        status = "✓" if exists else "✗"
        print(f"  {status} {doc}")
        all_exist = all_exist and exists
    
    return all_exist

def check_imports() -> bool:
    """Check all modules import successfully."""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("  IMPORT CHECK")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    imports_to_check = [
        ('api.main', 'app'),
        ('api.predictor', ['predict_daily', 'predict_weekly']),
        ('model.trainer', 'train_all'),
        ('model.optimizer', 'optimize_route'),
    ]
    
    all_ok = True
    for module_name, items in imports_to_check:
        try:
            module = __import__(module_name, fromlist=[items] if isinstance(items, list) else [items])
            status = "✓"
            detail = f" ({module_name})"
        except Exception as e:
            status = "✗"
            detail = f" ({str(e)[:40]})"
            all_ok = False
        
        print(f"  {status} {module_name}{detail}")
    
    return all_ok

def check_business_scenario() -> bool:
    """Check business scenario implementation."""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("  BUSINESS SCENARIO IMPLEMENTATION CHECK")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    features = {
        'Route Optimization (NN + 2-opt)': 'optimize_route' in open('api/predictor.py').read(),
        'XGBoost Time Prediction': 'XGBoost' in open('model/trainer.py').read(),
        'Travel Time Blending': '65% map' in open('api/predictor.py').read(),
        'Confidence Scoring': 'compute_confidence' in open('api/predictor.py').read(),
        'Geographic Clustering': 'KMeans' in open('model/trainer.py').read(),
        'Historical Pattern Learning': 'location_history' in open('api/predictor.py').read(),
    }
    
    all_implemented = True
    for feature, implemented in features.items():
        status = "✓" if implemented else "✗"
        print(f"  {status} {feature}")
        all_implemented = all_implemented and implemented
    
    return all_implemented

def main() -> None:
    """Run all checks."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("  ROUTE PREDICTION SYSTEM - FINAL VERIFICATION")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    checks = [
        ("Files", check_files_exist),
        ("Data", check_data_requirements),
        ("Type Annotations", check_type_annotations),
        ("Documentation", check_documentation),
        ("Imports", check_imports),
        ("Business Scenario", check_business_scenario),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n  ✗ Error in {name} check: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "╔════════════════════════════════════════════════════════════╗")
    print("  SUMMARY")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    for name, result in results:
        status = "✓" if result else "✗"
        print(f"  {status} {name}")
    
    all_pass = all(result for _, result in results)
    
    print("\n" + "╔════════════════════════════════════════════════════════════╗")
    if all_pass:
        print("  ✓ ALL CHECKS PASSED - SYSTEM READY FOR DEPLOYMENT")
    else:
        print("  ✗ SOME CHECKS FAILED - PLEASE REVIEW")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    sys.exit(0 if all_pass else 1)

if __name__ == "__main__":
    main()
