# tests/optimizer/test_ml_integration.py

"""Tests for ML prediction integration."""

import pytest

from optimizer.ml_integration import (
    PredictionFeatures,
    PredictionResult,
    PredictionModel,
    apply_predictions_to_trade_context,
)


class MockPredictionModel:
    """Mock ML model for testing."""
    
    def predict(self, features: PredictionFeatures) -> PredictionResult:
        """Return deterministic prediction."""
        return PredictionResult(
            prob_up=0.6,
            prob_down=0.4,
            expected_return=0.02,
            expected_vol=0.15,
            meta={"model_version": "v1.0", "confidence": 0.8},
        )


@pytest.fixture
def sample_features():
    """Create sample prediction features."""
    return PredictionFeatures(
        raw={
            "rsi": 65.0,
            "macd": 1.2,
            "vix": 18.5,
            "gex": 5000.0,
            "dex": -2000.0,
            "iv_rank": 0.35,
        }
    )


@pytest.fixture
def sample_prediction():
    """Create sample prediction result."""
    return PredictionResult(
        prob_up=0.65,
        prob_down=0.35,
        expected_return=0.03,
        expected_vol=0.20,
        meta={"model": "lightgbm", "version": "2.0"},
    )


@pytest.fixture
def base_context():
    """Create base trade context."""
    return {
        "asset": "SPY",
        "current_price": 450.0,
        "direction": "bullish",
        "confidence": 0.7,
        "volatility_regime": "mid",
    }


class TestPredictionFeatures:
    """Test PredictionFeatures data structure."""
    
    def test_features_creation(self, sample_features):
        """Test creating prediction features."""
        assert "rsi" in sample_features.raw
        assert "macd" in sample_features.raw
        assert "vix" in sample_features.raw
    
    def test_features_raw_dict(self):
        """Test raw features dictionary."""
        features = PredictionFeatures(raw={"feature1": 1.0, "feature2": 2.0})
        
        assert features.raw["feature1"] == 1.0
        assert features.raw["feature2"] == 2.0


class TestPredictionResult:
    """Test PredictionResult data structure."""
    
    def test_result_creation(self, sample_prediction):
        """Test creating prediction result."""
        assert sample_prediction.prob_up == 0.65
        assert sample_prediction.prob_down == 0.35
        assert sample_prediction.expected_return == 0.03
        assert sample_prediction.expected_vol == 0.20
    
    def test_result_probabilities_sum(self):
        """Test that probabilities sum to 1."""
        result = PredictionResult(
            prob_up=0.7,
            prob_down=0.3,
            expected_return=0.05,
            expected_vol=0.25,
            meta={},
        )
        
        assert abs((result.prob_up + result.prob_down) - 1.0) < 0.01


class TestMockPredictionModel:
    """Test mock ML model."""
    
    def test_model_predict(self, sample_features):
        """Test model prediction."""
        model = MockPredictionModel()
        result = model.predict(sample_features)
        
        assert isinstance(result, PredictionResult)
        assert result.prob_up == 0.6
        assert result.prob_down == 0.4
    
    def test_model_meta(self, sample_features):
        """Test model returns metadata."""
        model = MockPredictionModel()
        result = model.predict(sample_features)
        
        assert "model_version" in result.meta
        assert result.meta["model_version"] == "v1.0"


class TestApplyPredictionsToTradeContext:
    """Test merging predictions into trade context."""
    
    def test_context_merge(self, base_context, sample_prediction):
        """Test predictions are merged into context."""
        enhanced = apply_predictions_to_trade_context(base_context, sample_prediction)
        
        assert "ml_prob_up" in enhanced
        assert "ml_prob_down" in enhanced
        assert "ml_expected_return" in enhanced
        assert "ml_expected_vol" in enhanced
        assert "ml_meta" in enhanced
    
    def test_context_values(self, base_context, sample_prediction):
        """Test prediction values are correctly copied."""
        enhanced = apply_predictions_to_trade_context(base_context, sample_prediction)
        
        assert enhanced["ml_prob_up"] == 0.65
        assert enhanced["ml_prob_down"] == 0.35
        assert enhanced["ml_expected_return"] == 0.03
        assert enhanced["ml_expected_vol"] == 0.20
    
    def test_original_context_preserved(self, base_context, sample_prediction):
        """Test original context fields are preserved."""
        enhanced = apply_predictions_to_trade_context(base_context, sample_prediction)
        
        assert enhanced["asset"] == "SPY"
        assert enhanced["current_price"] == 450.0
        assert enhanced["direction"] == "bullish"
        assert enhanced["confidence"] == 0.7
    
    def test_context_non_destructive(self, base_context, sample_prediction):
        """Test original context dict is not modified."""
        original_keys = set(base_context.keys())
        
        enhanced = apply_predictions_to_trade_context(base_context, sample_prediction)
        
        # Original should be unchanged
        assert set(base_context.keys()) == original_keys
        assert "ml_prob_up" not in base_context
    
    def test_meta_merge(self, base_context, sample_prediction):
        """Test meta dict is properly copied."""
        enhanced = apply_predictions_to_trade_context(base_context, sample_prediction)
        
        assert enhanced["ml_meta"]["model"] == "lightgbm"
        assert enhanced["ml_meta"]["version"] == "2.0"
