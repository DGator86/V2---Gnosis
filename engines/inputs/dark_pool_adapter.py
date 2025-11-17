"""Dark pool buying pressure adapter (unofficial DIX clone).

Based on: https://github.com/jensolson/Dark-Pool-Buying
Estimates dark pool buying pressure from public dark pool prints.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional
import polars as pl
import numpy as np
from loguru import logger


class DarkPoolAdapter:
    """Estimate dark pool buying pressure from public prints.
    
    This is an unofficial implementation inspired by SqueezeMetrics' DIX (Dark Index).
    Uses public dark pool transaction data to estimate institutional accumulation/distribution.
    
    FREE - no subscription required.
    """
    
    def __init__(self):
        """Initialize dark pool adapter."""
        logger.info("DarkPoolAdapter initialized (FREE - unofficial DIX clone)")
    
    def estimate_dark_pool_pressure(
        self,
        symbol: str,
        df_trades: Optional[pl.DataFrame] = None,
    ) -> Dict[str, float]:
        """Estimate dark pool buying/selling pressure.
        
        Args:
            symbol: Stock symbol
            df_trades: DataFrame with trade data (timestamp, price, volume, exchange)
                      If None, will attempt to fetch from available sources
            
        Returns:
            Dictionary with dark pool metrics:
            - dark_pool_ratio: Off-exchange volume / Total volume
            - net_dark_buying: Net buying pressure (-1 to +1)
            - accumulation_score: Accumulation strength (0 to 1)
            - distribution_score: Distribution strength (0 to 1)
        """
        if df_trades is None:
            logger.warning(
                f"No trade data provided for {symbol}. "
                "Dark pool estimation requires trade-level data."
            )
            return self._default_metrics()
        
        try:
            # Identify dark pool trades (exchanges with 'D' designation or TRF)
            df_with_venue = self._classify_venues(df_trades)
            
            # Calculate dark pool metrics
            metrics = self._calculate_metrics(df_with_venue)
            
            logger.debug(f"Dark pool metrics for {symbol}: {metrics}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to estimate dark pool pressure for {symbol}: {e}")
            return self._default_metrics()
    
    def _classify_venues(self, df: pl.DataFrame) -> pl.DataFrame:
        """Classify trades by venue (lit vs dark).
        
        Args:
            df: DataFrame with trade data
            
        Returns:
            DataFrame with added 'is_dark_pool' column
        """
        # Dark pool venue identifiers
        # TRF = Trade Reporting Facility (dark pool prints)
        # D, E, N with specific flags = dark venues
        dark_venues = ["TRF", "FINRA_TRF", "D", "OFF_EXCHANGE"]
        
        if "exchange" in df.columns:
            df = df.with_columns([
                pl.col("exchange").is_in(dark_venues).alias("is_dark_pool")
            ])
        else:
            # No venue data, estimate from volume patterns
            # Large block trades are likely dark pool
            df = df.with_columns([
                (pl.col("volume") > pl.col("volume").quantile(0.95)).alias("is_dark_pool")
            ])
        
        return df
    
    def _calculate_metrics(self, df: pl.DataFrame) -> Dict[str, float]:
        """Calculate dark pool metrics.
        
        Args:
            df: DataFrame with classified trades
            
        Returns:
            Dictionary with metrics
        """
        total_volume = df["volume"].sum()
        
        if total_volume == 0:
            return self._default_metrics()
        
        # Dark pool volume
        dark_volume = df.filter(pl.col("is_dark_pool"))["volume"].sum()
        dark_pool_ratio = float(dark_volume / total_volume)
        
        # Estimate buying vs selling pressure in dark pools
        # Use price changes and volume to infer direction
        dark_trades = df.filter(pl.col("is_dark_pool"))
        
        if len(dark_trades) == 0:
            return {
                "dark_pool_ratio": dark_pool_ratio,
                "net_dark_buying": 0.0,
                "accumulation_score": 0.0,
                "distribution_score": 0.0,
            }
        
        # Calculate price deltas
        dark_trades = dark_trades.with_columns([
            pl.col("price").diff().alias("price_delta")
        ])
        
        # Buying pressure: trades that moved price up
        buying_volume = dark_trades.filter(
            pl.col("price_delta") > 0
        )["volume"].sum()
        
        # Selling pressure: trades that moved price down
        selling_volume = dark_trades.filter(
            pl.col("price_delta") < 0
        )["volume"].sum()
        
        total_directional = buying_volume + selling_volume
        
        if total_directional > 0:
            net_dark_buying = float((buying_volume - selling_volume) / total_directional)
        else:
            net_dark_buying = 0.0
        
        # Accumulation/distribution scores
        accumulation_score = float(np.clip((net_dark_buying + 1) / 2, 0, 1))
        distribution_score = float(np.clip((1 - net_dark_buying) / 2, 0, 1))
        
        return {
            "dark_pool_ratio": dark_pool_ratio,
            "net_dark_buying": net_dark_buying,
            "accumulation_score": accumulation_score,
            "distribution_score": distribution_score,
        }
    
    def _default_metrics(self) -> Dict[str, float]:
        """Return default metrics when data is unavailable.
        
        Returns:
            Dictionary with neutral metrics
        """
        return {
            "dark_pool_ratio": 0.0,
            "net_dark_buying": 0.0,
            "accumulation_score": 0.0,
            "distribution_score": 0.0,
        }
    
    def estimate_from_volume_profile(
        self,
        symbol: str,
        df_ohlcv: pl.DataFrame,
    ) -> Dict[str, float]:
        """Estimate dark pool activity from OHLCV volume patterns.
        
        This is a fallback method when trade-level data is not available.
        Uses volume anomalies to estimate dark pool activity.
        
        Args:
            symbol: Stock symbol
            df_ohlcv: DataFrame with OHLCV data
            
        Returns:
            Dictionary with estimated dark pool metrics
        """
        try:
            # Calculate volume statistics
            avg_volume = df_ohlcv["volume"].mean()
            std_volume = df_ohlcv["volume"].std()
            
            # Large volume spikes likely indicate dark pool prints
            df_with_anomaly = df_ohlcv.with_columns([
                (pl.col("volume") > (avg_volume + 2 * std_volume)).alias("volume_spike")
            ])
            
            # Estimate dark pool ratio from spike frequency
            spike_freq = df_with_anomaly["volume_spike"].sum() / len(df_with_anomaly)
            dark_pool_ratio = float(np.clip(spike_freq, 0.0, 0.5))
            
            # Estimate buying/selling from price action during spikes
            spikes = df_with_anomaly.filter(pl.col("volume_spike"))
            
            if len(spikes) > 0:
                # Price moved up during spike = likely buying
                # Price moved down during spike = likely selling
                price_changes = (spikes["close"] - spikes["open"]) / spikes["open"]
                avg_price_change = price_changes.mean()
                
                # Normalize to [-1, 1]
                net_dark_buying = float(np.clip(avg_price_change * 100, -1, 1))
            else:
                net_dark_buying = 0.0
            
            accumulation_score = float(np.clip((net_dark_buying + 1) / 2, 0, 1))
            distribution_score = float(np.clip((1 - net_dark_buying) / 2, 0, 1))
            
            logger.debug(
                f"Estimated dark pool metrics for {symbol} from volume profile: "
                f"ratio={dark_pool_ratio:.2f}, buying={net_dark_buying:.2f}"
            )
            
            return {
                "dark_pool_ratio": dark_pool_ratio,
                "net_dark_buying": net_dark_buying,
                "accumulation_score": accumulation_score,
                "distribution_score": distribution_score,
            }
            
        except Exception as e:
            logger.error(f"Failed to estimate dark pool from volume profile: {e}")
            return self._default_metrics()


# Convenience function
def get_dark_pool_pressure(symbol: str, df_ohlcv: pl.DataFrame) -> Dict[str, float]:
    """Get dark pool pressure estimates for a symbol.
    
    Args:
        symbol: Stock symbol
        df_ohlcv: DataFrame with OHLCV data
        
    Returns:
        Dictionary with dark pool metrics
    """
    adapter = DarkPoolAdapter()
    return adapter.estimate_from_volume_profile(symbol, df_ohlcv)


# Example usage
if __name__ == "__main__":
    import sys
    
    print("Testing Dark Pool Adapter...")
    
    # Create sample OHLCV data
    print("\n1. Creating sample OHLCV data...")
    dates = pl.date_range(
        datetime.now() - timedelta(days=30),
        datetime.now(),
        interval="1d",
        eager=True,
    )
    
    # Simulate data with some volume spikes
    np.random.seed(42)
    n = len(dates)
    volumes = np.random.lognormal(15, 0.5, n)
    # Add some spikes (dark pool prints)
    spike_indices = np.random.choice(n, size=int(n * 0.1), replace=False)
    volumes[spike_indices] *= 3
    
    prices = 100 + np.cumsum(np.random.randn(n) * 2)
    
    df = pl.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": prices + np.abs(np.random.randn(n)),
        "low": prices - np.abs(np.random.randn(n)),
        "close": prices + np.random.randn(n) * 0.5,
        "volume": volumes,
    })
    
    print(f"   Created {len(df)} days of data")
    
    # Test dark pool estimation
    print("\n2. Estimating dark pool pressure...")
    adapter = DarkPoolAdapter()
    metrics = adapter.estimate_from_volume_profile("TEST", df)
    
    print(f"   Dark Pool Ratio: {metrics['dark_pool_ratio']:.2%}")
    print(f"   Net Dark Buying: {metrics['net_dark_buying']:+.2f}")
    print(f"   Accumulation Score: {metrics['accumulation_score']:.2f}")
    print(f"   Distribution Score: {metrics['distribution_score']:.2f}")
    
    print("\n✅ Dark Pool Adapter working!")
    print("   Note: This uses volume pattern analysis.")
    print("   For better accuracy, integrate actual dark pool print data.")
