"""
Event Discretization for Microstructure Analysis
Based on: https://github.com/neurotrader888/event-discretization

Convert continuous price data into discrete microstructure events.
"""

from dataclasses import dataclass
from typing import List
import numpy as np
import pandas as pd


@dataclass
class EventFeatures:
    """Discretized event features."""
    
    events: pd.DataFrame
    """DataFrame of events with timestamps."""
    
    event_returns: pd.Series
    """Returns associated with each event."""
    
    event_volumes: pd.Series
    """Volumes associated with each event."""


def discretize_events(
    ohlcv: pd.DataFrame,
    method: str = 'tick',
    threshold: Optional[float] = None,
) -> EventFeatures:
    """
    Discretize price series into events.
    
    Args:
        ohlcv: OHLCV data
        method: 'tick' (every bar), 'volume' (volume threshold), 'dollar' (dollar threshold)
        threshold: Threshold for volume/dollar methods
    
    Returns:
        EventFeatures
    """
    if method == 'tick':
        events = ohlcv.copy()
        event_returns = ohlcv['close'].pct_change()
        event_volumes = ohlcv['volume']
    
    elif method == 'volume':
        if threshold is None:
            threshold = ohlcv['volume'].median()
        
        cumvol = ohlcv['volume'].cumsum()
        event_idx = []
        last_cumvol = 0
        
        for i in range(len(ohlcv)):
            if cumvol.iloc[i] - last_cumvol >= threshold:
                event_idx.append(i)
                last_cumvol = cumvol.iloc[i]
        
        events = ohlcv.iloc[event_idx]
        event_returns = events['close'].pct_change()
        event_volumes = events['volume']
    
    elif method == 'dollar':
        if threshold is None:
            threshold = (ohlcv['close'] * ohlcv['volume']).median()
        
        cumdollar = (ohlcv['close'] * ohlcv['volume']).cumsum()
        event_idx = []
        last_cumdollar = 0
        
        for i in range(len(ohlcv)):
            if cumdollar.iloc[i] - last_cumdollar >= threshold:
                event_idx.append(i)
                last_cumdollar = cumdollar.iloc[i]
        
        events = ohlcv.iloc[event_idx]
        event_returns = events['close'].pct_change()
        event_volumes = events['volume']
    
    return EventFeatures(
        events=events,
        event_returns=event_returns,
        event_volumes=event_volumes,
    )


if __name__ == "__main__":
    np.random.seed(42)
    n = 200
    
    ohlcv = pd.DataFrame({
        'open': 100 + np.cumsum(np.random.randn(n) * 0.5),
        'high': 100,
        'low': 100,
        'close': 100 + np.cumsum(np.random.randn(n) * 0.5),
        'volume': np.abs(np.random.randn(n) * 1000000 + 5000000),
    })
    
    result = discretize_events(ohlcv, method='volume')
    
    print(f"Original bars: {len(ohlcv)}")
    print(f"Events: {len(result.events)}")
