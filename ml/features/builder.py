"""Feature builder that merges all engine outputs into ML-ready matrix."""

from __future__ import annotations

from typing import Dict, List, Optional, Any
import polars as pl
from pydantic import BaseModel, Field

from engines.hedge.models import HedgeEngineOutput
from engines.liquidity.models import LiquidityEngineOutput
from engines.sentiment.models import SentimentEnvelope


class FeatureConfig(BaseModel):
    """Configuration for feature building."""
    
    # Feature selection
    include_hedge: bool = Field(default=True)
    include_liquidity: bool = Field(default=True)
    include_sentiment: bool = Field(default=True)
    include_technical: bool = Field(default=True)
    include_regime: bool = Field(default=True)
    
    # Normalization
    normalize_features: bool = Field(default=True)
    normalization_method: str = Field(default="zscore", pattern="^(zscore|minmax|robust)$")
    
    # Missing value handling
    fill_method: str = Field(default="forward", pattern="^(forward|backward|mean|zero)$")
    
    # Feature engineering
    add_lag_features: bool = Field(default=True)
    lag_periods: List[int] = Field(default=[1, 2, 5, 10])
    
    add_rolling_features: bool = Field(default=True)
    rolling_windows: List[int] = Field(default=[5, 10, 20, 50])


class FeatureBuilder:
    """Build ML-ready feature matrix from engine outputs."""
    
    def __init__(self, config: FeatureConfig | None = None):
        """Initialize feature builder.
        
        Args:
            config: Feature building configuration
        """
        self.config = config or FeatureConfig()
        self._feature_names: List[str] = []
    
    def build_feature_frame(
        self,
        df_ohlcv: pl.DataFrame,
        hedge_outputs: Optional[List[HedgeEngineOutput]] = None,
        liquidity_outputs: Optional[List[LiquidityEngineOutput]] = None,
        sentiment_outputs: Optional[List[SentimentEnvelope]] = None,
    ) -> pl.DataFrame:
        """Build complete feature matrix from engine outputs.
        
        Args:
            df_ohlcv: Base OHLCV dataframe with timestamp
            hedge_outputs: List of HedgeEngineOutput (aligned with df_ohlcv)
            liquidity_outputs: List of LiquidityEngineOutput (aligned with df_ohlcv)
            sentiment_outputs: List of SentimentEnvelope (aligned with df_ohlcv)
            
        Returns:
            DataFrame with all features merged and aligned
        """
        if df_ohlcv.is_empty():
            return pl.DataFrame()
        
        # Start with base OHLCV features
        feature_df = self._build_ohlcv_features(df_ohlcv)
        
        # Add engine features
        if self.config.include_hedge and hedge_outputs:
            hedge_df = self._extract_hedge_features(hedge_outputs)
            feature_df = self._merge_features(feature_df, hedge_df, "hedge")
        
        if self.config.include_liquidity and liquidity_outputs:
            liquidity_df = self._extract_liquidity_features(liquidity_outputs)
            feature_df = self._merge_features(feature_df, liquidity_df, "liquidity")
        
        if self.config.include_sentiment and sentiment_outputs:
            sentiment_df = self._extract_sentiment_features(sentiment_outputs)
            feature_df = self._merge_features(feature_df, sentiment_df, "sentiment")
        
        # Add derived features
        if self.config.add_lag_features:
            feature_df = self._add_lag_features(feature_df)
        
        if self.config.add_rolling_features:
            feature_df = self._add_rolling_features(feature_df)
        
        # Handle missing values
        feature_df = self._handle_missing_values(feature_df)
        
        # Normalize features
        if self.config.normalize_features:
            feature_df = self._normalize_features(feature_df)
        
        # Track feature names
        self._feature_names = [col for col in feature_df.columns if col not in ["timestamp"]]
        
        return feature_df
    
    def _build_ohlcv_features(self, df: pl.DataFrame) -> pl.DataFrame:
        """Extract basic OHLCV features.
        
        Args:
            df: OHLCV dataframe
            
        Returns:
            DataFrame with OHLCV features
        """
        features = df.select([
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ])
        
        # Add basic derived features
        features = features.with_columns([
            # Price ranges
            ((pl.col("high") - pl.col("low")) / pl.col("close")).alias("range_pct"),
            ((pl.col("close") - pl.col("open")) / pl.col("open")).alias("body_pct"),
            
            # Wick ratios
            ((pl.col("high") - pl.col("close").max(pl.col("open"))) / 
             (pl.col("high") - pl.col("low") + 1e-8)).alias("upper_wick_ratio"),
            ((pl.col("close").min(pl.col("open")) - pl.col("low")) / 
             (pl.col("high") - pl.col("low") + 1e-8)).alias("lower_wick_ratio"),
            
            # Volume
            pl.col("volume").log1p().alias("log_volume"),
        ])
        
        return features
    
    def _extract_hedge_features(self, outputs: List[HedgeEngineOutput]) -> pl.DataFrame:
        """Extract features from hedge engine outputs.
        
        Args:
            outputs: List of HedgeEngineOutput
            
        Returns:
            DataFrame with hedge features
        """
        rows = []
        for output in outputs:
            row = {
                "hedge_pressure_up": output.pressure_up,
                "hedge_pressure_down": output.pressure_down,
                "hedge_net_pressure": output.net_pressure,
                "hedge_elasticity": output.elasticity,
                "hedge_movement_energy": output.movement_energy,
                "hedge_elasticity_up": output.elasticity_up,
                "hedge_elasticity_down": output.elasticity_down,
                "hedge_movement_energy_up": output.movement_energy_up,
                "hedge_movement_energy_down": output.movement_energy_down,
                "hedge_energy_asymmetry": output.energy_asymmetry,
                "hedge_gamma_pressure": output.gamma_pressure,
                "hedge_vanna_pressure": output.vanna_pressure,
                "hedge_charm_pressure": output.charm_pressure,
                "hedge_dealer_gamma_sign": output.dealer_gamma_sign,
                "hedge_confidence": output.confidence,
                "hedge_regime_stability": output.regime_stability,
                "hedge_cross_asset_correlation": output.cross_asset_correlation,
            }
            
            # Encode categorical regimes as one-hot or ordinal
            # For simplicity, we'll use label encoding here
            row["hedge_primary_regime"] = self._encode_regime(output.primary_regime)
            row["hedge_gamma_regime"] = self._encode_regime(output.gamma_regime)
            row["hedge_vanna_regime"] = self._encode_regime(output.vanna_regime)
            row["hedge_charm_regime"] = self._encode_regime(output.charm_regime)
            row["hedge_jump_risk_regime"] = self._encode_regime(output.jump_risk_regime)
            row["hedge_potential_shape"] = self._encode_potential_shape(output.potential_shape)
            
            rows.append(row)
        
        return pl.DataFrame(rows)
    
    def _extract_liquidity_features(self, outputs: List[LiquidityEngineOutput]) -> pl.DataFrame:
        """Extract features from liquidity engine outputs.
        
        Args:
            outputs: List of LiquidityEngineOutput
            
        Returns:
            DataFrame with liquidity features
        """
        rows = []
        for output in outputs:
            row = {
                "liq_score": output.liquidity_score,
                "liq_friction_cost": output.friction_cost,
                "liq_kyle_lambda": output.kyle_lambda,
                "liq_amihud": output.amihud,
                "liq_orderbook_imbalance": output.orderbook_imbalance,
                "liq_sweep_alerts": float(output.sweep_alerts),
                "liq_iceberg_alerts": float(output.iceberg_alerts),
                "liq_compression_energy": output.compression_energy,
                "liq_expansion_energy": output.expansion_energy,
                "liq_volume_strength": output.volume_strength,
                "liq_buying_effort": output.buying_effort,
                "liq_selling_effort": output.selling_effort,
                "liq_off_exchange_ratio": output.off_exchange_ratio,
                "liq_hidden_accumulation": output.hidden_accumulation,
                "liq_wyckoff_energy": output.wyckoff_energy,
                "liq_polr_direction": output.polr_direction,
                "liq_polr_strength": output.polr_strength,
                "liq_confidence": output.confidence,
            }
            
            # Encode categorical
            row["liq_wyckoff_phase"] = self._encode_wyckoff_phase(output.wyckoff_phase)
            row["liq_regime"] = self._encode_liquidity_regime(output.liquidity_regime)
            row["liq_regime_confidence"] = output.regime_confidence
            
            # Zone counts (structural features)
            row["liq_n_absorption_zones"] = len(output.absorption_zones)
            row["liq_n_displacement_zones"] = len(output.displacement_zones)
            row["liq_n_voids"] = len(output.voids)
            
            rows.append(row)
        
        return pl.DataFrame(rows)
    
    def _extract_sentiment_features(self, outputs: List[SentimentEnvelope]) -> pl.DataFrame:
        """Extract features from sentiment engine outputs.
        
        Args:
            outputs: List of SentimentEnvelope
            
        Returns:
            DataFrame with sentiment features
        """
        rows = []
        for output in outputs:
            row = {
                "sent_bias": self._encode_sentiment_bias(output.bias),
                "sent_strength": output.strength,
                "sent_energy": output.energy,
                "sent_confidence": output.confidence,
                "sent_n_drivers": len(output.drivers),
            }
            
            # Top driver strengths (pad with zeros if fewer than 5 drivers)
            driver_values = sorted(output.drivers.values(), reverse=True)[:5]
            for i in range(5):
                row[f"sent_driver_{i+1}"] = driver_values[i] if i < len(driver_values) else 0.0
            
            # Optional regime encoding
            if output.wyckoff_phase:
                row["sent_wyckoff_phase"] = self._encode_wyckoff_phase(output.wyckoff_phase)
            if output.liquidity_regime:
                row["sent_liquidity_regime"] = self._encode_liquidity_regime(output.liquidity_regime)
            if output.volatility_regime:
                row["sent_volatility_regime"] = self._encode_volatility_regime(output.volatility_regime)
            if output.flow_regime:
                row["sent_flow_regime"] = self._encode_flow_regime(output.flow_regime)
            
            rows.append(row)
        
        return pl.DataFrame(rows)
    
    def _merge_features(self, base_df: pl.DataFrame, new_df: pl.DataFrame, prefix: str) -> pl.DataFrame:
        """Merge feature DataFrames with validation.
        
        Args:
            base_df: Base feature DataFrame
            new_df: New features to merge
            prefix: Prefix for logging
            
        Returns:
            Merged DataFrame
        """
        if len(base_df) != len(new_df):
            raise ValueError(
                f"Length mismatch: base_df has {len(base_df)} rows, "
                f"{prefix}_df has {len(new_df)} rows"
            )
        
        # Horizontal concatenation
        return pl.concat([base_df, new_df], how="horizontal")
    
    def _add_lag_features(self, df: pl.DataFrame) -> pl.DataFrame:
        """Add lagged features.
        
        Args:
            df: Feature DataFrame
            
        Returns:
            DataFrame with lagged features added
        """
        numeric_cols = [col for col in df.columns if col != "timestamp" and df[col].dtype in (pl.Float64, pl.Float32, pl.Int64, pl.Int32)]
        
        lag_exprs = []
        for col in numeric_cols[:20]:  # Limit to top 20 features to avoid explosion
            for lag in self.config.lag_periods:
                lag_exprs.append(
                    pl.col(col).shift(lag).alias(f"{col}_lag{lag}")
                )
        
        if lag_exprs:
            df = df.with_columns(lag_exprs)
        
        return df
    
    def _add_rolling_features(self, df: pl.DataFrame) -> pl.DataFrame:
        """Add rolling window features.
        
        Args:
            df: Feature DataFrame
            
        Returns:
            DataFrame with rolling features added
        """
        numeric_cols = [col for col in df.columns if col != "timestamp" and "_lag" not in col and df[col].dtype in (pl.Float64, pl.Float32)]
        
        rolling_exprs = []
        for col in numeric_cols[:15]:  # Limit features
            for window in self.config.rolling_windows:
                rolling_exprs.extend([
                    pl.col(col).rolling_mean(window_size=window).alias(f"{col}_ma{window}"),
                    pl.col(col).rolling_std(window_size=window).alias(f"{col}_std{window}"),
                ])
        
        if rolling_exprs:
            df = df.with_columns(rolling_exprs)
        
        return df
    
    def _handle_missing_values(self, df: pl.DataFrame) -> pl.DataFrame:
        """Handle missing values according to configuration.
        
        Args:
            df: Feature DataFrame
            
        Returns:
            DataFrame with missing values handled
        """
        if self.config.fill_method == "forward":
            df = df.fill_null(strategy="forward")
        elif self.config.fill_method == "backward":
            df = df.fill_null(strategy="backward")
        elif self.config.fill_method == "mean":
            # Fill with column means
            for col in df.columns:
                if col != "timestamp" and df[col].dtype in (pl.Float64, pl.Float32):
                    mean_val = df[col].mean()
                    if mean_val is not None:
                        df = df.with_columns(pl.col(col).fill_null(mean_val))
        else:  # zero
            df = df.fill_null(0.0)
        
        # Final fallback: fill any remaining nulls with 0
        df = df.fill_null(0.0)
        
        return df
    
    def _normalize_features(self, df: pl.DataFrame) -> pl.DataFrame:
        """Normalize features according to configuration.
        
        Args:
            df: Feature DataFrame
            
        Returns:
            DataFrame with normalized features
        """
        numeric_cols = [col for col in df.columns if col != "timestamp" and df[col].dtype in (pl.Float64, pl.Float32)]
        
        if self.config.normalization_method == "zscore":
            # Z-score normalization
            for col in numeric_cols:
                mean = df[col].mean()
                std = df[col].std()
                if std and std > 1e-8:
                    df = df.with_columns([
                        ((pl.col(col) - mean) / std).alias(col)
                    ])
        
        elif self.config.normalization_method == "minmax":
            # Min-max normalization
            for col in numeric_cols:
                min_val = df[col].min()
                max_val = df[col].max()
                if max_val != min_val:
                    df = df.with_columns([
                        ((pl.col(col) - min_val) / (max_val - min_val)).alias(col)
                    ])
        
        elif self.config.normalization_method == "robust":
            # Robust scaling (median and IQR)
            for col in numeric_cols:
                median = df[col].median()
                q25 = df[col].quantile(0.25)
                q75 = df[col].quantile(0.75)
                iqr = q75 - q25
                if iqr and iqr > 1e-8:
                    df = df.with_columns([
                        ((pl.col(col) - median) / iqr).alias(col)
                    ])
        
        return df
    
    # Encoding helpers
    
    def _encode_regime(self, regime: str) -> float:
        """Encode regime string to numeric value."""
        regime_map = {
            "low": 0.0,
            "normal": 0.5,
            "elevated": 0.75,
            "high": 1.0,
            "crisis": 1.5,
            "unknown": 0.5,
        }
        return regime_map.get(regime.lower(), 0.5)
    
    def _encode_potential_shape(self, shape: str) -> float:
        """Encode potential field shape."""
        shape_map = {
            "quadratic": 0.0,
            "cubic": 0.5,
            "double_well": 1.0,
            "flat": 0.25,
            "unknown": 0.5,
        }
        return shape_map.get(shape.lower(), 0.5)
    
    def _encode_wyckoff_phase(self, phase: str) -> float:
        """Encode Wyckoff phase."""
        phase_map = {
            "A": 0.0,
            "B": 0.25,
            "C": 0.5,
            "D": 0.75,
            "E": 1.0,
            "Unknown": 0.5,
        }
        return phase_map.get(phase, 0.5)
    
    def _encode_liquidity_regime(self, regime: str) -> float:
        """Encode liquidity regime."""
        regime_map = {
            "Normal": 0.5,
            "Thin": 0.25,
            "Stressed": 0.0,
            "Crisis": -0.5,
            "Abundant": 1.0,
        }
        return regime_map.get(regime, 0.5)
    
    def _encode_sentiment_bias(self, bias: str) -> float:
        """Encode sentiment bias."""
        bias_map = {
            "bullish": 1.0,
            "neutral": 0.0,
            "bearish": -1.0,
        }
        return bias_map.get(bias.lower(), 0.0)
    
    def _encode_volatility_regime(self, regime: str) -> float:
        """Encode volatility regime."""
        regime_map = {
            "low": 0.0,
            "normal": 0.5,
            "elevated": 0.75,
            "high": 1.0,
        }
        return regime_map.get(regime.lower(), 0.5)
    
    def _encode_flow_regime(self, regime: str) -> float:
        """Encode flow regime."""
        regime_map = {
            "accumulation": 1.0,
            "distribution": -1.0,
            "neutral": 0.0,
            "markup": 0.75,
            "markdown": -0.75,
        }
        return regime_map.get(regime.lower(), 0.0)
    
    @property
    def feature_names(self) -> List[str]:
        """Get list of feature names after building."""
        return self._feature_names
