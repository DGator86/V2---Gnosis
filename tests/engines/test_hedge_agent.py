"""
Comprehensive tests for Hedge Agent v3.0

Tests cover:
- Direction classification
- Strength calculation
- Confidence haircuts
- Regime-based adjustments
- Edge cases
"""

import pytest

from engines.hedge_agent.agent import HedgeAgent
from engines.hedge_agent.schemas import HedgeAgentInput, HedgeAgentOutput


# ============================================================================
# Test Fixtures and Helpers
# ============================================================================

def make_input(
    net_pressure: float = 0.0,
    regime: str = "quadratic",
    gamma_curvature: float = 0.0,
    vanna_drift: float = 0.0,
    charm_decay: float = 0.0,
    cross_gamma: float = 0.0,
    volatility_drag: float = 0.0,
    energy: float = 0.0,
    confidence: float = 0.9,
    realized_move_score: float = 0.0,
    cross_asset_pressure: float = 0.0,
) -> HedgeAgentInput:
    """
    Helper factory to build a minimal valid HedgeAgentInput.
    """
    return HedgeAgentInput(
        net_pressure=net_pressure,
        pressure_mtf={},  # Can be expanded later
        gamma_curvature=gamma_curvature,
        vanna_drift=vanna_drift,
        charm_decay=charm_decay,
        cross_gamma=cross_gamma,
        volatility_drag=volatility_drag,
        regime=regime,
        energy=energy,
        confidence=confidence,
        realized_move_score=realized_move_score,
        cross_asset_pressure=cross_asset_pressure,
    )


# ============================================================================
# Direction Classification Tests
# ============================================================================

def test_neutral_direction_when_net_pressure_small():
    """Test neutral classification when pressure is within threshold."""
    agent = HedgeAgent()
    x = make_input(net_pressure=0.01)  # Within neutral threshold (0.05)

    out = agent.interpret(x)

    assert isinstance(out, HedgeAgentOutput)
    assert out.direction == "neutral"
    assert 0.0 <= out.strength <= 1.0
    assert 0.0 <= out.confidence <= 1.0


def test_bull_direction_when_positive_pressure():
    """Test bull classification with positive net pressure."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.3,
        confidence=0.8,
    )

    out = agent.interpret(x)

    assert "bull" in out.direction
    assert out.confidence > 0.0


def test_bear_direction_when_negative_pressure():
    """Test bear classification with negative net pressure."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=-0.5,
        gamma_curvature=0.3,
        confidence=0.8,
    )

    out = agent.interpret(x)

    assert "bear" in out.direction
    assert out.confidence > 0.0


def test_strong_bull_when_high_positive_pressure_and_strength():
    """Test strong bull classification with high pressure and strength."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=1.0,
        gamma_curvature=1.0,  # High curvature = high strength
        cross_gamma=0.8,
        volatility_drag=0.6,
        confidence=0.9,
    )

    out = agent.interpret(x)

    assert out.direction.startswith("strong")
    assert "bull" in out.direction
    assert 0.65 <= out.strength <= 1.0
    assert out.confidence > 0.5


def test_strong_bear_when_high_negative_pressure_and_strength():
    """Test strong bear classification with high negative pressure."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=-1.0,
        gamma_curvature=1.2,
        cross_gamma=0.7,
        volatility_drag=0.5,
        confidence=0.9,
    )

    out = agent.interpret(x)

    assert out.direction.startswith("strong")
    assert "bear" in out.direction
    assert 0.65 <= out.strength <= 1.0
    assert out.confidence > 0.5


def test_weak_bull_when_low_strength():
    """Test weak bull classification with low strength."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.1,  # Low curvature = low strength
        cross_gamma=0.05,
        volatility_drag=0.02,
        confidence=0.8,
    )

    out = agent.interpret(x)

    assert out.direction.startswith("weak")
    assert "bull" in out.direction
    assert out.strength < 0.25


def test_weak_bear_when_low_strength():
    """Test weak bear classification with low strength."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=-0.5,
        gamma_curvature=0.1,
        cross_gamma=0.05,
        volatility_drag=0.02,
        confidence=0.8,
    )

    out = agent.interpret(x)

    assert out.direction.startswith("weak")
    assert "bear" in out.direction
    assert out.strength < 0.25


# ============================================================================
# Strength Calculation Tests
# ============================================================================

def test_strength_calculation_from_curvature():
    """Test that gamma curvature contributes to strength."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        cross_gamma=0.0,
        volatility_drag=0.0,
    )

    out = agent.interpret(x)

    # Strength should be dominated by gamma_curvature (0.8)
    assert 0.7 <= out.strength <= 0.9


def test_strength_calculation_with_friction():
    """Test that cross-gamma friction contributes to strength."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.5,
        cross_gamma=0.6,  # High friction
        volatility_drag=0.0,
    )

    out = agent.interpret(x)

    # Strength = 0.5 + 0.5*0.6 = 0.8
    assert 0.75 <= out.strength <= 0.85


def test_strength_calculation_with_vol_drag():
    """Test that volatility drag contributes to strength."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.5,
        cross_gamma=0.0,
        volatility_drag=0.8,
    )

    out = agent.interpret(x)

    # Strength = 0.5 + 0.25*0.8 = 0.7
    assert 0.65 <= out.strength <= 0.75


def test_strength_capped_at_one():
    """Test that strength is capped at 1.0."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=5.0,  # Extremely high
        cross_gamma=5.0,
        volatility_drag=5.0,
    )

    out = agent.interpret(x)

    assert out.strength == 1.0


# ============================================================================
# Confidence Haircut Tests
# ============================================================================

def test_jump_regime_applies_confidence_haircut_and_note():
    """Test jump-risk regime applies severe confidence haircut."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        regime="jump",
        confidence=0.9,
    )

    out = agent.interpret(x)

    # Jump haircut is 0.35, so confidence should be ~0.315
    assert out.confidence < 0.4
    assert any("jump-risk" in note for note in out.notes)


def test_double_well_regime_applies_confidence_haircut_and_note():
    """Test double-well regime applies ambiguity haircut."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        regime="double_well",
        confidence=0.9,
    )

    out = agent.interpret(x)

    # Double-well haircut is 0.50, so confidence should be ~0.45
    assert out.confidence < 0.5
    assert any("double-well" in note for note in out.notes)


def test_realized_move_mismatch_reduces_confidence_and_adds_note():
    """Test realized move mismatch applies confidence haircut."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        realized_move_score=-1.0,  # Below mismatch threshold (-0.5)
        confidence=0.9,
    )

    out = agent.interpret(x)

    # Mismatch haircut is 0.55, so confidence should be ~0.495
    assert out.confidence < 0.55
    assert any("realized move mismatch" in note for note in out.notes)


def test_multiple_haircuts_stack():
    """Test that multiple haircuts are multiplied together."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        regime="jump",
        realized_move_score=-1.0,
        confidence=0.9,
    )

    out = agent.interpret(x)

    # Jump (0.35) * Mismatch (0.55) * 0.9 = ~0.173
    assert out.confidence < 0.2
    assert len(out.notes) >= 2


def test_confidence_bounds_clipped_between_zero_and_one():
    """Test confidence is always clamped to [0, 1]."""
    agent = HedgeAgent()
    
    # Test upper bound
    x_high = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        confidence=5.0,  # Absurdly high
    )
    out_high = agent.interpret(x_high)
    assert 0.0 <= out_high.confidence <= 1.0
    
    # Test lower bound with extreme haircuts
    x_low = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        regime="jump",
        realized_move_score=-1.0,
        confidence=0.01,  # Very low base confidence
    )
    out_low = agent.interpret(x_low)
    assert 0.0 <= out_low.confidence <= 1.0


# ============================================================================
# Chaotic Detection Tests
# ============================================================================

def test_chaotic_when_low_confidence_and_unstable_regime():
    """Test chaotic classification with low confidence and unstable regime."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        regime="double_well",
        confidence=0.1,  # Very low confidence
    )

    out = agent.interpret(x)

    assert out.direction == "chaotic"
    assert any("low confidence" in note for note in out.notes)


def test_chaotic_when_jump_regime_and_low_confidence():
    """Test chaotic classification in jump regime with low confidence."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        regime="jump",
        confidence=0.15,
    )

    out = agent.interpret(x)

    # After jump haircut (0.35), confidence becomes ~0.0525
    assert out.direction == "chaotic"


# ============================================================================
# Notes Generation Tests
# ============================================================================

def test_high_vanna_drift_adds_note():
    """Test that high vanna drift adds interpretation note."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        vanna_drift=0.6,  # Above threshold (0.5)
    )

    out = agent.interpret(x)

    assert any("high vanna drift" in note for note in out.notes)


def test_significant_charm_decay_adds_note():
    """Test that significant charm decay adds note."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        charm_decay=0.6,  # Above threshold (0.5)
    )

    out = agent.interpret(x)

    assert any("significant charm decay" in note for note in out.notes)


def test_cross_asset_influence_adds_note():
    """Test that cross-asset pressure adds note."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        cross_asset_pressure=0.4,  # Above threshold (0.3)
    )

    out = agent.interpret(x)

    assert any("cross-asset influence" in note for note in out.notes)


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================

def test_all_zeros_input():
    """Test agent handles all-zero input gracefully."""
    agent = HedgeAgent()
    x = make_input()  # All defaults (mostly zeros)

    out = agent.interpret(x)

    assert out.direction == "neutral"
    assert out.strength == 0.0
    assert 0.0 <= out.confidence <= 1.0


def test_extreme_positive_pressure():
    """Test agent handles extreme positive pressure."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=10.0,
        gamma_curvature=2.0,
        confidence=0.9,
    )

    out = agent.interpret(x)

    assert "bull" in out.direction
    assert out.strength <= 1.0  # Capped


def test_extreme_negative_pressure():
    """Test agent handles extreme negative pressure."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=-10.0,
        gamma_curvature=2.0,
        confidence=0.9,
    )

    out = agent.interpret(x)

    assert "bear" in out.direction
    assert out.strength <= 1.0


def test_custom_config():
    """Test agent respects custom configuration."""
    custom_config = {
        "neutral_net_pressure_abs_max": 0.1,  # Wider neutral zone
        "weak_strength_max": 0.3,
        "strong_strength_min": 0.7,
    }
    
    agent = HedgeAgent(config=custom_config)
    x = make_input(
        net_pressure=0.08,  # Would be bull with default config
        gamma_curvature=0.5,
    )

    out = agent.interpret(x)

    # With custom config, this should be neutral
    assert out.direction == "neutral"


def test_regime_passthrough():
    """Test that regime is passed through to output."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
        regime="cubic",
    )

    out = agent.interpret(x)

    assert out.regime == "cubic"


def test_output_types():
    """Test that output types match schema."""
    agent = HedgeAgent()
    x = make_input(
        net_pressure=0.5,
        gamma_curvature=0.8,
    )

    out = agent.interpret(x)

    assert isinstance(out, HedgeAgentOutput)
    assert isinstance(out.direction, str)
    assert isinstance(out.strength, float)
    assert isinstance(out.confidence, float)
    assert isinstance(out.regime, str)
    assert isinstance(out.notes, list)
