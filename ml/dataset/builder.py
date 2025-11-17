"""Dataset builder for ML training."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np
import polars as pl
from pydantic import BaseModel, Field


class DatasetConfig(BaseModel):
    """Configuration for dataset building."""
    
    # Train/valid/test split
    train_ratio: float = Field(default=0.7, ge=0.0, le=1.0)
    valid_ratio: float = Field(default=0.15, ge=0.0, le=1.0)
    test_ratio: float = Field(default=0.15, ge=0.0, le=1.0)
    
    # Purged CV
    use_purged_cv: bool = Field(default=True)
    embargo_bars: int = Field(default=10, ge=0, description="Embargo period in bars")
    n_splits: int = Field(default=5, ge=2)
    
    # Energy-aware weighting
    use_energy_weighting: bool = Field(default=True)
    energy_col: str = Field(default="hedge_movement_energy")
    
    # Feature/label columns
    exclude_cols: List[str] = Field(
        default=["timestamp", "symbol", "open", "high", "low", "close", "volume"],
        description="Columns to exclude from features"
    )
    
    # Missing value handling
    drop_na: bool = Field(default=True)
    min_valid_samples: int = Field(default=100)


class MLDataset(BaseModel):
    """Container for ML dataset with features, labels, and weights."""
    
    model_config = {"arbitrary_types_allowed": True}
    
    # Features and labels
    X: np.ndarray = Field(..., description="Feature matrix")
    y_direction: np.ndarray = Field(..., description="Direction labels (±1)")
    y_magnitude: np.ndarray = Field(..., description="Magnitude labels (0/1/2)")
    y_volatility: np.ndarray = Field(..., description="Volatility targets")
    
    # Sample weights
    weights: Optional[np.ndarray] = Field(default=None, description="Sample weights")
    
    # Metadata
    feature_names: List[str] = Field(default_factory=list)
    timestamps: Optional[np.ndarray] = Field(default=None)
    
    n_samples: int = 0
    n_features: int = 0
    
    def __init__(self, **data):
        super().__init__(**data)
        self.n_samples = len(self.X)
        self.n_features = self.X.shape[1] if len(self.X.shape) > 1 else 0


class DatasetBuilder:
    """Build ML datasets with proper splitting and weighting."""
    
    def __init__(self, config: DatasetConfig | None = None):
        """Initialize dataset builder.
        
        Args:
            config: Dataset configuration
        """
        self.config = config or DatasetConfig()
        
        # Validate split ratios
        total = self.config.train_ratio + self.config.valid_ratio + self.config.test_ratio
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Split ratios must sum to 1.0, got {total}")
    
    def build_dataset(
        self,
        df: pl.DataFrame,
        horizon: int = 5,
        include_weights: bool = True,
    ) -> MLDataset:
        """Build ML dataset from feature/label DataFrame.
        
        Args:
            df: DataFrame with features and labels
            horizon: Forecast horizon for label selection
            include_weights: Whether to compute sample weights
            
        Returns:
            MLDataset with features, labels, and weights
        """
        if df.is_empty():
            raise ValueError("Cannot build dataset from empty DataFrame")
        
        # Extract features
        X, feature_names = self._extract_features(df)
        
        # Extract labels for specified horizon
        y_direction = self._extract_label(df, f"direction_{horizon}")
        y_magnitude = self._extract_label(df, f"magnitude_{horizon}")
        y_volatility = self._extract_label(df, f"volatility_{horizon}")
        
        # Extract timestamps if available
        timestamps = None
        if "timestamp" in df.columns:
            timestamps = df["timestamp"].to_numpy()
        
        # Handle missing values
        if self.config.drop_na:
            valid_mask = self._get_valid_mask(X, y_direction, y_magnitude, y_volatility)
            X = X[valid_mask]
            y_direction = y_direction[valid_mask]
            y_magnitude = y_magnitude[valid_mask]
            y_volatility = y_volatility[valid_mask]
            if timestamps is not None:
                timestamps = timestamps[valid_mask]
        
        # Check minimum samples
        if len(X) < self.config.min_valid_samples:
            raise ValueError(
                f"Not enough valid samples: {len(X)} < {self.config.min_valid_samples}"
            )
        
        # Compute sample weights
        weights = None
        if include_weights and self.config.use_energy_weighting:
            weights = self._compute_energy_weights(df, valid_mask if self.config.drop_na else None)
        
        return MLDataset(
            X=X,
            y_direction=y_direction,
            y_magnitude=y_magnitude,
            y_volatility=y_volatility,
            weights=weights,
            feature_names=feature_names,
            timestamps=timestamps,
        )
    
    def temporal_split(
        self,
        dataset: MLDataset,
    ) -> Tuple[MLDataset, MLDataset, MLDataset]:
        """Split dataset temporally into train/valid/test.
        
        Args:
            dataset: Full dataset to split
            
        Returns:
            Tuple of (train_dataset, valid_dataset, test_dataset)
        """
        n = dataset.n_samples
        
        # Calculate split indices
        train_end = int(n * self.config.train_ratio)
        valid_end = int(n * (self.config.train_ratio + self.config.valid_ratio))
        
        # Split features and labels
        train_dataset = MLDataset(
            X=dataset.X[:train_end],
            y_direction=dataset.y_direction[:train_end],
            y_magnitude=dataset.y_magnitude[:train_end],
            y_volatility=dataset.y_volatility[:train_end],
            weights=dataset.weights[:train_end] if dataset.weights is not None else None,
            feature_names=dataset.feature_names,
            timestamps=dataset.timestamps[:train_end] if dataset.timestamps is not None else None,
        )
        
        valid_dataset = MLDataset(
            X=dataset.X[train_end:valid_end],
            y_direction=dataset.y_direction[train_end:valid_end],
            y_magnitude=dataset.y_magnitude[train_end:valid_end],
            y_volatility=dataset.y_volatility[train_end:valid_end],
            weights=dataset.weights[train_end:valid_end] if dataset.weights is not None else None,
            feature_names=dataset.feature_names,
            timestamps=dataset.timestamps[train_end:valid_end] if dataset.timestamps is not None else None,
        )
        
        test_dataset = MLDataset(
            X=dataset.X[valid_end:],
            y_direction=dataset.y_direction[valid_end:],
            y_magnitude=dataset.y_magnitude[valid_end:],
            y_volatility=dataset.y_volatility[valid_end:],
            weights=dataset.weights[valid_end:] if dataset.weights is not None else None,
            feature_names=dataset.feature_names,
            timestamps=dataset.timestamps[valid_end:] if dataset.timestamps is not None else None,
        )
        
        return train_dataset, valid_dataset, test_dataset
    
    def _extract_features(self, df: pl.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Extract feature matrix from DataFrame.
        
        Args:
            df: DataFrame with features
            
        Returns:
            Tuple of (feature matrix, feature names)
        """
        # Identify feature columns (exclude metadata and labels)
        all_cols = df.columns
        feature_cols = [
            col for col in all_cols
            if col not in self.config.exclude_cols
            and not col.startswith("return_")
            and not col.startswith("direction_")
            and not col.startswith("magnitude_")
            and not col.startswith("volatility_")
        ]
        
        if not feature_cols:
            raise ValueError("No feature columns found in DataFrame")
        
        # Extract numeric features
        X = df.select(feature_cols).to_numpy()
        
        return X, feature_cols
    
    def _extract_label(self, df: pl.DataFrame, label_col: str) -> np.ndarray:
        """Extract label array from DataFrame.
        
        Args:
            df: DataFrame with labels
            label_col: Name of label column
            
        Returns:
            Label array
        """
        if label_col not in df.columns:
            raise ValueError(f"Label column '{label_col}' not found in DataFrame")
        
        return df[label_col].to_numpy()
    
    def _get_valid_mask(
        self,
        X: np.ndarray,
        y_direction: np.ndarray,
        y_magnitude: np.ndarray,
        y_volatility: np.ndarray,
    ) -> np.ndarray:
        """Get mask for valid (non-NaN) samples.
        
        Args:
            X: Feature matrix
            y_direction: Direction labels
            y_magnitude: Magnitude labels
            y_volatility: Volatility labels
            
        Returns:
            Boolean mask for valid samples
        """
        # Check for NaNs in features
        valid_X = ~np.isnan(X).any(axis=1)
        
        # Check for NaNs in labels
        valid_y_dir = ~np.isnan(y_direction)
        valid_y_mag = ~np.isnan(y_magnitude)
        valid_y_vol = ~np.isnan(y_volatility)
        
        # Combined mask
        valid_mask = valid_X & valid_y_dir & valid_y_mag & valid_y_vol
        
        return valid_mask
    
    def _compute_energy_weights(
        self,
        df: pl.DataFrame,
        valid_mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Compute energy-aware sample weights.
        
        Weight = 1 / (energy_cost_of_price_move + epsilon)
        
        Lower energy moves are weighted higher (easier to predict).
        
        Args:
            df: DataFrame with energy column
            valid_mask: Optional mask for valid samples
            
        Returns:
            Sample weights array
        """
        if self.config.energy_col not in df.columns:
            # No energy column, return uniform weights
            n = len(df) if valid_mask is None else valid_mask.sum()
            return np.ones(n)
        
        # Extract energy values
        energy = df[self.config.energy_col].to_numpy()
        
        # Apply valid mask if provided
        if valid_mask is not None:
            energy = energy[valid_mask]
        
        # Compute weights (inverse energy)
        weights = 1.0 / (energy + 1e-6)
        
        # Normalize weights to sum to n_samples
        weights = weights / weights.mean()
        
        return weights
