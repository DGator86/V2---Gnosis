"""
Liquidity & Dark Pool Engine
Computes Amihud illiquidity, Kyle's λ, VPOC, zones, dark pool ratio, and liquidity trend.
"""

import numpy as np
import pandas as pd
from typing import List, Optional
from datetime import datetime
from ..schemas.bars import Bar
from ..schemas.features import LiquidityFields


def compute_liquidity_fields(
    symbol: str,
    bars: List[Bar],
    dark_pool_df: Optional[pd.DataFrame] = None
) -> LiquidityFields:
    """
    Compute Amihud, Kyle's λ, VPOC, zones[], dark pool ratio, and liquidity_trend.
    
    Parameters
    ----------
    symbol : str
        Ticker symbol
    bars : list[Bar]
        Recent price bars
    dark_pool_df : pd.DataFrame, optional
        Dark pool data with columns ['off_exchange_vol', 'total_vol']
        
    Returns
    -------
    LiquidityFields
        Computed liquidity metrics
    """
    if not bars or len(bars) < 2:
        return LiquidityFields(
            ts=bars[0].ts if bars else datetime.now(),
            symbol=symbol,
            amihud=0.0,
            kyle_lambda=0.0,
            vpoc=0.0,
            zones=[],
            dark_pool_ratio=None,
            liquidity_trend="neutral"
        )
    
    # Extract arrays
    close = np.array([b.close for b in bars], dtype=float)
    volume = np.array([b.volume for b in bars], dtype=float)
    
    # Compute returns
    ret = np.diff(close) / close[:-1]
    abs_ret = np.abs(ret)
    
    # Amihud illiquidity: |r_t| / Vol_t
    dollar_vol = close[:-1] * volume[1:]
    dollar_vol = np.maximum(dollar_vol, 1.0)  # avoid division by zero
    amihud_raw = abs_ret / dollar_vol
    amihud = float(np.mean(amihud_raw))
    
    # Kyle's λ: price impact per unit volume
    # Proxy: slope of |ΔP| vs sqrt(volume)
    sqrt_vol = np.sqrt(volume[1:])
    if len(abs_ret) > 10 and sqrt_vol.std() > 0:
        # Simple linear regression slope
        kyle_lambda = float(np.cov(abs_ret, sqrt_vol)[0, 1] / np.var(sqrt_vol))
    else:
        kyle_lambda = float(np.mean(abs_ret / (sqrt_vol + 1e-9)))
    
    # Volume Profile: VPOC and zones
    # Approximate with price percentiles weighted by volume
    vpoc = float(np.average(close, weights=volume))
    
    # Key zones: volume-weighted percentiles
    zones = [
        float(np.percentile(close, 10)),
        float(np.percentile(close, 25)),
        float(vpoc),
        float(np.percentile(close, 75)),
        float(np.percentile(close, 90))
    ]
    
    # Dark pool ratio
    dark_pool_ratio = None
    if dark_pool_df is not None and len(dark_pool_df) > 0:
        off_ex_vol = dark_pool_df['off_exchange_vol'].sum()
        total_vol = dark_pool_df['total_vol'].sum()
        if total_vol > 0:
            dark_pool_ratio = float(off_ex_vol / total_vol)
    
    # Liquidity trend: compare recent Kyle's λ to longer-term average
    # Tightening = increasing λ (worse liquidity)
    # Loosening = decreasing λ (better liquidity)
    if len(bars) > 40:
        recent_bars = bars[-20:]
        recent_close = np.array([b.close for b in recent_bars])
        recent_volume = np.array([b.volume for b in recent_bars])
        recent_ret = np.abs(np.diff(recent_close) / recent_close[:-1])
        recent_sqrt_vol = np.sqrt(recent_volume[1:])
        
        if recent_sqrt_vol.std() > 0:
            recent_lambda = np.mean(recent_ret / (recent_sqrt_vol + 1e-9))
            # Compare to overall average
            if recent_lambda > kyle_lambda * 1.2:
                liquidity_trend = "tightening"
            elif recent_lambda < kyle_lambda * 0.8:
                liquidity_trend = "loosening"
            else:
                liquidity_trend = "neutral"
        else:
            liquidity_trend = "neutral"
    else:
        liquidity_trend = "neutral"
    
    return LiquidityFields(
        ts=bars[-1].ts,
        symbol=symbol,
        amihud=amihud,
        kyle_lambda=kyle_lambda,
        vpoc=vpoc,
        zones=zones,
        dark_pool_ratio=dark_pool_ratio,
        liquidity_trend=liquidity_trend
    )
