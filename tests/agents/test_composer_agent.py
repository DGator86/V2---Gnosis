"""
Comprehensive tests for Composer Agent v1.0

Tests cover:
- Field fusion (direction, confidence)
- Energy aggregation
- Conflict resolution
- Regime-based weighting
- Trade style classification
- Expected move cone generation
- Full integration scenarios
"""

import pytest
from agents.composer import ComposerAgent, EngineDirective, CompositeMarketDirective


# ============================================================================
# Test Fixtures
# ============================================================================

class MockAgent:
    """Mock agent that returns a predefined output."""
    def __init__(self, output_dict):
        self._output = output_dict
    
    def output(self):
        return self._output


def mock_price_getter(price=100.0):
    """Factory for reference price getter."""
    return lambda: price


def make_engine_directive(
    name: str = "test",
    direction: float = 0.0,
    strength: float = 0.5,
    confidence: float = 0.8,
    regime: str = "normal",
    energy: float = 0.5,
    volatility_proxy: float = None,
    features: dict = None,
) -> EngineDirective:
    """Helper to create EngineDirective for testing."""
    return EngineDirective(
        name=name,
        direction=direction,
        strength=strength,
        confidence=confidence,
        regime=regime,
        energy=energy,
        volatility_proxy=volatility_proxy,
        features=features or {},
    )


# ============================================================================
# Direction Fusion Tests
# ============================================================================

def test_all_agents_agree_bullish():
    """Test that unanimous bullish signals produce long bias."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.8, confidence=0.9))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=0.7, confidence=0.85))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=0.9, confidence=0.8))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert result.direction == 1  # Long bias
    assert result.confidence > 0.7


def test_all_agents_agree_bearish():
    """Test that unanimous bearish signals produce short bias."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=-0.8, confidence=0.9))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=-0.7, confidence=0.85))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=-0.9, confidence=0.8))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert result.direction == -1  # Short bias
    assert result.confidence > 0.7


def test_mixed_signals_produce_neutral():
    """Test that weak or conflicting signals produce neutral."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.1, confidence=0.9))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=-0.1, confidence=0.85))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=0.0, confidence=0.8))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert result.direction == 0  # Neutral


def test_conflicting_directions_resolved_by_confidence():
    """Test that high-confidence agent dominates in conflicts."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.8, confidence=0.95))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=-0.3, confidence=0.5))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=-0.2, confidence=0.6))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    # Hedge agent's high confidence should dominate
    assert result.direction == 1


# ============================================================================
# Confidence Fusion Tests
# ============================================================================

def test_confidence_weighted_average():
    """Test that confidence is properly weighted across agents."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.8, confidence=0.9))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=0.7, confidence=0.7))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=0.9, confidence=0.8))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    # Confidence should be approximately the weighted average
    assert 0.75 < result.confidence < 0.85


def test_low_confidence_agents_reduce_overall_confidence():
    """Test that low-confidence agents pull down composite confidence."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.8, confidence=0.3))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=0.7, confidence=0.4))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=0.9, confidence=0.3))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert result.confidence < 0.5


# ============================================================================
# Energy Cost Tests
# ============================================================================

def test_energy_aggregation():
    """Test that energy costs are properly aggregated."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.8, energy=2.0))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=0.7, energy=1.5))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=0.9, energy=1.0))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    # Energy should be sum of weighted energies
    assert result.energy_cost > 3.0


def test_high_energy_reduces_strength():
    """Test that high energy cost reduces effective strength."""
    high_energy = MockAgent(make_engine_directive(
        name="hedge", direction=0.8, confidence=0.9, energy=5.0
    ))
    low_energy = MockAgent(make_engine_directive(
        name="liquidity", direction=0.7, confidence=0.85, energy=0.5
    ))
    sentiment = MockAgent(make_engine_directive(
        name="sentiment", direction=0.9, confidence=0.8, energy=0.5
    ))
    
    composer = ComposerAgent(high_energy, low_energy, sentiment, mock_price_getter())
    result = composer.compose()
    
    # Strength should be discounted by high energy
    assert result.strength < 60  # Confidence ~0.85 but energy is high


# ============================================================================
# Regime-Based Weighting Tests
# ============================================================================

def test_jump_regime_favors_hedge():
    """Test that jump regime increases hedge agent weight."""
    hedge = MockAgent(make_engine_directive(
        name="hedge", direction=0.9, confidence=0.85, regime="jump"
    ))
    liquidity = MockAgent(make_engine_directive(
        name="liquidity", direction=-0.3, confidence=0.8, regime="normal"
    ))
    sentiment = MockAgent(make_engine_directive(
        name="sentiment", direction=-0.2, confidence=0.8, regime="normal"
    ))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    # Hedge should dominate in jump regime
    assert result.direction == 1


def test_vacuum_regime_favors_liquidity():
    """Test that vacuum regime increases liquidity agent weight."""
    hedge = MockAgent(make_engine_directive(
        name="hedge", direction=-0.3, confidence=0.8, regime="normal"
    ))
    liquidity = MockAgent(make_engine_directive(
        name="liquidity", direction=0.9, confidence=0.85, regime="vacuum"
    ))
    sentiment = MockAgent(make_engine_directive(
        name="sentiment", direction=-0.2, confidence=0.8, regime="normal"
    ))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    # Liquidity should dominate in vacuum regime
    assert result.direction == 1


def test_trend_regime_favors_sentiment():
    """Test that trend/markup regime increases sentiment agent weight."""
    hedge = MockAgent(make_engine_directive(
        name="hedge", direction=-0.3, confidence=0.8, regime="normal"
    ))
    liquidity = MockAgent(make_engine_directive(
        name="liquidity", direction=-0.2, confidence=0.8, regime="normal"
    ))
    sentiment = MockAgent(make_engine_directive(
        name="sentiment", direction=0.9, confidence=0.85, regime="markup"
    ))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    # Sentiment should dominate in markup regime
    assert result.direction == 1


# ============================================================================
# Trade Style Classification Tests
# ============================================================================

def test_no_trade_when_confidence_low():
    """Test that low confidence produces 'no_trade' style."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.8, confidence=0.3))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=0.7, confidence=0.3))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=0.9, confidence=0.3))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert result.trade_style == "no_trade"


def test_momentum_style_with_low_energy():
    """Test that high confidence + low energy produces 'momentum' style."""
    hedge = MockAgent(make_engine_directive(
        name="hedge", direction=0.8, confidence=0.9, energy=0.3
    ))
    liquidity = MockAgent(make_engine_directive(
        name="liquidity", direction=0.7, confidence=0.85, energy=0.2
    ))
    sentiment = MockAgent(make_engine_directive(
        name="sentiment", direction=0.9, confidence=0.8, energy=0.2
    ))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert result.trade_style == "momentum"


def test_breakout_style_with_high_energy():
    """Test that high confidence + high energy produces 'breakout' style."""
    hedge = MockAgent(make_engine_directive(
        name="hedge", direction=0.8, confidence=0.9, energy=2.0
    ))
    liquidity = MockAgent(make_engine_directive(
        name="liquidity", direction=0.7, confidence=0.85, energy=1.5
    ))
    sentiment = MockAgent(make_engine_directive(
        name="sentiment", direction=0.9, confidence=0.8, energy=1.0
    ))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert result.trade_style == "breakout"


def test_mean_revert_style_with_conflicts():
    """Test that conflicting directions produce 'mean_revert' style."""
    hedge = MockAgent(make_engine_directive(
        name="hedge", direction=0.8, confidence=0.7
    ))
    liquidity = MockAgent(make_engine_directive(
        name="liquidity", direction=-0.7, confidence=0.7
    ))
    sentiment = MockAgent(make_engine_directive(
        name="sentiment", direction=0.3, confidence=0.7
    ))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert result.trade_style == "mean_revert"


# ============================================================================
# Expected Move Cone Tests
# ============================================================================

def test_expected_move_cone_generated():
    """Test that expected move cone is properly generated."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.8))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=0.7))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=0.9))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter(100.0))
    result = composer.compose()
    
    assert result.expected_move_cone is not None
    assert result.expected_move_cone.reference_price == 100.0
    assert "15m" in result.expected_move_cone.bands
    assert "1h" in result.expected_move_cone.bands
    assert "1d" in result.expected_move_cone.bands


def test_cone_shifts_with_direction():
    """Test that expected move cone shifts based on direction."""
    # Bullish scenario
    hedge_bull = MockAgent(make_engine_directive(name="hedge", direction=0.9))
    liquidity_bull = MockAgent(make_engine_directive(name="liquidity", direction=0.8))
    sentiment_bull = MockAgent(make_engine_directive(name="sentiment", direction=0.9))
    
    composer_bull = ComposerAgent(hedge_bull, liquidity_bull, sentiment_bull, mock_price_getter(100.0))
    result_bull = composer_bull.compose()
    
    # Bearish scenario
    hedge_bear = MockAgent(make_engine_directive(name="hedge", direction=-0.9))
    liquidity_bear = MockAgent(make_engine_directive(name="liquidity", direction=-0.8))
    sentiment_bear = MockAgent(make_engine_directive(name="sentiment", direction=-0.9))
    
    composer_bear = ComposerAgent(hedge_bear, liquidity_bear, sentiment_bear, mock_price_getter(100.0))
    result_bear = composer_bear.compose()
    
    # Bullish cone should have higher center than bearish
    bull_1h = result_bull.expected_move_cone.bands["1h"]
    bear_1h = result_bear.expected_move_cone.bands["1h"]
    
    bull_center = (bull_1h.upper + bull_1h.lower) / 2
    bear_center = (bear_1h.upper + bear_1h.lower) / 2
    
    assert bull_center > bear_center


# ============================================================================
# Rationale Generation Tests
# ============================================================================

def test_rationale_includes_all_engines():
    """Test that rationale mentions all three engines."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.8))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=0.7))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=0.9))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert "Hedge" in result.rationale
    assert "Liquidity" in result.rationale
    assert "Sentiment" in result.rationale


def test_rationale_mentions_conflicts():
    """Test that rationale identifies conflicts."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.8))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=-0.7))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=0.3))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert "disagree" in result.rationale.lower() or "conflict" in result.rationale.lower()


# ============================================================================
# Output Structure Tests
# ============================================================================

def test_output_has_required_fields():
    """Test that CompositeMarketDirective has all required fields."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.8))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=0.7))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=0.9))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert isinstance(result, CompositeMarketDirective)
    assert result.direction in [-1, 0, 1]
    assert 0 <= result.strength <= 100
    assert 0 <= result.confidence <= 1
    assert result.volatility >= 0
    assert result.energy_cost >= 0
    assert result.trade_style in ["momentum", "mean_revert", "breakout", "no_trade"]
    assert result.expected_move_cone is not None
    assert isinstance(result.rationale, str)


def test_raw_engines_snapshot_included():
    """Test that raw engine data is preserved in output."""
    hedge = MockAgent(make_engine_directive(name="hedge", direction=0.8))
    liquidity = MockAgent(make_engine_directive(name="liquidity", direction=0.7))
    sentiment = MockAgent(make_engine_directive(name="sentiment", direction=0.9))
    
    composer = ComposerAgent(hedge, liquidity, sentiment, mock_price_getter())
    result = composer.compose()
    
    assert result.raw_engines is not None
    assert "hedge" in result.raw_engines
    assert "liquidity" in result.raw_engines
    assert "sentiment" in result.raw_engines
