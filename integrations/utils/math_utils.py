"""Mathematical utilities for feature computation."""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Union, Optional


def rolling_window(a: np.ndarray, window: int) -> np.ndarray:
    """Create rolling window view of array.
    
    Args:
        a: Input array
        window: Window size
        
    Returns:
        Array of shape (len(a)-window+1, window)
    """
    if window > a.shape[0]:
        return np.empty((0, window))
    
    shape = a.shape[:-1] + (a.shape[-1] - window + 1, window)
    strides = a.strides + (a.strides[-1],)
    
    return np.lib.stride_tricks.as_strided(a, shape=shape, strides=strides)


def zscore(
    x: Union[np.ndarray, pd.Series],
    window: int = 50,
    min_periods: Optional[int] = None
) -> np.ndarray:
    """Compute rolling z-score.
    
    Args:
        x: Input data
        window: Rolling window size
        min_periods: Minimum periods for computation
        
    Returns:
        Z-scores
    """
    x = np.asarray(x, dtype=float)
    
    if len(x) < window:
        return np.full_like(x, np.nan)
    
    if min_periods is None:
        min_periods = window
    
    # Use rolling window for efficiency
    rw = rolling_window(x, window)
    m = rw.mean(axis=-1)
    s = rw.std(axis=-1, ddof=1)
    
    # Compute z-scores
    z = (x[window-1:] - m) / (s + 1e-9)
    
    # Pad with NaN at start
    result = np.concatenate([np.full(window-1, np.nan), z])
    
    return result


def ewma(
    series: Union[np.ndarray, pd.Series],
    span: int,
    adjust: bool = False
) -> Union[np.ndarray, pd.Series]:
    """Compute exponentially weighted moving average.
    
    Args:
        series: Input data
        span: EW span
        adjust: Whether to use adjustment
        
    Returns:
        EWMA values
    """
    if isinstance(series, pd.Series):
        return series.ewm(span=span, adjust=adjust).mean()
    else:
        # Numpy implementation
        alpha = 2.0 / (span + 1.0)
        result = np.empty_like(series, dtype=float)
        result[0] = series[0]
        
        for i in range(1, len(series)):
            if np.isnan(series[i]):
                result[i] = result[i-1]
            else:
                result[i] = alpha * series[i] + (1 - alpha) * result[i-1]
        
        return result


def safe_divide(
    numerator: Union[float, np.ndarray],
    denominator: Union[float, np.ndarray],
    fill_value: float = 0.0
) -> Union[float, np.ndarray]:
    """Safe division with handling of zero/inf.
    
    Args:
        numerator: Numerator
        denominator: Denominator
        fill_value: Value to use when denominator is zero
        
    Returns:
        Division result
    """
    with np.errstate(divide='ignore', invalid='ignore'):
        result = numerator / denominator
        
    if isinstance(result, np.ndarray):
        result[~np.isfinite(result)] = fill_value
    elif not np.isfinite(result):
        result = fill_value
        
    return result


def normalize(
    x: Union[np.ndarray, pd.Series],
    method: str = "zscore",
    **kwargs
) -> Union[np.ndarray, pd.Series]:
    """Normalize data using specified method.
    
    Args:
        x: Input data
        method: Normalization method ('zscore', 'minmax', 'robust')
        **kwargs: Additional arguments
        
    Returns:
        Normalized data
    """
    x = np.asarray(x, dtype=float)
    
    if method == "zscore":
        mean = np.nanmean(x)
        std = np.nanstd(x)
        return (x - mean) / (std + 1e-9)
    
    elif method == "minmax":
        xmin = np.nanmin(x)
        xmax = np.nanmax(x)
        return (x - xmin) / (xmax - xmin + 1e-9)
    
    elif method == "robust":
        median = np.nanmedian(x)
        q75, q25 = np.nanpercentile(x, [75, 25])
        iqr = q75 - q25
        return (x - median) / (iqr + 1e-9)
    
    else:
        raise ValueError(f"Unknown normalization method: {method}")


def rolling_rank(
    x: Union[np.ndarray, pd.Series],
    window: int
) -> np.ndarray:
    """Compute rolling rank (percentile).
    
    Args:
        x: Input data
        window: Window size
        
    Returns:
        Rolling ranks in [0, 1]
    """
    x = np.asarray(x, dtype=float)
    result = np.full_like(x, np.nan)
    
    for i in range(window-1, len(x)):
        window_data = x[i-window+1:i+1]
        valid_data = window_data[~np.isnan(window_data)]
        
        if len(valid_data) > 0:
            rank = (valid_data < x[i]).sum() / len(valid_data)
            result[i] = rank
    
    return result