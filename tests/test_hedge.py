import numpy as np
import pandas as pd
from datetime import datetime
from gnosis.engines.hedge_v0 import compute_hedge_v0

def test_empty_chain():
    """Test with empty options chain"""
    now = datetime(2025, 11, 3, 14, 31)
    spot = 451.65
    chain = pd.DataFrame()
    
    features = compute_hedge_v0("SPY", now, spot, chain)
    
    assert features.present.hedge_force == 0
    assert features.present.regime == "neutral"
    assert features.present.conf == 0

def test_pin_regime():
    """Test detection of pin regime (low gamma)"""
    now = datetime(2025, 11, 3, 14, 31)
    spot = 451.65
    
    chain = pd.DataFrame({
        "strike": np.linspace(spot*0.95, spot*1.05, 20),
        "expiry": pd.Timestamp(now + pd.Timedelta(days=7)),
        "iv": np.full(20, 0.20),
        "delta": np.linspace(-0.5, 0.5, 20),
        "gamma": np.full(20, 1e-6),  # Very low gamma
        "vega": np.full(20, 0.02),
        "theta": np.full(20, -0.01),
        "open_interest": np.full(20, 100)
    })
    
    features = compute_hedge_v0("SPY", now, spot, chain)
    
    assert features.present.regime == "pin"
    assert abs(features.present.hedge_force) < 0.2

def test_breakout_regime():
    """Test detection of breakout regime (high gamma)"""
    now = datetime(2025, 11, 3, 14, 31)
    spot = 451.65
    
    chain = pd.DataFrame({
        "strike": [spot],  # All OI at one strike
        "expiry": pd.Timestamp(now + pd.Timedelta(days=1)),
        "iv": [0.35],
        "delta": [0.5],
        "gamma": [1e-2],  # Very high gamma
        "vega": [0.1],
        "theta": [-0.5],
        "open_interest": [10000]  # Massive OI
    })
    
    features = compute_hedge_v0("SPY", now, spot, chain)
    
    # With massive gamma concentration, should show strong directional force
    assert abs(features.present.hedge_force) > 0  
    assert features.present.conf > 0.5

def test_wall_detection():
    """Test gamma wall detection"""
    now = datetime(2025, 11, 3, 14, 31)
    spot = 451.65
    
    chain = pd.DataFrame({
        "strike": [450, 451, 452, 453, 455],  # Wall at 455
        "expiry": pd.Timestamp(now + pd.Timedelta(days=7)),
        "iv": [0.20] * 5,
        "delta": [0.3, 0.4, 0.5, 0.6, 0.7],
        "gamma": [1e-5, 1e-5, 1e-5, 1e-5, 1e-3],  # Huge gamma at 455
        "vega": [0.02] * 5,
        "theta": [-0.01] * 5,
        "open_interest": [100, 100, 100, 100, 5000]  # Massive OI at 455
    })
    
    features = compute_hedge_v0("SPY", now, spot, chain)
    
    # Should detect wall at 455
    assert features.present.wall_dist > 0
    assert features.present.wall_dist < 5  # Within reasonable range

def test_confidence_scaling():
    """Test that confidence scales with data quality"""
    now = datetime(2025, 11, 3, 14, 31)
    spot = 451.65
    
    # Low OI, scattered chain
    chain_low_conf = pd.DataFrame({
        "strike": np.linspace(spot*0.8, spot*1.2, 5),
        "expiry": pd.Timestamp(now + pd.Timedelta(days=30)),
        "iv": np.random.uniform(0.15, 0.25, 5),
        "delta": np.linspace(-0.9, 0.9, 5),
        "gamma": np.abs(np.random.normal(1e-5, 1e-6, 5)),
        "vega": np.random.uniform(0.01, 0.05, 5),
        "theta": -np.abs(np.random.uniform(0.01, 0.03, 5)),
        "open_interest": np.full(5, 10)  # Very low OI
    })
    
    # High OI, concentrated chain
    chain_high_conf = pd.DataFrame({
        "strike": np.linspace(spot*0.95, spot*1.05, 40),
        "expiry": pd.Timestamp(now + pd.Timedelta(days=7)),
        "iv": np.full(40, 0.20),
        "delta": np.linspace(-0.5, 0.5, 40),
        "gamma": np.full(40, 5e-5),
        "vega": np.full(40, 0.03),
        "theta": np.full(40, -0.02),
        "open_interest": np.random.randint(500, 1000, 40)  # High OI
    })
    # Add concentration
    chain_high_conf.loc[20, "open_interest"] = 5000  # Spike at ATM
    
    features_low = compute_hedge_v0("SPY", now, spot, chain_low_conf)
    features_high = compute_hedge_v0("SPY", now, spot, chain_high_conf)
    
    # Higher OI concentration should lead to higher confidence
    assert features_high.present.conf >= features_low.present.conf