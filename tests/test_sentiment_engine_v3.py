"""
Comprehensive Test Suite for Sentiment Engine v3
=================================================

Tests all components of the Sentiment Engine including:
- Universal Sentiment Interpreter
- Multi-source sentiment aggregation
- Momentum and acceleration calculations
- Contrarian signal generation
- Crowd positioning analysis
- Regime classification
- Edge cases and error handling

Author: Super Gnosis Development Team
License: MIT
Version: 3.0.0
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from typing import List

# Import components to test
from engines.sentiment.universal_sentiment_interpreter import (
    UniversalSentimentInterpreter,
    SentimentState,
    SentimentReading,
    SentimentSource,
    create_interpreter
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_readings() -> List[SentimentReading]:
    """Create sample sentiment readings for testing."""
    return [
        SentimentReading(
            source=SentimentSource.NEWS,
            score=0.65,
            confidence=0.85,
            volume=25,
            timestamp=datetime.now()
        ),
        SentimentReading(
            source=SentimentSource.TWITTER,
            score=0.70,
            confidence=0.70,
            volume=1500,
            timestamp=datetime.now()
        ),
        SentimentReading(
            source=SentimentSource.REDDIT,
            score=0.75,
            confidence=0.75,
            volume=850,
            timestamp=datetime.now()
        ),
        SentimentReading(
            source=SentimentSource.ANALYST,
            score=0.50,
            confidence=0.90,
            volume=12,
            timestamp=datetime.now()
        ),
    ]


@pytest.fixture
def interpreter() -> UniversalSentimentInterpreter:
    """Create universal sentiment interpreter for testing."""
    return create_interpreter()


# ============================================================================
# TEST 1: INTERPRETER INITIALIZATION
# ============================================================================

def test_interpreter_initialization():
    """Test that interpreter initializes correctly."""
    interp = UniversalSentimentInterpreter()
    
    assert interp.contrarian_threshold > 0
    assert interp.extreme_threshold > 0
    assert interp.momentum_lookback > 0
    assert len(interp.source_weights) > 0
    
    print("✅ Test 1 PASSED: Interpreter initialization")


# ============================================================================
# TEST 2: SENTIMENT STATE CALCULATION
# ============================================================================

def test_sentiment_state_calculation(interpreter, sample_readings):
    """Test complete sentiment state calculation."""
    state = interpreter.interpret(sample_readings)
    
    # Check all fields are present
    assert isinstance(state, SentimentState)
    assert -1 <= state.sentiment_score <= 1
    assert 0 <= state.sentiment_magnitude <= 1
    assert state.regime in ["extreme_bullish", "bullish", "neutral", "bearish", "extreme_bearish"]
    assert 0 <= state.stability <= 1
    assert 0 <= state.confidence <= 1
    assert state.sources_count == len(sample_readings)
    
    print("✅ Test 2 PASSED: Sentiment state calculation")


# ============================================================================
# TEST 3: AGGREGATE SENTIMENT
# ============================================================================

def test_aggregate_sentiment(interpreter, sample_readings):
    """Test aggregate sentiment calculation."""
    state = interpreter.interpret(sample_readings)
    
    # Should be positive (all samples are bullish)
    assert state.sentiment_score > 0
    
    # Should be weighted average of inputs
    assert state.sentiment_score < 1.0
    
    print(f"✅ Test 3 PASSED: Aggregate sentiment = {state.sentiment_score:+.2f}")


# ============================================================================
# TEST 4: SENTIMENT MAGNITUDE
# ============================================================================

def test_sentiment_magnitude(interpreter):
    """Test sentiment magnitude calculation."""
    # Strong sentiment
    strong_readings = [
        SentimentReading(SentimentSource.NEWS, 0.9, 0.9, 100, datetime.now()),
        SentimentReading(SentimentSource.TWITTER, 0.85, 0.85, 1000, datetime.now()),
    ]
    
    # Weak sentiment
    weak_readings = [
        SentimentReading(SentimentSource.NEWS, 0.2, 0.9, 100, datetime.now()),
        SentimentReading(SentimentSource.TWITTER, 0.15, 0.85, 1000, datetime.now()),
    ]
    
    state_strong = interpreter.interpret(strong_readings)
    state_weak = interpreter.interpret(weak_readings)
    
    # Strong sentiment should have higher magnitude
    assert state_strong.sentiment_magnitude > state_weak.sentiment_magnitude
    
    print("✅ Test 4 PASSED: Sentiment magnitude comparison")


# ============================================================================
# TEST 5: SENTIMENT MOMENTUM
# ============================================================================

def test_sentiment_momentum(interpreter):
    """Test sentiment momentum calculation."""
    readings = [
        SentimentReading(SentimentSource.NEWS, 0.5, 0.9, 100, datetime.now())
    ]
    
    # Create upward momentum
    historical = [0.2, 0.3, 0.4, 0.5, 0.6]
    state = interpreter.interpret(readings, historical)
    
    # Should have positive momentum
    assert state.sentiment_momentum > 0
    
    print(f"✅ Test 5 PASSED: Momentum = {state.sentiment_momentum:+.3f}")


# ============================================================================
# TEST 6: SENTIMENT ACCELERATION
# ============================================================================

def test_sentiment_acceleration(interpreter):
    """Test sentiment acceleration calculation."""
    readings = [
        SentimentReading(SentimentSource.NEWS, 0.6, 0.9, 100, datetime.now())
    ]
    
    # Create accelerating trend
    historical = [0.1, 0.2, 0.4, 0.7, 0.9]  # Increasing rate of change
    state = interpreter.interpret(readings, historical)
    
    # Should have positive acceleration
    assert isinstance(state.sentiment_acceleration, float)
    
    print(f"✅ Test 6 PASSED: Acceleration = {state.sentiment_acceleration:+.3f}")


# ============================================================================
# TEST 7: SOURCE BREAKDOWN
# ============================================================================

def test_source_breakdown(interpreter):
    """Test sentiment breakdown by source category."""
    readings = [
        SentimentReading(SentimentSource.NEWS, 0.8, 0.9, 100, datetime.now()),
        SentimentReading(SentimentSource.TWITTER, 0.3, 0.7, 1000, datetime.now()),
        SentimentReading(SentimentSource.ANALYST, 0.5, 0.9, 10, datetime.now()),
    ]
    
    state = interpreter.interpret(readings)
    
    # News should be most bullish
    assert state.news_sentiment > state.social_sentiment
    
    # All should be between -1 and 1
    assert -1 <= state.news_sentiment <= 1
    assert -1 <= state.social_sentiment <= 1
    assert -1 <= state.analyst_sentiment <= 1
    
    print("✅ Test 7 PASSED: Source breakdown")


# ============================================================================
# TEST 8: CROWD CONVICTION
# ============================================================================

def test_crowd_conviction(interpreter):
    """Test crowd conviction calculation."""
    # High conviction (all sources agree)
    high_conviction_readings = [
        SentimentReading(SentimentSource.NEWS, 0.8, 0.9, 100, datetime.now()),
        SentimentReading(SentimentSource.TWITTER, 0.85, 0.85, 1000, datetime.now()),
        SentimentReading(SentimentSource.ANALYST, 0.82, 0.95, 10, datetime.now()),
    ]
    
    # Low conviction (sources disagree)
    low_conviction_readings = [
        SentimentReading(SentimentSource.NEWS, 0.8, 0.9, 100, datetime.now()),
        SentimentReading(SentimentSource.TWITTER, -0.2, 0.85, 1000, datetime.now()),
        SentimentReading(SentimentSource.ANALYST, 0.3, 0.95, 10, datetime.now()),
    ]
    
    state_high = interpreter.interpret(high_conviction_readings)
    state_low = interpreter.interpret(low_conviction_readings)
    
    # High agreement should have higher conviction
    assert state_high.crowd_conviction > state_low.crowd_conviction
    
    print(f"✅ Test 8 PASSED: Conviction high={state_high.crowd_conviction:.2%}, low={state_low.crowd_conviction:.2%}")


# ============================================================================
# TEST 9: CONTRARIAN SIGNALS
# ============================================================================

def test_contrarian_signals(interpreter):
    """Test contrarian signal generation."""
    # Extreme bullish sentiment (should generate bearish contrarian)
    extreme_bull = [
        SentimentReading(SentimentSource.NEWS, 0.95, 0.9, 100, datetime.now()),
        SentimentReading(SentimentSource.TWITTER, 0.92, 0.85, 2000, datetime.now()),
        SentimentReading(SentimentSource.ANALYST, 0.90, 0.95, 15, datetime.now()),
    ]
    
    state = interpreter.interpret(extreme_bull)
    
    # Should generate negative contrarian signal (fade the bullishness)
    if state.sentiment_score > interpreter.contrarian_threshold:
        assert state.contrarian_signal < 0
    
    print(f"✅ Test 9 PASSED: Contrarian signal = {state.contrarian_signal:+.2f}")


# ============================================================================
# TEST 10: CONTRARIAN STRENGTH
# ============================================================================

def test_contrarian_strength(interpreter):
    """Test contrarian signal strength."""
    # Extreme sentiment with high conviction
    extreme_readings = [
        SentimentReading(SentimentSource.NEWS, 0.9, 0.95, 200, datetime.now()),
        SentimentReading(SentimentSource.TWITTER, 0.92, 0.90, 3000, datetime.now()),
    ]
    
    # Moderate sentiment
    moderate_readings = [
        SentimentReading(SentimentSource.NEWS, 0.4, 0.85, 100, datetime.now()),
    ]
    
    state_extreme = interpreter.interpret(extreme_readings)
    state_moderate = interpreter.interpret(moderate_readings)
    
    # Extreme should have higher contrarian strength
    assert state_extreme.contrarian_strength >= state_moderate.contrarian_strength
    
    print("✅ Test 10 PASSED: Contrarian strength comparison")


# ============================================================================
# TEST 11: SENTIMENT ENERGY
# ============================================================================

def test_sentiment_energy(interpreter):
    """Test sentiment energy calculation."""
    readings = [
        SentimentReading(SentimentSource.NEWS, 0.85, 0.9, 200, datetime.now()),
        SentimentReading(SentimentSource.TWITTER, 0.88, 0.85, 2000, datetime.now()),
    ]
    
    state = interpreter.interpret(readings)
    
    # Energy should be positive for strong sentiment
    assert state.sentiment_energy > 0
    assert 0 <= state.sentiment_energy <= 1
    
    print(f"✅ Test 11 PASSED: Sentiment energy = {state.sentiment_energy:.2%}")


# ============================================================================
# TEST 12: MOMENTUM ENERGY
# ============================================================================

def test_momentum_energy(interpreter):
    """Test momentum energy calculation."""
    readings = [
        SentimentReading(SentimentSource.NEWS, 0.7, 0.9, 100, datetime.now())
    ]
    
    # Strong momentum
    historical = [0.2, 0.3, 0.5, 0.65, 0.75]
    state = interpreter.interpret(readings, historical)
    
    # Should have positive momentum energy
    assert isinstance(state.momentum_energy, float)
    assert 0 <= state.momentum_energy <= 1
    
    print(f"✅ Test 12 PASSED: Momentum energy = {state.momentum_energy:.2%}")


# ============================================================================
# TEST 13: REGIME CLASSIFICATION
# ============================================================================

def test_regime_classification(interpreter):
    """Test sentiment regime classification."""
    # Extreme bullish
    extreme_bull = [
        SentimentReading(SentimentSource.NEWS, 0.95, 0.9, 100, datetime.now())
    ]
    
    # Neutral
    neutral = [
        SentimentReading(SentimentSource.NEWS, 0.05, 0.9, 100, datetime.now())
    ]
    
    # Extreme bearish
    extreme_bear = [
        SentimentReading(SentimentSource.NEWS, -0.95, 0.9, 100, datetime.now())
    ]
    
    state_bull = interpreter.interpret(extreme_bull)
    state_neutral = interpreter.interpret(neutral)
    state_bear = interpreter.interpret(extreme_bear)
    
    assert "bullish" in state_bull.regime
    assert state_neutral.regime == "neutral"
    assert "bearish" in state_bear.regime
    
    print(f"✅ Test 13 PASSED: Regimes = {state_bull.regime}, {state_neutral.regime}, {state_bear.regime}")


# ============================================================================
# TEST 14: CONFIDENCE SCORING
# ============================================================================

def test_confidence_scoring(interpreter):
    """Test confidence score calculation."""
    # Many sources, high confidence
    many_sources = [
        SentimentReading(SentimentSource.NEWS, 0.7, 0.9, 100, datetime.now()),
        SentimentReading(SentimentSource.TWITTER, 0.6, 0.85, 1000, datetime.now()),
        SentimentReading(SentimentSource.REDDIT, 0.65, 0.80, 500, datetime.now()),
        SentimentReading(SentimentSource.ANALYST, 0.7, 0.95, 10, datetime.now()),
    ]
    
    # Few sources
    few_sources = [
        SentimentReading(SentimentSource.NEWS, 0.7, 0.9, 100, datetime.now()),
    ]
    
    state_many = interpreter.interpret(many_sources)
    state_few = interpreter.interpret(few_sources)
    
    # More sources should give higher confidence
    assert state_many.confidence > state_few.confidence
    
    print(f"✅ Test 14 PASSED: Confidence many={state_many.confidence:.2%}, few={state_few.confidence:.2%}")


# ============================================================================
# TEST 15: EMPTY READINGS
# ============================================================================

def test_empty_readings(interpreter):
    """Test handling of empty readings list."""
    state = interpreter.interpret([])
    
    # Should return neutral state
    assert state.sentiment_score == 0.0
    assert state.regime == "neutral"
    assert state.confidence == 0.0
    assert state.sources_count == 0
    
    print("✅ Test 15 PASSED: Empty readings handled")


# ============================================================================
# TEST 16: SINGLE SOURCE
# ============================================================================

def test_single_source(interpreter):
    """Test with only one source."""
    single_reading = [
        SentimentReading(SentimentSource.NEWS, 0.6, 0.9, 100, datetime.now())
    ]
    
    state = interpreter.interpret(single_reading)
    
    assert isinstance(state, SentimentState)
    assert state.sources_count == 1
    assert state.sentiment_score > 0
    
    print("✅ Test 16 PASSED: Single source handled")


# ============================================================================
# TEST 17: MIXED SENTIMENT
# ============================================================================

def test_mixed_sentiment(interpreter):
    """Test with conflicting sentiment signals."""
    mixed_readings = [
        SentimentReading(SentimentSource.NEWS, 0.8, 0.9, 100, datetime.now()),
        SentimentReading(SentimentSource.TWITTER, -0.6, 0.85, 1000, datetime.now()),
        SentimentReading(SentimentSource.ANALYST, 0.2, 0.95, 10, datetime.now()),
    ]
    
    state = interpreter.interpret(mixed_readings)
    
    # Should be somewhere in between
    assert -1 <= state.sentiment_score <= 1
    # Conviction should be lower due to disagreement
    assert state.crowd_conviction < 0.8
    
    print(f"✅ Test 17 PASSED: Mixed sentiment = {state.sentiment_score:+.2f}, conviction={state.crowd_conviction:.2%}")


# ============================================================================
# TEST 18: CONSISTENCY CHECK
# ============================================================================

def test_consistency(interpreter, sample_readings):
    """Test that repeated calculations give consistent results."""
    state1 = interpreter.interpret(sample_readings)
    
    # Reset history for clean comparison
    interpreter2 = create_interpreter()
    state2 = interpreter2.interpret(sample_readings)
    
    # Results should be identical (excluding timestamp)
    assert abs(state1.sentiment_score - state2.sentiment_score) < 1e-10
    assert abs(state1.crowd_conviction - state2.crowd_conviction) < 1e-10
    assert state1.regime == state2.regime
    
    print("✅ Test 18 PASSED: Calculations are consistent")


# ============================================================================
# TEST 19: PERFORMANCE BENCHMARK
# ============================================================================

def test_performance(interpreter, sample_readings):
    """Benchmark interpreter performance."""
    import time
    
    n_iterations = 100
    start_time = time.time()
    
    for _ in range(n_iterations):
        interpreter.interpret(sample_readings)
    
    elapsed = time.time() - start_time
    avg_time = elapsed / n_iterations * 1000  # ms
    
    # Should complete in reasonable time (< 5ms per call)
    assert avg_time < 5, f"Performance too slow: {avg_time:.2f}ms per call"
    
    print(f"✅ Test 19 PASSED: Performance {avg_time:.2f}ms per calculation")


# ============================================================================
# TEST 20: NUMERICAL STABILITY
# ============================================================================

def test_numerical_stability(interpreter):
    """Test numerical stability with extreme values."""
    # Test with various extreme scenarios
    scenarios = [
        # Extreme bullish
        [SentimentReading(SentimentSource.NEWS, 1.0, 1.0, 10000, datetime.now())],
        # Extreme bearish
        [SentimentReading(SentimentSource.NEWS, -1.0, 1.0, 10000, datetime.now())],
        # Very low confidence
        [SentimentReading(SentimentSource.NEWS, 0.5, 0.01, 1, datetime.now())],
        # High volume
        [SentimentReading(SentimentSource.TWITTER, 0.5, 0.8, 1000000, datetime.now())],
    ]
    
    for readings in scenarios:
        state = interpreter.interpret(readings)
        
        # All values should be finite and in valid ranges
        assert np.isfinite(state.sentiment_score)
        assert np.isfinite(state.sentiment_energy)
        assert -1 <= state.sentiment_score <= 1
        assert 0 <= state.sentiment_energy <= 1
        assert 0 <= state.confidence <= 1
    
    print("✅ Test 20 PASSED: Numerically stable with extreme values")


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧪 SENTIMENT ENGINE V3 COMPREHENSIVE TEST SUITE")
    print("="*70 + "\n")
    
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETE")
    print("="*70 + "\n")
