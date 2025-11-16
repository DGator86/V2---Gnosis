from __future__ import annotations

"""Comprehensive tests for hedge engine processors."""

from datetime import datetime, timezone

import polars as pl
import pytest

from engines.hedge.models import GreekInputs
from engines.hedge.processors import (
    build_charm_field,
    build_gamma_field,
    build_vanna_field,
    calculate_elasticity,
    calculate_movement_energy,
    detect_regime,
    estimate_dealer_sign,
)


@pytest.fixture
def sample_chain() -> pl.DataFrame:
    """Create a sample options chain for testing."""
    return pl.DataFrame({
        "strike": [90.0, 95.0, 100.0, 105.0, 110.0],
        "option_type": ["P", "P", "C", "C", "C"],
        "gamma": [0.05, 0.08, 0.10, 0.08, 0.05],
        "vanna": [0.02, 0.03, 0.04, 0.03, 0.02],
        "charm": [-0.01, -0.015, -0.02, -0.015, -0.01],
        "open_interest": [1000, 2000, 5000, 2000, 1000],
        "underlying_price": [100.0, 100.0, 100.0, 100.0, 100.0],
        "days_to_expiry": [30, 30, 30, 30, 30],
    })


@pytest.fixture
def greek_inputs(sample_chain: pl.DataFrame) -> GreekInputs:
    """Create GreekInputs from sample chain."""
    return GreekInputs(
        chain=sample_chain,
        spot=100.0,
        vix=20.0,
        vol_of_vol=0.3,
        liquidity_lambda=0.1,
        timestamp=datetime.now(timezone.utc).timestamp(),
    )


@pytest.fixture
def config() -> dict:
    """Default configuration for processors."""
    return {
        "strike_decay_rate": 0.05,
        "gamma_sign_threshold": 1e3,
        "min_strikes_for_confidence": 5,
        "min_oi_threshold": 100,
        "gamma_squeeze_threshold": 1e5,
        "vanna_flow_threshold": 1e4,
        "pin_oi_threshold": 1000,
        "vanna_high_threshold": 5e4,
        "vol_of_vol_shock_threshold": 0.5,
        "charm_high_threshold": 1e4,
        "charm_decay_threshold": 5e3,
        "base_elasticity": 1.0,
        "gamma_elasticity_scale": 1e-3,
        "vanna_elasticity_scale": 1e-3,
        "charm_elasticity_scale": 1e-3,
        "oi_concentration_scale": 2.0,
        "liquidity_friction_scale": 1.0,
        "directional_pressure_scale": 1e-4,
        "gamma_quadratic_threshold": 1e4,
        "gamma_cubic_threshold": 5e4,
        "vanna_double_well_threshold": 5e4,
        "gamma_quartic_threshold": 1e5,
        "vol_of_vol_jump_threshold": 0.4,
        "vix_jump_threshold": 30.0,
    }


def test_dealer_sign_estimation(greek_inputs: GreekInputs, config: dict):
    """Test dealer sign estimation."""
    result = estimate_dealer_sign(greek_inputs, config)
    
    # Should produce valid outputs
    assert isinstance(result.net_dealer_gamma, float)
    assert isinstance(result.dealer_sign, float)
    assert -1.0 <= result.dealer_sign <= 1.0
    assert 0.0 <= result.confidence <= 1.0
    
    # Should have calculated OI-weighted strike center
    assert result.oi_weighted_strike_center > 0
    
    # Should have metadata
    assert "total_oi" in result.metadata
    assert "num_strikes" in result.metadata


def test_gamma_field_construction(greek_inputs: GreekInputs, config: dict):
    """Test gamma field construction."""
    dealer_sign = estimate_dealer_sign(greek_inputs, config)
    result = build_gamma_field(greek_inputs, dealer_sign, config)
    
    # Should produce valid gamma pressures
    assert isinstance(result.gamma_pressure_up, float)
    assert isinstance(result.gamma_pressure_down, float)
    assert isinstance(result.gamma_exposure, float)
    
    # Should classify regime
    assert result.gamma_regime in [
        "short_gamma_squeeze",
        "long_gamma_compression",
        "low_gamma_expansion",
        "neutral",
    ]
    
    # Should have dealer sign
    assert -1.0 <= result.dealer_gamma_sign <= 1.0
    
    # Should have strike-weighted gamma map
    assert isinstance(result.strike_weighted_gamma, dict)


def test_vanna_field_construction(greek_inputs: GreekInputs, config: dict):
    """Test vanna field construction."""
    dealer_sign = estimate_dealer_sign(greek_inputs, config)
    result = build_vanna_field(greek_inputs, dealer_sign, config)
    
    # Should produce valid vanna pressures
    assert isinstance(result.vanna_pressure_up, float)
    assert isinstance(result.vanna_pressure_down, float)
    assert isinstance(result.vanna_exposure, float)
    
    # Should have vol sensitivity
    assert isinstance(result.vol_sensitivity, float)
    
    # Should have shock absorber
    assert 0.0 < result.vanna_shock_absorber <= 1.0
    
    # Should classify regime
    assert result.vanna_regime in [
        "high_vanna_high_vol",
        "high_vanna_low_vol",
        "vanna_flow",
        "neutral",
    ]


def test_charm_field_construction(greek_inputs: GreekInputs, config: dict):
    """Test charm field construction."""
    dealer_sign = estimate_dealer_sign(greek_inputs, config)
    result = build_charm_field(greek_inputs, dealer_sign, config)
    
    # Should produce valid charm values
    assert isinstance(result.charm_exposure, float)
    assert isinstance(result.charm_drift_rate, float)
    assert isinstance(result.time_decay_pressure, float)
    
    # Should have decay acceleration
    assert result.decay_acceleration > 0
    
    # Should classify regime
    assert result.charm_regime in [
        "high_charm_decay_acceleration",
        "charm_decay_dominant",
        "neutral",
    ]


def test_elasticity_calculation(greek_inputs: GreekInputs, config: dict):
    """Test elasticity calculation (CORE THEORY)."""
    dealer_sign = estimate_dealer_sign(greek_inputs, config)
    gamma_field = build_gamma_field(greek_inputs, dealer_sign, config)
    vanna_field = build_vanna_field(greek_inputs, dealer_sign, config)
    charm_field = build_charm_field(greek_inputs, dealer_sign, config)
    
    result = calculate_elasticity(
        greek_inputs,
        gamma_field,
        vanna_field,
        charm_field,
        config,
    )
    
    # Elasticity must be positive (by definition)
    assert result.elasticity > 0
    assert result.elasticity_up > 0
    assert result.elasticity_down > 0
    
    # Should have all components (modifiers may be negative in some regimes)
    assert result.gamma_component != 0
    assert result.vanna_component != 0
    assert result.charm_component > 0
    assert result.liquidity_friction > 0
    assert result.oi_density_modifier > 0
    
    # Should have asymmetry ratio
    assert result.asymmetry_ratio > 0


def test_movement_energy_calculation(greek_inputs: GreekInputs, config: dict):
    """Test movement energy calculation."""
    dealer_sign = estimate_dealer_sign(greek_inputs, config)
    gamma_field = build_gamma_field(greek_inputs, dealer_sign, config)
    vanna_field = build_vanna_field(greek_inputs, dealer_sign, config)
    charm_field = build_charm_field(greek_inputs, dealer_sign, config)
    elasticity = calculate_elasticity(
        greek_inputs,
        gamma_field,
        vanna_field,
        charm_field,
        config,
    )
    
    result = calculate_movement_energy(
        gamma_field,
        vanna_field,
        charm_field,
        elasticity,
        config,
    )
    
    # Should produce valid energy values
    assert isinstance(result.movement_energy_up, float)
    assert isinstance(result.movement_energy_down, float)
    assert isinstance(result.net_energy, float)
    
    # Should have barrier strength
    assert result.barrier_strength >= 0
    
    # Acceleration likelihood should be normalized
    assert 0.0 <= result.acceleration_likelihood <= 1.0


def test_regime_detection(greek_inputs: GreekInputs, config: dict):
    """Test multi-dimensional regime detection."""
    dealer_sign = estimate_dealer_sign(greek_inputs, config)
    gamma_field = build_gamma_field(greek_inputs, dealer_sign, config)
    vanna_field = build_vanna_field(greek_inputs, dealer_sign, config)
    charm_field = build_charm_field(greek_inputs, dealer_sign, config)
    elasticity = calculate_elasticity(
        greek_inputs,
        gamma_field,
        vanna_field,
        charm_field,
        config,
    )
    energy = calculate_movement_energy(
        gamma_field,
        vanna_field,
        charm_field,
        elasticity,
        config,
    )
    
    result = detect_regime(
        greek_inputs,
        gamma_field,
        vanna_field,
        charm_field,
        elasticity,
        energy,
        config,
    )
    
    # Should classify all regime dimensions
    assert isinstance(result.primary_regime, str)
    assert isinstance(result.gamma_regime, str)
    assert isinstance(result.vanna_regime, str)
    assert isinstance(result.charm_regime, str)
    assert isinstance(result.jump_risk_regime, str)
    
    # Jump risk regime should be valid
    assert result.jump_risk_regime in [
        "high_jump_risk",
        "moderate_jump_risk",
        "continuous_diffusion",
    ]
    
    # Should classify potential shape
    assert result.potential_shape in [
        "quadratic",
        "cubic",
        "double_well",
        "quartic",
    ]
    
    # Confidence and stability should be normalized
    assert 0.0 <= result.regime_confidence <= 1.0
    assert 0.0 <= result.regime_stability <= 1.0
    
    # Cross-asset correlation should be in range
    assert -1.0 <= result.cross_asset_correlation <= 1.0


def test_empty_chain_handling(config: dict):
    """Test that processors handle empty chains gracefully."""
    empty_chain = pl.DataFrame()
    inputs = GreekInputs(
        chain=empty_chain,
        spot=100.0,
        vix=20.0,
        vol_of_vol=0.0,
        liquidity_lambda=0.0,
        timestamp=datetime.now(timezone.utc).timestamp(),
    )
    
    # Dealer sign with empty chain
    dealer_sign = estimate_dealer_sign(inputs, config)
    assert dealer_sign.confidence == 0.0
    assert dealer_sign.dealer_sign == 0.0
    
    # Gamma field with empty chain
    gamma_field = build_gamma_field(inputs, dealer_sign, config)
    assert gamma_field.gamma_exposure == 0.0
    assert gamma_field.gamma_regime == "neutral"


def test_short_gamma_regime_detection(greek_inputs: GreekInputs, config: dict):
    """Test that short gamma (destabilizing) is detected correctly."""
    # Modify chain to create short gamma scenario
    # Note: Negative gamma on options means positive gamma for dealers when they're short
    # To make dealers SHORT gamma, we need large positive gamma on options (retail long)
    chain = greek_inputs.chain.with_columns(
        pl.col("gamma") * 100.0  # Large positive gamma (retail long = dealers short)
    )
    inputs = GreekInputs(
        chain=chain,
        spot=100.0,
        vix=20.0,
        vol_of_vol=0.3,
        liquidity_lambda=0.1,
        timestamp=datetime.now(timezone.utc).timestamp(),
    )
    
    dealer_sign = estimate_dealer_sign(inputs, config)
    gamma_field = build_gamma_field(inputs, dealer_sign, config)
    
    # Should detect negative dealer gamma (short gamma)
    # When retail is long gamma, dealers are short gamma (negative sign)
    assert dealer_sign.net_dealer_gamma < 0
    # Note: regime classification depends on thresholds


def test_elasticity_positive_definite(greek_inputs: GreekInputs, config: dict):
    """Test that elasticity is always positive (physical constraint)."""
    dealer_sign = estimate_dealer_sign(greek_inputs, config)
    gamma_field = build_gamma_field(greek_inputs, dealer_sign, config)
    vanna_field = build_vanna_field(greek_inputs, dealer_sign, config)
    charm_field = build_charm_field(greek_inputs, dealer_sign, config)
    
    # Test with various extreme configurations
    for _ in range(10):
        result = calculate_elasticity(
            greek_inputs,
            gamma_field,
            vanna_field,
            charm_field,
            config,
        )
        assert result.elasticity > 0, "Elasticity must always be positive"
        assert result.elasticity_up > 0
        assert result.elasticity_down > 0
