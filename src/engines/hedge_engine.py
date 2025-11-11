"""
Hedge Engine - Dealer Hedge Pressure Fields
Computes GEX, Vanna, Charm, gamma-flip level, and normalized pressure score.
"""

import numpy as np
from typing import List
from datetime import datetime
from ..schemas.bars import Bar
from ..schemas.options import OptionSnapshot
from ..schemas.features import HedgeFields


def compute_hedge_fields(
    symbol: str,
    options: List[OptionSnapshot],
    bars: List[Bar]
) -> HedgeFields:
    """
    Compute dealer-driven fields (GEX, vanna, charm, gamma flip, pressure_score).
    Vectorized aggregation over strikes/expiries. Returns normalized pressure_score 0..1.
    
    Parameters
    ----------
    symbol : str
        Ticker symbol
    options : list[OptionSnapshot]
        Options chain snapshot
    bars : list[Bar]
        Recent price bars for context
        
    Returns
    -------
    HedgeFields
        Computed hedge pressure fields
    """
    if not options or not bars:
        ts = bars[-1].ts if bars else (options[0].ts if options else datetime.now())
        return HedgeFields(
            ts=ts,
            symbol=symbol,
            gex=0.0,
            vanna=0.0,
            charm=0.0,
            gamma_flip_level=None,
            pressure_score=0.0
        )
    
    # Aggregate options Greeks weighted by OI and mid-price
    gex = 0.0
    vanna_sum = 0.0
    charm_sum = 0.0
    
    for opt in options:
        mid_price = (opt.bid + opt.ask) / 2.0
        oi = opt.open_interest if opt.open_interest else 1.0
        
        # Weight by OI * mid_price
        weight = oi * mid_price
        
        # Aggregate GEX (net gamma exposure)
        # Call gamma is positive for dealers (short calls = negative gamma)
        # Put gamma is positive for dealers (short puts = negative gamma)
        sign = -1.0 if opt.right == "C" else -1.0  # dealers short both
        gex += sign * opt.gamma * weight
        
        # Vanna: sensitivity to spot-vol correlation
        vanna_sum += opt.vega * opt.delta * weight
        
        # Charm: gamma decay with time
        charm_sum += -opt.theta * abs(opt.delta) * weight
    
    # Normalize pressure_score using sigmoid
    # Higher absolute GEX -> higher pressure
    pressure_score = float(1.0 / (1.0 + np.exp(-0.000001 * abs(gex))))
    
    # Estimate gamma flip level (where net gamma crosses zero)
    # Simplified: look for strike where gamma changes sign
    gamma_flip_level = None
    current_price = bars[-1].close
    
    # Find strikes around current price
    strikes_around = [o for o in options if abs(o.strike - current_price) / current_price < 0.05]
    if len(strikes_around) > 1:
        # Use VWAP of strikes weighted by OI as proxy for gamma flip
        total_oi = sum(o.open_interest or 1.0 for o in strikes_around)
        gamma_flip_level = sum(
            o.strike * (o.open_interest or 1.0) / total_oi 
            for o in strikes_around
        )
    
    return HedgeFields(
        ts=bars[-1].ts,
        symbol=symbol,
        gex=float(gex),
        vanna=float(vanna_sum),
        charm=float(charm_sum),
        gamma_flip_level=float(gamma_flip_level) if gamma_flip_level else None,
        pressure_score=pressure_score
    )
