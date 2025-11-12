"""
Fractal Dimension and Hurst Exponent
Based on: https://github.com/neurotrader888/fast-fractal-research

Hurst exponent H:
- H > 0.5: Trending (persistent)
- H = 0.5: Random walk
- H < 0.5: Mean-reverting (anti-persistent)
"""

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class FractalMetrics:
    """Fractal dimension metrics."""
    
    hurst_exponent: pd.Series
    """Hurst exponent H ∈ [0, 1]."""
    
    fractal_dimension: pd.Series
    """Fractal dimension D = 2 - H."""
    
    regime: pd.Series
    """Market regime: 'trending', 'random', or 'mean_reverting'."""


def compute_hurst_exponent(
    ts: pd.Series,
    window: int = 100,
    max_lag: int = 20,
    method: str = 'rs',
) -> FractalMetrics:
    """
    Compute Hurst exponent using R/S analysis.
    
    Args:
        ts: Time series
        window: Rolling window
        max_lag: Maximum lag for R/S calculation
        method: 'rs' (rescaled range) or 'dfa' (detrended fluctuation)
    
    Returns:
        FractalMetrics
    """
    hurst_values = []
    
    for i in range(window, len(ts) + 1):
        data = ts.iloc[i-window:i].values
        
        if method == 'rs':
            h = _hurst_rs(data, max_lag)
        else:
            h = _hurst_dfa(data, max_lag)
        
        hurst_values.append(h)
    
    hurst_series = pd.Series(hurst_values, index=ts.index[window-1:])
    
    # Fractal dimension
    fractal_dim = 2 - hurst_series
    
    # Regime classification
    regime = pd.Series('random', index=hurst_series.index)
    regime[hurst_series > 0.55] = 'trending'
    regime[hurst_series < 0.45] = 'mean_reverting'
    
    return FractalMetrics(
        hurst_exponent=hurst_series,
        fractal_dimension=fractal_dim,
        regime=regime,
    )


def _hurst_rs(data: np.ndarray, max_lag: int) -> float:
    """Rescaled range (R/S) method."""
    lags = range(2, max_lag + 1)
    rs_values = []
    
    for lag in lags:
        # Split into non-overlapping blocks
        n_blocks = len(data) // lag
        if n_blocks == 0:
            continue
        
        rs_block = []
        for i in range(n_blocks):
            block = data[i*lag:(i+1)*lag]
            
            # Mean-centered cumulative sum
            mean = block.mean()
            y = np.cumsum(block - mean)
            
            # Range
            R = y.max() - y.min()
            
            # Standard deviation
            S = block.std()
            
            if S > 0:
                rs_block.append(R / S)
        
        if len(rs_block) > 0:
            rs_values.append(np.mean(rs_block))
    
    if len(rs_values) < 2:
        return 0.5
    
    # Fit log(R/S) = log(c) + H * log(lag)
    log_lags = np.log(list(lags[:len(rs_values)]))
    log_rs = np.log(rs_values)
    
    # Linear regression
    H = np.polyfit(log_lags, log_rs, 1)[0]
    
    return np.clip(H, 0, 1)


def _hurst_dfa(data: np.ndarray, max_lag: int) -> float:
    """Detrended Fluctuation Analysis method."""
    # Cumulative sum
    y = np.cumsum(data - data.mean())
    
    lags = range(4, max_lag + 1)
    fluct = []
    
    for lag in lags:
        # Divide into segments
        n_seg = len(y) // lag
        if n_seg == 0:
            continue
        
        segments = []
        for i in range(n_seg):
            seg = y[i*lag:(i+1)*lag]
            
            # Fit linear trend
            x = np.arange(len(seg))
            coef = np.polyfit(x, seg, 1)
            trend = np.polyval(coef, x)
            
            # Detrended fluctuation
            segments.append(((seg - trend) ** 2).mean())
        
        if len(segments) > 0:
            fluct.append(np.sqrt(np.mean(segments)))
    
    if len(fluct) < 2:
        return 0.5
    
    # Fit log(F) = log(c) + H * log(lag)
    log_lags = np.log(list(lags[:len(fluct)]))
    log_fluct = np.log(fluct)
    
    H = np.polyfit(log_lags, log_fluct, 1)[0]
    
    return np.clip(H, 0, 1)


if __name__ == "__main__":
    np.random.seed(42)
    
    # Trending series
    n = 200
    trending = np.cumsum(np.random.randn(n) * 0.5 + 0.1)
    
    result = compute_hurst_exponent(pd.Series(trending), window=100)
    
    print(f"Mean Hurst: {result.hurst_exponent.mean():.3f}")
    print(f"Regime: {result.regime.value_counts().to_dict()}")
