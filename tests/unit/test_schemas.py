"""
Unit tests for schema models.
"""

import pytest
from datetime import datetime
from src.schemas import Bar, OptionSnapshot, HedgeFields, LiquidityFields


def test_bar_creation():
    """Test Bar model creation and validation."""
    bar = Bar(
        ts=datetime(2024, 1, 1, 10, 0),
        symbol="SPY",
        open=450.0,
        high=452.0,
        low=449.0,
        close=451.0,
        volume=1000000.0,
        vwap=450.5
    )
    
    assert bar.symbol == "SPY"
    assert bar.close == 451.0
    assert bar.volume == 1000000.0


def test_option_snapshot_creation():
    """Test OptionSnapshot model creation."""
    opt = OptionSnapshot(
        ts=datetime(2024, 1, 1, 10, 0),
        symbol="SPY",
        expiry="2024-01-15",
        strike=450.0,
        right="C",
        bid=5.0,
        ask=5.5,
        iv=0.25,
        delta=0.5,
        gamma=0.05,
        vega=0.1,
        theta=-0.05,
        open_interest=1000,
        volume=100
    )
    
    assert opt.symbol == "SPY"
    assert opt.right == "C"
    assert opt.strike == 450.0
    assert opt.delta == 0.5


def test_hedge_fields_validation():
    """Test HedgeFields model validation."""
    fields = HedgeFields(
        ts=datetime(2024, 1, 1, 10, 0),
        symbol="SPY",
        gex=1000000.0,
        vanna=50000.0,
        charm=-10000.0,
        gamma_flip_level=450.0,
        pressure_score=0.75
    )
    
    assert fields.symbol == "SPY"
    assert fields.gex == 1000000.0
    assert 0 <= fields.pressure_score <= 1


def test_liquidity_fields_validation():
    """Test LiquidityFields model validation."""
    fields = LiquidityFields(
        ts=datetime(2024, 1, 1, 10, 0),
        symbol="SPY",
        amihud=1e-9,
        kyle_lambda=1e-6,
        vpoc=450.0,
        zones=[440.0, 445.0, 450.0, 455.0, 460.0],
        dark_pool_ratio=0.35,
        liquidity_trend="neutral"
    )
    
    assert fields.symbol == "SPY"
    assert fields.liquidity_trend in ["tightening", "loosening", "neutral"]
    assert len(fields.zones) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
