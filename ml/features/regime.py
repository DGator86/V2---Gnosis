"""Regime classification features for ML."""

from __future__ import annotations

from typing import Optional
import numpy as np
import polars as pl
from pydantic import BaseModel, Field


class RegimeConfig(BaseModel):
    """Configuration for regime classification."""
    
    # VIX thresholds
    vix_low: float = Field(default=15.0)
    vix_normal: float = Field(default=20.0)
    vix_elevated: float = Field(default=30.0)
    
    # Realized volatility window
    realized_vol_window: int = Field(default=20)
    
    # Market structure detection
    trend_ma_fast: int = Field(default=20)
    trend_ma_slow: int = Field(default=50)
    chop_threshold: float = Field(default=0.05, description="ADX threshold for choppy market")


class RegimeClassifier:
    """Classify market regimes for ML features."""
    
    def __init__(self, config: RegimeConfig | None = None):
        """Initialize regime classifier.
        
        Args:
            config: Regime classification configuration
        """
        self.config = config or RegimeConfig()
    
    def add_all_regimes(
        self,
        df: pl.DataFrame,
        vix_series: Optional[pl.Series] = None,
        spx_series: Optional[pl.Series] = None,
    ) -> pl.DataFrame:
        """Add all regime classification features.
        
        Args:
            df: DataFrame with OHLCV data
            vix_series: Optional VIX time series (aligned with df)
            spx_series: Optional SPX time series (aligned with df)
            
        Returns:
            DataFrame with regime features added
        """
        if df.is_empty():
            return df
        
        result = df.clone()
        
        # VIX regime
        if vix_series is not None and len(vix_series) == len(df):
            result = self.add_vix_regime(result, vix_series)
        
        # SPX realized volatility regime
        if spx_series is not None and len(spx_series) == len(df):
            result = self.add_spx_vol_regime(result, spx_series)
        
        # Market structure classification
        result = self.add_market_structure(result)
        
        # Session-of-day encoding
        result = self.add_session_regime(result)
        
        # Liquidity time regime
        result = self.add_liquidity_time_regime(result)
        
        return result
    
    def add_vix_regime(self, df: pl.DataFrame, vix_series: pl.Series) -> pl.DataFrame:
        """Add VIX regime classification.
        
        VIX Buckets:
        - Low: VIX < 15
        - Normal: 15 <= VIX < 20
        - Elevated: 20 <= VIX < 30
        - Crisis: VIX >= 30
        
        Args:
            df: DataFrame
            vix_series: VIX values (aligned with df)
            
        Returns:
            DataFrame with VIX regime features
        """
        # Add VIX column
        df = df.with_columns([
            vix_series.alias("regime_vix")
        ])
        
        # Classify into buckets
        df = df.with_columns([
            pl.when(pl.col("regime_vix") < self.config.vix_low)
              .then(pl.lit(0.0))  # Low
              .when(pl.col("regime_vix") < self.config.vix_normal)
              .then(pl.lit(0.33))  # Normal
              .when(pl.col("regime_vix") < self.config.vix_elevated)
              .then(pl.lit(0.67))  # Elevated
              .otherwise(pl.lit(1.0))  # Crisis
              .alias("regime_vix_bucket")
        ])
        
        # VIX momentum (rate of change)
        df = df.with_columns([
            pl.col("regime_vix").pct_change().alias("regime_vix_change")
        ])
        
        return df
    
    def add_spx_vol_regime(self, df: pl.DataFrame, spx_series: pl.Series) -> pl.DataFrame:
        """Add SPX realized volatility regime.
        
        Args:
            df: DataFrame
            spx_series: SPX price series (aligned with df)
            
        Returns:
            DataFrame with SPX volatility regime features
        """
        # Calculate SPX returns
        spx_returns = spx_series.pct_change()
        
        # Realized volatility (rolling std of returns, annualized)
        realized_vol = spx_returns.rolling_std(window_size=self.config.realized_vol_window) * np.sqrt(252)
        
        df = df.with_columns([
            spx_series.alias("regime_spx_price"),
            realized_vol.alias("regime_spx_realized_vol")
        ])
        
        # Classify into buckets (percentile-based)
        vol_values = realized_vol.drop_nulls().to_numpy()
        if len(vol_values) > 0:
            p33 = float(np.percentile(vol_values, 33))
            p67 = float(np.percentile(vol_values, 67))
            
            df = df.with_columns([
                pl.when(pl.col("regime_spx_realized_vol") < p33)
                  .then(pl.lit(0.0))  # Low vol
                  .when(pl.col("regime_spx_realized_vol") < p67)
                  .then(pl.lit(0.5))  # Normal vol
                  .otherwise(pl.lit(1.0))  # High vol
                  .alias("regime_spx_vol_bucket")
            ])
        else:
            df = df.with_columns([
                pl.lit(0.5).alias("regime_spx_vol_bucket")
            ])
        
        return df
    
    def add_market_structure(self, df: pl.DataFrame, price_col: str = "close") -> pl.DataFrame:
        """Add market structure classification.
        
        Classifies market as:
        - Trend (uptrend or downtrend)
        - Rotation (sideways with directional swings)
        - Chop (low momentum, rangebound)
        
        Args:
            df: DataFrame with price data
            price_col: Column name for price
            
        Returns:
            DataFrame with market structure features
        """
        # Calculate moving averages
        ma_fast = pl.col(price_col).rolling_mean(window_size=self.config.trend_ma_fast)
        ma_slow = pl.col(price_col).rolling_mean(window_size=self.config.trend_ma_slow)
        
        df = df.with_columns([
            ma_fast.alias("_ma_fast"),
            ma_slow.alias("_ma_slow")
        ])
        
        # Trend direction
        df = df.with_columns([
            (pl.col("_ma_fast") - pl.col("_ma_slow")).alias("_ma_diff")
        ])
        
        # Calculate ADX for trend strength (simplified version)
        # High ADX = trending, Low ADX = choppy
        returns = pl.col(price_col).pct_change().abs()
        adx_proxy = returns.rolling_mean(window_size=14)
        
        df = df.with_columns([
            adx_proxy.alias("_adx_proxy")
        ])
        
        # Classify market structure
        df = df.with_columns([
            pl.when((pl.col("_ma_diff") > 0) & (pl.col("_adx_proxy") > self.config.chop_threshold))
              .then(pl.lit(1.0))  # Uptrend
              .when((pl.col("_ma_diff") < 0) & (pl.col("_adx_proxy") > self.config.chop_threshold))
              .then(pl.lit(-1.0))  # Downtrend
              .when(pl.col("_adx_proxy") <= self.config.chop_threshold)
              .then(pl.lit(0.0))  # Chop
              .otherwise(pl.lit(0.5))  # Rotation
              .alias("regime_market_structure")
        ])
        
        # Clean up temporary columns
        df = df.drop(["_ma_fast", "_ma_slow", "_ma_diff", "_adx_proxy"])
        
        return df
    
    def add_session_regime(self, df: pl.DataFrame) -> pl.DataFrame:
        """Add session-of-day encoding.
        
        Encodes:
        - Pre-market: 04:00-09:30 ET → 0.0
        - RTH (Regular Trading Hours): 09:30-16:00 ET → 1.0
        - After-hours: 16:00-20:00 ET → 0.5
        
        Note: This is a simplified version. In production, use actual timestamp parsing.
        
        Args:
            df: DataFrame with timestamp
            
        Returns:
            DataFrame with session regime features
        """
        # Placeholder: assume we have a timestamp column
        # In production, parse timestamp and extract hour
        
        if "timestamp" in df.columns:
            # Extract hour (assume timestamp is datetime or unix timestamp)
            try:
                df = df.with_columns([
                    pl.col("timestamp").cast(pl.Datetime).dt.hour().alias("_hour")
                ])
                
                # Classify session
                df = df.with_columns([
                    pl.when((pl.col("_hour") >= 4) & (pl.col("_hour") < 9))
                      .then(pl.lit(0.0))  # Pre-market
                      .when((pl.col("_hour") >= 9) & (pl.col("_hour") < 16))
                      .then(pl.lit(1.0))  # RTH
                      .when((pl.col("_hour") >= 16) & (pl.col("_hour") < 20))
                      .then(pl.lit(0.5))  # After-hours
                      .otherwise(pl.lit(0.25))  # Extended hours
                      .alias("regime_session")
                ])
                
                df = df.drop(["_hour"])
            except Exception:
                # Fallback: assume RTH
                df = df.with_columns([
                    pl.lit(1.0).alias("regime_session")
                ])
        else:
            # No timestamp, assume RTH
            df = df.with_columns([
                pl.lit(1.0).alias("regime_session")
            ])
        
        return df
    
    def add_liquidity_time_regime(self, df: pl.DataFrame) -> pl.DataFrame:
        """Add liquidity time regime.
        
        Classifies trading periods as:
        - Dense liquidity (market open, high volume)
        - Thin liquidity (pre/post-market, low volume)
        
        Uses volume as proxy for liquidity density.
        
        Args:
            df: DataFrame with volume data
            
        Returns:
            DataFrame with liquidity time regime features
        """
        if "volume" not in df.columns:
            # No volume data, assign neutral
            df = df.with_columns([
                pl.lit(0.5).alias("regime_liquidity_time")
            ])
            return df
        
        # Calculate rolling average volume
        avg_volume = pl.col("volume").rolling_mean(window_size=20)
        
        df = df.with_columns([
            avg_volume.alias("_avg_volume")
        ])
        
        # Classify based on volume relative to average
        df = df.with_columns([
            pl.when(pl.col("volume") > pl.col("_avg_volume") * 1.2)
              .then(pl.lit(1.0))  # Dense liquidity
              .when(pl.col("volume") < pl.col("_avg_volume") * 0.8)
              .then(pl.lit(0.0))  # Thin liquidity
              .otherwise(pl.lit(0.5))  # Normal
              .alias("regime_liquidity_time")
        ])
        
        df = df.drop(["_avg_volume"])
        
        return df
    
    def add_dealer_stress_index(
        self,
        df: pl.DataFrame,
        dealer_gamma_sign: Optional[pl.Series] = None,
        vix_series: Optional[pl.Series] = None,
    ) -> pl.DataFrame:
        """Add dealer stress index.
        
        Combines dealer positioning with volatility to estimate dealer stress.
        
        Args:
            df: DataFrame
            dealer_gamma_sign: Dealer gamma positioning (-1 to +1)
            vix_series: VIX values
            
        Returns:
            DataFrame with dealer stress index
        """
        if dealer_gamma_sign is None or vix_series is None:
            # No data, assign neutral
            df = df.with_columns([
                pl.lit(0.5).alias("regime_dealer_stress")
            ])
            return df
        
        # Normalize VIX to [0, 1]
        vix_norm = (vix_series - vix_series.min()) / (vix_series.max() - vix_series.min() + 1e-8)
        
        # Dealer stress is high when:
        # - Dealers are short gamma (dealer_gamma_sign < 0)
        # - VIX is elevated
        
        dealer_stress = (1 - dealer_gamma_sign) / 2 * vix_norm  # [0, 1]
        
        df = df.with_columns([
            dealer_stress.alias("regime_dealer_stress")
        ])
        
        return df
    
    def add_cross_asset_correlation_regime(
        self,
        df: pl.DataFrame,
        asset_returns: pl.Series,
        spx_returns: pl.Series,
        window: int = 20,
    ) -> pl.DataFrame:
        """Add cross-asset correlation regime.
        
        Args:
            df: DataFrame
            asset_returns: Returns of the target asset
            spx_returns: Returns of SPX (market proxy)
            window: Rolling window for correlation
            
        Returns:
            DataFrame with cross-asset correlation features
        """
        # Calculate rolling correlation
        rolling_corr = self._rolling_correlation(asset_returns, spx_returns, window)
        
        df = df.with_columns([
            pl.Series("regime_spx_correlation", rolling_corr)
        ])
        
        # Classify correlation regime
        df = df.with_columns([
            pl.when(pl.col("regime_spx_correlation") > 0.7)
              .then(pl.lit(1.0))  # High positive correlation
              .when(pl.col("regime_spx_correlation") > 0.3)
              .then(pl.lit(0.67))  # Moderate positive
              .when(pl.col("regime_spx_correlation") > -0.3)
              .then(pl.lit(0.5))  # Low/neutral correlation
              .when(pl.col("regime_spx_correlation") > -0.7)
              .then(pl.lit(0.33))  # Moderate negative
              .otherwise(pl.lit(0.0))  # High negative correlation
              .alias("regime_correlation_bucket")
        ])
        
        return df
    
    def _rolling_correlation(self, series1: pl.Series, series2: pl.Series, window: int) -> list[float]:
        """Calculate rolling correlation between two series.
        
        Args:
            series1: First series
            series2: Second series
            window: Rolling window size
            
        Returns:
            List of rolling correlation values
        """
        arr1 = series1.to_numpy()
        arr2 = series2.to_numpy()
        
        n = len(arr1)
        corr = np.full(n, np.nan)
        
        for i in range(window - 1, n):
            window_1 = arr1[i - window + 1:i + 1]
            window_2 = arr2[i - window + 1:i + 1]
            
            # Remove NaNs
            mask = ~(np.isnan(window_1) | np.isnan(window_2))
            if mask.sum() > 2:
                corr[i] = np.corrcoef(window_1[mask], window_2[mask])[0, 1]
        
        return corr.tolist()
