import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from gnosis.engines.liquidity_v0 import compute_liquidity_v0, _amihud, _kyle_lambda, _volume_profile_zones

def test_amihud_calculation():
    """Test Amihud illiquidity measure"""
    df = pd.DataFrame({
        "t_event": pd.date_range("2025-11-03 14:00", periods=5, freq="1min"),
        "price": [100, 100.5, 100.2, 100.8, 101],
        "dollar_volume": [10000, 15000, 12000, 18000, 20000]
    })
    amihud = _amihud(df)
    assert np.isfinite(amihud)
    assert amihud > 0  # Should be positive for illiquidity

def test_kyle_lambda():
    """Test Kyle's lambda calculation"""
    df = pd.DataFrame({
        "t_event": pd.date_range("2025-11-03 14:00", periods=5, freq="1min"),
        "price": [100, 100.5, 100.2, 100.8, 101],
        "dollar_volume": [10000, 15000, 12000, 18000, 20000]
    })
    kyle = _kyle_lambda(df)
    assert np.isfinite(kyle) or np.isnan(kyle)  # Can be nan if no correlation

def test_volume_profile_zones():
    """Test volume profile zone detection"""
    df = pd.DataFrame({
        "t_event": pd.date_range("2025-11-03 14:00", periods=100, freq="1min"),
        "price": np.random.normal(100, 2, 100),
        "volume": np.random.randint(1000, 5000, 100)
    })
    zones = _volume_profile_zones(df)
    assert isinstance(zones, list)
    for zone in zones:
        assert zone.lo < zone.hi

def test_compute_liquidity_full():
    """Test full liquidity computation"""
    now = datetime(2025, 11, 3, 14, 31)
    df = pd.DataFrame({
        "t_event": pd.date_range(end=now, periods=60, freq="1min"),
        "price": 451 + np.cumsum(np.random.randn(60) * 0.1),
        "volume": np.random.randint(2000, 5000, 60)
    })
    
    features = compute_liquidity_v0("SPY", now, df)
    
    # Check structure
    assert features.past is not None
    assert features.present is not None
    assert features.future is not None
    
    # Check values are reasonable
    assert 0 <= features.present.conf <= 1
    assert features.present.amihud >= 0
    assert features.present.lambda_impact >= 0
    assert isinstance(features.present.support, list)
    assert isinstance(features.present.resistance, list)