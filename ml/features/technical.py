"""Technical indicators for ML features."""

from __future__ import annotations

import numpy as np
import polars as pl
from pydantic import BaseModel, Field


class TechnicalConfig(BaseModel):
    """Configuration for technical indicators."""
    
    # MACD
    macd_fast: int = Field(default=12)
    macd_slow: int = Field(default=26)
    macd_signal: int = Field(default=9)
    
    # RSI
    rsi_period: int = Field(default=14)
    
    # ATR
    atr_period: int = Field(default=14)
    
    # ROC (Rate of Change)
    roc_periods: list[int] = Field(default=[5, 10, 20])
    
    # Momentum z-scores
    momentum_window: int = Field(default=20)
    
    # Bollinger Bands
    bb_period: int = Field(default=20)
    bb_std: float = Field(default=2.0)


class TechnicalIndicators:
    """Calculate technical indicators for ML features."""
    
    def __init__(self, config: TechnicalConfig | None = None):
        """Initialize technical indicators calculator.
        
        Args:
            config: Technical indicator configuration
        """
        self.config = config or TechnicalConfig()
    
    def add_all_indicators(self, df: pl.DataFrame) -> pl.DataFrame:
        """Add all technical indicators to DataFrame.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with all technical indicators added
        """
        if df.is_empty():
            return df
        
        result = df.clone()
        
        # MACD
        result = self.add_macd(result)
        
        # RSI
        result = self.add_rsi(result)
        
        # ATR
        result = self.add_atr(result)
        
        # ROC (Rate of Change)
        result = self.add_roc(result)
        
        # Momentum z-scores
        result = self.add_momentum_zscore(result)
        
        # Bollinger Bands
        result = self.add_bollinger_bands(result)
        
        # Stochastic oscillator
        result = self.add_stochastic(result)
        
        # ADX (Average Directional Index)
        result = self.add_adx(result)
        
        return result
    
    def add_macd(self, df: pl.DataFrame, price_col: str = "close") -> pl.DataFrame:
        """Add MACD indicator.
        
        Args:
            df: DataFrame with price data
            price_col: Column name for price
            
        Returns:
            DataFrame with MACD features added
        """
        # Calculate EMAs
        ema_fast = self._ema(df[price_col], self.config.macd_fast)
        ema_slow = self._ema(df[price_col], self.config.macd_slow)
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line
        macd_signal = self._ema(pl.Series(macd_line), self.config.macd_signal)
        
        # Histogram
        macd_histogram = macd_line - macd_signal
        
        # Add to DataFrame
        result = df.with_columns([
            pl.Series("tech_macd_line", macd_line),
            pl.Series("tech_macd_signal", macd_signal),
            pl.Series("tech_macd_histogram", macd_histogram),
        ])
        
        # MACD histogram slope (momentum)
        result = result.with_columns([
            pl.col("tech_macd_histogram").diff().alias("tech_macd_histogram_slope")
        ])
        
        return result
    
    def add_rsi(self, df: pl.DataFrame, price_col: str = "close") -> pl.DataFrame:
        """Add RSI indicator.
        
        Args:
            df: DataFrame with price data
            price_col: Column name for price
            
        Returns:
            DataFrame with RSI features added
        """
        # Calculate price changes
        delta = df[price_col].diff()
        
        # Separate gains and losses
        gains = delta.clip_min(0)
        losses = (-delta).clip_min(0)
        
        # Calculate average gains and losses
        avg_gain = gains.rolling_mean(window_size=self.config.rsi_period)
        avg_loss = losses.rolling_mean(window_size=self.config.rsi_period)
        
        # Calculate RS and RSI
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        result = df.with_columns([
            rsi.alias("tech_rsi"),
        ])
        
        # RSI momentum (slope)
        result = result.with_columns([
            pl.col("tech_rsi").diff().alias("tech_rsi_slope")
        ])
        
        return result
    
    def add_atr(self, df: pl.DataFrame) -> pl.DataFrame:
        """Add ATR (Average True Range) indicator.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with ATR features added
        """
        # True Range calculation
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        
        # Stack and take maximum
        tr = pl.concat([
            high_low.to_frame("tr"),
            high_close.to_frame("tr"),
            low_close.to_frame("tr"),
        ]).group_by(pl.int_range(len(df)).alias("idx") % len(df)).agg(pl.col("tr").max())
        
        # Simple approach: max of the three
        tr_values = []
        for i in range(len(df)):
            tr_val = max(
                high_low[i],
                high_close[i] if i > 0 else high_low[i],
                low_close[i] if i > 0 else high_low[i]
            )
            tr_values.append(tr_val)
        
        tr_series = pl.Series("tr", tr_values)
        
        # ATR is the rolling mean of TR
        atr = tr_series.rolling_mean(window_size=self.config.atr_period)
        
        result = df.with_columns([
            atr.alias("tech_atr"),
        ])
        
        # ATR expansion factor (ATR / ATR_MA_50)
        result = result.with_columns([
            (pl.col("tech_atr") / (pl.col("tech_atr").rolling_mean(window_size=50) + 1e-8))
            .alias("tech_atr_expansion")
        ])
        
        return result
    
    def add_roc(self, df: pl.DataFrame, price_col: str = "close") -> pl.DataFrame:
        """Add Rate of Change indicators.
        
        Args:
            df: DataFrame with price data
            price_col: Column name for price
            
        Returns:
            DataFrame with ROC features added
        """
        for period in self.config.roc_periods:
            roc = (
                (pl.col(price_col) - pl.col(price_col).shift(period)) 
                / (pl.col(price_col).shift(period) + 1e-8)
            ) * 100
            
            df = df.with_columns([
                roc.alias(f"tech_roc_{period}")
            ])
        
        return df
    
    def add_momentum_zscore(self, df: pl.DataFrame, price_col: str = "close") -> pl.DataFrame:
        """Add momentum z-scores.
        
        Args:
            df: DataFrame with price data
            price_col: Column name for price
            
        Returns:
            DataFrame with momentum z-score features added
        """
        # Calculate returns
        returns = pl.col(price_col).pct_change()
        
        # Calculate rolling mean and std
        rolling_mean = returns.rolling_mean(window_size=self.config.momentum_window)
        rolling_std = returns.rolling_std(window_size=self.config.momentum_window)
        
        # Z-score
        momentum_zscore = (returns - rolling_mean) / (rolling_std + 1e-8)
        
        df = df.with_columns([
            returns.alias("tech_return"),
            momentum_zscore.alias("tech_momentum_zscore"),
        ])
        
        return df
    
    def add_bollinger_bands(self, df: pl.DataFrame, price_col: str = "close") -> pl.DataFrame:
        """Add Bollinger Bands.
        
        Args:
            df: DataFrame with price data
            price_col: Column name for price
            
        Returns:
            DataFrame with Bollinger Band features added
        """
        # Calculate middle band (SMA)
        sma = pl.col(price_col).rolling_mean(window_size=self.config.bb_period)
        
        # Calculate standard deviation
        std = pl.col(price_col).rolling_std(window_size=self.config.bb_period)
        
        # Upper and lower bands
        upper_band = sma + (std * self.config.bb_std)
        lower_band = sma - (std * self.config.bb_std)
        
        # %B (position within bands)
        percent_b = (pl.col(price_col) - lower_band) / (upper_band - lower_band + 1e-8)
        
        # Bandwidth (volatility measure)
        bandwidth = (upper_band - lower_band) / (sma + 1e-8)
        
        df = df.with_columns([
            sma.alias("tech_bb_middle"),
            upper_band.alias("tech_bb_upper"),
            lower_band.alias("tech_bb_lower"),
            percent_b.alias("tech_bb_percent_b"),
            bandwidth.alias("tech_bb_bandwidth"),
        ])
        
        return df
    
    def add_stochastic(self, df: pl.DataFrame, k_period: int = 14, d_period: int = 3) -> pl.DataFrame:
        """Add Stochastic Oscillator.
        
        Args:
            df: DataFrame with OHLC data
            k_period: Period for %K calculation
            d_period: Period for %D calculation
            
        Returns:
            DataFrame with Stochastic features added
        """
        # %K calculation
        lowest_low = pl.col("low").rolling_min(window_size=k_period)
        highest_high = pl.col("high").rolling_max(window_size=k_period)
        
        k_value = 100 * (pl.col("close") - lowest_low) / (highest_high - lowest_low + 1e-8)
        
        df = df.with_columns([
            k_value.alias("tech_stoch_k")
        ])
        
        # %D is SMA of %K
        df = df.with_columns([
            pl.col("tech_stoch_k").rolling_mean(window_size=d_period).alias("tech_stoch_d")
        ])
        
        return df
    
    def add_adx(self, df: pl.DataFrame, period: int = 14) -> pl.DataFrame:
        """Add ADX (Average Directional Index).
        
        Args:
            df: DataFrame with OHLC data
            period: Period for ADX calculation
            
        Returns:
            DataFrame with ADX features added
        """
        # Calculate +DM and -DM
        high_diff = df["high"].diff()
        low_diff = -df["low"].diff()
        
        plus_dm = (pl.when(high_diff > low_diff)
                   .then(high_diff.clip_min(0))
                   .otherwise(pl.lit(0.0)))
        
        minus_dm = (pl.when(low_diff > high_diff)
                    .then(low_diff.clip_min(0))
                    .otherwise(pl.lit(0.0)))
        
        # Calculate TR (True Range) - reuse from ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        
        tr_values = []
        for i in range(len(df)):
            tr_val = max(
                high_low[i],
                high_close[i] if i > 0 else high_low[i],
                low_close[i] if i > 0 else high_low[i]
            )
            tr_values.append(tr_val)
        
        tr_series = pl.Series("_tr", tr_values)
        
        # Smooth +DM, -DM, TR
        smoothed_plus_dm = self._wilder_smooth(plus_dm, period)
        smoothed_minus_dm = self._wilder_smooth(minus_dm, period)
        smoothed_tr = self._wilder_smooth(tr_series, period)
        
        # Calculate +DI and -DI
        plus_di = 100 * smoothed_plus_dm / (smoothed_tr + 1e-8)
        minus_di = 100 * smoothed_minus_dm / (smoothed_tr + 1e-8)
        
        # Calculate DX
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-8)
        
        # ADX is smoothed DX
        adx = self._wilder_smooth(pl.Series("_dx", dx), period)
        
        result = df.with_columns([
            pl.Series("tech_adx", adx),
            pl.Series("tech_plus_di", plus_di),
            pl.Series("tech_minus_di", minus_di),
        ])
        
        return result
    
    def _ema(self, series: pl.Series, period: int) -> list[float]:
        """Calculate Exponential Moving Average.
        
        Args:
            series: Price series
            period: EMA period
            
        Returns:
            List of EMA values
        """
        values = series.to_numpy()
        ema = np.zeros_like(values, dtype=float)
        
        # Alpha (smoothing factor)
        alpha = 2.0 / (period + 1)
        
        # Initialize with SMA
        if len(values) >= period:
            ema[period - 1] = np.mean(values[:period])
            
            # Calculate EMA
            for i in range(period, len(values)):
                ema[i] = alpha * values[i] + (1 - alpha) * ema[i - 1]
        
        # Fill leading NaNs
        ema[:period - 1] = np.nan
        
        return ema.tolist()
    
    def _wilder_smooth(self, series: pl.Series, period: int) -> list[float]:
        """Wilder's smoothing (used in ADX calculation).
        
        Args:
            series: Input series
            period: Smoothing period
            
        Returns:
            List of smoothed values
        """
        values = series.to_numpy()
        smoothed = np.zeros_like(values, dtype=float)
        
        if len(values) >= period:
            # Initialize with sum of first period values
            smoothed[period - 1] = np.sum(values[:period])
            
            # Apply Wilder's smoothing
            for i in range(period, len(values)):
                smoothed[i] = smoothed[i - 1] - (smoothed[i - 1] / period) + values[i]
        
        # Fill leading values
        smoothed[:period - 1] = np.nan
        
        return smoothed.tolist()
