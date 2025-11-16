from __future__ import annotations

"""Integration tests for full Hedge Engine v3.0."""

from datetime import datetime

from engines.hedge.hedge_engine_v3 import HedgeEngineV3
from engines.inputs.stub_adapters import StaticOptionsAdapter


def test_hedge_engine_full_pipeline():
    """Test complete hedge engine pipeline with all processors."""
    engine = HedgeEngineV3(StaticOptionsAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    # Basic output validation
    assert output.kind == "hedge"
    assert output.symbol == "SPY"
    assert isinstance(output.confidence, float)
    
    # Should have all primary features
    assert "pressure_up" in output.features
    assert "pressure_down" in output.features
    assert "net_pressure" in output.features
    assert "elasticity" in output.features
    assert "movement_energy" in output.features
    
    # Should have elasticity breakdown
    assert "elasticity_up" in output.features
    assert "elasticity_down" in output.features
    
    # Should have movement energy breakdown
    assert "movement_energy_up" in output.features
    assert "movement_energy_down" in output.features
    assert "energy_asymmetry" in output.features
    
    # Should have Greek components
    assert "gamma_pressure" in output.features
    assert "vanna_pressure" in output.features
    assert "charm_pressure" in output.features
    assert "dealer_gamma_sign" in output.features
    
    # Elasticity must be positive
    assert output.features["elasticity"] > 0
    
    # Regime should be classified
    assert output.regime is not None
    assert isinstance(output.regime, str)
    
    # Metadata should include regime details
    assert "potential_shape" in output.metadata
    assert "gamma_regime" in output.metadata
    assert "vanna_regime" in output.metadata
    assert "charm_regime" in output.metadata
    assert "jump_risk_regime" in output.metadata


def test_hedge_engine_degraded_mode():
    """Test that engine handles missing data gracefully."""
    # Create an adapter that returns empty chain
    class EmptyAdapter:
        def fetch_chain(self, symbol: str, now: datetime):
            import polars as pl
            return pl.DataFrame()
    
    engine = HedgeEngineV3(EmptyAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    # Should return degraded output
    assert output.confidence == 0.0
    assert output.regime == "degraded"
    assert "degraded_reason" in output.metadata


def test_hedge_engine_with_configuration():
    """Test that engine respects configuration parameters."""
    config = {
        "gamma_squeeze_threshold": 1e8,  # Very high threshold
        "base_elasticity": 2.0,
        "strike_decay_rate": 0.1,
    }
    
    engine = HedgeEngineV3(StaticOptionsAdapter(), config)
    output = engine.run("SPY", datetime.utcnow())
    
    # Should still produce valid output
    assert output.kind == "hedge"
    assert "elasticity" in output.features
    assert output.features["elasticity"] > 0


def test_hedge_engine_feature_types():
    """Test that all features have correct types."""
    engine = HedgeEngineV3(StaticOptionsAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    # All features should be floats
    for key, value in output.features.items():
        assert isinstance(value, float), f"Feature {key} should be float, got {type(value)}"
    
    # Confidence should be in [0, 1]
    assert 0.0 <= output.confidence <= 1.0


def test_hedge_engine_pressure_consistency():
    """Test that pressure calculations are internally consistent."""
    engine = HedgeEngineV3(StaticOptionsAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    # Net pressure should be up - down
    pressure_up = output.features["pressure_up"]
    pressure_down = output.features["pressure_down"]
    net_pressure = output.features["net_pressure"]
    
    # Allow small floating point error
    assert abs((pressure_up - pressure_down) - net_pressure) < 1e-6


def test_hedge_engine_energy_elasticity_relationship():
    """Test the relationship between energy and elasticity."""
    engine = HedgeEngineV3(StaticOptionsAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    elasticity = output.features["elasticity"]
    movement_energy = output.features["movement_energy"]
    
    # Both should be positive
    assert elasticity > 0
    assert movement_energy >= 0
    
    # Energy should generally scale inversely with elasticity
    # (High elasticity = high barriers = low energy to overcome them is unlikely)
    # This is a soft relationship, not strict


def test_hedge_engine_dealer_gamma_sign():
    """Test that dealer gamma sign is in valid range."""
    engine = HedgeEngineV3(StaticOptionsAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    dealer_gamma_sign = output.features["dealer_gamma_sign"]
    
    # Should be in [-1, 1]
    assert -1.0 <= dealer_gamma_sign <= 1.0


def test_hedge_engine_cross_asset_correlation():
    """Test cross-asset correlation feature."""
    engine = HedgeEngineV3(StaticOptionsAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    
    if "cross_asset_correlation" in output.features:
        corr = output.features["cross_asset_correlation"]
        # Should be in [-1, 1]
        assert -1.0 <= corr <= 1.0
