#!/usr/bin/env python3
"""
Generate test data for a full trading day
Creates both L1 (price/volume) and L3 (features) data
"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Configuration
SYMBOL = "SPY"
DATE = "2025-11-03"
START_TIME = "09:30:00"
END_TIME = "16:00:00"
BASE_PRICE = 451.50
API_BASE = "http://127.0.0.1:8000"

print(f"Generating test data for {SYMBOL} on {DATE}")
print("=" * 60)

# Generate intraday bars (1-minute frequency)
start_dt = datetime.fromisoformat(f"{DATE}T{START_TIME}")
end_dt = datetime.fromisoformat(f"{DATE}T{END_TIME}")
num_bars = int((end_dt - start_dt).total_seconds() / 60) + 1

print(f"Generating {num_bars} 1-minute bars from {START_TIME} to {END_TIME}")

# Create realistic price action
np.random.seed(42)  # Reproducible

# Price path with trend + mean reversion
trend = np.linspace(0, 2, num_bars)  # Slow uptrend
noise = np.random.randn(num_bars) * 0.15
mean_reversion = np.cumsum(np.random.randn(num_bars) * 0.05)
prices = BASE_PRICE + trend + noise + mean_reversion

# Volume with realistic patterns
base_volume = 3000
open_bars = num_bars // 4
close_bars = num_bars // 4
mid_bars = num_bars - open_bars - close_bars

volume_profile = np.concatenate([
    np.linspace(5000, 2000, open_bars),  # High volume at open
    np.full(mid_bars, base_volume),       # Mid-day lull
    np.linspace(2000, 6000, close_bars)  # Pick up into close
])
volumes = volume_profile + np.random.randint(-500, 500, num_bars)
volumes = np.maximum(volumes, 1000)  # Min 1000

# Generate timestamps
timestamps = [start_dt + timedelta(minutes=i) for i in range(num_bars)]

# Create L1 DataFrame
l1_data = pd.DataFrame({
    "symbol": SYMBOL,
    "t_event": timestamps,
    "source": "test_generator",
    "units_normalized": True,
    "price": prices,
    "volume": volumes,
    "dollar_volume": prices * volumes,
    "iv_dec": np.random.uniform(0.18, 0.22, num_bars),
    "oi": None,
    "raw_ref": [f"test://{DATE}/{i}" for i in range(num_bars)]
})

# Save L1 data
l1_path = f"data_l1/l1_{DATE}.parquet"
l1_data.to_parquet(l1_path, index=False)
print(f"✓ Saved L1 data to {l1_path}")

# Generate L3 features by calling /run_bar for each timestamp
print(f"\nGenerating L3 features (calling /run_bar {num_bars} times)...")
print("This will take a moment...")

success_count = 0
error_count = 0

for i, (ts, price, vol) in enumerate(zip(timestamps, prices, volumes)):
    if i % 50 == 0:
        print(f"  Progress: {i}/{num_bars} bars processed...")
    
    try:
        response = requests.post(
            f"{API_BASE}/run_bar/{SYMBOL}",
            params={
                "price": float(price),
                "bar": ts.isoformat(),
                "volume": float(vol)
            },
            timeout=5
        )
        
        if response.status_code == 200:
            success_count += 1
        else:
            error_count += 1
            if error_count < 5:  # Only show first few errors
                print(f"  ⚠ Error at bar {i}: {response.status_code}")
    
    except Exception as e:
        error_count += 1
        if error_count < 5:
            print(f"  ⚠ Exception at bar {i}: {str(e)[:50]}")

print(f"\n✓ L3 feature generation complete:")
print(f"  Success: {success_count}/{num_bars}")
print(f"  Errors:  {error_count}/{num_bars}")

if success_count > 0:
    print(f"\n🎉 Test data ready! You can now run:")
    print(f"   python -m gnosis.backtest --symbol {SYMBOL} --date {DATE}")
else:
    print(f"\n⚠ Warning: No L3 features generated successfully")
    print(f"   Make sure the API server is running on {API_BASE}")