"""Build reference series from ETF prices for correlation analysis."""

from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Tuple, Deque, Optional
from datetime import datetime, timezone
import math
import logging

logger = logging.getLogger(__name__)


@dataclass
class WindowSpec:
    """Specification for a time window."""
    seconds: int  # Window size in seconds
    ema_span: int  # EMA span for smoothing


DEFAULT_WINDOWS: Dict[str, WindowSpec] = {
    "5m": WindowSpec(seconds=300, ema_span=20),
    "30m": WindowSpec(seconds=1800, ema_span=20),
    "1h": WindowSpec(seconds=3600, ema_span=20),
    "1d": WindowSpec(seconds=86400, ema_span=20),
}


class ReferenceBuilder:
    """Build reference series from price data (e.g., ETFs) for correlation."""
    
    def __init__(
        self,
        windows: Optional[Dict[str, WindowSpec]] = None,
        maxlen: int = 800
    ):
        """Initialize reference builder.
        
        Args:
            windows: Window specifications
            maxlen: Maximum length for each series
        """
        self.windows = windows or DEFAULT_WINDOWS
        self.maxlen = maxlen
        
        # State for each (ref_name, window)
        self._state: Dict[Tuple[str, str], Dict[str, float]] = {}
        
        # Series data
        self._series: Dict[Tuple[str, str], Deque[float]] = defaultdict(
            lambda: deque(maxlen=maxlen)
        )
        
        logger.info(
            f"Initialized ReferenceBuilder with {len(self.windows)} windows"
        )
    
    @staticmethod
    def _timestamp(dt: datetime) -> float:
        """Convert datetime to timestamp.
        
        Args:
            dt: Datetime object
            
        Returns:
            Unix timestamp
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    
    def update_price(
        self,
        ref_name: str,
        when: datetime,
        price: float
    ):
        """Update reference with a new price point.
        
        Args:
            ref_name: Reference name (e.g., "XLK" for tech sector)
            when: Timestamp of price
            price: Price value
        """
        if price <= 0:
            logger.warning(f"Invalid price {price} for {ref_name}")
            return
        
        ts = self._timestamp(when)
        
        for window_name, spec in self.windows.items():
            key = (ref_name, window_name)
            
            # Get or create state
            state = self._state.setdefault(key, {
                "last_ts": ts,
                "last_price": price,
                "ema": 0.0,
                "alpha": 2.0 / (spec.ema_span + 1.0),
                "n_updates": 0,
            })
            
            # Compute log return
            last_price = state["last_price"]
            if last_price > 0 and state["n_updates"] > 0:
                log_return = math.log(price / last_price)
            else:
                log_return = 0.0
            
            # Update EMA
            if state["n_updates"] == 0:
                state["ema"] = log_return
            else:
                alpha = state["alpha"]
                state["ema"] = alpha * log_return + (1.0 - alpha) * state["ema"]
            
            # Store value
            self._series[key].append(state["ema"])
            
            # Update state
            state["last_price"] = price
            state["last_ts"] = ts
            state["n_updates"] += 1
    
    def update_prices_batch(
        self,
        updates: Dict[str, List[Tuple[datetime, float]]]
    ):
        """Update multiple references with price data.
        
        Args:
            updates: Dictionary mapping ref_name to list of (datetime, price) tuples
        """
        for ref_name, price_series in updates.items():
            for when, price in price_series:
                self.update_price(ref_name, when, price)
    
    def latest(self, ref_name: str, window: str) -> Optional[float]:
        """Get latest value for a reference series.
        
        Args:
            ref_name: Reference name
            window: Window name
            
        Returns:
            Latest value or None if no data
        """
        series = self._series.get((ref_name, window))
        if series and len(series) > 0:
            return float(series[-1])
        return None
    
    def series(self, ref_name: str, window: str) -> Deque[float]:
        """Get full series for a reference.
        
        Args:
            ref_name: Reference name
            window: Window name
            
        Returns:
            Series data
        """
        return self._series[(ref_name, window)]
    
    def get_available_references(self) -> Dict[str, List[str]]:
        """Get all available reference series.
        
        Returns:
            Dictionary mapping ref_name to list of windows with data
        """
        refs = defaultdict(list)
        for (ref_name, window), series in self._series.items():
            if series and len(series) > 0:
                refs[ref_name].append(window)
        return dict(refs)
    
    def clear(self, ref_name: Optional[str] = None):
        """Clear reference data.
        
        Args:
            ref_name: Specific reference to clear, or None for all
        """
        if ref_name is None:
            self._state.clear()
            self._series.clear()
        else:
            # Clear specific reference
            keys_to_remove = [
                key for key in self._state.keys()
                if key[0] == ref_name
            ]
            for key in keys_to_remove:
                del self._state[key]
                if key in self._series:
                    del self._series[key]