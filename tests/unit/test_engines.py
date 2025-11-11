"""
Unit tests for engine computations.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from src.schemas import Bar, OptionSnapshot
from src.engines import compute_hedge_fields, compute_liquidity_fields, compute_sentiment_fields


def create_test_bars(n=100):
    """Create test bars."""
    bars = []
    base_time = datetime(2024, 1, 1, 10, 0)
    
    for i in range(n):
        bar = Bar(
            ts=base_time + timedelta(hours=i),
            symbol="SPY",
            open=450.0 + i * 0.1,
            high=451.0 + i * 0.1,
            low=449.0 + i * 0.1,
            close=450.5 + i * 0.1,
            volume=1e6,
        )
        bars.append(bar)
    
    return bars


def create_test_options():
    """Create test options chain."""
    options = []
    base_time = datetime(2024, 1, 1, 10, 0)
    
    for strike in [440, 445, 450, 455, 460]:
        for right in ["C", "P"]:
            opt = OptionSnapshot(
                ts=base_time,
                symbol="SPY",
                expiry="2024-01-15",
                strike=float(strike),
                right=right,
                bid=5.0,
                ask=5.5,
                iv=0.25,
                delta=0.5 if right == "C" else -0.5,
                gamma=0.05,
                vega=0.1,
                theta=-0.05,
                open_interest=1000,
                volume=100
            )
            options.append(opt)
    
    return options


def test_compute_hedge_fields():
    """Test hedge engine computation."""
    bars = create_test_bars()
    options = create_test_options()
    
    fields = compute_hedge_fields("SPY", options, bars)
    
    assert fields.symbol == "SPY"
    assert isinstance(fields.gex, float)
    assert isinstance(fields.vanna, float)
    assert isinstance(fields.charm, float)
    assert 0 <= fields.pressure_score <= 1


def test_compute_liquidity_fields():
    """Test liquidity engine computation."""
    bars = create_test_bars()
    
    fields = compute_liquidity_fields("SPY", bars)
    
    assert fields.symbol == "SPY"
    assert fields.amihud >= 0
    assert fields.kyle_lambda >= 0
    assert fields.vpoc > 0
    assert len(fields.zones) > 0
    assert fields.liquidity_trend in ["tightening", "loosening", "neutral"]


def test_compute_sentiment_fields():
    """Test sentiment engine computation."""
    bars = create_test_bars()
    news_scores = [0.1, 0.2, -0.1, 0.3, 0.15]
    
    fields = compute_sentiment_fields("SPY", bars, news_scores)
    
    assert fields.symbol == "SPY"
    assert -1 <= fields.news_sentiment <= 1
    assert fields.regime in ["calm", "normal", "elevated", "squeeze_risk", "gamma_storm", "unknown"]
    assert fields.wyckoff_phase in ["accumulation", "markup", "distribution", "markdown", "unknown"]


def test_empty_data_handling():
    """Test engines handle empty data gracefully."""
    # Empty bars
    fields = compute_hedge_fields("SPY", [], [])
    assert fields.gex == 0.0
    
    fields = compute_liquidity_fields("SPY", [])
    assert fields.amihud == 0.0
    
    fields = compute_sentiment_fields("SPY", [])
    assert fields.regime == "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
