"""
ICSS Changepoint Detection
Based on: https://github.com/neurotrader888/ICSS-changepoints

Iterative Cumulative Sum of Squares for detecting variance regime changes.
"""

from dataclasses import dataclass
from typing import List
import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class ChangepointResult:
    """Changepoint detection results."""
    
    changepoints: List[int]
    """Indices of detected changepoints."""
    
    regimes: pd.Series
    """Regime labels for each time point."""
    
    variance_levels: List[float]
    """Variance level for each regime."""


def detect_changepoints(
    ts: pd.Series,
    alpha: float = 0.05,
    min_regime_length: int = 20,
) -> ChangepointResult:
    """
    Detect changepoints in variance using ICSS algorithm.
    
    Args:
        ts: Time series
        alpha: Significance level
        min_regime_length: Minimum length of a regime
    
    Returns:
        ChangepointResult
    """
    data = ts.values
    n = len(data)
    
    changepoints = _icss_algorithm(data, alpha, min_regime_length)
    
    # Assign regimes
    regimes = np.zeros(n, dtype=int)
    for i, cp in enumerate(changepoints[:-1]):
        regimes[cp:changepoints[i+1]] = i
    
    # Compute variance levels
    variance_levels = []
    for i in range(len(changepoints) - 1):
        start, end = changepoints[i], changepoints[i+1]
        variance_levels.append(data[start:end].var())
    
    return ChangepointResult(
        changepoints=changepoints,
        regimes=pd.Series(regimes, index=ts.index),
        variance_levels=variance_levels,
    )


def _icss_algorithm(data: np.ndarray, alpha: float, min_length: int) -> List[int]:
    """ICSS iterative algorithm."""
    n = len(data)
    changepoints = [0, n]
    
    while True:
        new_cp = None
        
        for i in range(len(changepoints) - 1):
            start, end = changepoints[i], changepoints[i+1]
            
            if end - start < min_length * 2:
                continue
            
            segment = data[start:end]
            cp = _find_changepoint(segment, alpha)
            
            if cp is not None:
                new_cp = start + cp
                break
        
        if new_cp is None:
            break
        
        changepoints.append(new_cp)
        changepoints.sort()
    
    return changepoints


def _find_changepoint(data: np.ndarray, alpha: float) -> int:
    """Find single changepoint in segment."""
    n = len(data)
    centered = data - data.mean()
    cumsum = np.cumsum(centered ** 2)
    
    # Test statistic
    D = np.zeros(n)
    total_ss = cumsum[-1]
    
    for k in range(1, n):
        if total_ss > 0:
            D[k] = abs(cumsum[k] / total_ss - k / n)
    
    k_max = D.argmax()
    d_max = D[k_max]
    
    # Critical value
    critical = np.sqrt(-0.5 * np.log(alpha / 2))
    
    if d_max > critical:
        return k_max
    
    return None


if __name__ == "__main__":
    np.random.seed(42)
    
    # Series with regime change
    n1, n2, n3 = 100, 100, 100
    s1 = np.random.randn(n1) * 0.5
    s2 = np.random.randn(n2) * 2.0
    s3 = np.random.randn(n3) * 0.8
    
    ts = pd.Series(np.concatenate([s1, s2, s3]))
    
    result = detect_changepoints(ts)
    
    print(f"Detected changepoints: {result.changepoints}")
    print(f"Variance levels: {[f'{v:.3f}' for v in result.variance_levels]}")
