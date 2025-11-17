"""Prediction pipeline with confidence calibration and energy weighting."""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
from pydantic import BaseModel, Field


class PredictionConfig(BaseModel):
    """Configuration for prediction pipeline."""
    
    # Confidence calibration
    use_calibration: bool = Field(default=True)
    calibration_method: str = Field(default="platt", pattern="^(platt|isotonic|beta)$")
    
    # Energy-aware adjustment
    use_energy_adjustment: bool = Field(default=True)
    energy_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    
    # Thresholds
    min_confidence: float = Field(default=0.55, ge=0.0, le=1.0)
    high_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class PredictionResult(BaseModel):
    """Result from ML prediction."""
    
    # Direction prediction
    direction: int = Field(..., description="Predicted direction: +1 (up), -1 (down)")
    direction_probability: float = Field(..., ge=0.0, le=1.0)
    direction_confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Magnitude prediction
    magnitude: int = Field(..., description="Predicted magnitude: 0=small, 1=medium, 2=large")
    magnitude_probabilities: Dict[int, float] = Field(default_factory=dict)
    magnitude_confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Volatility prediction
    predicted_volatility: float = Field(..., ge=0.0)
    volatility_confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Combined confidence
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Energy context
    movement_energy: Optional[float] = Field(default=None)
    energy_adjusted_confidence: Optional[float] = Field(default=None)
    
    # Metadata
    model_versions: Dict[str, str] = Field(default_factory=dict)
    feature_count: int = 0


class Predictor:
    """Make predictions with trained ML models."""
    
    def __init__(self, config: PredictionConfig | None = None):
        """Initialize predictor.
        
        Args:
            config: Prediction configuration
        """
        self.config = config or PredictionConfig()
    
    def predict(
        self,
        models: Dict[str, Any],
        X: np.ndarray,
        movement_energy: Optional[float] = None,
    ) -> PredictionResult:
        """Make prediction with all models.
        
        Args:
            models: Dictionary with "direction", "magnitude", "volatility" models
            X: Feature vector (single sample)
            movement_energy: Optional movement energy for adjustment
            
        Returns:
            PredictionResult with all predictions
        """
        # Ensure X is 2D (1 sample)
        if len(X.shape) == 1:
            X = X.reshape(1, -1)
        
        # Direction prediction
        direction, dir_prob, dir_conf = self._predict_direction(models.get("direction"), X)
        
        # Magnitude prediction
        magnitude, mag_probs, mag_conf = self._predict_magnitude(models.get("magnitude"), X)
        
        # Volatility prediction
        volatility, vol_conf = self._predict_volatility(models.get("volatility"), X)
        
        # Compute overall confidence
        overall_conf = self._compute_overall_confidence(dir_conf, mag_conf, vol_conf)
        
        # Energy adjustment
        energy_adjusted_conf = None
        if self.config.use_energy_adjustment and movement_energy is not None:
            energy_adjusted_conf = self._apply_energy_adjustment(
                overall_conf, movement_energy
            )
        
        return PredictionResult(
            direction=direction,
            direction_probability=dir_prob,
            direction_confidence=dir_conf,
            magnitude=magnitude,
            magnitude_probabilities=mag_probs,
            magnitude_confidence=mag_conf,
            predicted_volatility=volatility,
            volatility_confidence=vol_conf,
            overall_confidence=overall_conf,
            movement_energy=movement_energy,
            energy_adjusted_confidence=energy_adjusted_conf,
            feature_count=X.shape[1],
        )
    
    def _predict_direction(
        self,
        model: Any,
        X: np.ndarray,
    ) -> tuple[int, float, float]:
        """Predict direction.
        
        Args:
            model: Direction model
            X: Features
            
        Returns:
            Tuple of (direction, probability, confidence)
        """
        if model is None:
            return 0, 0.5, 0.0
        
        # Get probability
        prob = model.predict(X)[0]
        
        # Calibrate if needed
        if self.config.use_calibration:
            prob = self._calibrate_probability(prob)
        
        # Convert to direction (±1)
        direction = 1 if prob > 0.5 else -1
        
        # Confidence is distance from 0.5
        confidence = abs(prob - 0.5) * 2
        
        return direction, float(prob), float(confidence)
    
    def _predict_magnitude(
        self,
        model: Any,
        X: np.ndarray,
    ) -> tuple[int, Dict[int, float], float]:
        """Predict magnitude.
        
        Args:
            model: Magnitude model
            X: Features
            
        Returns:
            Tuple of (magnitude, probabilities, confidence)
        """
        if model is None:
            return 1, {0: 0.33, 1: 0.34, 2: 0.33}, 0.0
        
        # Get probabilities
        probs = model.predict(X)[0]  # Shape: (3,)
        
        # Predicted class
        magnitude = int(np.argmax(probs))
        
        # Confidence is max probability
        confidence = float(probs.max())
        
        # Convert to dict
        prob_dict = {i: float(p) for i, p in enumerate(probs)}
        
        return magnitude, prob_dict, confidence
    
    def _predict_volatility(
        self,
        model: Any,
        X: np.ndarray,
    ) -> tuple[float, float]:
        """Predict volatility.
        
        Args:
            model: Volatility model
            X: Features
            
        Returns:
            Tuple of (volatility, confidence)
        """
        if model is None:
            return 0.01, 0.0
        
        # Get prediction
        vol = model.predict(X)[0]
        
        # Confidence for regression is more complex
        # For now, use a fixed confidence based on model training performance
        # In production, use prediction intervals or ensemble variance
        confidence = 0.7
        
        return float(vol), confidence
    
    def _compute_overall_confidence(
        self,
        dir_conf: float,
        mag_conf: float,
        vol_conf: float,
    ) -> float:
        """Compute overall confidence from individual confidences.
        
        Args:
            dir_conf: Direction confidence
            mag_conf: Magnitude confidence
            vol_conf: Volatility confidence
            
        Returns:
            Overall confidence
        """
        # Weighted average (direction is most important)
        weights = np.array([0.5, 0.3, 0.2])
        confs = np.array([dir_conf, mag_conf, vol_conf])
        
        overall = float(np.average(confs, weights=weights))
        
        return overall
    
    def _apply_energy_adjustment(
        self,
        confidence: float,
        movement_energy: float,
    ) -> float:
        """Adjust confidence based on movement energy.
        
        Lower energy moves are easier to predict → boost confidence.
        Higher energy moves are harder → reduce confidence.
        
        Args:
            confidence: Base confidence
            movement_energy: Movement energy value
            
        Returns:
            Energy-adjusted confidence
        """
        # Normalize energy to [0, 1] range (assume typical range 0-100)
        energy_norm = np.clip(movement_energy / 100.0, 0.0, 1.0)
        
        # Adjustment factor: high energy → lower confidence
        energy_penalty = energy_norm * self.config.energy_weight
        
        # Apply adjustment
        adjusted = confidence * (1.0 - energy_penalty)
        
        return float(np.clip(adjusted, 0.0, 1.0))
    
    def _calibrate_probability(self, prob: float) -> float:
        """Calibrate probability using simple method.
        
        In production, this should use fitted calibration models (Platt scaling, isotonic).
        
        Args:
            prob: Raw probability
            
        Returns:
            Calibrated probability
        """
        # Simple beta calibration: push probabilities away from 0.5
        if self.config.calibration_method == "beta":
            alpha, beta = 2.0, 2.0
            # Beta transform
            prob_cal = prob ** alpha / (prob ** alpha + (1 - prob) ** beta)
            return float(np.clip(prob_cal, 0.0, 1.0))
        
        # Default: return as-is
        return prob
