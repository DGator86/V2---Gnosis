"""
Microstructure Features - Order Flow and Trade Dynamics
Based on: https://github.com/neurotrader888/microstructure-features

Key concepts:
- Order Flow Imbalance (OFI): Buy volume - Sell volume
- Trade Intensity: Rate of trades per time unit
- Effective Spread: Cost of immediate execution
- Price Impact: How much volume moves price
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class MicrostructureFeatures:
    """Container for microstructure feature calculations."""
    
    order_flow_imbalance: pd.Series
    """Net buying pressure (buy volume - sell volume)."""
    
    trade_intensity: pd.Series
    """Number of trades per time window."""
    
    effective_spread: pd.Series
    """Realized spread from mid-price."""
    
    price_impact: pd.Series
    """Price change per unit volume."""
    
    kyle_lambda: pd.Series
    """Kyle's lambda (price impact coefficient)."""
    
    roll_spread: pd.Series
    """Roll's spread estimator from serial covariance."""


def compute_order_flow(
    ohlcv: pd.DataFrame,
    tick_rule: str = 'tick',
    window: int = 20,
) -> MicrostructureFeatures:
    """
    Compute microstructure features from OHLCV data.
    
    Args:
        ohlcv: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
        tick_rule: Method to classify trades ('tick', 'quote', 'lr')
        window: Rolling window for some features
    
    Returns:
        MicrostructureFeatures object
    """
    # Classify trades as buyer/seller initiated
    if tick_rule == 'tick':
        # Tick rule: compare to previous price
        buy_volume = ohlcv['volume'] * (ohlcv['close'] > ohlcv['close'].shift(1))
        sell_volume = ohlcv['volume'] * (ohlcv['close'] < ohlcv['close'].shift(1))
    elif tick_rule == 'quote':
        # Quote rule: position in bid-ask spread
        mid = (ohlcv['high'] + ohlcv['low']) / 2
        buy_volume = ohlcv['volume'] * (ohlcv['close'] > mid)
        sell_volume = ohlcv['volume'] * (ohlcv['close'] < mid)
    else:
        # LR rule: Lee-Ready algorithm
        price_change = ohlcv['close'].diff()
        mid = (ohlcv['high'] + ohlcv['low']) / 2
        above_mid = ohlcv['close'] > mid
        
        buy_volume = ohlcv['volume'] * (
            (price_change > 0) | ((price_change == 0) & above_mid)
        )
        sell_volume = ohlcv['volume'] * (
            (price_change < 0) | ((price_change == 0) & ~above_mid)
        )
    
    # Order Flow Imbalance
    ofi = buy_volume - sell_volume
    
    # Trade Intensity (count of non-zero volume bars)
    trade_intensity = (ohlcv['volume'] > 0).rolling(window).sum()
    
    # Effective Spread
    mid_price = (ohlcv['high'] + ohlcv['low']) / 2
    effective_spread = 2 * abs(ohlcv['close'] - mid_price) / mid_price
    
    # Price Impact: price change per unit volume
    price_change = ohlcv['close'].diff()
    volume_normalized = ohlcv['volume'] / ohlcv['volume'].rolling(window).mean()
    price_impact = price_change / (volume_normalized + 1e-9)
    
    # Kyle's Lambda: cov(Δp, ofi) / var(ofi)
    kyle_lambda = _compute_kyle_lambda(price_change, ofi, window)
    
    # Roll's Spread: 2 * sqrt(-cov(Δp_t, Δp_{t-1}))
    roll_spread = _compute_roll_spread(price_change, window)
    
    return MicrostructureFeatures(
        order_flow_imbalance=ofi,
        trade_intensity=trade_intensity,
        effective_spread=effective_spread,
        price_impact=price_impact,
        kyle_lambda=kyle_lambda,
        roll_spread=roll_spread,
    )


def _compute_kyle_lambda(
    price_change: pd.Series,
    ofi: pd.Series,
    window: int,
) -> pd.Series:
    """Kyle's lambda: price impact of order flow."""
    # Rolling covariance and variance
    cov = price_change.rolling(window).cov(ofi)
    var = ofi.rolling(window).var()
    
    lambda_series = cov / (var + 1e-9)
    return lambda_series


def _compute_roll_spread(
    price_change: pd.Series,
    window: int,
) -> pd.Series:
    """Roll's spread estimator."""
    # Serial covariance
    serial_cov = price_change.rolling(window).cov(price_change.shift(1))
    
    # Spread = 2 * sqrt(-cov)
    spread = 2 * np.sqrt(np.maximum(-serial_cov, 0))
    return spread


# Example
if __name__ == "__main__":
    np.random.seed(42)
    n = 500
    dates = pd.date_range('2024-01-01', periods=n, freq='1min')
    
    price = 100 + np.cumsum(np.random.randn(n) * 0.01)
    ohlcv = pd.DataFrame({
        'open': price,
        'high': price + np.abs(np.random.randn(n) * 0.05),
        'low': price - np.abs(np.random.randn(n) * 0.05),
        'close': price + np.random.randn(n) * 0.02,
        'volume': np.abs(np.random.randn(n) * 100000 + 500000),
    }, index=dates)
    
    features = compute_order_flow(ohlcv)
    
    print(f"Mean OFI: {features.order_flow_imbalance.mean():.0f}")
    print(f"Mean Kyle's Lambda: {features.kyle_lambda.mean():.6f}")
    print(f"Mean Effective Spread: {features.effective_spread.mean():.4f}")
