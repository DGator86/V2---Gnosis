"""Label generation for ML training."""

from __future__ import annotations

from typing import Dict, List, Literal
import numpy as np
import polars as pl
from pydantic import BaseModel, Field


class LabelConfig(BaseModel):
    """Configuration for label generation."""
    
    # Forward return horizons (in number of bars)
    horizons: List[int] = Field(default=[5, 15, 60], description="Forward horizons in bars")
    
    # Magnitude classification percentiles
    magnitude_small_threshold: float = Field(default=0.33, ge=0.0, le=1.0)
    magnitude_large_threshold: float = Field(default=0.67, ge=0.0, le=1.0)
    
    # Minimum volatility for direction classification (filter noise)
    min_vol_threshold: float = Field(default=0.0001, ge=0.0)
    
    # Rolling window for realized volatility
    vol_window: int = Field(default=20, ge=1)


class LabelSet(BaseModel):
    """Complete set of labels for ML training."""
    
    # Forward returns for each horizon
    forward_returns: Dict[str, List[float]] = Field(
        default_factory=dict,
        description="Forward returns keyed by horizon (e.g., 'return_5', 'return_15')"
    )
    
    # Direction labels (±1)
    directions: Dict[str, List[int]] = Field(
        default_factory=dict,
        description="Direction labels keyed by horizon (e.g., 'direction_5')"
    )
    
    # Magnitude labels (0=small, 1=medium, 2=large)
    magnitudes: Dict[str, List[int]] = Field(
        default_factory=dict,
        description="Magnitude labels keyed by horizon (e.g., 'magnitude_5')"
    )
    
    # Volatility estimates (forward realized vol)
    volatilities: Dict[str, List[float]] = Field(
        default_factory=dict,
        description="Volatility estimates keyed by horizon (e.g., 'volatility_5')"
    )
    
    # Metadata
    n_samples: int = 0
    n_horizons: int = 0


class LabelGenerator:
    """Generate labels from price time series."""
    
    def __init__(self, config: LabelConfig | None = None):
        """Initialize label generator.
        
        Args:
            config: Label generation configuration
        """
        self.config = config or LabelConfig()
    
    def generate(self, df: pl.DataFrame, price_col: str = "close") -> pl.DataFrame:
        """Generate all labels from price time series.
        
        Args:
            df: DataFrame with OHLCV data and timestamp
            price_col: Column name for price (default: "close")
            
        Returns:
            DataFrame with original data + all label columns
        """
        if df.is_empty():
            return df
        
        result = df.clone()
        
        # Generate labels for each horizon
        for horizon in self.config.horizons:
            # 1. Forward returns
            forward_return_col = f"return_{horizon}"
            result = result.with_columns([
                (
                    (pl.col(price_col).shift(-horizon) - pl.col(price_col)) 
                    / pl.col(price_col)
                ).alias(forward_return_col)
            ])
            
            # 2. Direction labels (±1)
            direction_col = f"direction_{horizon}"
            result = result.with_columns([
                pl.when(pl.col(forward_return_col) > 0)
                  .then(pl.lit(1))
                  .when(pl.col(forward_return_col) < 0)
                  .then(pl.lit(-1))
                  .otherwise(pl.lit(0))
                  .cast(pl.Int32)
                  .alias(direction_col)
            ])
            
            # 3. Magnitude labels (volatility-adjusted percentiles)
            magnitude_col = f"magnitude_{horizon}"
            result = self._generate_magnitude_labels(
                result, forward_return_col, magnitude_col, horizon
            )
            
            # 4. Forward realized volatility
            volatility_col = f"volatility_{horizon}"
            result = self._generate_volatility_labels(
                result, price_col, volatility_col, horizon
            )
        
        return result
    
    def _generate_magnitude_labels(
        self, 
        df: pl.DataFrame, 
        return_col: str, 
        magnitude_col: str,
        horizon: int
    ) -> pl.DataFrame:
        """Generate volatility-adjusted magnitude labels.
        
        Magnitude categories:
        - 0: small move (bottom 33rd percentile of |return| / recent_vol)
        - 1: medium move (33rd-67th percentile)
        - 2: large move (top 33rd percentile)
        
        Args:
            df: DataFrame with return column
            return_col: Name of return column
            magnitude_col: Name for output magnitude column
            horizon: Forecast horizon
            
        Returns:
            DataFrame with magnitude column added
        """
        # Calculate rolling realized volatility
        vol_window = min(self.config.vol_window, len(df) // 4)
        if vol_window < 2:
            vol_window = 2
            
        df_with_vol = df.with_columns([
            pl.col(return_col)
              .abs()
              .rolling_std(window_size=vol_window)
              .alias("_rolling_vol")
        ])
        
        # Volatility-adjusted absolute return
        df_with_vol = df_with_vol.with_columns([
            (pl.col(return_col).abs() / (pl.col("_rolling_vol") + 1e-8))
            .alias("_vol_adjusted_return")
        ])
        
        # Calculate percentile thresholds
        vol_adjusted = df_with_vol.select("_vol_adjusted_return").to_numpy().flatten()
        vol_adjusted = vol_adjusted[~np.isnan(vol_adjusted)]
        
        if len(vol_adjusted) == 0:
            # No valid data, assign all to medium
            return df.with_columns([pl.lit(1).cast(pl.Int32).alias(magnitude_col)])
        
        p33 = float(np.percentile(vol_adjusted, 33))
        p67 = float(np.percentile(vol_adjusted, 67))
        
        # Classify into magnitude buckets
        df_result = df_with_vol.with_columns([
            pl.when(pl.col("_vol_adjusted_return") <= p33)
              .then(pl.lit(0))  # small
              .when(pl.col("_vol_adjusted_return") <= p67)
              .then(pl.lit(1))  # medium
              .otherwise(pl.lit(2))  # large
              .cast(pl.Int32)
              .alias(magnitude_col)
        ])
        
        # Drop temporary columns
        df_result = df_result.drop(["_rolling_vol", "_vol_adjusted_return"])
        
        return df_result
    
    def _generate_volatility_labels(
        self,
        df: pl.DataFrame,
        price_col: str,
        volatility_col: str,
        horizon: int
    ) -> pl.DataFrame:
        """Generate forward realized volatility labels.
        
        Args:
            df: DataFrame with price column
            price_col: Name of price column
            volatility_col: Name for output volatility column
            horizon: Forecast horizon
            
        Returns:
            DataFrame with volatility column added
        """
        # Calculate returns for rolling window
        df_with_returns = df.with_columns([
            (pl.col(price_col).pct_change()).alias("_return")
        ])
        
        # Forward-looking rolling standard deviation
        # Shift the window to look forward, not backward
        df_result = df_with_returns.with_columns([
            pl.col("_return")
              .shift(-horizon)
              .rolling_std(window_size=min(horizon, len(df) // 4))
              .alias(volatility_col)
        ])
        
        # Drop temporary column
        df_result = df_result.drop(["_return"])
        
        return df_result
    
    def generate_label_set(self, df: pl.DataFrame, price_col: str = "close") -> LabelSet:
        """Generate labels and return as structured LabelSet.
        
        Args:
            df: DataFrame with OHLCV data
            price_col: Column name for price
            
        Returns:
            LabelSet with all labels organized by type and horizon
        """
        df_with_labels = self.generate(df, price_col)
        
        label_set = LabelSet(
            n_samples=len(df),
            n_horizons=len(self.config.horizons)
        )
        
        for horizon in self.config.horizons:
            # Extract labels for this horizon
            return_col = f"return_{horizon}"
            direction_col = f"direction_{horizon}"
            magnitude_col = f"magnitude_{horizon}"
            volatility_col = f"volatility_{horizon}"
            
            if return_col in df_with_labels.columns:
                label_set.forward_returns[return_col] = (
                    df_with_labels.select(return_col).to_series().to_list()
                )
            
            if direction_col in df_with_labels.columns:
                label_set.directions[direction_col] = (
                    df_with_labels.select(direction_col).to_series().to_list()
                )
            
            if magnitude_col in df_with_labels.columns:
                label_set.magnitudes[magnitude_col] = (
                    df_with_labels.select(magnitude_col).to_series().to_list()
                )
            
            if volatility_col in df_with_labels.columns:
                label_set.volatilities[volatility_col] = (
                    df_with_labels.select(volatility_col).to_series().to_list()
                )
        
        return label_set
    
    def validate_labels(self, df: pl.DataFrame) -> Dict[str, any]:
        """Validate label quality and return statistics.
        
        Args:
            df: DataFrame with generated labels
            
        Returns:
            Dictionary with validation statistics
        """
        stats = {
            "n_samples": len(df),
            "horizons": {}
        }
        
        for horizon in self.config.horizons:
            horizon_stats = {}
            
            # Check forward returns
            return_col = f"return_{horizon}"
            if return_col in df.columns:
                returns = df.select(return_col).to_series().drop_nulls()
                horizon_stats["n_valid_returns"] = len(returns)
                horizon_stats["mean_return"] = float(returns.mean()) if len(returns) > 0 else 0.0
                horizon_stats["std_return"] = float(returns.std()) if len(returns) > 0 else 0.0
            
            # Check direction balance
            direction_col = f"direction_{horizon}"
            if direction_col in df.columns:
                directions = df.select(direction_col).to_series().drop_nulls()
                n_up = int((directions == 1).sum())
                n_down = int((directions == -1).sum())
                n_neutral = int((directions == 0).sum())
                horizon_stats["direction_balance"] = {
                    "up": n_up,
                    "down": n_down,
                    "neutral": n_neutral,
                    "up_ratio": n_up / len(directions) if len(directions) > 0 else 0.0
                }
            
            # Check magnitude distribution
            magnitude_col = f"magnitude_{horizon}"
            if magnitude_col in df.columns:
                magnitudes = df.select(magnitude_col).to_series().drop_nulls()
                n_small = int((magnitudes == 0).sum())
                n_medium = int((magnitudes == 1).sum())
                n_large = int((magnitudes == 2).sum())
                horizon_stats["magnitude_distribution"] = {
                    "small": n_small,
                    "medium": n_medium,
                    "large": n_large
                }
            
            # Check volatility
            volatility_col = f"volatility_{horizon}"
            if volatility_col in df.columns:
                vols = df.select(volatility_col).to_series().drop_nulls()
                horizon_stats["mean_volatility"] = float(vols.mean()) if len(vols) > 0 else 0.0
            
            stats["horizons"][f"horizon_{horizon}"] = horizon_stats
        
        return stats
