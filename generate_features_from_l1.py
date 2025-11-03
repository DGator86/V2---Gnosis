"""
Generate L3 features from L1 data

This processes L1 bars through all engines to create L3 feature store.
"""

import pandas as pd
from datetime import datetime
from pathlib import Path
from gnosis.feature_store.store import FeatureStore
from gnosis.schemas.base import L3Canonical
from gnosis.engines.hedge_v0 import compute_hedge_v0
from gnosis.engines.liquidity_v0 import compute_liquidity_v0
from gnosis.engines.sentiment_v0 import compute_sentiment_v0
import numpy as np

def generate_features(l1_file: str, symbol: str = "SPY"):
    """Generate L3 features from L1 data"""
    
    print(f"\n{'='*70}")
    print(f"  Generating L3 Features")
    print(f"  Input: {l1_file}")
    print(f"{'='*70}\n")
    
    # Load L1 data
    df = pd.read_parquet(l1_file)
    df = df[df["symbol"] == symbol].sort_values("t_event").reset_index(drop=True)
    
    print(f"📊 Loaded {len(df)} bars for {symbol}")
    print(f"   Date range: {df['t_event'].min()} to {df['t_event'].max()}")
    
    # Initialize feature store
    fs = FeatureStore(root="data")
    
    features_created = 0
    
    # Process each bar (need at least 50 bars of history for engines)
    for i in range(50, len(df)):
        t = df.loc[i, "t_event"]
        price = df.loc[i, "price"]
        
        # Get historical window
        window = df.iloc[max(0, i-60):i+1].copy()
        
        # Generate fake options chain (since we don't have real options data)
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
        
        try:
            # Compute features
            hedge = compute_hedge_v0(symbol, t, price, chain)
            liq = compute_liquidity_v0(symbol, t, window)
            sent = compute_sentiment_v0(symbol, t, window)
            
            # Create L3 row
            row = L3Canonical(
                symbol=symbol,
                bar=t,
                hedge=hedge,
                liquidity=liq,
                sentiment=sent
            )
            
            # Write to feature store
            fs.write(row)
            features_created += 1
            
            if features_created % 20 == 0:
                print(f"   ✅ Generated {features_created} feature rows...")
                
        except Exception as e:
            print(f"   ⚠️  Skipped bar {i} at {t}: {e}")
            continue
    
    print(f"\n✅ Generated {features_created} L3 feature rows")
    print(f"   Stored in: data/date={t.strftime('%Y-%m-%d')}/symbol={symbol}/")
    print(f"\n🚀 Ready for comparative backtest!")

if __name__ == "__main__":
    import sys
    
    l1_file = sys.argv[1] if len(sys.argv) > 1 else "data_l1/l1_2024-10-01.parquet"
    symbol = sys.argv[2] if len(sys.argv) > 2 else "SPY"
    
    generate_features(l1_file, symbol)
