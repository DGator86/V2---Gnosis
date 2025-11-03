#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime
from gnosis.engines.hedge_v0 import compute_hedge_v0

now = datetime(2025, 11, 3, 14, 31)
spot = 451.65

print("=" * 60)
print("SCENARIO 1: High Gamma Concentration (Pin Risk)")
print("-" * 60)
# Concentrated OI at specific strikes
chain_pin = pd.DataFrame({
    "strike": np.linspace(spot*0.9, spot*1.1, 40),
    "expiry": pd.Timestamp(now + pd.Timedelta(days=7)),
    "iv": np.random.uniform(0.15, 0.25, 40),
    "delta": np.linspace(-0.9, 0.9, 40),
    "gamma": np.abs(np.random.normal(1e-4, 2e-5, 40)),  # Higher gamma
    "vega": np.random.uniform(0.01, 0.05, 40),
    "theta": -np.abs(np.random.uniform(0.01, 0.03, 40)),
    "open_interest": np.random.randint(50, 100, 40)
})
# Massive OI concentration at 452 strike
pin_strike_idx = np.argmin(np.abs(chain_pin["strike"] - 452))
chain_pin.loc[pin_strike_idx, "open_interest"] = 5000
chain_pin.loc[pin_strike_idx, "gamma"] = 5e-4

features_pin = compute_hedge_v0("SPY", now, spot, chain_pin)
print(f"Hedge Force: {features_pin.present.hedge_force:.4f}")
print(f"Regime: {features_pin.present.regime}")
print(f"Wall Distance: ${features_pin.present.wall_dist:.2f}")
print(f"Confidence: {features_pin.present.conf:.2f}")
print(f"Exhaustion: {features_pin.past.exhaustion_score:.4f}")

print("\n" + "=" * 60)
print("SCENARIO 2: Negative Gamma (Breakout Setup)")
print("-" * 60)
# Dealers short gamma - explosive potential
chain_breakout = pd.DataFrame({
    "strike": np.linspace(spot*0.9, spot*1.1, 40),
    "expiry": pd.Timestamp(now + pd.Timedelta(days=2)),  # Near expiry
    "iv": np.random.uniform(0.25, 0.35, 40),  # Higher IV
    "delta": np.linspace(-0.9, 0.9, 40),
    "gamma": np.random.normal(-2e-4, 3e-5, 40),  # Negative gamma!
    "vega": np.random.uniform(0.01, 0.05, 40),
    "theta": -np.abs(np.random.uniform(0.05, 0.10, 40)),  # High theta decay
    "open_interest": np.random.randint(200, 800, 40)
})

features_breakout = compute_hedge_v0("SPY", now, spot, chain_breakout)
print(f"Hedge Force: {features_breakout.present.hedge_force:.4f}")
print(f"Regime: {features_breakout.present.regime}")
print(f"Wall Distance: ${features_breakout.present.wall_dist:.2f}")
print(f"Confidence: {features_breakout.present.conf:.2f}")
print(f"Future Q10/Q50/Q90: {features_breakout.future.q10:.2f}/{features_breakout.future.q50:.2f}/{features_breakout.future.q90:.2f}")

print("\n" + "=" * 60)
print("SCENARIO 3: Balanced Book (Neutral)")
print("-" * 60)
# Well-distributed, balanced positioning
chain_neutral = pd.DataFrame({
    "strike": np.linspace(spot*0.9, spot*1.1, 40),
    "expiry": pd.Timestamp(now + pd.Timedelta(days=30)),
    "iv": np.random.uniform(0.18, 0.22, 40),
    "delta": np.linspace(-0.9, 0.9, 40),
    "gamma": np.abs(np.random.normal(5e-5, 1e-5, 40)),
    "vega": np.random.uniform(0.01, 0.05, 40),
    "theta": -np.abs(np.random.uniform(0.005, 0.015, 40)),
    "open_interest": np.random.randint(100, 300, 40)
})

features_neutral = compute_hedge_v0("SPY", now, spot, chain_neutral)
print(f"Hedge Force: {features_neutral.present.hedge_force:.4f}")
print(f"Regime: {features_neutral.present.regime}")
print(f"Wall Distance: ${features_neutral.present.wall_dist:.2f}")
print(f"Hit Probability T+1: {features_neutral.future.hit_prob_tp1:.2%}")
print(f"ETA Bars: {features_neutral.future.eta_bars}")

print("\n" + "=" * 60)
print("SCENARIO 4: Vanna-Driven (Spot-Vol Correlation)")
print("-" * 60)
# High vega exposure creating vanna effects
chain_vanna = pd.DataFrame({
    "strike": np.linspace(spot*0.9, spot*1.1, 40),
    "expiry": pd.Timestamp(now + pd.Timedelta(days=14)),
    "iv": np.random.uniform(0.15, 0.30, 40),
    "delta": np.linspace(-0.9, 0.9, 40),
    "gamma": np.abs(np.random.normal(3e-5, 1e-5, 40)),
    "vega": np.random.uniform(0.05, 0.15, 40) * 2,  # High vega
    "theta": -np.abs(np.random.uniform(0.01, 0.03, 40)),
    "open_interest": np.random.randint(100, 500, 40)
})
# Skew the OI to create vanna imbalance
otm_puts = chain_vanna["strike"] < spot * 0.95
chain_vanna.loc[otm_puts, "open_interest"] *= 3

features_vanna = compute_hedge_v0("SPY", now, spot, chain_vanna)
print(f"Hedge Force: {features_vanna.present.hedge_force:.4f}")
print(f"Regime: {features_vanna.present.regime}")
print(f"Charm exhaustion: {features_vanna.past.exhaustion_score:.4f}")
print(f"Future confidence: {features_vanna.future.conf:.2f}")