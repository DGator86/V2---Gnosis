"""Core training interfaces and results."""

from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TrainingResult(BaseModel):
    """Result from model training."""
    
    # Model identification
    model_type: str
    symbol: str
    horizon: int
    
    # Training metadata
    trained_at: datetime = Field(default_factory=datetime.utcnow)
    n_train_samples: int
    n_valid_samples: int
    n_features: int
    
    # Performance metrics
    metrics: Dict[str, float] = Field(default_factory=dict)
    
    # Model artifacts
    model: Optional[Any] = Field(default=None, exclude=True)
    feature_importance: Optional[Dict[str, float]] = Field(default=None)
    
    # Hyperparameters
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    
    # Training info
    training_time_seconds: float = 0.0
    convergence_info: Optional[Dict[str, Any]] = Field(default=None)
    
    model_config = {"arbitrary_types_allowed": True}


class ModelTrainer:
    """Base class for model trainers."""
    
    def train(
        self,
        X_train: Any,
        y_train: Any,
        X_valid: Any,
        y_valid: Any,
        sample_weights: Optional[Any] = None,
    ) -> TrainingResult:
        """Train model.
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_valid: Validation features
            y_valid: Validation labels
            sample_weights: Optional sample weights
            
        Returns:
            TrainingResult with model and metrics
        """
        raise NotImplementedError
    
    def predict(self, model: Any, X: Any) -> Any:
        """Make predictions with trained model.
        
        Args:
            model: Trained model
            X: Features
            
        Returns:
            Predictions
        """
        raise NotImplementedError
