from __future__ import annotations

"""Comprehensive tests for Liquidity Engine v1.0."""

from datetime import datetime

import polars as pl
import pytest

from engines.liquidity.liquidity_engine_v1 import LiquidityEngineV1
from engines.inputs.stub_adapters import StaticMarketDataAdapter


def test_liquidity_engine_full_pipeline():
    """Test complete liquidity engine pipeline."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    # Basic validation
    assert output.kind == "liquidity"
    assert output.symbol == "SPY"
    assert 0.0 <= output.confidence <= 1.0
    
    # Core features
    assert "liquidity_score" in output.features
    assert "friction_cost" in output.features
    assert "amihud_illiquidity" in output.features
    assert "kyle_lambda" in output.features
    
    # Liquidity score must be in [0, 1]
    assert 0.0 <= output.features["liquidity_score"] <= 1.0
    
    # Friction cost must be non-negative
    assert output.features["friction_cost"] >= 0.0
    
    # Order flow features
    assert "orderbook_imbalance" in output.features
    assert -1.0 <= output.features["orderbook_imbalance"] <= 1.0
    
    # Volume features
    assert "volume_strength" in output.features
    assert "buying_effort" in output.features
    assert "selling_effort" in output.features
    
    # Structural features
    assert "num_absorption_zones" in output.features
    assert "num_displacement_zones" in output.features
    
    # Volatility-liquidity
    assert "compression_energy" in output.features
    assert "expansion_energy" in output.features
    
    # POLR
    assert "polr_direction" in output.features
    assert "polr_strength" in output.features
    assert -1.0 <= output.features["polr_direction"] <= 1.0
    assert 0.0 <= output.features["polr_strength"] <= 1.0
    
    # Regime
    assert output.regime in ["Normal", "Thin", "Stressed", "Crisis", "Abundant", "degraded"]
    
    # Metadata
    assert "liquidity_regime" in output.metadata
    assert "wyckoff_phase" in output.metadata


def test_liquidity_engine_degraded_mode():
    """Test degraded mode with no data."""
    class EmptyAdapter:
        def fetch_ohlcv(self, symbol: str, lookback: int, now: datetime):
            return pl.DataFrame()
    
    engine = LiquidityEngineV1(EmptyAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    assert output.confidence == 0.0
    assert output.regime == "degraded"
    assert "degraded_reason" in output.metadata


def test_liquidity_engine_with_configuration():
    """Test that engine respects configuration."""
    config = {
        "lookback_bars": 50,
        "volume_lookback": 10,
        "bb_period": 15,
        "kc_period": 15,
    }
    
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), config)
    output = engine.run("SPY", datetime.utcnow())
    
    assert output.kind == "liquidity"
    assert "liquidity_score" in output.features


def test_liquidity_score_bounds():
    """Test that liquidity score stays in valid range."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    score = output.features["liquidity_score"]
    assert 0.0 <= score <= 1.0, f"Liquidity score {score} out of bounds"


def test_friction_cost_non_negative():
    """Test that friction costs are never negative."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    friction = output.features["friction_cost"]
    assert friction >= 0.0, f"Friction cost {friction} is negative"


def test_polr_metrics():
    """Test POLR (Path of Least Resistance) metrics."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    polr_direction = output.features["polr_direction"]
    polr_strength = output.features["polr_strength"]
    
    # Direction must be in [-1, 1]
    assert -1.0 <= polr_direction <= 1.0
    
    # Strength must be in [0, 1]
    assert 0.0 <= polr_strength <= 1.0


def test_regime_classification():
    """Test regime classification is valid."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    valid_regimes = ["Normal", "Thin", "Stressed", "Crisis", "Abundant", "degraded"]
    assert output.regime in valid_regimes


def test_wyckoff_phase_output():
    """Test Wyckoff phase is included in metadata."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    assert "wyckoff_phase" in output.metadata
    wyckoff_phase = output.metadata["wyckoff_phase"]
    
    valid_phases = ["A", "B", "C", "D", "E", "Unknown"]
    assert wyckoff_phase in valid_phases


def test_compression_expansion_energy():
    """Test compression/expansion energy metrics."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    compression = output.features["compression_energy"]
    expansion = output.features["expansion_energy"]
    
    # Both must be non-negative
    assert compression >= 0.0
    assert expansion >= 0.0


def test_structural_zone_counts():
    """Test structural zone counts are non-negative integers."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    assert output.features["num_absorption_zones"] >= 0
    assert output.features["num_displacement_zones"] >= 0
    assert output.features["num_voids"] >= 0
    assert output.features["num_hvn_nodes"] >= 0


def test_order_flow_imbalance_bounds():
    """Test OFI stays in [-1, 1] range."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    ofi = output.features["orderbook_imbalance"]
    assert -1.0 <= ofi <= 1.0


def test_volume_metrics_bounds():
    """Test volume metrics are in [0, 1] range."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    assert 0.0 <= output.features["volume_strength"] <= 1.0
    assert 0.0 <= output.features["buying_effort"] <= 1.0
    assert 0.0 <= output.features["selling_effort"] <= 1.0


def test_impact_metrics_non_negative():
    """Test impact metrics are non-negative."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    assert output.features["amihud_illiquidity"] >= 0.0
    assert output.features["kyle_lambda"] >= 0.0


def test_confidence_in_valid_range():
    """Test overall confidence is in [0, 1]."""
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    assert 0.0 <= output.confidence <= 1.0
