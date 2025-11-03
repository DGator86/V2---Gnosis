#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime
from gnosis.engines.liquidity_v0 import compute_liquidity_v0

# Scenario 1: High liquidity (tight, stable market)
print("=" * 60)
print("SCENARIO 1: High Liquidity Market")
print("-" * 60)
now = datetime(2025, 11, 3, 14, 31)
df_high_liq = pd.DataFrame({
    "t_event": pd.date_range(end=now, periods=60, freq="1min"),
    "price": 451.5 + np.random.randn(60) * 0.02,  # Very small price moves
    "volume": np.random.randint(8000, 12000, 60)  # High volume
})
features_high = compute_liquidity_v0("SPY", now, df_high_liq)
print(f"Amihud (lower=better): {features_high.present.amihud:.2e}")
print(f"Kyle λ: {features_high.present.lambda_impact:.2e}")
print(f"Support zones: {len(features_high.present.support)}")
print(f"Resistance zones: {len(features_high.present.resistance)}")
print(f"Confidence: {features_high.present.conf}")

# Scenario 2: Low liquidity (wide, volatile market)
print("\n" + "=" * 60)
print("SCENARIO 2: Low Liquidity Market")
print("-" * 60)
df_low_liq = pd.DataFrame({
    "t_event": pd.date_range(end=now, periods=60, freq="1min"),
    "price": 451.5 + np.cumsum(np.random.randn(60) * 0.2),  # Large price moves
    "volume": np.random.randint(500, 2000, 60)  # Low volume
})
features_low = compute_liquidity_v0("SPY", now, df_low_liq)
print(f"Amihud (lower=better): {features_low.present.amihud:.2e}")
print(f"Kyle λ: {features_low.present.lambda_impact:.2e}")
print(f"Support zones: {len(features_low.present.support)}")
print(f"Resistance zones: {len(features_low.present.resistance)}")
print(f"Confidence: {features_low.present.conf}")

# Scenario 3: Trending market with volume clusters
print("\n" + "=" * 60)
print("SCENARIO 3: Trending Market with Volume Clusters")
print("-" * 60)
prices = np.linspace(450, 453, 60) + np.random.randn(60) * 0.1
volumes = np.where(
    (prices > 451) & (prices < 451.5), 
    np.random.randint(10000, 15000, 60),  # High volume cluster
    np.random.randint(1000, 3000, 60)
)
df_trend = pd.DataFrame({
    "t_event": pd.date_range(end=now, periods=60, freq="1min"),
    "price": prices,
    "volume": volumes
})
features_trend = compute_liquidity_v0("SPY", now, df_trend)
print(f"Amihud (lower=better): {features_trend.present.amihud:.2e}")
print(f"Kyle λ: {features_trend.present.lambda_impact:.2e}")
print(f"Support zones: {features_trend.present.support[:2]}")
print(f"Resistance zones: {features_trend.present.resistance[:2]}")
print(f"Next magnet: ${features_trend.future.next_magnet:.2f}")
print(f"Zone survival probability: {features_trend.future.zone_survival}")