"""
Burst Detection - Identify Activity Spikes
Based on: https://github.com/neurotrader888/BurstDetection

Detects sudden increases in activity (volume, volatility, news).
"""

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class BurstResult:
    """Burst detection results."""
    
    burst_score: pd.Series
    """Continuous burst score."""
    
    is_burst: pd.Series
    """Boolean burst indicators."""
    
    burst_duration: pd.Series
    """Duration of each burst."""


def detect_bursts(
    activity: pd.Series,
    window: int = 20,
    threshold: float = 2.5,
    min_duration: int = 2,
) -> BurstResult:
    """
    Detect bursts in activity time series.
    
    Args:
        activity: Activity metric (volume, volatility, etc.)
        window: Baseline window
        threshold: Z-score threshold
        min_duration: Minimum burst duration
    
    Returns:
        BurstResult
    """
    # Z-score
    mu = activity.rolling(window).mean()
    std = activity.rolling(window).std()
    burst_score = (activity - mu) / (std + 1e-9)
    
    # Detect bursts
    is_burst = burst_score > threshold
    
    # Compute duration
    duration = pd.Series(0, index=activity.index)
    count = 0
    
    for i in range(len(is_burst)):
        if is_burst.iloc[i]:
            count += 1
            duration.iloc[i] = count
        else:
            count = 0
    
    # Filter by minimum duration
    is_burst = is_burst & (duration >= min_duration)
    
    return BurstResult(
        burst_score=burst_score,
        is_burst=is_burst,
        burst_duration=duration,
    )


if __name__ == "__main__":
    np.random.seed(42)
    n = 300
    
    # Activity with bursts
    activity = np.abs(np.random.randn(n)) + 1
    activity[100:110] *= 5  # Burst
    activity[200:205] *= 4  # Burst
    
    result = detect_bursts(pd.Series(activity))
    
    print(f"Detected bursts: {result.is_burst.sum()}")
    print(f"Max burst score: {result.burst_score.max():.2f}")
