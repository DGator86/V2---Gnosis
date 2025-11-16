from __future__ import annotations

"""Vanna field construction with volatility sensitivity and shock absorption."""

import polars as pl

from engines.hedge.models import DealerSignOutput, GreekInputs, VannaFieldOutput


def build_vanna_field(
    inputs: GreekInputs,
    dealer_sign: DealerSignOutput,
    config: dict,
) -> VannaFieldOutput:
    """
    Build vanna pressure field with vol sensitivity analysis.
    
    Vanna (∂Δ/∂σ) describes how delta changes with volatility:
    - Positive vanna: rising vol increases delta (more bullish)
    - Negative vanna: rising vol decreases delta (more bearish)
    
    For dealers:
    - If short vanna: rising vol forces MORE delta hedging
    - If long vanna: rising vol reduces delta hedging needs
    
    This creates volatility-dependent elasticity reshaping.
    
    Args:
        inputs: Raw Greek inputs with vol-of-vol
        dealer_sign: Dealer positioning estimate
        config: Configuration parameters
        
    Returns:
        VannaFieldOutput with vol-adjusted pressure vectors
    """
    chain = inputs.chain
    spot = inputs.spot
    vix = inputs.vix or 20.0  # Default VIX if not provided
    vol_of_vol = inputs.vol_of_vol
    
    if chain.is_empty():
        return VannaFieldOutput(
            vanna_exposure=0.0,
            vanna_pressure_up=0.0,
            vanna_pressure_down=0.0,
            vanna_regime="neutral",
            vol_sensitivity=0.0,
            vanna_shock_absorber=1.0,
        )
    
    # Vanna exposure from dealer sign
    vanna_exposure = dealer_sign.net_dealer_vanna
    
    # Strike-weighted vanna field
    decay_rate = config.get("strike_decay_rate", 0.05)
    chain = chain.with_columns(
        (pl.lit(-decay_rate) * (pl.col("strike") - spot).abs() / spot).exp().alias("strike_weight")
    )
    
    if "vanna" in chain.columns and "open_interest" in chain.columns:
        chain = chain.with_columns(
            (pl.col("vanna") * pl.col("open_interest") * pl.col("strike_weight")).alias("weighted_vanna")
        )
    else:
        return VannaFieldOutput(
            vanna_exposure=0.0,
            vanna_pressure_up=0.0,
            vanna_pressure_down=0.0,
            vanna_regime="neutral",
            vol_sensitivity=0.0,
            vanna_shock_absorber=1.0,
        )
    
    # Separate by strike location
    above_spot = chain.filter(pl.col("strike") > spot)
    below_spot = chain.filter(pl.col("strike") <= spot)
    
    vanna_pressure_up = float(above_spot["weighted_vanna"].sum() if not above_spot.is_empty() else 0.0)
    vanna_pressure_down = float(below_spot["weighted_vanna"].sum() if not below_spot.is_empty() else 0.0)
    
    # Volatility sensitivity: how much does vanna exposure change with vol?
    # This is approximately vanna * vol_of_vol
    vol_sensitivity = float(vanna_exposure * vol_of_vol)
    
    # Vanna regime classification
    vanna_magnitude = abs(vanna_exposure)
    vanna_flow_threshold = config.get("vanna_flow_threshold", 1e6)
    vanna_high_threshold = config.get("vanna_high_threshold", 5e6)
    
    if vanna_magnitude > vanna_high_threshold:
        if vix > 25:
            vanna_regime = "high_vanna_high_vol"
        else:
            vanna_regime = "high_vanna_low_vol"
    elif vanna_magnitude > vanna_flow_threshold:
        vanna_regime = "vanna_flow"
    else:
        vanna_regime = "neutral"
    
    # Vanna shock absorber (SWOT fix)
    # During vol spikes, vanna can cause violent delta shifts
    # This dampens extreme vanna influence during high vol-of-vol
    shock_threshold = config.get("vol_of_vol_shock_threshold", 0.5)
    if vol_of_vol > shock_threshold:
        # Reduce vanna influence as vol-of-vol increases
        absorber = 1.0 / (1.0 + (vol_of_vol - shock_threshold) * 2.0)
    else:
        absorber = 1.0
    
    vanna_shock_absorber = float(absorber)
    
    # Apply shock absorber to pressures
    vanna_pressure_up *= vanna_shock_absorber
    vanna_pressure_down *= vanna_shock_absorber
    
    metadata = {
        "vix_level": float(vix),
        "vol_of_vol": float(vol_of_vol),
        "vanna_skew": float(vanna_pressure_up / (abs(vanna_pressure_down) + 1e-9)),
        "shock_absorber_active": float(vanna_shock_absorber < 0.99),
    }
    
    return VannaFieldOutput(
        vanna_exposure=vanna_exposure,
        vanna_pressure_up=vanna_pressure_up,
        vanna_pressure_down=vanna_pressure_down,
        vanna_regime=vanna_regime,
        vol_sensitivity=vol_sensitivity,
        vanna_shock_absorber=vanna_shock_absorber,
        metadata=metadata,
    )
