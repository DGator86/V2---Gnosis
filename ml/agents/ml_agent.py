"""ML Agent for providing predictions to Composer Agent."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import numpy as np

from ml.prediction.predictor import Predictor, PredictionResult, PredictionConfig
from ml.persistence.manager import ModelManager


class MLAgentConfig(BaseModel):
    """Configuration for ML Agent."""
    
    # Model paths
    models_dir: str = Field(default="./ml_models")
    
    # Prediction config
    prediction_config: PredictionConfig = Field(default_factory=PredictionConfig)
    
    # Thresholds
    min_confidence_for_signal: float = Field(default=0.6, ge=0.0, le=1.0)
    
    # Enable/disable
    enabled: bool = Field(default=True)
    
    # Fallback behavior
    fallback_on_error: bool = Field(default=True)


class MLOutput(BaseModel):
    """ML agent output for Composer integration."""
    
    # Predictions
    prediction: Optional[PredictionResult] = None
    
    # Signal quality
    has_signal: bool = Field(default=False)
    signal_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Directional bias for Composer
    ml_bias: float = Field(default=0.0, ge=-1.0, le=1.0, description="ML directional bias: -1 (bearish) to +1 (bullish)")
    ml_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Expected move characteristics
    expected_magnitude: str = Field(default="medium", pattern="^(small|medium|large)$")
    expected_volatility: float = Field(default=0.01, ge=0.0)
    
    # Metadata
    models_loaded: bool = Field(default=False)
    error: Optional[str] = Field(default=None)


class MLAgent:
    """ML Agent provides predictions to Composer Agent.
    
    Responsibilities:
    - Load trained models for given symbol
    - Make predictions on current features
    - Provide ML bias and confidence to Composer
    - Does NOT make trade decisions (Composer does that)
    """
    
    def __init__(self, config: MLAgentConfig | None = None):
        """Initialize ML Agent.
        
        Args:
            config: ML agent configuration
        """
        self.config = config or MLAgentConfig()
        self.model_manager = ModelManager(base_dir=self.config.models_dir)
        self.predictor = Predictor(config=self.config.prediction_config)
        
        # Cache loaded models
        self._model_cache: Dict[str, Dict[str, Any]] = {}
    
    def process(
        self,
        symbol: str,
        features: np.ndarray,
        movement_energy: Optional[float] = None,
        horizon: int = 5,
    ) -> MLOutput:
        """Process features and generate ML output.
        
        Args:
            symbol: Trading symbol
            features: Feature vector for prediction
            movement_energy: Optional movement energy from hedge engine
            horizon: Forecast horizon
            
        Returns:
            MLOutput with predictions and signals
        """
        if not self.config.enabled:
            return MLOutput(has_signal=False, ml_confidence=0.0)
        
        try:
            # Load models
            models = self._load_models(symbol, horizon)
            
            if not models:
                return MLOutput(
                    has_signal=False,
                    models_loaded=False,
                    error="No models available"
                )
            
            # Make prediction
            prediction = self.predictor.predict(models, features, movement_energy)
            
            # Convert to ML output
            ml_output = self._convert_to_output(prediction)
            ml_output.models_loaded = True
            
            return ml_output
            
        except Exception as e:
            if self.config.fallback_on_error:
                return MLOutput(
                    has_signal=False,
                    models_loaded=False,
                    error=str(e)
                )
            else:
                raise
    
    def _load_models(self, symbol: str, horizon: int) -> Dict[str, Any]:
        """Load models for symbol and horizon.
        
        Args:
            symbol: Trading symbol
            horizon: Forecast horizon
            
        Returns:
            Dictionary of models
        """
        cache_key = f"{symbol}_{horizon}"
        
        # Check cache
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]
        
        models = {}
        
        # Load direction model
        try:
            direction_model, _ = self.model_manager.load_model(
                symbol=symbol,
                task="direction",
                horizon=horizon,
            )
            models["direction"] = direction_model
        except FileNotFoundError:
            pass
        
        # Load magnitude model
        try:
            magnitude_model, _ = self.model_manager.load_model(
                symbol=symbol,
                task="magnitude",
                horizon=horizon,
            )
            models["magnitude"] = magnitude_model
        except FileNotFoundError:
            pass
        
        # Load volatility model
        try:
            volatility_model, _ = self.model_manager.load_model(
                symbol=symbol,
                task="volatility",
                horizon=horizon,
            )
            models["volatility"] = volatility_model
        except FileNotFoundError:
            pass
        
        # Cache models
        if models:
            self._model_cache[cache_key] = models
        
        return models
    
    def _convert_to_output(self, prediction: PredictionResult) -> MLOutput:
        """Convert PredictionResult to MLOutput for Composer.
        
        Args:
            prediction: Prediction result
            
        Returns:
            MLOutput
        """
        # Determine if signal is strong enough
        confidence = prediction.energy_adjusted_confidence or prediction.overall_confidence
        has_signal = confidence >= self.config.min_confidence_for_signal
        
        # Convert direction to bias (-1 to +1)
        ml_bias = float(prediction.direction)  # Already ±1
        
        # Signal strength is confidence
        signal_strength = confidence
        
        # Expected magnitude label
        magnitude_labels = ["small", "medium", "large"]
        expected_magnitude = magnitude_labels[prediction.magnitude]
        
        return MLOutput(
            prediction=prediction,
            has_signal=has_signal,
            signal_strength=signal_strength,
            ml_bias=ml_bias,
            ml_confidence=confidence,
            expected_magnitude=expected_magnitude,
            expected_volatility=prediction.predicted_volatility,
            models_loaded=True,
        )
    
    def check_drift(
        self,
        symbol: str,
        horizon: int,
        X_recent: np.ndarray,
        threshold: float = 0.2,
    ) -> tuple[bool, float]:
        """Check for model drift.
        
        Args:
            symbol: Trading symbol
            horizon: Forecast horizon
            X_recent: Recent feature data
            threshold: Drift threshold
            
        Returns:
            Tuple of (drift_detected, psi_score)
        """
        try:
            drift_detected, psi_score, _ = self.model_manager.detect_drift(
                symbol=symbol,
                task="direction",  # Check direction model
                horizon=horizon,
                X_recent=X_recent,
                threshold=threshold,
            )
            return drift_detected, psi_score
        except Exception:
            return False, 0.0
    
    def clear_cache(self):
        """Clear model cache (e.g., after retraining)."""
        self._model_cache.clear()
