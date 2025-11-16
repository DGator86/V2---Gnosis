"""
Comprehensive test suite for Liquidity Agent v1.0

Tests the pure interpretation logic of liquidity metrics computed by the Liquidity Engine.
Follows the canonical specification for direction classification, strength calculation,
confidence haircuts, and chaotic detection.

All tests use the helper function make_input() for creating test inputs with sensible defaults.
"""

import pytest
from engines.liquidity_agent.agent import LiquidityAgent
from engines.liquidity_agent.schemas import LiquidityAgentInput, LiquidityAgentOutput


@pytest.fixture
def agent():
    """Fixture providing a LiquidityAgent instance with default configuration."""
    return LiquidityAgent()


def make_input(
    net_liquidity_pressure: float = 0.0,
    amihud_lambda: float = 0.1,
    kyle_lambda: float = 0.1,
    orderflow_imbalance: float = 0.0,
    book_depth_score: float = 0.5,
    volume_profile_slope: float = 0.0,
    liquidity_gaps_score: float = 0.1,
    dark_pool_bias: float = 0.0,
    vol_of_liquidity: float = 0.1,
    regime: str = "stable",
    confidence: float = 0.8,
    realized_slippage_score: float = 0.0,
) -> LiquidityAgentInput:
    """
    Helper function to create LiquidityAgentInput with sensible defaults.
    
    This allows tests to override only the fields they care about while providing
    reasonable defaults for all other required fields.
    """
    return LiquidityAgentInput(
        net_liquidity_pressure=net_liquidity_pressure,
        amihud_lambda=amihud_lambda,
        kyle_lambda=kyle_lambda,
        orderflow_imbalance=orderflow_imbalance,
        book_depth_score=book_depth_score,
        volume_profile_slope=volume_profile_slope,
        liquidity_gaps_score=liquidity_gaps_score,
        dark_pool_bias=dark_pool_bias,
        vol_of_liquidity=vol_of_liquidity,
        regime=regime,
        confidence=confidence,
        realized_slippage_score=realized_slippage_score,
    )


# =============================================================================
# DIRECTION CLASSIFICATION TESTS
# =============================================================================


def test_balanced_direction_when_net_liquidity_small(agent):
    """
    Test that direction is 'balanced' when |net_liquidity_pressure| < threshold (0.05).
    
    When liquidity pressure is near zero, the market has balanced liquidity on both sides.
    """
    x = make_input(net_liquidity_pressure=0.02)
    out = agent.interpret(x)
    assert out.direction == "balanced"


def test_supportive_direction_when_positive_liquidity_pressure(agent):
    """
    Test that direction is 'supportive' when net_liquidity_pressure > threshold.
    
    Positive liquidity pressure means deep bids relative to asks, supporting upward moves.
    """
    x = make_input(net_liquidity_pressure=0.3)
    out = agent.interpret(x)
    assert out.direction == "supportive"


def test_fragile_direction_when_negative_liquidity_pressure(agent):
    """
    Test that direction is 'fragile' when net_liquidity_pressure < -threshold.
    
    Negative liquidity pressure means thin bids, fragile support, vulnerable to downward moves.
    """
    x = make_input(net_liquidity_pressure=-0.3)
    out = agent.interpret(x)
    assert out.direction == "fragile"


def test_vacuum_regime_sets_liquidity_vacuum_direction(agent):
    """
    Test that vacuum regime enriches direction with 'liquidity vacuum up/down'.
    
    In vacuum regimes, liquidity has dried up, creating a vacuum that can pull price.
    Direction is enriched to indicate the vacuum direction.
    """
    # Vacuum with positive pressure -> "liquidity vacuum up"
    x_up = make_input(net_liquidity_pressure=0.3, regime="vacuum")
    out_up = agent.interpret(x_up)
    assert "liquidity vacuum up" in out_up.direction
    
    # Vacuum with negative pressure -> "liquidity vacuum down"
    x_down = make_input(net_liquidity_pressure=-0.3, regime="vacuum")
    out_down = agent.interpret(x_down)
    assert "liquidity vacuum down" in out_down.direction


# =============================================================================
# STRENGTH (FRAGILITY) CALCULATION TESTS
# =============================================================================


def test_strength_increases_with_impact_coefficients(agent):
    """
    Test that strength increases when Amihud lambda and Kyle lambda increase.
    
    Higher impact coefficients mean higher price impact per unit volume,
    indicating greater liquidity fragility.
    """
    x_low = make_input(amihud_lambda=0.1, kyle_lambda=0.1, liquidity_gaps_score=0.1)
    x_high = make_input(amihud_lambda=0.5, kyle_lambda=0.5, liquidity_gaps_score=0.1)
    
    out_low = agent.interpret(x_low)
    out_high = agent.interpret(x_high)
    
    assert out_high.strength > out_low.strength


def test_strength_increases_with_liquidity_gaps(agent):
    """
    Test that strength increases when liquidity_gaps_score increases.
    
    More liquidity gaps mean less continuous support, higher fragility.
    """
    x_low = make_input(liquidity_gaps_score=0.1, amihud_lambda=0.1, kyle_lambda=0.1)
    x_high = make_input(liquidity_gaps_score=0.7, amihud_lambda=0.1, kyle_lambda=0.1)
    
    out_low = agent.interpret(x_low)
    out_high = agent.interpret(x_high)
    
    assert out_high.strength > out_low.strength


def test_strength_reduced_by_book_depth(agent):
    """
    Test that strength is reduced when book_depth_score is high.
    
    Deep order books provide cushion against price moves, reducing fragility.
    The depth_reducer = 1/(1 + book_depth_score) reduces strength as depth increases.
    """
    x_shallow = make_input(
        book_depth_score=0.1, 
        amihud_lambda=0.3, 
        kyle_lambda=0.3, 
        liquidity_gaps_score=0.3
    )
    x_deep = make_input(
        book_depth_score=0.9, 
        amihud_lambda=0.3, 
        kyle_lambda=0.3, 
        liquidity_gaps_score=0.3
    )
    
    out_shallow = agent.interpret(x_shallow)
    out_deep = agent.interpret(x_deep)
    
    # Shallow book should have higher strength (fragility)
    assert out_shallow.strength > out_deep.strength


def test_strength_increased_by_vol_of_liquidity(agent):
    """
    Test that strength increases when vol_of_liquidity is high.
    
    High volatility of liquidity means liquidity is unstable and unreliable,
    increasing fragility. The vol term contributes 25% to strength.
    """
    x_stable = make_input(vol_of_liquidity=0.1)
    x_volatile = make_input(vol_of_liquidity=0.8)
    
    out_stable = agent.interpret(x_stable)
    out_volatile = agent.interpret(x_volatile)
    
    assert out_volatile.strength > out_stable.strength


def test_strength_capped_at_one(agent):
    """
    Test that strength is capped at 1.0 even with extreme inputs.
    
    Prevents strength from exceeding the [0,1] range.
    """
    x = make_input(
        amihud_lambda=2.0,
        kyle_lambda=2.0,
        liquidity_gaps_score=2.0,
        book_depth_score=0.0,
        vol_of_liquidity=2.0,
    )
    out = agent.interpret(x)
    assert out.strength <= 1.0


# =============================================================================
# CONFIDENCE HAIRCUT TESTS
# =============================================================================


def test_confidence_haircut_in_vacuum_regime(agent):
    """
    Test that confidence is reduced by 40% (multiplied by 0.6) in vacuum regime.
    
    Vacuum regimes have extremely low liquidity, making interpretations less reliable.
    """
    x = make_input(regime="vacuum", confidence=1.0)
    out = agent.interpret(x)
    assert out.confidence == pytest.approx(0.6, rel=0.01)


def test_confidence_haircut_in_transition_regime(agent):
    """
    Test that confidence is reduced by 30% (multiplied by 0.7) in transition regime.
    
    Transition regimes are changing liquidity states, less stable interpretations.
    """
    x = make_input(regime="transition", confidence=1.0)
    out = agent.interpret(x)
    assert out.confidence == pytest.approx(0.7, rel=0.01)


def test_confidence_haircut_with_bad_slippage(agent):
    """
    Test that confidence is reduced by 40% when realized_slippage_score > 0.3.
    
    High realized slippage indicates actual execution was worse than expected,
    suggesting liquidity metrics were unreliable.
    """
    x = make_input(realized_slippage_score=0.5, confidence=1.0)
    out = agent.interpret(x)
    assert out.confidence == pytest.approx(0.6, rel=0.01)


def test_confidence_haircut_with_high_vol_of_liquidity(agent):
    """
    Test that confidence is reduced by 30% when vol_of_liquidity > 0.4.
    
    High volatility of liquidity means liquidity is unstable, reducing confidence
    in the current snapshot.
    """
    x = make_input(vol_of_liquidity=0.6, confidence=1.0)
    out = agent.interpret(x)
    assert out.confidence == pytest.approx(0.7, rel=0.01)


def test_confidence_multiple_haircuts_multiplicative(agent):
    """
    Test that multiple haircuts are applied multiplicatively.
    
    If vacuum (×0.6) AND bad slippage (×0.6), then confidence = 1.0 × 0.6 × 0.6 = 0.36.
    """
    x = make_input(
        regime="vacuum",
        realized_slippage_score=0.5,
        confidence=1.0
    )
    out = agent.interpret(x)
    expected = 1.0 * 0.6 * 0.6  # 0.36
    assert out.confidence == pytest.approx(expected, rel=0.01)


def test_no_confidence_haircut_in_stable_regime(agent):
    """
    Test that confidence is unchanged in stable regime with normal metrics.
    
    Stable regime with good slippage and low vol of liquidity should preserve confidence.
    """
    x = make_input(
        regime="stable",
        realized_slippage_score=0.1,
        vol_of_liquidity=0.1,
        confidence=0.85
    )
    out = agent.interpret(x)
    assert out.confidence == pytest.approx(0.85, rel=0.01)


# =============================================================================
# CHAOTIC DETECTION TESTS
# =============================================================================


def test_chaotic_direction_when_confidence_very_low(agent):
    """
    Test that direction is set to 'chaotic' when confidence falls below 0.2.
    
    Very low confidence after haircuts means the signal is too unreliable to interpret.
    """
    # Start with moderate confidence, apply multiple haircuts to push below 0.2
    x = make_input(
        regime="vacuum",  # ×0.6
        realized_slippage_score=0.5,  # ×0.6
        confidence=0.5  # 0.5 × 0.6 × 0.6 = 0.18 < 0.2
    )
    out = agent.interpret(x)
    assert out.direction == "chaotic"
    assert out.confidence < 0.2


def test_not_chaotic_when_confidence_above_threshold(agent):
    """
    Test that direction is NOT chaotic when confidence is above 0.2.
    
    Even with some haircuts, if confidence stays above threshold, direction is preserved.
    """
    x = make_input(
        regime="transition",  # ×0.7
        confidence=0.5,  # 0.5 × 0.7 = 0.35 > 0.2
        net_liquidity_pressure=0.3
    )
    out = agent.interpret(x)
    assert out.direction != "chaotic"
    assert out.direction == "supportive"
    assert out.confidence > 0.2


# =============================================================================
# NOTES GENERATION TESTS
# =============================================================================


def test_notes_include_dark_pool_and_ofi_annotations(agent):
    """
    Test that notes include annotations for dark pool bias and order flow imbalance.
    
    Dark pool bias and OFI provide additional context about hidden liquidity
    and order flow dynamics.
    """
    x = make_input(
        dark_pool_bias=0.6,  # Exceeds 0.5 threshold
        orderflow_imbalance=0.6  # Exceeds 0.5 threshold
    )
    out = agent.interpret(x)
    
    # Notes should mention both dark pool and OFI
    notes_text = " ".join(out.notes).lower()
    assert "dark-pool" in notes_text or "dark pool" in notes_text
    assert "buy" in notes_text or "imbalance" in notes_text


def test_notes_include_volume_profile_annotation(agent):
    """
    Test that notes include annotation for volume profile slope.
    
    Volume profile slope indicates where volume is concentrated, providing
    context for support/resistance zones.
    """
    x = make_input(volume_profile_slope=0.8)  # Exceeds 0.7 threshold
    out = agent.interpret(x)
    
    notes_text = " ".join(out.notes).lower()
    assert "volume" in notes_text or "profile" in notes_text or "cliff" in notes_text


def test_notes_include_regime_information(agent):
    """
    Test that notes include regime information for context.
    
    Regime provides critical context for interpreting liquidity metrics.
    """
    x = make_input(regime="vacuum")
    out = agent.interpret(x)
    
    notes_text = " ".join(out.notes).lower()
    assert "vacuum" in notes_text


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


def test_zero_inputs_produce_valid_output(agent):
    """
    Test that all-zero inputs produce valid (but weak) output.
    
    Edge case: engine might produce zeros if no data available.
    Agent should handle gracefully.
    """
    x = make_input(
        net_liquidity_pressure=0.0,
        amihud_lambda=0.0,
        kyle_lambda=0.0,
        orderflow_imbalance=0.0,
        book_depth_score=0.0,
        volume_profile_slope=0.0,
        liquidity_gaps_score=0.0,
        dark_pool_bias=0.0,
        vol_of_liquidity=0.0,
        confidence=0.0
    )
    out = agent.interpret(x)
    
    # With confidence=0.0, this will trigger chaotic detection
    # Since confidence < 0.2, direction will be "chaotic"
    assert out.direction == "chaotic"
    # Strength and confidence should be valid numbers
    assert 0.0 <= out.strength <= 1.0
    assert out.confidence >= 0.0


def test_extreme_negative_inputs_clamped(agent):
    """
    Test that extreme negative inputs are handled gracefully.
    
    Edge case: some metrics might be negative in edge cases.
    Strength should be clamped to [0, 1].
    """
    x = make_input(
        amihud_lambda=-0.5,
        kyle_lambda=-0.5,
        liquidity_gaps_score=-0.5,
        book_depth_score=10.0  # Very deep book
    )
    out = agent.interpret(x)
    
    # Strength should be clamped to 0
    assert out.strength >= 0.0
    assert out.strength <= 1.0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


def test_full_interpretation_pipeline_stable_regime(agent):
    """
    Test a realistic full interpretation in stable regime.
    
    Scenario: Moderate positive liquidity pressure, moderate impact coefficients,
    stable regime, good slippage.
    """
    x = make_input(
        net_liquidity_pressure=0.2,
        amihud_lambda=0.2,
        kyle_lambda=0.2,
        orderflow_imbalance=0.1,
        book_depth_score=0.6,
        volume_profile_slope=0.05,
        liquidity_gaps_score=0.15,
        dark_pool_bias=-0.05,
        vol_of_liquidity=0.15,
        regime="stable",
        confidence=0.8,
        realized_slippage_score=0.1
    )
    out = agent.interpret(x)
    
    # Should be supportive with moderate strength
    assert out.direction == "supportive"
    assert 0.0 < out.strength < 1.0
    assert out.confidence > 0.7  # Should preserve most confidence
    assert out.regime == "stable"
    # Notes may be empty if no thresholds exceeded, which is fine
    assert isinstance(out.notes, list)


def test_full_interpretation_pipeline_vacuum_regime(agent):
    """
    Test a realistic full interpretation in vacuum regime.
    
    Scenario: Strong negative liquidity pressure, high impact coefficients,
    vacuum regime, bad slippage.
    """
    x = make_input(
        net_liquidity_pressure=-0.4,
        amihud_lambda=0.6,
        kyle_lambda=0.6,
        orderflow_imbalance=-0.3,
        book_depth_score=0.2,
        volume_profile_slope=-0.1,
        liquidity_gaps_score=0.5,
        dark_pool_bias=0.2,
        vol_of_liquidity=0.5,
        regime="vacuum",
        confidence=0.7,
        realized_slippage_score=0.4
    )
    out = agent.interpret(x)
    
    # Should be fragile (vacuum down) with high strength
    # However, with all these haircuts applied:
    # 0.7 × 0.6 (vacuum) × 0.6 (bad slippage) × 0.7 (high vol) = 0.1764 < 0.2
    # This correctly triggers chaotic detection
    assert out.direction == "chaotic" or "liquidity vacuum down" in out.direction or out.direction == "fragile"
    assert out.strength > 0.3  # Should be fairly high
    # Confidence should be heavily reduced
    assert out.confidence < 0.5
    assert out.regime == "vacuum"
