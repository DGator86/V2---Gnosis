from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from ..schemas.base import LiquidityPast, LiquidityPresent, LiquidityFuture, LiquidityFeatures, Zone

def _amihud(df: pd.DataFrame) -> float:
    """Calculate Amihud illiquidity measure: |ΔP| / $Vol"""
    if len(df) < 2: 
        return np.nan
    df = df.sort_values("t_event")
    ret = df["price"].pct_change().abs()
    # Filter out zero dollar volumes to avoid division by zero
    valid_mask = df["dollar_volume"] > 0
    if not valid_mask.any():
        return np.nan
    amihud = (ret[valid_mask] / df["dollar_volume"][valid_mask]).median()
    return float(amihud) if np.isfinite(amihud) else np.nan

def _kyle_lambda(df: pd.DataFrame) -> float:
    """Calculate Kyle's lambda: price impact per unit of signed volume"""
    if len(df) < 2: 
        return np.nan
    df = df.sort_values("t_event")
    ret = df["price"].pct_change()
    # Use next return sign for signed volume (order flow)
    signed_vol = np.sign(ret.shift(-1)) * df["dollar_volume"]
    num = (ret * signed_vol).sum()
    den = (signed_vol ** 2).sum()
    return float(abs(num / den)) if den != 0 else np.nan

def _volume_profile_zones(df: pd.DataFrame, price_col="price", bins=20) -> list[Zone]:
    """Identify high-volume price zones from volume profile"""
    if df.empty or "volume" not in df.columns: 
        return []
    
    # Filter valid data
    valid_df = df[df["volume"] > 0].copy()
    if valid_df.empty:
        return []
    
    try:
        hist, edges = np.histogram(valid_df[price_col], bins=bins, weights=valid_df["volume"])
        if hist.sum() == 0:
            return []
        
        # Find peaks above 80th percentile
        threshold = np.percentile(hist[hist > 0], 80) if (hist > 0).any() else 0
        peaks = np.argwhere(hist > threshold).flatten()
        
        zones = []
        for i in peaks:
            lo = float(edges[max(i-1, 0)])
            hi = float(edges[min(i+1, len(edges)-1)])
            zones.append(Zone(lo=lo, hi=hi))
        
        # Merge overlapping zones
        merged_zones = []
        for zone in sorted(zones, key=lambda z: z.lo):
            if merged_zones and zone.lo <= merged_zones[-1].hi:
                merged_zones[-1].hi = max(merged_zones[-1].hi, zone.hi)
            else:
                merged_zones.append(zone)
        
        return merged_zones
    except Exception:
        return []

def compute_liquidity_v0(symbol: str, now: datetime, df: pd.DataFrame) -> LiquidityFeatures:
    """
    Compute liquidity features from recent price/volume data
    
    Args:
        symbol: Trading symbol
        now: Current timestamp
        df: DataFrame with columns: t_event, price, volume, dollar_volume
    """
    df = df.copy()
    
    # Ensure we have dollar_volume
    if "dollar_volume" not in df.columns:
        df["dollar_volume"] = df["price"] * df.get("volume", 0)
    
    # Get last hour window
    window = df[df["t_event"] > now - timedelta(minutes=60)]
    if window.empty:
        window = df.tail(20)  # fallback to last 20 bars
    
    # Compute metrics
    amihud = _amihud(window)
    kyle = _kyle_lambda(window)
    zones = _volume_profile_zones(window)
    
    # Split zones into support (below current) and resistance (above current)
    current_price = window["price"].iloc[-1] if not window.empty else 0
    support_zones = [z for z in zones if z.hi < current_price]
    resistance_zones = [z for z in zones if z.lo > current_price]
    
    # Build feature components
    past = LiquidityPast(
        zones_held=len([z for z in support_zones if z.hi > current_price * 0.995]),
        zones_broken=max(0, len(support_zones) - 2),  # rough estimate
        slippage_err_bps=5.0
    )
    
    present = LiquidityPresent(
        support=support_zones[-2:] if support_zones else [],  # nearest 2 supports
        resistance=resistance_zones[:2] if resistance_zones else [],  # nearest 2 resistances
        amihud=float(amihud) if np.isfinite(amihud) else 0.004,
        lambda_impact=float(kyle) if np.isfinite(kyle) else 1.2,
        conf=0.7 if np.isfinite(amihud) and np.isfinite(kyle) else 0.5
    )
    
    # Identify next magnet (nearest significant zone)
    next_magnet = None
    if resistance_zones:
        next_magnet = float((resistance_zones[0].lo + resistance_zones[0].hi) / 2)
    elif support_zones:
        next_magnet = float((support_zones[-1].lo + support_zones[-1].hi) / 2)
    else:
        next_magnet = current_price
    
    future = LiquidityFuture(
        zone_survival=0.7 if zones else 0.5,
        slippage_cone_bps=[5, 10, 20],
        next_magnet=next_magnet,
        eta_bars=6,
        conf=0.65 if zones else 0.4
    )
    
    return LiquidityFeatures(past=past, present=present, future=future)