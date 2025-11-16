from __future__ import annotations

"""Dealer sign estimation with OI-weighted positioning analysis."""

import polars as pl

from engines.hedge.models import DealerSignOutput, GreekInputs


def estimate_dealer_sign(inputs: GreekInputs, config: dict) -> DealerSignOutput:
    """
    Estimate dealer positioning sign based on option flow structure.
    
    Dealers are typically:
    - SHORT gamma when retail/institutions are LONG (puts/calls for protection)
    - LONG gamma when market-makers hedge large directional flows
    
    This uses OI distribution, volume patterns, and put/call structure
    to infer dealer positioning.
    
    Args:
        inputs: Raw Greek inputs with chain data
        config: Configuration parameters
        
    Returns:
        DealerSignOutput with positioning estimates
    """
    chain = inputs.chain
    spot = inputs.spot
    
    if chain.is_empty():
        return DealerSignOutput(
            net_dealer_gamma=0.0,
            net_dealer_vanna=0.0,
            net_dealer_charm=0.0,
            dealer_sign=0.0,
            confidence=0.0,
            oi_weighted_strike_center=spot,
        )
    
    # Required columns check
    required = {"strike", "gamma", "vanna", "charm", "open_interest", "option_type"}
    if not required.issubset(set(chain.columns)):
        return DealerSignOutput(
            net_dealer_gamma=0.0,
            net_dealer_vanna=0.0,
            net_dealer_charm=0.0,
            dealer_sign=0.0,
            confidence=0.0,
            oi_weighted_strike_center=spot,
        )
    
    # Separate calls and puts
    calls = chain.filter(pl.col("option_type") == "C")
    puts = chain.filter(pl.col("option_type") == "P")
    
    # OI-weighted Greek exposures
    # Assumption: Dealers are SHORT retail options (retail buys, dealers sell)
    # So we flip the sign - if retail is long gamma, dealers are short gamma
    
    # Call gamma exposure (dealers short calls = negative gamma for dealers)
    call_gamma_exp = -(calls["gamma"] * calls["open_interest"]).sum() if not calls.is_empty() else 0.0
    
    # Put gamma exposure (dealers short puts = negative gamma for dealers below spot)
    # But puts have negative gamma, so short puts = positive gamma for dealers
    put_gamma_exp = -(puts["gamma"] * puts["open_interest"]).sum() if not puts.is_empty() else 0.0
    
    net_dealer_gamma = float(call_gamma_exp + put_gamma_exp)
    
    # Vanna exposure (OI-weighted)
    call_vanna_exp = -(calls["vanna"] * calls["open_interest"]).sum() if not calls.is_empty() else 0.0
    put_vanna_exp = -(puts["vanna"] * puts["open_interest"]).sum() if not puts.is_empty() else 0.0
    net_dealer_vanna = float(call_vanna_exp + put_vanna_exp)
    
    # Charm exposure (OI-weighted)
    call_charm_exp = -(calls["charm"] * calls["open_interest"]).sum() if not calls.is_empty() else 0.0
    put_charm_exp = -(puts["charm"] * puts["open_interest"]).sum() if not puts.is_empty() else 0.0
    net_dealer_charm = float(call_charm_exp + put_charm_exp)
    
    # Calculate OI-weighted strike center
    total_oi = chain["open_interest"].sum()
    if total_oi > 0:
        oi_weighted_strike = float((chain["strike"] * chain["open_interest"]).sum() / total_oi)
    else:
        oi_weighted_strike = spot
    
    # Dealer sign: normalize net gamma to [-1, 1]
    # Negative gamma = short gamma = destabilizing
    # Positive gamma = long gamma = stabilizing
    gamma_magnitude = abs(net_dealer_gamma)
    gamma_threshold = config.get("gamma_sign_threshold", 1e6)
    
    if gamma_magnitude > gamma_threshold:
        dealer_sign = float(net_dealer_gamma / gamma_magnitude)
    else:
        dealer_sign = 0.0
    
    # Confidence based on OI concentration and data quality
    total_strikes = len(chain)
    confidence = min(1.0, total_strikes / config.get("min_strikes_for_confidence", 50))
    
    # Additional confidence from OI concentration
    if total_oi > config.get("min_oi_threshold", 1000):
        confidence = min(1.0, confidence * 1.2)
    
    # Metadata
    metadata = {
        "call_gamma_exposure": float(call_gamma_exp),
        "put_gamma_exposure": float(put_gamma_exp),
        "total_oi": float(total_oi),
        "num_strikes": float(total_strikes),
        "strike_distance_from_spot": abs(oi_weighted_strike - spot) / spot,
    }
    
    return DealerSignOutput(
        net_dealer_gamma=net_dealer_gamma,
        net_dealer_vanna=net_dealer_vanna,
        net_dealer_charm=net_dealer_charm,
        dealer_sign=dealer_sign,
        confidence=confidence,
        oi_weighted_strike_center=oi_weighted_strike,
        metadata=metadata,
    )
