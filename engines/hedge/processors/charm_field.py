from __future__ import annotations

"""Charm field construction with time decay dynamics."""

import polars as pl

from engines.hedge.models import CharmFieldOutput, DealerSignOutput, GreekInputs


def build_charm_field(
    inputs: GreekInputs,
    dealer_sign: DealerSignOutput,
    config: dict,
) -> CharmFieldOutput:
    """
    Build charm decay field representing time-decay-driven delta changes.
    
    Charm (∂Δ/∂t) describes how delta decays with time:
    - For dealers: charm changes their delta hedging needs over time
    - Creates a "drift" in hedge pressure independent of price movement
    - Accelerates near expiration
    
    This acts as a time-dependent force field that modifies elasticity.
    
    Args:
        inputs: Raw Greek inputs with time-to-expiry info
        dealer_sign: Dealer positioning estimate
        config: Configuration parameters
        
    Returns:
        CharmFieldOutput with decay-driven pressure dynamics
    """
    chain = inputs.chain
    spot = inputs.spot
    
    if chain.is_empty():
        return CharmFieldOutput(
            charm_exposure=0.0,
            charm_drift_rate=0.0,
            time_decay_pressure=0.0,
            charm_regime="neutral",
            decay_acceleration=0.0,
        )
    
    # Charm exposure from dealer sign
    charm_exposure = dealer_sign.net_dealer_charm
    
    # Strike-weighted charm field
    decay_rate = config.get("strike_decay_rate", 0.05)
    chain = chain.with_columns(
        (pl.lit(-decay_rate) * (pl.col("strike") - spot).abs() / spot).exp().alias("strike_weight")
    )
    
    if "charm" not in chain.columns or "open_interest" not in chain.columns:
        return CharmFieldOutput(
            charm_exposure=0.0,
            charm_drift_rate=0.0,
            time_decay_pressure=0.0,
            charm_regime="neutral",
            decay_acceleration=0.0,
        )
    
    chain = chain.with_columns(
        (pl.col("charm") * pl.col("open_interest") * pl.col("strike_weight")).alias("weighted_charm")
    )
    
    # Time decay pressure (aggregate charm effect)
    time_decay_pressure = float(chain["weighted_charm"].sum())
    
    # Charm drift rate: how fast is dealer delta changing due to time?
    # This is essentially charm exposure normalized by time
    # Assume 1 day time step for normalization
    charm_drift_rate = charm_exposure / 1.0  # per day
    
    # Decay acceleration: if near expiration, charm accelerates
    # Check if we have days_to_expiry column
    if "days_to_expiry" in chain.columns:
        avg_dte = float(chain["days_to_expiry"].mean())
        # Acceleration increases as DTE approaches zero
        # Using inverse square to model gamma/charm explosion near expiry
        if avg_dte > 0:
            decay_acceleration = float(1.0 / (avg_dte**0.5))
        else:
            decay_acceleration = 10.0  # Max acceleration at expiry
    else:
        # Default assumption: 30 DTE average
        decay_acceleration = 1.0 / (30.0**0.5)
    
    # Charm regime classification
    charm_magnitude = abs(charm_exposure)
    charm_high_threshold = config.get("charm_high_threshold", 1e6)
    charm_decay_threshold = config.get("charm_decay_threshold", 5e5)
    
    if charm_magnitude > charm_high_threshold and decay_acceleration > 0.5:
        charm_regime = "high_charm_decay_acceleration"
    elif charm_magnitude > charm_decay_threshold:
        charm_regime = "charm_decay_dominant"
    else:
        charm_regime = "neutral"
    
    metadata = {
        "avg_days_to_expiry": float(chain["days_to_expiry"].mean() if "days_to_expiry" in chain.columns else 30.0),
        "decay_acceleration_factor": float(decay_acceleration),
        "charm_magnitude": float(charm_magnitude),
    }
    
    return CharmFieldOutput(
        charm_exposure=charm_exposure,
        charm_drift_rate=charm_drift_rate,
        time_decay_pressure=time_decay_pressure,
        charm_regime=charm_regime,
        decay_acceleration=decay_acceleration,
        metadata=metadata,
    )
