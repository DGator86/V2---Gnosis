"""
Volume Spread Analysis (VSA) Implementation
Based on: https://github.com/neurotrader888/VSA

VSA identifies supply/demand imbalances through the relationship between
volume and price spread. Key concepts:
- High volume + narrow spread = absorption (potential reversal)
- High volume + wide spread = distribution/accumulation
- Climax bars indicate exhaustion points
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class VSASignals:
    """Container for VSA analysis results."""
    
    vsa_score: pd.Series
    """VSA score: volume_ratio / spread_ratio. High values indicate absorption."""
    
    volume_ratio: pd.Series
    """Current volume / rolling mean volume."""
    
    spread_ratio: pd.Series
    """Current spread / rolling mean spread."""
    
    climax_bar: pd.Series
    """Boolean series: True for potential climax/exhaustion bars."""
    
    no_supply: pd.Series
    """Boolean series: True for no supply bars (bullish)."""
    
    no_demand: pd.Series
    """Boolean series: True for no demand bars (bearish)."""
    
    effort_vs_result: pd.Series
    """Effort (volume) vs Result (spread). Negative = divergence."""


def compute_vsa(
    ohlcv: pd.DataFrame,
    window: int = 50,
    climax_vol_threshold: float = 2.0,
    climax_spread_threshold: float = 1.5,
    no_supply_vol_threshold: float = 0.5,
    no_demand_vol_threshold: float = 0.5,
) -> VSASignals:
    """
    Compute Volume Spread Analysis signals.
    
    Args:
        ohlcv: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
        window: Lookback window for rolling statistics
        climax_vol_threshold: Volume ratio threshold for climax identification
        climax_spread_threshold: Spread ratio threshold for climax identification
        no_supply_vol_threshold: Max volume ratio for no supply
        no_demand_vol_threshold: Max volume ratio for no demand
    
    Returns:
        VSASignals object with all computed signals
    
    Example:
        >>> signals = compute_vsa(ohlcv_data, window=50)
        >>> # Identify climax selling (potential bottom)
        >>> climax_sell = signals.climax_bar & (ohlcv_data['close'] < ohlcv_data['open'])
        >>> # Identify no supply (bullish continuation)
        >>> bullish = signals.no_supply & (ohlcv_data['close'] > ohlcv_data['open'])
    """
    # Validate input
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    missing = [col for col in required_cols if col not in ohlcv.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    if len(ohlcv) < window:
        raise ValueError(f"Insufficient data: need at least {window} bars")
    
    # Calculate spread (range)
    spread = (ohlcv['high'] - ohlcv['low']).replace(0, np.nan)
    
    # Calculate volume ratios
    volume_ma = ohlcv['volume'].rolling(window=window, min_periods=1).mean()
    volume_ratio = ohlcv['volume'] / volume_ma.replace(0, 1)
    
    # Calculate spread ratios
    spread_ma = spread.rolling(window=window, min_periods=1).mean()
    spread_ratio = spread / spread_ma.replace(0, 1)
    
    # VSA Score: high score = high volume with narrow spread (absorption)
    vsa_score = volume_ratio / (spread_ratio + 1e-9)
    
    # Climax bars: ultra-high volume with wide spread (exhaustion)
    climax_bar = (volume_ratio > climax_vol_threshold) & (spread_ratio > climax_spread_threshold)
    
    # No supply: up close on low volume and narrow spread (bullish)
    close_position = (ohlcv['close'] - ohlcv['low']) / (spread + 1e-9)
    no_supply = (
        (volume_ratio < no_supply_vol_threshold) &
        (spread_ratio < 1.0) &
        (close_position > 0.7) &
        (ohlcv['close'] > ohlcv['open'])
    )
    
    # No demand: down close on low volume and narrow spread (bearish)
    no_demand = (
        (volume_ratio < no_demand_vol_threshold) &
        (spread_ratio < 1.0) &
        (close_position < 0.3) &
        (ohlcv['close'] < ohlcv['open'])
    )
    
    # Effort vs Result: volume should correlate with spread
    # Negative values indicate divergence (high effort, low result)
    effort_vs_result = volume_ratio - spread_ratio
    
    return VSASignals(
        vsa_score=vsa_score,
        volume_ratio=volume_ratio,
        spread_ratio=spread_ratio,
        climax_bar=climax_bar,
        no_supply=no_supply,
        no_demand=no_demand,
        effort_vs_result=effort_vs_result,
    )


def identify_absorption(
    ohlcv: pd.DataFrame,
    vsa_signals: VSASignals,
    vsa_threshold: float = 3.0,
) -> pd.Series:
    """
    Identify absorption bars where smart money is accumulating/distributing.
    
    Absorption characteristics:
    - Very high volume (professional activity)
    - Narrow spread (price doesn't move despite volume)
    - Typically occurs at support/resistance
    
    Args:
        ohlcv: OHLCV DataFrame
        vsa_signals: Output from compute_vsa()
        vsa_threshold: Minimum VSA score for absorption
    
    Returns:
        Boolean Series indicating absorption bars
    """
    absorption = vsa_signals.vsa_score > vsa_threshold
    return absorption


def identify_stopping_volume(
    ohlcv: pd.DataFrame,
    vsa_signals: VSASignals,
    volume_threshold: float = 2.0,
) -> Tuple[pd.Series, pd.Series]:
    """
    Identify stopping volume - high volume that stops a price move.
    
    Args:
        ohlcv: OHLCV DataFrame
        vsa_signals: Output from compute_vsa()
        volume_threshold: Minimum volume ratio for stopping volume
    
    Returns:
        Tuple of (bullish_stopping, bearish_stopping) boolean Series
    """
    high_volume = vsa_signals.volume_ratio > volume_threshold
    
    # Bullish stopping: high volume on down bar that closes off lows
    close_position = (ohlcv['close'] - ohlcv['low']) / (ohlcv['high'] - ohlcv['low'] + 1e-9)
    bullish_stopping = (
        high_volume &
        (ohlcv['close'] < ohlcv['open']) &
        (close_position > 0.5)
    )
    
    # Bearish stopping: high volume on up bar that closes off highs
    bearish_stopping = (
        high_volume &
        (ohlcv['close'] > ohlcv['open']) &
        (close_position < 0.5)
    )
    
    return bullish_stopping, bearish_stopping


def compute_vsa_divergence(
    ohlcv: pd.DataFrame,
    vsa_signals: VSASignals,
    lookback: int = 5,
) -> pd.Series:
    """
    Detect VSA divergence: price makes new high/low but volume doesn't confirm.
    
    Args:
        ohlcv: OHLCV DataFrame
        vsa_signals: Output from compute_vsa()
        lookback: Bars to look back for divergence detection
    
    Returns:
        Series with values: 1 (bullish divergence), -1 (bearish), 0 (none)
    """
    # Price trends
    price_high = ohlcv['high'].rolling(lookback).max()
    price_low = ohlcv['low'].rolling(lookback).min()
    
    # Volume trends
    volume_high = vsa_signals.volume_ratio.rolling(lookback).max()
    volume_low = vsa_signals.volume_ratio.rolling(lookback).min()
    
    # Bullish divergence: new low in price but volume not confirming
    bullish_div = (
        (ohlcv['low'] == price_low) &
        (vsa_signals.volume_ratio < volume_high * 0.7)
    )
    
    # Bearish divergence: new high in price but volume not confirming
    bearish_div = (
        (ohlcv['high'] == price_high) &
        (vsa_signals.volume_ratio < volume_high * 0.7)
    )
    
    divergence = pd.Series(0, index=ohlcv.index)
    divergence[bullish_div] = 1
    divergence[bearish_div] = -1
    
    return divergence


# Example usage and testing
if __name__ == "__main__":
    # Generate sample data
    np.random.seed(42)
    n = 200
    dates = pd.date_range('2024-01-01', periods=n, freq='1h')
    
    price = 100 + np.cumsum(np.random.randn(n) * 0.5)
    ohlcv_sample = pd.DataFrame({
        'open': price + np.random.randn(n) * 0.1,
        'high': price + np.abs(np.random.randn(n) * 0.3),
        'low': price - np.abs(np.random.randn(n) * 0.3),
        'close': price + np.random.randn(n) * 0.1,
        'volume': np.abs(np.random.randn(n) * 1000000 + 5000000),
    }, index=dates)
    
    # Ensure OHLC relationship is valid
    ohlcv_sample['high'] = ohlcv_sample[['open', 'close', 'high']].max(axis=1)
    ohlcv_sample['low'] = ohlcv_sample[['open', 'close', 'low']].min(axis=1)
    
    # Compute VSA signals
    signals = compute_vsa(ohlcv_sample, window=50)
    
    print("VSA Analysis Results:")
    print(f"Mean VSA Score: {signals.vsa_score.mean():.2f}")
    print(f"Climax Bars: {signals.climax_bar.sum()}")
    print(f"No Supply Bars: {signals.no_supply.sum()}")
    print(f"No Demand Bars: {signals.no_demand.sum()}")
    
    # Identify special patterns
    absorption = identify_absorption(ohlcv_sample, signals)
    print(f"Absorption Bars: {absorption.sum()}")
    
    bullish_stop, bearish_stop = identify_stopping_volume(ohlcv_sample, signals)
    print(f"Bullish Stopping Volume: {bullish_stop.sum()}")
    print(f"Bearish Stopping Volume: {bearish_stop.sum()}")
    
    divergence = compute_vsa_divergence(ohlcv_sample, signals)
    print(f"Bullish Divergences: {(divergence == 1).sum()}")
    print(f"Bearish Divergences: {(divergence == -1).sum()}")
