"""Energy-aware sample weighting for ML training."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field


class WeightingConfig(BaseModel):
    """Configuration for sample weighting."""
    
    # Energy-aware weighting
    use_energy_weighting: bool = Field(default=True)
    energy_power: float = Field(default=1.0, description="Power to apply to energy weights")
    
    # Volatility-based weighting
    use_volatility_weighting: bool = Field(default=False)
    target_volatility: float = Field(default=0.02, description="Target volatility for normalization")
    
    # Time decay weighting
    use_time_decay: bool = Field(default=True)
    decay_halflife: int = Field(default=100, description="Halflife for time decay in samples")
    
    # Uniqueness weighting
    use_uniqueness_weighting: bool = Field(default=False)
    
    # Normalization
    normalize_weights: bool = Field(default=True)


class EnergyAwareWeighter:
    """Compute energy-aware sample weights for ML training."""
    
    def __init__(self, config: WeightingConfig | None = None):
        """Initialize weighter.
        
        Args:
            config: Weighting configuration
        """
        self.config = config or WeightingConfig()
    
    def compute_weights(
        self,
        energy: np.ndarray,
        volatility: np.ndarray | None = None,
        timestamps: np.ndarray | None = None,
        uniqueness: np.ndarray | None = None,
    ) -> np.ndarray:
        """Compute combined sample weights.
        
        Args:
            energy: Movement energy for each sample
            volatility: Forward volatility for each sample (optional)
            timestamps: Sample timestamps for time decay (optional)
            uniqueness: Sample uniqueness scores (optional)
            
        Returns:
            Array of sample weights
        """
        n = len(energy)
        weights = np.ones(n)
        
        # Energy-aware weighting
        if self.config.use_energy_weighting:
            energy_weights = self._compute_energy_weights(energy)
            weights *= energy_weights
        
        # Volatility-based weighting
        if self.config.use_volatility_weighting and volatility is not None:
            vol_weights = self._compute_volatility_weights(volatility)
            weights *= vol_weights
        
        # Time decay weighting
        if self.config.use_time_decay and timestamps is not None:
            time_weights = self._compute_time_decay_weights(timestamps)
            weights *= time_weights
        
        # Uniqueness weighting
        if self.config.use_uniqueness_weighting and uniqueness is not None:
            weights *= uniqueness
        
        # Normalize weights
        if self.config.normalize_weights:
            weights = self._normalize_weights(weights)
        
        return weights
    
    def _compute_energy_weights(self, energy: np.ndarray) -> np.ndarray:
        """Compute weights inversely proportional to energy.
        
        Lower energy moves are easier to predict and receive higher weight.
        
        Args:
            energy: Movement energy array
            
        Returns:
            Energy-based weights
        """
        # Handle NaN and infinite values
        energy_clean = np.nan_to_num(energy, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Avoid division by zero
        energy_clean = np.clip(energy_clean, 1e-8, None)
        
        # Inverse weighting with power
        weights = 1.0 / (energy_clean ** self.config.energy_power)
        
        return weights
    
    def _compute_volatility_weights(self, volatility: np.ndarray) -> np.ndarray:
        """Compute weights based on volatility.
        
        Normalizes samples to target volatility level.
        
        Args:
            volatility: Forward volatility array
            
        Returns:
            Volatility-based weights
        """
        # Handle NaN and zero values
        vol_clean = np.nan_to_num(volatility, nan=self.config.target_volatility)
        vol_clean = np.clip(vol_clean, 1e-8, None)
        
        # Weight inversely proportional to volatility
        weights = self.config.target_volatility / vol_clean
        
        return weights
    
    def _compute_time_decay_weights(self, timestamps: np.ndarray) -> np.ndarray:
        """Compute exponential time decay weights.
        
        More recent samples receive higher weight.
        
        Args:
            timestamps: Array of timestamps (unix timestamps or sequential indices)
            
        Returns:
            Time decay weights
        """
        # Normalize timestamps to [0, N]
        if len(timestamps) == 0:
            return np.ones(len(timestamps))
        
        t_min = timestamps.min()
        t_max = timestamps.max()
        
        if t_max == t_min:
            return np.ones(len(timestamps))
        
        # Normalize to [0, 1]
        t_norm = (timestamps - t_min) / (t_max - t_min)
        
        # Convert to sample indices
        sample_ages = len(timestamps) * (1 - t_norm)
        
        # Exponential decay
        decay_rate = np.log(2) / self.config.decay_halflife
        weights = np.exp(-decay_rate * sample_ages)
        
        return weights
    
    def _normalize_weights(self, weights: np.ndarray) -> np.ndarray:
        """Normalize weights to sum to number of samples.
        
        Args:
            weights: Raw weights
            
        Returns:
            Normalized weights
        """
        if weights.sum() == 0:
            return np.ones_like(weights)
        
        # Normalize to mean = 1
        weights_normalized = weights / weights.mean()
        
        return weights_normalized
    
    def compute_class_weights(
        self,
        y: np.ndarray,
        method: str = "balanced",
    ) -> dict[int, float]:
        """Compute class weights for imbalanced classification.
        
        Args:
            y: Target labels
            method: Weighting method ("balanced" or "sqrt")
            
        Returns:
            Dictionary mapping class to weight
        """
        classes, counts = np.unique(y, return_counts=True)
        n_samples = len(y)
        n_classes = len(classes)
        
        if method == "balanced":
            # Inverse frequency weighting
            weights = n_samples / (n_classes * counts)
        elif method == "sqrt":
            # Square root of inverse frequency (less aggressive)
            weights = np.sqrt(n_samples / (n_classes * counts))
        else:
            # Uniform weights
            weights = np.ones(n_classes)
        
        return dict(zip(classes.tolist(), weights.tolist()))
    
    def apply_class_weights_to_samples(
        self,
        y: np.ndarray,
        class_weights: dict[int, float],
    ) -> np.ndarray:
        """Apply class weights to individual samples.
        
        Args:
            y: Target labels
            class_weights: Dictionary mapping class to weight
            
        Returns:
            Array of sample weights
        """
        sample_weights = np.zeros(len(y))
        
        for class_label, weight in class_weights.items():
            mask = (y == class_label)
            sample_weights[mask] = weight
        
        return sample_weights
