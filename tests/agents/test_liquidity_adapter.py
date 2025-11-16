"""
Tests for Liquidity Agent Composer adapter.

Tests the glue layer that converts LiquidityAgentOutput into
Composer-native signals and feature dictionaries.
"""

import pytest

from engines.liquidity_agent.schemas import LiquidityAgentOutput
from agents.composer.liquidity_adapter import (
    LiquiditySignalForComposer,
    liquidity_output_to_composer_signal,
    liquidity_signal_to_feature_dict,
)


def test_liquidity_signal_for_composer_structure():
    """Test that LiquiditySignalForComposer has the expected structure."""
    signal = LiquiditySignalForComposer(
        direction="supportive",
        strength=0.6,
        confidence=0.8,
        regime="stable",
        notes=("note1", "note2"),
    )
    
    assert signal.direction == "supportive"
    assert signal.strength == 0.6
    assert signal.confidence == 0.8
    assert signal.regime == "stable"
    assert signal.notes == ("note1", "note2")


def test_liquidity_output_to_composer_signal_conversion():
    """Test conversion from LiquidityAgentOutput to LiquiditySignalForComposer."""
    output = LiquidityAgentOutput(
        direction="fragile",
        strength=0.75,
        confidence=0.65,
        regime="transition",
        notes=["liquidity vacuum regime", "aggressive sell imbalance"],
    )
    
    signal = liquidity_output_to_composer_signal(output)
    
    assert isinstance(signal, LiquiditySignalForComposer)
    assert signal.direction == "fragile"
    assert signal.strength == 0.75
    assert signal.confidence == 0.65
    assert signal.regime == "transition"
    assert signal.notes == ("liquidity vacuum regime", "aggressive sell imbalance")
    assert isinstance(signal.notes, tuple)  # Should be converted to tuple


def test_liquidity_output_to_composer_signal_empty_notes():
    """Test conversion handles empty notes list correctly."""
    output = LiquidityAgentOutput(
        direction="balanced",
        strength=0.2,
        confidence=0.9,
        regime="stable",
        notes=[],
    )
    
    signal = liquidity_output_to_composer_signal(output)
    
    assert signal.notes == ()
    assert isinstance(signal.notes, tuple)


def test_liquidity_signal_to_feature_dict_basic():
    """Test conversion of signal to feature dictionary."""
    signal = LiquiditySignalForComposer(
        direction="supportive",
        strength=0.6,
        confidence=0.8,
        regime="stable",
        notes=("note1", "note2"),
    )
    
    features = liquidity_signal_to_feature_dict(signal)
    
    assert isinstance(features, dict)
    assert features["liquidity_direction"] == "supportive"
    assert features["liquidity_strength"] == 0.6
    assert features["liquidity_confidence"] == 0.8
    assert features["liquidity_regime"] == "stable"
    assert features["liquidity_notes"] == ["note1", "note2"]
    assert isinstance(features["liquidity_notes"], list)  # Should be list in feature dict


def test_liquidity_signal_to_feature_dict_prefixed_keys():
    """Test that all feature dictionary keys are prefixed with 'liquidity_'."""
    signal = LiquiditySignalForComposer(
        direction="fragile",
        strength=0.4,
        confidence=0.7,
        regime="vacuum",
        notes=(),
    )
    
    features = liquidity_signal_to_feature_dict(signal)
    
    # All keys should start with "liquidity_"
    for key in features.keys():
        assert key.startswith("liquidity_"), f"Key '{key}' should be prefixed with 'liquidity_'"


def test_liquidity_signal_to_feature_dict_empty_notes():
    """Test feature dict handles empty notes correctly."""
    signal = LiquiditySignalForComposer(
        direction="balanced",
        strength=0.3,
        confidence=0.85,
        regime="stable",
        notes=(),
    )
    
    features = liquidity_signal_to_feature_dict(signal)
    
    assert features["liquidity_notes"] == []
    assert isinstance(features["liquidity_notes"], list)


def test_full_pipeline_output_to_features():
    """Test full pipeline from LiquidityAgentOutput to feature dict."""
    # Start with agent output
    output = LiquidityAgentOutput(
        direction="liquidity vacuum up",
        strength=0.85,
        confidence=0.42,
        regime="vacuum",
        notes=[
            "liquidity vacuum regime",
            "worse-than-expected realized slippage",
            "high volatility of liquidity (unstable book)",
        ],
    )
    
    # Convert to composer signal
    signal = liquidity_output_to_composer_signal(output)
    
    # Convert to feature dict
    features = liquidity_signal_to_feature_dict(signal)
    
    # Verify end-to-end transformation
    assert features["liquidity_direction"] == "liquidity vacuum up"
    assert features["liquidity_strength"] == 0.85
    assert features["liquidity_confidence"] == 0.42
    assert features["liquidity_regime"] == "vacuum"
    assert len(features["liquidity_notes"]) == 3
    assert "liquidity vacuum regime" in features["liquidity_notes"]


def test_chaotic_direction_preserved():
    """Test that chaotic direction is preserved through conversion."""
    output = LiquidityAgentOutput(
        direction="chaotic",
        strength=0.5,
        confidence=0.15,
        regime="transition",
        notes=["very low confidence"],
    )
    
    signal = liquidity_output_to_composer_signal(output)
    features = liquidity_signal_to_feature_dict(signal)
    
    assert features["liquidity_direction"] == "chaotic"
    assert features["liquidity_confidence"] < 0.2


def test_all_direction_types_supported():
    """Test that all direction types are correctly converted."""
    directions = [
        "supportive",
        "fragile",
        "balanced",
        "liquidity vacuum up",
        "liquidity vacuum down",
        "liquidity vacuum",
        "chaotic",
    ]
    
    for direction in directions:
        output = LiquidityAgentOutput(
            direction=direction,
            strength=0.5,
            confidence=0.7,
            regime="stable",
            notes=[],
        )
        
        signal = liquidity_output_to_composer_signal(output)
        features = liquidity_signal_to_feature_dict(signal)
        
        assert features["liquidity_direction"] == direction


def test_feature_dict_values_types():
    """Test that feature dict values have correct types."""
    signal = LiquiditySignalForComposer(
        direction="supportive",
        strength=0.6,
        confidence=0.8,
        regime="stable",
        notes=("note1",),
    )
    
    features = liquidity_signal_to_feature_dict(signal)
    
    assert isinstance(features["liquidity_direction"], str)
    assert isinstance(features["liquidity_strength"], float)
    assert isinstance(features["liquidity_confidence"], float)
    assert isinstance(features["liquidity_regime"], str)
    assert isinstance(features["liquidity_notes"], list)


def test_signal_immutability_with_tuple():
    """Test that using tuple for notes prevents accidental mutation."""
    signal = LiquiditySignalForComposer(
        direction="supportive",
        strength=0.6,
        confidence=0.8,
        regime="stable",
        notes=("note1", "note2"),
    )
    
    # Tuples are immutable
    assert isinstance(signal.notes, tuple)
    
    # This should raise an error if someone tries to mutate
    with pytest.raises((TypeError, AttributeError)):
        signal.notes.append("note3")


def test_feature_dict_no_namespace_collision():
    """Test that liquidity features don't collide with potential hedge/sentiment features."""
    signal = LiquiditySignalForComposer(
        direction="supportive",
        strength=0.6,
        confidence=0.8,
        regime="stable",
        notes=(),
    )
    
    features = liquidity_signal_to_feature_dict(signal)
    
    # Simulate hedge and sentiment features (without actual implementation)
    hedge_features = {
        "hedge_direction": "bull",
        "hedge_strength": 0.7,
        "hedge_confidence": 0.85,
    }
    
    sentiment_features = {
        "sentiment_direction": "bullish",
        "sentiment_strength": 0.65,
        "sentiment_confidence": 0.75,
    }
    
    # Merge all feature dicts
    merged = {**hedge_features, **sentiment_features, **features}
    
    # No key collisions - all prefixes are unique
    assert len(merged) == len(hedge_features) + len(sentiment_features) + len(features)
    assert "liquidity_direction" in merged
    assert "hedge_direction" in merged
    assert "sentiment_direction" in merged
