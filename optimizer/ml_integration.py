# optimizer/ml_integration.py

"""
ML prediction integration layer for Trade Agent optimization.

Provides a framework-agnostic interface for integrating ML predictions
into the trade decision context. Supports any ML backend (TensorFlow,
PyTorch, scikit-learn, etc.) through a Protocol-based design.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Protocol


@dataclass
class PredictionFeatures:
    """
    Features used by the ML model to predict direction/vol/trend.

    Example fields:
        - technical indicators (RSI, MACD, Bollinger Bands)
        - hedge engine fields (GEX, DEX, charm, vanna)
        - liquidity metrics (bid-ask spread, volume, depth)
        - sentiment scores (put/call ratio, VIX, news sentiment)
        - vol surface features (IV rank, skew, term structure)
    """
    raw: Dict[str, float]


@dataclass
class PredictionResult:
    """
    Output of the ML model for a single prediction horizon.

    Attributes:
        prob_up: Probability of upward move.
        prob_down: Probability of downward move.
        expected_return: Expected percentage move (can be signed).
        expected_vol: Expected volatility (e.g., 1-day or 5-day).
        meta: Arbitrary metadata for diagnostics (e.g., model version).
    """
    prob_up: float
    prob_down: float
    expected_return: float
    expected_vol: float
    meta: Dict[str, Any]


class PredictionModel(Protocol):
    """
    Protocol for ML models used by the optimizer.

    Implementations can be wrappers around any ML framework.
    
    Example implementations:
    - TensorFlowPredictor: Wraps TF/Keras models
    - PyTorchPredictor: Wraps PyTorch models
    - SKLearnPredictor: Wraps scikit-learn models
    - LightGBMPredictor: Wraps LightGBM/XGBoost models
    """

    def predict(self, features: PredictionFeatures) -> PredictionResult:
        """
        Make a prediction given features.
        
        Args:
            features: PredictionFeatures with raw feature dict
        
        Returns:
            PredictionResult with probabilities and expected values
        """
        ...


def apply_predictions_to_trade_context(
    base_context: Dict[str, Any],
    prediction: PredictionResult,
) -> Dict[str, Any]:
    """
    Merge ML predictions into the trade decision context.

    This function is meant to be used right before strategy selection
    or Kelly sizing, so that ML-derived expectations are available.

    Args:
        base_context: Existing context dict (from engines, vol layer, etc.).
        prediction: ML prediction result.

    Returns:
        New context dict with additional keys:
            - 'ml_prob_up'
            - 'ml_prob_down'
            - 'ml_expected_return'
            - 'ml_expected_vol'
            - 'ml_meta'
    """
    ctx = dict(base_context)
    ctx["ml_prob_up"] = prediction.prob_up
    ctx["ml_prob_down"] = prediction.prob_down
    ctx["ml_expected_return"] = prediction.expected_return
    ctx["ml_expected_vol"] = prediction.expected_vol
    ctx["ml_meta"] = prediction.meta
    return ctx
