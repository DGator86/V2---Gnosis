#!/usr/bin/env python3
"""
Generate L3 features for multiple days of real market data.
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from gnosis.feature_store.store import FeatureStore
from gnosis.schemas.base import L3Canonical
from gnosis.engines.hedge_v0 import compute_hedge_v0
from gnosis.engines.liquidity_v0 import compute_liquidity_v0
from gnosis.engines.sentiment_v0 import compute_sentiment_v0

def generate_features_for_date(date: str, symbol: str = "SPY"):
    """Generate L3 features for a single date."""
    input_path = f"data_l1/l1_{date}.parquet"
    
    if not Path(input_path).exists():
        print(f"⚠ Skipping {date}: No L1 data found")
        return 0
    
    print(f"\n📊 Processing {date}...")
    l1 = pd.read_parquet(input_path)
    l1 = l1[l1["symbol"] == symbol].sort_values("t_event").reset_index(drop=True)
    print(f"  Loaded {len(l1)} L1 bars")
    
    fs = FeatureStore(root="data")
    feature_count = 0
    
    # Sample every 10th bar to avoid overwhelming the system
    for i in range(50, len(l1), 10):
        t = l1.loc[i, "t_event"]
        price = l1.loc[i, "price"]
        
        # Get recent window
        df_recent = l1.iloc[max(0, i-60):i+1].copy()
        
        # Generate synthetic options chain (placeholder)
        chain = pd.DataFrame({
            "strike": np.linspace(price*0.9, price*1.1, 40),
            "expiry": pd.Timestamp(t) + pd.Timedelta(days=7),
            "iv": np.random.uniform(0.15, 0.25, 40),
            "delta": np.linspace(-0.9, 0.9, 40),
            "gamma": np.abs(np.random.normal(1e-5, 2e-6, 40)),
            "vega": np.random.uniform(0.01, 0.05, 40),
            "theta": -np.abs(np.random.uniform(0.01, 0.03, 40)),
            "open_interest": np.random.randint(50, 500, 40)
        })
        
        # Compute features
        hedge = compute_hedge_v0(symbol, t, price, chain)
        liq = compute_liquidity_v0(symbol, t, df_recent)
        sent = compute_sentiment_v0(symbol, t, df_recent)
        
        # Write to feature store
        row = L3Canonical(symbol=symbol, bar=t, hedge=hedge, liquidity=liq, sentiment=sent)
        fs.write(row)
        feature_count += 1
    
    print(f"  ✓ Generated {feature_count} L3 features")
    return feature_count

def main():
    dates = ['2025-10-24', '2025-10-27', '2025-10-28', '2025-10-29', '2025-10-30']
    
    print("=" * 60)
    print("GENERATING L3 FEATURES FOR MULTI-DAY DATA")
    print("=" * 60)
    
    total_features = 0
    for date in dates:
        try:
            count = generate_features_for_date(date)
            total_features += count
        except Exception as e:
            print(f"✗ Error processing {date}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f'\n{"=" * 60}')
    print(f'✓ Total L3 features generated: {total_features}')
    print(f'{"=" * 60}\n')

if __name__ == '__main__':
    main()
