"""
Integration tests for Agent .output() methods with Composer.

Tests the full integration path:
Engine → Agent.set_engine_output() → Agent.output() → Composer.compose()
"""

from datetime import datetime
from typing import Dict, Any

import pytest

from agents.hedge_agent_v3 import HedgeAgentV3
from agents.liquidity_agent_v1 import LiquidityAgentV1
from agents.sentiment_agent_v1 import SentimentAgentV1
from agents.composer.composer_agent import ComposerAgent
from agents.composer.schemas import EngineDirective, CompositeMarketDirective
from schemas.core_schemas import EngineOutput
from engines.sentiment.models import SentimentEnvelope


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_hedge_config() -> Dict[str, Any]:
    """Mock configuration for HedgeAgentV3."""
    return {
        "energy_threshold_low": 100.0,
        "energy_threshold_high": 1000.0,
        "asymmetry_threshold": 1.2,
        "gamma_sign_threshold": 0.5,
        "high_elasticity_threshold": 5.0,
        "pressure_threshold": 1e6,
        "pressure_normalization_scale": 1e6,
        "energy_normalization_scale": 1000.0,
    }


@pytest.fixture
def mock_liquidity_config() -> Dict[str, Any]:
    """Mock configuration for LiquidityAgentV1."""
    return {
        "thin_threshold": 0.001,
        "one_sided_threshold": 0.6,
    }


@pytest.fixture
def mock_sentiment_config() -> Dict[str, Any]:
    """Mock configuration for SentimentAgentV1."""
    return {
        "bullish_threshold": 0.2,
        "bearish_threshold": 0.2,
    }


@pytest.fixture
def mock_price_getter():
    """Mock price getter for Composer."""
    return lambda: 100.0


# ============================================================================
# HedgeAgentV3 .output() Tests
# ============================================================================

def test_hedge_agent_output_bullish(mock_hedge_config):
    """Test HedgeAgentV3.output() with bullish pressure."""
    agent = HedgeAgentV3(mock_hedge_config)
    
    # Create mock engine output with bullish pressure
    engine_output = EngineOutput(
        kind="hedge",
        symbol="SPY",
        timestamp=datetime.now(),
        features={
            "net_pressure": 500000.0,  # Positive pressure = upward bias
            "pressure_up": 800000.0,
            "pressure_down": 300000.0,
            "elasticity": 1.5,
            "movement_energy": 150.0,
            "movement_energy_up": 100.0,
            "movement_energy_down": 200.0,
            "energy_asymmetry": 0.5,  # Easier to move up
            "gamma_pressure": 50000.0,
            "dealer_gamma_sign": 0.8,
        },
        confidence=0.85,
        regime="long_gamma_dampening",
        metadata={
            "gamma_regime": "long_gamma",
            "potential_shape": "single_well",
        },
    )
    
    agent.set_engine_output(engine_output)
    directive = agent.output()
    
    # Verify directive structure
    assert isinstance(directive, EngineDirective)
    assert directive.name == "hedge"
    assert directive.direction > 0.0  # Bullish
    assert 0.0 <= directive.confidence <= 1.0
    assert directive.regime == "long_gamma_dampening"
    assert directive.energy > 0.0
    assert "hedge." in list(directive.features.keys())[0]  # Namespaced
    assert "HedgeAgentV3" in directive.notes


def test_hedge_agent_output_bearish(mock_hedge_config):
    """Test HedgeAgentV3.output() with bearish pressure."""
    agent = HedgeAgentV3(mock_hedge_config)
    
    engine_output = EngineOutput(
        kind="hedge",
        symbol="SPY",
        timestamp=datetime.now(),
        features={
            "net_pressure": -500000.0,  # Negative pressure = downward bias
            "elasticity": 2.0,
            "movement_energy": 200.0,
            "energy_asymmetry": 2.0,  # Easier to move down
            "dealer_gamma_sign": -0.7,
        },
        confidence=0.75,
        regime="short_gamma_squeeze",
        metadata={"gamma_regime": "short_gamma"},
    )
    
    agent.set_engine_output(engine_output)
    directive = agent.output()
    
    assert directive.direction < 0.0  # Bearish
    assert directive.confidence == 0.75


def test_hedge_agent_output_without_engine_raises():
    """Test that .output() raises if no engine output is set."""
    agent = HedgeAgentV3({})
    
    with pytest.raises(RuntimeError, match="has no engine output"):
        agent.output()


# ============================================================================
# LiquidityAgentV1 .output() Tests
# ============================================================================

def test_liquidity_agent_output_bullish(mock_liquidity_config):
    """Test LiquidityAgentV1.output() with bullish POLR."""
    agent = LiquidityAgentV1(mock_liquidity_config)
    
    engine_output = EngineOutput(
        kind="liquidity",
        symbol="SPY",
        timestamp=datetime.now(),
        features={
            "liquidity_score": 0.8,
            "friction_cost": 0.002,
            "polr_direction": 0.7,  # Bullish POLR
            "polr_strength": 0.85,
            "orderbook_imbalance": 0.6,
            "compression_energy": 0.3,
            "expansion_energy": 0.1,
            "amihud_illiquidity": 0.0001,
            "sweep_detected": 1.0,
            "iceberg_detected": 0.0,
        },
        confidence=0.8,
        regime="Normal",
        metadata={
            "liquidity_regime": "Normal",
            "wyckoff_phase": "Phase_C",
        },
    )
    
    agent.set_engine_output(engine_output)
    directive = agent.output()
    
    assert isinstance(directive, EngineDirective)
    assert directive.name == "liquidity"
    assert directive.direction > 0.0  # Bullish
    assert directive.strength > 0.0
    assert directive.regime == "Normal"
    assert "liquidity." in list(directive.features.keys())[0]
    assert "sweep_alert" in directive.notes


def test_liquidity_agent_output_bearish(mock_liquidity_config):
    """Test LiquidityAgentV1.output() with bearish flow."""
    agent = LiquidityAgentV1(mock_liquidity_config)
    
    engine_output = EngineOutput(
        kind="liquidity",
        symbol="SPY",
        timestamp=datetime.now(),
        features={
            "liquidity_score": 0.6,
            "friction_cost": 0.005,
            "polr_direction": -0.6,  # Bearish POLR
            "polr_strength": 0.7,
            "orderbook_imbalance": -0.5,
        },
        confidence=0.7,
        regime="Thin",
        metadata={"liquidity_regime": "Thin"},
    )
    
    agent.set_engine_output(engine_output)
    directive = agent.output()
    
    assert directive.direction < 0.0  # Bearish
    assert directive.regime == "Thin"


# ============================================================================
# SentimentAgentV1 .output() Tests
# ============================================================================

def test_sentiment_agent_output_bullish(mock_sentiment_config):
    """Test SentimentAgentV1.output() with bullish sentiment."""
    agent = SentimentAgentV1(mock_sentiment_config)
    
    envelope = SentimentEnvelope(
        bias="bullish",
        strength=0.75,
        energy=2.5,
        confidence=0.8,
        drivers={
            "wyckoff": 0.7,
            "oscillators": 0.6,
            "flow": 0.8,
        },
        wyckoff_phase="Phase_D",
        liquidity_regime="markup",
        volatility_regime="expansion",
        flow_regime="bullish_flow",
    )
    
    agent.set_sentiment_envelope(envelope)
    directive = agent.output()
    
    assert isinstance(directive, EngineDirective)
    assert directive.name == "sentiment"
    assert directive.direction > 0.0  # Bullish
    assert directive.strength == 0.75
    assert directive.confidence == 0.8
    assert directive.regime == "markup"
    assert "sentiment." in list(directive.features.keys())[0]
    assert "Phase_D" in directive.notes


def test_sentiment_agent_output_bearish(mock_sentiment_config):
    """Test SentimentAgentV1.output() with bearish sentiment."""
    agent = SentimentAgentV1(mock_sentiment_config)
    
    envelope = SentimentEnvelope(
        bias="bearish",
        strength=0.6,
        energy=1.8,
        confidence=0.7,
        drivers={
            "wyckoff": -0.5,
            "oscillators": -0.7,
        },
        liquidity_regime="markdown",
    )
    
    agent.set_sentiment_envelope(envelope)
    directive = agent.output()
    
    assert directive.direction < 0.0  # Bearish
    assert directive.regime == "markdown"


def test_sentiment_agent_output_neutral(mock_sentiment_config):
    """Test SentimentAgentV1.output() with neutral sentiment."""
    agent = SentimentAgentV1(mock_sentiment_config)
    
    envelope = SentimentEnvelope(
        bias="neutral",
        strength=0.3,
        energy=0.5,
        confidence=0.4,
        drivers={},
    )
    
    agent.set_sentiment_envelope(envelope)
    directive = agent.output()
    
    assert directive.direction == 0.0  # Neutral


# ============================================================================
# Full Composer Integration Tests
# ============================================================================

def test_composer_with_real_agent_directives(
    mock_hedge_config,
    mock_liquidity_config,
    mock_sentiment_config,
    mock_price_getter,
):
    """Test full integration: Agents → Composer → CompositeMarketDirective."""
    # Initialize agents
    hedge_agent = HedgeAgentV3(mock_hedge_config)
    liquidity_agent = LiquidityAgentV1(mock_liquidity_config)
    sentiment_agent = SentimentAgentV1(mock_sentiment_config)
    
    # Set up hedge engine output (bullish)
    hedge_output = EngineOutput(
        kind="hedge",
        symbol="SPY",
        timestamp=datetime.now(),
        features={
            "net_pressure": 800000.0,
            "elasticity": 1.2,
            "movement_energy": 120.0,
            "energy_asymmetry": 0.6,
            "dealer_gamma_sign": 0.5,
        },
        confidence=0.85,
        regime="normal",
        metadata={},
    )
    hedge_agent.set_engine_output(hedge_output)
    
    # Set up liquidity engine output (bullish)
    liquidity_output = EngineOutput(
        kind="liquidity",
        symbol="SPY",
        timestamp=datetime.now(),
        features={
            "liquidity_score": 0.8,
            "friction_cost": 0.002,
            "polr_direction": 0.7,
            "polr_strength": 0.8,
        },
        confidence=0.8,
        regime="Normal",
        metadata={"liquidity_regime": "Normal"},
    )
    liquidity_agent.set_engine_output(liquidity_output)
    
    # Set up sentiment envelope (bullish)
    sentiment_envelope = SentimentEnvelope(
        bias="bullish",
        strength=0.75,
        energy=2.0,
        confidence=0.8,
        drivers={"wyckoff": 0.7},
        liquidity_regime="markup",
    )
    sentiment_agent.set_sentiment_envelope(sentiment_envelope)
    
    # Create composer
    composer = ComposerAgent(
        hedge_agent=hedge_agent,
        liquidity_agent=liquidity_agent,
        sentiment_agent=sentiment_agent,
        reference_price_getter=mock_price_getter,
    )
    
    # Compose directive
    directive = composer.compose()
    
    # Verify composite directive
    assert isinstance(directive, CompositeMarketDirective)
    assert directive.direction in [-1, 0, 1]
    assert directive.direction == 1  # All agents bullish → should be bullish
    assert 0.0 <= directive.strength <= 100.0
    assert 0.0 <= directive.confidence <= 1.0
    assert directive.confidence > 0.7  # High confidence with aligned signals
    assert directive.trade_style in ["momentum", "breakout", "mean_revert", "no_trade"]
    assert directive.expected_move_cone is not None
    assert directive.raw_engines is not None
    assert "hedge" in directive.raw_engines
    assert "liquidity" in directive.raw_engines
    assert "sentiment" in directive.raw_engines


def test_composer_with_conflicting_directives(
    mock_hedge_config,
    mock_liquidity_config,
    mock_sentiment_config,
    mock_price_getter,
):
    """Test Composer with conflicting agent signals."""
    # Initialize agents
    hedge_agent = HedgeAgentV3(mock_hedge_config)
    liquidity_agent = LiquidityAgentV1(mock_liquidity_config)
    sentiment_agent = SentimentAgentV1(mock_sentiment_config)
    
    # Hedge: Bearish
    hedge_output = EngineOutput(
        kind="hedge",
        symbol="SPY",
        timestamp=datetime.now(),
        features={
            "net_pressure": -600000.0,
            "elasticity": 2.0,
            "movement_energy": 200.0,
            "dealer_gamma_sign": -0.6,
        },
        confidence=0.8,
        regime="short_gamma",
        metadata={},
    )
    hedge_agent.set_engine_output(hedge_output)
    
    # Liquidity: Bullish
    liquidity_output = EngineOutput(
        kind="liquidity",
        symbol="SPY",
        timestamp=datetime.now(),
        features={
            "polr_direction": 0.6,
            "polr_strength": 0.7,
            "friction_cost": 0.003,
        },
        confidence=0.75,
        regime="Normal",
        metadata={},
    )
    liquidity_agent.set_engine_output(liquidity_output)
    
    # Sentiment: Neutral
    sentiment_envelope = SentimentEnvelope(
        bias="neutral",
        strength=0.3,
        energy=1.0,
        confidence=0.5,
        drivers={},
    )
    sentiment_agent.set_sentiment_envelope(sentiment_envelope)
    
    # Compose
    composer = ComposerAgent(
        hedge_agent=hedge_agent,
        liquidity_agent=liquidity_agent,
        sentiment_agent=sentiment_agent,
        reference_price_getter=mock_price_getter,
    )
    
    directive = composer.compose()
    
    # With conflicts, expect:
    # - Lower confidence
    # - Possibly mean_revert trade style
    # - Direction resolved by weighted voting
    assert directive.confidence < 0.8  # Lower confidence due to conflicts
    assert "disagree" in directive.rationale.lower() or directive.trade_style == "mean_revert"


def test_composer_with_jump_regime_favors_hedge(
    mock_hedge_config,
    mock_liquidity_config,
    mock_sentiment_config,
    mock_price_getter,
):
    """Test that jump regime gives hedge agent higher weight."""
    # Initialize agents
    hedge_agent = HedgeAgentV3(mock_hedge_config)
    liquidity_agent = LiquidityAgentV1(mock_liquidity_config)
    sentiment_agent = SentimentAgentV1(mock_sentiment_config)
    
    # Hedge: Strong bullish with jump regime
    hedge_output = EngineOutput(
        kind="hedge",
        symbol="SPY",
        timestamp=datetime.now(),
        features={
            "net_pressure": 900000.0,
            "elasticity": 3.0,
            "movement_energy": 400.0,
            "dealer_gamma_sign": -0.8,
        },
        confidence=0.9,
        regime="jump",  # Jump regime
        metadata={},
    )
    hedge_agent.set_engine_output(hedge_output)
    
    # Liquidity: Slight bearish
    liquidity_output = EngineOutput(
        kind="liquidity",
        symbol="SPY",
        timestamp=datetime.now(),
        features={
            "polr_direction": -0.2,
            "polr_strength": 0.5,
        },
        confidence=0.6,
        regime="Normal",
        metadata={},
    )
    liquidity_agent.set_engine_output(liquidity_output)
    
    # Sentiment: Slight bearish
    sentiment_envelope = SentimentEnvelope(
        bias="bearish",
        strength=0.3,
        energy=1.0,
        confidence=0.6,
        drivers={},
    )
    sentiment_agent.set_sentiment_envelope(sentiment_envelope)
    
    # Compose
    composer = ComposerAgent(
        hedge_agent=hedge_agent,
        liquidity_agent=liquidity_agent,
        sentiment_agent=sentiment_agent,
        reference_price_getter=mock_price_getter,
    )
    
    directive = composer.compose()
    
    # In jump regime, hedge should dominate
    # Even though liquidity and sentiment are bearish, hedge is bullish with high confidence
    assert directive.direction == 1  # Hedge dominates


# ============================================================================
# Feature Namespacing Tests
# ============================================================================

def test_feature_namespacing_is_preserved(mock_hedge_config):
    """Test that features are properly namespaced."""
    agent = HedgeAgentV3(mock_hedge_config)
    
    engine_output = EngineOutput(
        kind="hedge",
        symbol="SPY",
        timestamp=datetime.now(),
        features={
            "net_pressure": 100000.0,
            "elasticity": 1.5,
            "gamma_pressure": 50000.0,
            "custom_metric": 42.0,
        },
        confidence=0.8,
        regime="normal",
        metadata={},
    )
    
    agent.set_engine_output(engine_output)
    directive = agent.output()
    
    # All features should be namespaced with "hedge."
    assert all(key.startswith("hedge.") for key in directive.features.keys())
    assert "hedge.net_pressure" in directive.features
    assert "hedge.elasticity" in directive.features
    assert "hedge.custom_metric" in directive.features
    assert directive.features["hedge.custom_metric"] == 42.0
