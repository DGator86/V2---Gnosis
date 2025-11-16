from __future__ import annotations

"""Gamma field construction with strike weighting and pin zone detection."""

import polars as pl

from engines.hedge.models import DealerSignOutput, GammaFieldOutput, GreekInputs


def build_gamma_field(
    inputs: GreekInputs,
    dealer_sign: DealerSignOutput,
    config: dict,
) -> GammaFieldOutput:
    """
    Build gamma pressure field with strike-weighted contributions.
    
    Gamma determines dealer hedging behavior:
    - Positive dealer gamma: dealers buy dips, sell rips (stabilizing)
    - Negative dealer gamma: dealers sell dips, buy rips (destabilizing)
    
    The field is weighted by:
    - Distance from spot (closer = stronger)
    - Open interest concentration
    - Dealer positioning sign
    
    Args:
        inputs: Raw Greek inputs
        dealer_sign: Dealer positioning estimate
        config: Configuration parameters
        
    Returns:
        GammaFieldOutput with pressure field vectors
    """
    chain = inputs.chain
    spot = inputs.spot
    
    if chain.is_empty():
        return GammaFieldOutput(
            gamma_exposure=0.0,
            gamma_pressure_up=0.0,
            gamma_pressure_down=0.0,
            gamma_regime="neutral",
            dealer_gamma_sign=0.0,
            strike_weighted_gamma={},
        )
    
    # Strike weighting: exponential decay from spot
    decay_rate = config.get("strike_decay_rate", 0.05)
    chain = chain.with_columns(
        (pl.lit(-decay_rate) * (pl.col("strike") - spot).abs() / spot).exp().alias("strike_weight")
    )
    
    # Weighted gamma exposure by strike
    chain = chain.with_columns(
        (pl.col("gamma") * pl.col("open_interest") * pl.col("strike_weight") * spot).alias("weighted_gamma")
    )
    
    # Total gamma exposure (dealer perspective)
    gamma_exposure = dealer_sign.net_dealer_gamma
    
    # Separate up/down pressure based on strike location
    above_spot = chain.filter(pl.col("strike") > spot)
    below_spot = chain.filter(pl.col("strike") <= spot)
    
    # Gamma pressure interpretation:
    # If dealers are SHORT gamma (negative), they must:
    #   - SELL into rallies (creates resistance up)
    #   - BUY into selloffs (creates support down, but destabilizing)
    # If dealers are LONG gamma (positive), they:
    #   - BUY dips (stabilizing support)
    #   - SELL rips (stabilizing resistance)
    
    gamma_pressure_up = float(above_spot["weighted_gamma"].sum() if not above_spot.is_empty() else 0.0)
    gamma_pressure_down = float(below_spot["weighted_gamma"].sum() if not below_spot.is_empty() else 0.0)
    
    # Adjust pressure by dealer sign
    dealer_gamma_sign = dealer_sign.dealer_sign
    if dealer_gamma_sign < 0:  # Short gamma = destabilizing
        # Negative gamma creates acceleration, not resistance
        gamma_pressure_up *= -1
        gamma_pressure_down *= -1
    
    # Gamma regime classification
    gamma_magnitude = abs(gamma_exposure)
    gamma_squeeze_threshold = config.get("gamma_squeeze_threshold", 1e7)
    gamma_pin_threshold = config.get("gamma_pin_threshold", 5e6)
    
    if dealer_gamma_sign < -0.5 and gamma_magnitude > gamma_squeeze_threshold:
        gamma_regime = "short_gamma_squeeze"
    elif dealer_gamma_sign > 0.5 and gamma_magnitude > gamma_squeeze_threshold:
        gamma_regime = "long_gamma_compression"
    elif gamma_magnitude < gamma_pin_threshold:
        gamma_regime = "low_gamma_expansion"
    else:
        gamma_regime = "neutral"
    
    # Strike-weighted gamma map (for visualization/analysis)
    strike_weighted_gamma = {}
    if "strike" in chain.columns and "weighted_gamma" in chain.columns:
        for row in chain.select(["strike", "weighted_gamma"]).iter_rows():
            strike_weighted_gamma[float(row[0])] = float(row[1])
    
    # Pin zone detection (high OI concentration zones)
    pin_oi_threshold = config.get("pin_oi_threshold", 5000)
    pin_zones = []
    if "strike" in chain.columns and "open_interest" in chain.columns:
        high_oi_strikes = chain.filter(pl.col("open_interest") > pin_oi_threshold)
        if not high_oi_strikes.is_empty():
            strikes = high_oi_strikes["strike"].to_list()
            # Group consecutive strikes into zones
            if strikes:
                zone_start = strikes[0]
                prev_strike = strikes[0]
                for strike in strikes[1:]:
                    if strike - prev_strike > spot * 0.02:  # 2% gap = new zone
                        pin_zones.append((float(zone_start), float(prev_strike)))
                        zone_start = strike
                    prev_strike = strike
                pin_zones.append((float(zone_start), float(prev_strike)))
    
    metadata = {
        "total_strikes": float(len(chain)),
        "atm_gamma": float(chain.filter((pl.col("strike") - spot).abs() < spot * 0.01)["gamma"].sum()),
        "gamma_skew": float(gamma_pressure_up / (abs(gamma_pressure_down) + 1e-9)),
    }
    
    return GammaFieldOutput(
        gamma_exposure=gamma_exposure,
        gamma_pressure_up=gamma_pressure_up,
        gamma_pressure_down=gamma_pressure_down,
        gamma_regime=gamma_regime,
        dealer_gamma_sign=dealer_gamma_sign,
        strike_weighted_gamma=strike_weighted_gamma,
        pin_zones=pin_zones,
        metadata=metadata,
    )
