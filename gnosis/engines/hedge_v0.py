from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime
from ..schemas.base import HedgePast, HedgePresent, HedgeFuture, HedgeFeatures

def compute_hedge_v0(symbol: str, now: datetime, spot: float, chain: pd.DataFrame) -> HedgeFeatures:
    """
    Calculate dealer positioning pressure from options chain data.
    
    Args:
        symbol: Trading symbol
        now: Current timestamp
        spot: Current underlying spot price
        chain: DataFrame with columns: strike, expiry, iv, delta, gamma, vega, theta, open_interest
    
    Returns:
        HedgeFeatures with gamma/vanna/charm derived metrics
    """
    if chain.empty:
        return HedgeFeatures(
            past=HedgePast(exhaustion_score=0, window_bars=0, method="empty"),
            present=HedgePresent(hedge_force=0, regime="neutral", conf=0, half_life_bars=0),
            future=HedgeFuture(q10=0, q50=0, q90=0, hit_prob_tp1=0.5, eta_bars=0, conf=0)
        )

    # --- Normalize and calculate dollar Greeks ---
    chain = chain.copy()
    chain["moneyness"] = (chain["strike"] - spot) / spot
    
    # Dollar gamma: measure of hedging flow per $ move
    # Multiplied by 100 for contract multiplier, spot^2 for dollar sensitivity
    chain["gamma_dollar"] = chain["gamma"] * chain["open_interest"] * 100 * spot**2
    
    # Dollar vanna: cross-sensitivity between spot and vol
    # Shows how delta changes with IV moves
    chain["vanna_dollar"] = chain["vega"] * chain["open_interest"] * 100 * chain["moneyness"]
    
    # Dollar charm: theta decay's effect on delta
    # Shows how positions drift with time decay
    chain["charm_dollar"] = chain["theta"] * chain["open_interest"] * 100

    # --- Aggregate dealer book exposure ---
    gamma_profile = chain.groupby("strike")["gamma_dollar"].sum()
    vanna_sum = chain["vanna_dollar"].sum()
    charm_sum = chain["charm_dollar"].sum()

    # --- Detect gamma walls (high concentration strikes) ---
    if not gamma_profile.empty:
        wall_strikes = gamma_profile.sort_values(ascending=False).head(3).index.tolist()
        wall_dist = float(min(abs(spot - ws) for ws in wall_strikes)) if wall_strikes else 0.0
    else:
        wall_strikes = []
        wall_dist = 0.0
    
    # --- Calculate net hedge force ---
    gamma_net = gamma_profile.sum()
    
    # Scale gamma to [-1, 1] range using tanh
    # 1e10 is a typical scaling factor for SPY-like instruments
    hedge_force = np.tanh(gamma_net / 1e10)
    
    # Incorporate vanna effect (spot-vol correlation)
    vanna_effect = np.tanh(vanna_sum / 1e9)
    hedge_force = 0.7 * hedge_force + 0.3 * vanna_effect  # Weighted combination

    # --- Determine market regime ---
    abs_force = abs(hedge_force)
    if abs_force < 0.2:
        regime = "pin"  # Low gamma, prices likely to stick
    elif abs_force > 0.5:
        regime = "breakout"  # High gamma, volatile moves expected
    else:
        regime = "neutral"
    
    # --- Calculate confidence based on data quality and force strength ---
    conf = float(min(1.0, 0.5 + abs_force))
    
    # Adjust confidence based on open interest concentration
    oi_concentration = chain["open_interest"].std() / (chain["open_interest"].mean() + 1e-6)
    if oi_concentration > 2:  # High concentration = higher confidence
        conf = min(1.0, conf * 1.2)

    # --- Build feature components ---
    past = HedgePast(
        exhaustion_score=min(1.0, abs(charm_sum) / (1e9 + abs(charm_sum))),
        window_bars=20,
        method="gamma_agg"
    )
    
    present = HedgePresent(
        hedge_force=float(hedge_force),
        regime=regime,
        wall_dist=wall_dist,
        conf=conf,
        half_life_bars=6
    )
    
    # Future probabilities based on current positioning
    # Strong hedge force = directional bias
    # Weak hedge force = mean reversion likely
    hit_prob = 0.5 + 0.3 * hedge_force  # Directional probability
    eta_bars = int(8 - 4 * abs_force)  # Faster resolution with stronger force
    
    future = HedgeFuture(
        q10=-0.3 * (1 + abs_force),  # Wider tails with higher gamma
        q50=0.1 * hedge_force,  # Median shifts with force direction
        q90=0.3 * (1 + abs_force),
        hit_prob_tp1=float(np.clip(hit_prob, 0.1, 0.9)),
        eta_bars=max(1, eta_bars),
        conf=conf * 0.9  # Future less certain than present
    )
    
    return HedgeFeatures(past=past, present=present, future=future)