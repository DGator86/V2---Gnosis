# tests/agents/test_sentiment_adapter.py

from engines.sentiment_agent.schemas import SentimentAgentOutput
from agents.composer.sentiment_adapter import (
    SentimentSignalForComposer,
    sentiment_output_to_composer_signal,
    sentiment_signal_to_feature_dict,
)


def test_sentiment_adapter_roundtrip_structure():
    out = SentimentAgentOutput(
        direction="bullish",
        strength=0.7,
        confidence=0.8,
        regime="markup",
        notes=["test note"],
    )

    signal = sentiment_output_to_composer_signal(out)
    assert isinstance(signal, SentimentSignalForComposer)
    assert signal.direction == "bullish"
    assert signal.strength == 0.7
    assert signal.confidence == 0.8
    assert signal.regime == "markup"
    assert signal.notes == ("test note",)

    features = sentiment_signal_to_feature_dict(signal)

    assert features["sentiment_direction"] == "bullish"
    assert features["sentiment_strength"] == 0.7
    assert features["sentiment_confidence"] == 0.8
    assert features["sentiment_regime"] == "markup"
    assert features["sentiment_notes"] == ["test note"]


def test_sentiment_feature_namespace_prefixing():
    out = SentimentAgentOutput(
        direction="bearish",
        strength=0.5,
        confidence=0.6,
        regime="markdown",
        notes=[],
    )
    signal = sentiment_output_to_composer_signal(out)
    features = sentiment_signal_to_feature_dict(signal)

    assert all(k.startswith("sentiment_") for k in features.keys())


def test_sentiment_output_to_signal_empty_notes():
    """Test conversion handles empty notes list correctly."""
    out = SentimentAgentOutput(
        direction="range-bound",
        strength=0.3,
        confidence=0.9,
        regime="sideways",
        notes=[],
    )
    
    signal = sentiment_output_to_composer_signal(out)
    
    assert signal.notes == ()
    assert isinstance(signal.notes, tuple)


def test_all_direction_types_converted():
    """Test that all sentiment direction types are correctly converted."""
    directions = [
        "bullish",
        "bearish",
        "distribution top",
        "accumulation bottom",
        "range-bound",
        "chaotic",
    ]
    
    for direction in directions:
        out = SentimentAgentOutput(
            direction=direction,
            strength=0.5,
            confidence=0.7,
            regime="markup",
            notes=[],
        )
        
        signal = sentiment_output_to_composer_signal(out)
        features = sentiment_signal_to_feature_dict(signal)
        
        assert features["sentiment_direction"] == direction


def test_signal_immutability_with_tuple():
    """Test that using tuple for notes prevents accidental mutation."""
    import pytest
    
    signal = SentimentSignalForComposer(
        direction="bullish",
        strength=0.6,
        confidence=0.8,
        regime="markup",
        notes=("note1", "note2"),
    )
    
    # Tuples are immutable
    assert isinstance(signal.notes, tuple)
    
    # This should raise an error if someone tries to mutate
    with pytest.raises((TypeError, AttributeError)):
        signal.notes.append("note3")


def test_feature_dict_values_types():
    """Test that feature dict values have correct types."""
    signal = SentimentSignalForComposer(
        direction="bearish",
        strength=0.4,
        confidence=0.7,
        regime="markdown",
        notes=("note1",),
    )
    
    features = sentiment_signal_to_feature_dict(signal)
    
    assert isinstance(features["sentiment_direction"], str)
    assert isinstance(features["sentiment_strength"], float)
    assert isinstance(features["sentiment_confidence"], float)
    assert isinstance(features["sentiment_regime"], str)
    assert isinstance(features["sentiment_notes"], list)


def test_full_pipeline_conversion():
    """Test full pipeline from SentimentAgentOutput to feature dict."""
    # Start with agent output
    out = SentimentAgentOutput(
        direction="distribution top",
        strength=0.75,
        confidence=0.55,
        regime="distribution",
        notes=[
            "overbought with weak breadth (topping risk)",
            "transition sentiment regime (noisy)",
        ],
    )
    
    # Convert to composer signal
    signal = sentiment_output_to_composer_signal(out)
    
    # Convert to feature dict
    features = sentiment_signal_to_feature_dict(signal)
    
    # Verify end-to-end transformation
    assert features["sentiment_direction"] == "distribution top"
    assert features["sentiment_strength"] == 0.75
    assert features["sentiment_confidence"] == 0.55
    assert features["sentiment_regime"] == "distribution"
    assert len(features["sentiment_notes"]) == 2


def test_no_namespace_collision_with_other_agents():
    """Test that sentiment features don't collide with hedge/liquidity features."""
    signal = SentimentSignalForComposer(
        direction="bullish",
        strength=0.6,
        confidence=0.8,
        regime="markup",
        notes=(),
    )
    
    features = sentiment_signal_to_feature_dict(signal)
    
    # Simulate hedge and liquidity features
    hedge_features = {
        "hedge_direction": "bull",
        "hedge_strength": 0.7,
        "hedge_confidence": 0.85,
    }
    
    liquidity_features = {
        "liquidity_direction": "supportive",
        "liquidity_strength": 0.65,
        "liquidity_confidence": 0.75,
    }
    
    # Merge all feature dicts
    merged = {**hedge_features, **liquidity_features, **features}
    
    # No key collisions - all prefixes are unique
    assert len(merged) == len(hedge_features) + len(liquidity_features) + len(features)
    assert "sentiment_direction" in merged
    assert "hedge_direction" in merged
    assert "liquidity_direction" in merged


def test_chaotic_direction_preserved():
    """Test that chaotic direction is preserved through conversion."""
    out = SentimentAgentOutput(
        direction="chaotic",
        strength=0.3,
        confidence=0.15,
        regime="transition",
        notes=["very low confidence", "multiple conflicting signals"],
    )
    
    signal = sentiment_output_to_composer_signal(out)
    features = sentiment_signal_to_feature_dict(signal)
    
    assert features["sentiment_direction"] == "chaotic"
    assert features["sentiment_confidence"] < 0.2
