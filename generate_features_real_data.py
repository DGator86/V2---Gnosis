"""Generate L3 features for real market data"""

import pandas as pd
import numpy as np
from datetime import datetime
from gnosis.feature_store.store import FeatureStore
from gnosis.engines.hedge_v0 import compute_hedge_v0
from gnosis.engines.liquidity_v0 import compute_liquidity_v0
from gnosis.engines.sentiment_v0 import compute_sentiment_v0
from gnosis.schemas.base import L3Canonical

def generate_features_for_date(date: str, symbol: str = "SPY"):
    """Generate L3 features for a specific date"""
    
    # Load L1 data
    l1_file = f"data_l1/l1_{date}.parquet"
    l1 = pd.read_parquet(l1_file)
    l1 = l1[l1["symbol"] == symbol].sort_values("t_event").reset_index(drop=True)
    
    print(f"\nGenerating L3 features for {symbol} on {date}")
    print(f"Total bars: {len(l1)}")
    print(f"Sampling every 10th bar for speed...")
    
    fs = FeatureStore(root="data")
    
    count = 0
    for i in range(50, len(l1), 10):  # Every 10th bar
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
        
        # Save to feature store
        row = L3Canonical(symbol=symbol, bar=t, hedge=hedge, liquidity=liq, sentiment=sent)
        fs.write(row)
        
        count += 1
        if count % 5 == 0:
            print(f"  Processed {count} bars...")
    
    print(f"✅ Generated {count} feature rows for {date}")
    return count

if __name__ == "__main__":
    import sys
    
    date = sys.argv[1] if len(sys.argv) > 1 else "2025-10-31"
    symbol = sys.argv[2] if len(sys.argv) > 2 else "SPY"
    
    try:
        count = generate_features_for_date(date, symbol)
        print(f"\n✅ Success! Generated {count} L3 feature rows")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
