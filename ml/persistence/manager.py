"""Model persistence manager with versioning and drift detection."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import numpy as np


class ModelMetadata(BaseModel):
    """Metadata for persisted model."""
    
    symbol: str
    model_type: str
    task: str  # "direction", "magnitude", "volatility"
    horizon: int
    version: str
    trained_at: datetime
    
    # Training info
    n_train_samples: int
    n_features: int
    feature_names: List[str]
    
    # Performance metrics
    metrics: Dict[str, float]
    
    # Hyperparameters
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    
    # File paths
    model_path: str
    metadata_path: str


class ModelManager:
    """Manage model persistence with versioning."""
    
    def __init__(self, base_dir: str | Path = "./ml_models"):
        """Initialize model manager.
        
        Args:
            base_dir: Base directory for model storage
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def save_model(
        self,
        model: Any,
        symbol: str,
        model_type: str,
        task: str,
        horizon: int,
        feature_names: List[str],
        metrics: Dict[str, float],
        hyperparameters: Dict[str, Any],
        n_train_samples: int,
        version: Optional[str] = None,
    ) -> ModelMetadata:
        """Save model with metadata.
        
        Args:
            model: Trained model
            symbol: Trading symbol
            model_type: Type of model (e.g., "lightgbm")
            task: Task name ("direction", "magnitude", "volatility")
            horizon: Forecast horizon
            feature_names: List of feature names
            metrics: Performance metrics
            hyperparameters: Model hyperparameters
            n_train_samples: Number of training samples
            version: Optional version string (auto-generated if None)
            
        Returns:
            ModelMetadata for saved model
        """
        # Generate version if not provided
        if version is None:
            version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Create directory structure: base_dir/symbol/task/
        model_dir = self.base_dir / symbol / task
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # File paths
        model_filename = f"{model_type}_horizon{horizon}_v{version}.pkl"
        metadata_filename = f"{model_type}_horizon{horizon}_v{version}.json"
        
        model_path = model_dir / model_filename
        metadata_path = model_dir / metadata_filename
        
        # Save model
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        
        # Create metadata
        metadata = ModelMetadata(
            symbol=symbol,
            model_type=model_type,
            task=task,
            horizon=horizon,
            version=version,
            trained_at=datetime.utcnow(),
            n_train_samples=n_train_samples,
            n_features=len(feature_names),
            feature_names=feature_names,
            metrics=metrics,
            hyperparameters=hyperparameters,
            model_path=str(model_path),
            metadata_path=str(metadata_path),
        )
        
        # Save metadata
        with open(metadata_path, "w") as f:
            json.dump(metadata.model_dump(), f, indent=2, default=str)
        
        return metadata
    
    def load_model(
        self,
        symbol: str,
        task: str,
        horizon: int,
        version: Optional[str] = None,
    ) -> tuple[Any, ModelMetadata]:
        """Load model with metadata.
        
        Args:
            symbol: Trading symbol
            task: Task name
            horizon: Forecast horizon
            version: Specific version to load (latest if None)
            
        Returns:
            Tuple of (model, metadata)
        """
        model_dir = self.base_dir / symbol / task
        
        if not model_dir.exists():
            raise FileNotFoundError(f"No models found for {symbol}/{task}")
        
        # Find model file
        if version is None:
            # Load latest version
            model_files = sorted(model_dir.glob(f"*_horizon{horizon}_v*.pkl"))
            if not model_files:
                raise FileNotFoundError(f"No models found for horizon {horizon}")
            model_path = model_files[-1]
        else:
            # Load specific version
            model_files = list(model_dir.glob(f"*_horizon{horizon}_v{version}.pkl"))
            if not model_files:
                raise FileNotFoundError(f"Model version {version} not found")
            model_path = model_files[0]
        
        # Load model
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        
        # Load metadata
        metadata_path = model_path.with_suffix(".json")
        with open(metadata_path, "r") as f:
            metadata_dict = json.load(f)
        
        metadata = ModelMetadata(**metadata_dict)
        
        return model, metadata
    
    def list_models(self, symbol: str, task: Optional[str] = None) -> List[ModelMetadata]:
        """List all available models for a symbol.
        
        Args:
            symbol: Trading symbol
            task: Optional task filter
            
        Returns:
            List of ModelMetadata
        """
        symbol_dir = self.base_dir / symbol
        
        if not symbol_dir.exists():
            return []
        
        metadata_list = []
        
        # Search pattern
        if task:
            pattern = f"{task}/*.json"
        else:
            pattern = "*/*.json"
        
        for metadata_path in symbol_dir.glob(pattern):
            try:
                with open(metadata_path, "r") as f:
                    metadata_dict = json.load(f)
                metadata = ModelMetadata(**metadata_dict)
                metadata_list.append(metadata)
            except Exception:
                continue
        
        # Sort by trained_at (most recent first)
        metadata_list.sort(key=lambda m: m.trained_at, reverse=True)
        
        return metadata_list
    
    def detect_drift(
        self,
        symbol: str,
        task: str,
        horizon: int,
        X_recent: np.ndarray,
        X_train_stats: Optional[Dict[str, Any]] = None,
        threshold: float = 0.2,
    ) -> tuple[bool, float, Dict[str, Any]]:
        """Detect feature drift using PSI (Population Stability Index).
        
        Args:
            symbol: Trading symbol
            task: Task name
            horizon: Forecast horizon
            X_recent: Recent feature data
            X_train_stats: Training data statistics (if None, computed from saved metadata)
            threshold: PSI threshold for drift detection (default: 0.2)
            
        Returns:
            Tuple of (drift_detected, psi_score, drift_details)
        """
        # Load model metadata to get training statistics
        _, metadata = self.load_model(symbol, task, horizon)
        
        # Compute PSI for each feature
        psi_scores = []
        
        for i in range(X_recent.shape[1]):
            feature_recent = X_recent[:, i]
            
            # For simplicity, compute basic distribution stats
            # In production, use proper binning and PSI calculation
            psi = self._compute_feature_psi(feature_recent)
            psi_scores.append(psi)
        
        # Overall PSI
        overall_psi = float(np.mean(psi_scores))
        
        # Drift detected if PSI > threshold
        drift_detected = overall_psi > threshold
        
        drift_details = {
            "overall_psi": overall_psi,
            "threshold": threshold,
            "feature_psi_scores": psi_scores,
            "n_features_drifted": int((np.array(psi_scores) > threshold).sum()),
        }
        
        return drift_detected, overall_psi, drift_details
    
    def _compute_feature_psi(self, feature: np.ndarray) -> float:
        """Compute PSI for a single feature.
        
        Simplified version. In production, compare against training distribution.
        
        Args:
            feature: Feature values
            
        Returns:
            PSI score
        """
        # Simplified PSI: just return variance as a proxy
        # In production, implement proper PSI calculation
        feature_clean = feature[~np.isnan(feature)]
        
        if len(feature_clean) == 0:
            return 0.0
        
        # Use coefficient of variation as a simple drift indicator
        mean = np.mean(feature_clean)
        std = np.std(feature_clean)
        
        if mean == 0:
            return 0.0
        
        cv = std / abs(mean)
        
        # Normalize to typical PSI range
        psi = min(cv, 1.0)
        
        return float(psi)
    
    def cleanup_old_versions(
        self,
        symbol: str,
        task: str,
        keep_n: int = 5,
    ) -> int:
        """Remove old model versions, keeping only the N most recent.
        
        Args:
            symbol: Trading symbol
            task: Task name
            keep_n: Number of recent versions to keep
            
        Returns:
            Number of models deleted
        """
        models = self.list_models(symbol, task)
        
        if len(models) <= keep_n:
            return 0
        
        # Delete oldest models
        deleted_count = 0
        for metadata in models[keep_n:]:
            try:
                Path(metadata.model_path).unlink()
                Path(metadata.metadata_path).unlink()
                deleted_count += 1
            except Exception:
                continue
        
        return deleted_count
