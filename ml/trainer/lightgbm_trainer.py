"""LightGBM trainer for direction, magnitude, and volatility prediction."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    lgb = None

from ml.trainer.core import ModelTrainer, TrainingResult
from ml.dataset.builder import MLDataset


class LightGBMConfig(BaseModel):
    """Configuration for LightGBM training."""
    
    # Task-specific models
    train_direction: bool = Field(default=True)
    train_magnitude: bool = Field(default=True)
    train_volatility: bool = Field(default=True)
    
    # LightGBM hyperparameters
    num_leaves: int = Field(default=31, ge=2)
    max_depth: int = Field(default=-1)
    learning_rate: float = Field(default=0.05, gt=0.0)
    n_estimators: int = Field(default=100, ge=1)
    min_child_samples: int = Field(default=20, ge=1)
    subsample: float = Field(default=0.8, gt=0.0, le=1.0)
    colsample_bytree: float = Field(default=0.8, gt=0.0, le=1.0)
    reg_alpha: float = Field(default=0.0, ge=0.0)
    reg_lambda: float = Field(default=0.0, ge=0.0)
    
    # Training
    early_stopping_rounds: int = Field(default=50)
    verbose: int = Field(default=-1)
    
    # Device
    device: str = Field(default="cpu", pattern="^(cpu|gpu|cuda)$")


class LightGBMTrainer(ModelTrainer):
    """LightGBM trainer with multi-task support."""
    
    def __init__(self, config: LightGBMConfig | None = None):
        """Initialize LightGBM trainer.
        
        Args:
            config: Training configuration
        """
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("LightGBM not installed. Install with: pip install lightgbm")
        
        self.config = config or LightGBMConfig()
    
    def train_multi_task(
        self,
        train_dataset: MLDataset,
        valid_dataset: MLDataset,
        symbol: str,
        horizon: int,
    ) -> Dict[str, TrainingResult]:
        """Train all tasks (direction, magnitude, volatility).
        
        Args:
            train_dataset: Training dataset
            valid_dataset: Validation dataset
            symbol: Symbol being trained
            horizon: Forecast horizon
            
        Returns:
            Dictionary mapping task name to TrainingResult
        """
        results = {}
        
        # Train direction classifier
        if self.config.train_direction:
            results["direction"] = self.train_direction_model(
                train_dataset, valid_dataset, symbol, horizon
            )
        
        # Train magnitude classifier
        if self.config.train_magnitude:
            results["magnitude"] = self.train_magnitude_model(
                train_dataset, valid_dataset, symbol, horizon
            )
        
        # Train volatility regressor
        if self.config.train_volatility:
            results["volatility"] = self.train_volatility_model(
                train_dataset, valid_dataset, symbol, horizon
            )
        
        return results
    
    def train_direction_model(
        self,
        train_dataset: MLDataset,
        valid_dataset: MLDataset,
        symbol: str,
        horizon: int,
    ) -> TrainingResult:
        """Train binary direction classifier (±1).
        
        Args:
            train_dataset: Training dataset
            valid_dataset: Validation dataset
            symbol: Symbol
            horizon: Forecast horizon
            
        Returns:
            TrainingResult with trained model
        """
        start_time = time.time()
        
        # Convert direction labels from ±1 to 0/1
        y_train = (train_dataset.y_direction > 0).astype(int)
        y_valid = (valid_dataset.y_direction > 0).astype(int)
        
        # Create LightGBM datasets
        train_data = lgb.Dataset(
            train_dataset.X,
            label=y_train,
            weight=train_dataset.weights,
            feature_name=train_dataset.feature_names,
        )
        
        valid_data = lgb.Dataset(
            valid_dataset.X,
            label=y_valid,
            weight=valid_dataset.weights,
            feature_name=valid_dataset.feature_names,
            reference=train_data,
        )
        
        # Train model
        params = self._get_base_params()
        params.update({
            "objective": "binary",
            "metric": ["binary_logloss", "auc"],
        })
        
        callbacks = [
            lgb.early_stopping(self.config.early_stopping_rounds, verbose=False),
            lgb.log_evaluation(period=0 if self.config.verbose < 0 else 100),
        ]
        
        model = lgb.train(
            params,
            train_data,
            num_boost_round=self.config.n_estimators,
            valid_sets=[train_data, valid_data],
            valid_names=["train", "valid"],
            callbacks=callbacks,
        )
        
        # Evaluate
        y_pred_proba = model.predict(valid_dataset.X)
        y_pred = (y_pred_proba > 0.5).astype(int)
        
        metrics = self._compute_direction_metrics(y_valid, y_pred, y_pred_proba)
        
        # Feature importance
        feature_importance = dict(zip(
            train_dataset.feature_names,
            model.feature_importance(importance_type="gain").tolist()
        ))
        
        training_time = time.time() - start_time
        
        return TrainingResult(
            model_type="lightgbm_direction",
            symbol=symbol,
            horizon=horizon,
            n_train_samples=len(train_dataset.X),
            n_valid_samples=len(valid_dataset.X),
            n_features=train_dataset.n_features,
            metrics=metrics,
            model=model,
            feature_importance=feature_importance,
            hyperparameters=params,
            training_time_seconds=training_time,
            convergence_info={
                "best_iteration": model.best_iteration,
                "best_score": model.best_score,
            }
        )
    
    def train_magnitude_model(
        self,
        train_dataset: MLDataset,
        valid_dataset: MLDataset,
        symbol: str,
        horizon: int,
    ) -> TrainingResult:
        """Train multiclass magnitude classifier (small/medium/large).
        
        Args:
            train_dataset: Training dataset
            valid_dataset: Validation dataset
            symbol: Symbol
            horizon: Forecast horizon
            
        Returns:
            TrainingResult with trained model
        """
        start_time = time.time()
        
        # Create LightGBM datasets
        train_data = lgb.Dataset(
            train_dataset.X,
            label=train_dataset.y_magnitude,
            weight=train_dataset.weights,
            feature_name=train_dataset.feature_names,
        )
        
        valid_data = lgb.Dataset(
            valid_dataset.X,
            label=valid_dataset.y_magnitude,
            weight=valid_dataset.weights,
            feature_name=valid_dataset.feature_names,
            reference=train_data,
        )
        
        # Train model
        params = self._get_base_params()
        params.update({
            "objective": "multiclass",
            "metric": ["multi_logloss"],
            "num_class": 3,  # small, medium, large
        })
        
        callbacks = [
            lgb.early_stopping(self.config.early_stopping_rounds, verbose=False),
            lgb.log_evaluation(period=0 if self.config.verbose < 0 else 100),
        ]
        
        model = lgb.train(
            params,
            train_data,
            num_boost_round=self.config.n_estimators,
            valid_sets=[train_data, valid_data],
            valid_names=["train", "valid"],
            callbacks=callbacks,
        )
        
        # Evaluate
        y_pred_proba = model.predict(valid_dataset.X)
        y_pred = np.argmax(y_pred_proba, axis=1)
        
        metrics = self._compute_magnitude_metrics(valid_dataset.y_magnitude, y_pred)
        
        # Feature importance
        feature_importance = dict(zip(
            train_dataset.feature_names,
            model.feature_importance(importance_type="gain").tolist()
        ))
        
        training_time = time.time() - start_time
        
        return TrainingResult(
            model_type="lightgbm_magnitude",
            symbol=symbol,
            horizon=horizon,
            n_train_samples=len(train_dataset.X),
            n_valid_samples=len(valid_dataset.X),
            n_features=train_dataset.n_features,
            metrics=metrics,
            model=model,
            feature_importance=feature_importance,
            hyperparameters=params,
            training_time_seconds=training_time,
            convergence_info={
                "best_iteration": model.best_iteration,
                "best_score": model.best_score,
            }
        )
    
    def train_volatility_model(
        self,
        train_dataset: MLDataset,
        valid_dataset: MLDataset,
        symbol: str,
        horizon: int,
    ) -> TrainingResult:
        """Train volatility regressor.
        
        Args:
            train_dataset: Training dataset
            valid_dataset: Validation dataset
            symbol: Symbol
            horizon: Forecast horizon
            
        Returns:
            TrainingResult with trained model
        """
        start_time = time.time()
        
        # Create LightGBM datasets
        train_data = lgb.Dataset(
            train_dataset.X,
            label=train_dataset.y_volatility,
            weight=train_dataset.weights,
            feature_name=train_dataset.feature_names,
        )
        
        valid_data = lgb.Dataset(
            valid_dataset.X,
            label=valid_dataset.y_volatility,
            weight=valid_dataset.weights,
            feature_name=valid_dataset.feature_names,
            reference=train_data,
        )
        
        # Train model
        params = self._get_base_params()
        params.update({
            "objective": "regression",
            "metric": ["rmse", "mae"],
        })
        
        callbacks = [
            lgb.early_stopping(self.config.early_stopping_rounds, verbose=False),
            lgb.log_evaluation(period=0 if self.config.verbose < 0 else 100),
        ]
        
        model = lgb.train(
            params,
            train_data,
            num_boost_round=self.config.n_estimators,
            valid_sets=[train_data, valid_data],
            valid_names=["train", "valid"],
            callbacks=callbacks,
        )
        
        # Evaluate
        y_pred = model.predict(valid_dataset.X)
        
        metrics = self._compute_volatility_metrics(valid_dataset.y_volatility, y_pred)
        
        # Feature importance
        feature_importance = dict(zip(
            train_dataset.feature_names,
            model.feature_importance(importance_type="gain").tolist()
        ))
        
        training_time = time.time() - start_time
        
        return TrainingResult(
            model_type="lightgbm_volatility",
            symbol=symbol,
            horizon=horizon,
            n_train_samples=len(train_dataset.X),
            n_valid_samples=len(valid_dataset.X),
            n_features=train_dataset.n_features,
            metrics=metrics,
            model=model,
            feature_importance=feature_importance,
            hyperparameters=params,
            training_time_seconds=training_time,
            convergence_info={
                "best_iteration": model.best_iteration,
                "best_score": model.best_score,
            }
        )
    
    def _get_base_params(self) -> Dict[str, Any]:
        """Get base LightGBM parameters.
        
        Returns:
            Dictionary of parameters
        """
        return {
            "num_leaves": self.config.num_leaves,
            "max_depth": self.config.max_depth,
            "learning_rate": self.config.learning_rate,
            "min_child_samples": self.config.min_child_samples,
            "subsample": self.config.subsample,
            "colsample_bytree": self.config.colsample_bytree,
            "reg_alpha": self.config.reg_alpha,
            "reg_lambda": self.config.reg_lambda,
            "verbose": self.config.verbose,
            "device": self.config.device,
            "force_row_wise": True,  # Avoid warnings
        }
    
    def _compute_direction_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_pred_proba: np.ndarray,
    ) -> Dict[str, float]:
        """Compute direction prediction metrics.
        
        Args:
            y_true: True labels (0/1)
            y_pred: Predicted labels (0/1)
            y_pred_proba: Predicted probabilities
            
        Returns:
            Dictionary of metrics
        """
        from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score, log_loss
        
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        
        try:
            auc = roc_auc_score(y_true, y_pred_proba)
        except Exception:
            auc = 0.5
        
        try:
            logloss = log_loss(y_true, y_pred_proba)
        except Exception:
            logloss = 0.0
        
        return {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "auc": float(auc),
            "log_loss": float(logloss),
            "directional_accuracy": float(accuracy),  # Alias
        }
    
    def _compute_magnitude_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> Dict[str, float]:
        """Compute magnitude prediction metrics.
        
        Args:
            y_true: True labels (0/1/2)
            y_pred: Predicted labels (0/1/2)
            
        Returns:
            Dictionary of metrics
        """
        from sklearn.metrics import accuracy_score, f1_score
        
        accuracy = accuracy_score(y_true, y_pred)
        f1_macro = f1_score(y_true, y_pred, average="macro", zero_division=0)
        f1_weighted = f1_score(y_true, y_pred, average="weighted", zero_division=0)
        
        return {
            "accuracy": float(accuracy),
            "f1_macro": float(f1_macro),
            "f1_weighted": float(f1_weighted),
        }
    
    def _compute_volatility_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> Dict[str, float]:
        """Compute volatility prediction metrics.
        
        Args:
            y_true: True volatility values
            y_pred: Predicted volatility values
            
        Returns:
            Dictionary of metrics
        """
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
        
        # Remove NaNs
        mask = ~(np.isnan(y_true) | np.isnan(y_pred))
        y_true_clean = y_true[mask]
        y_pred_clean = y_pred[mask]
        
        if len(y_true_clean) == 0:
            return {"rmse": 0.0, "mae": 0.0, "r2": 0.0}
        
        rmse = np.sqrt(mean_squared_error(y_true_clean, y_pred_clean))
        mae = mean_absolute_error(y_true_clean, y_pred_clean)
        r2 = r2_score(y_true_clean, y_pred_clean)
        
        return {
            "rmse": float(rmse),
            "mae": float(mae),
            "r2": float(r2),
        }
    
    def predict(self, model: Any, X: np.ndarray) -> np.ndarray:
        """Make predictions with trained model.
        
        Args:
            model: Trained LightGBM model
            X: Feature matrix
            
        Returns:
            Predictions
        """
        return model.predict(X)
