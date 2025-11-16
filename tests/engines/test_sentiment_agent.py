# tests/engines/test_sentiment_agent.py

import pytest

from engines.sentiment_agent.schemas import SentimentAgentInput, SentimentAgentOutput
from engines.sentiment_agent.agent import SentimentAgent


def make_input(
    wyckoff_phase: str = "D",
    oscillator_score: float = 0.0,
    volatility_regime: str = "normal",
    vol_compression_score: float = 0.0,
    vol_expansion_score: float = 0.0,
    breadth_score: float = 0.0,
    flow_bias: float = 0.0,
    sentiment_energy: float = 0.2,
    regime: str = "markup",
    confidence: float = 0.9,
    realized_sentiment_divergence: float = 0.0,
) -> SentimentAgentInput:
    return SentimentAgentInput(
        wyckoff_phase=wyckoff_phase,
        oscillator_score=oscillator_score,
        volatility_regime=volatility_regime,
        vol_compression_score=vol_compression_score,
        vol_expansion_score=vol_expansion_score,
        breadth_score=breadth_score,
        flow_bias=flow_bias,
        sentiment_energy=sentiment_energy,
        regime=regime,
        confidence=confidence,
        realized_sentiment_divergence=realized_sentiment_divergence,
    )


def test_bullish_direction_from_strong_positive_signals():
    agent = SentimentAgent()
    x = make_input(
        wyckoff_phase="D",
        oscillator_score=0.8,
        breadth_score=0.5,
        flow_bias=0.3,
    )
    out = agent.interpret(x)

    assert isinstance(out, SentimentAgentOutput)
    assert out.direction == "bullish"
    assert out.strength > 0.5
    assert out.confidence > 0.5


def test_bearish_direction_from_strong_negative_signals():
    agent = SentimentAgent()
    x = make_input(
        wyckoff_phase="E",
        oscillator_score=-0.8,
        breadth_score=-0.6,
        flow_bias=-0.4,
        regime="markdown",
    )
    out = agent.interpret(x)

    assert "bearish" in out.direction
    assert out.strength > 0.5


def test_distribution_top_annotation_when_overbought_with_weak_breadth():
    agent = SentimentAgent()
    x = make_input(
        wyckoff_phase="E",
        oscillator_score=0.8,
        breadth_score=-0.1,
        flow_bias=0.1,
    )
    out = agent.interpret(x)

    assert out.direction in ("distribution top", "bearish", "range-bound")
    joined = " ".join(out.notes)
    assert "topping" in joined or "overbought" in joined


def test_accumulation_bottom_annotation_when_oversold_with_positive_breadth():
    agent = SentimentAgent()
    x = make_input(
        wyckoff_phase="C",
        oscillator_score=-0.8,
        breadth_score=0.2,
        flow_bias=-0.1,
        regime="accumulation",
    )
    out = agent.interpret(x)

    assert "accumulation" in out.direction
    joined = " ".join(out.notes)
    assert "bottom" in joined or "oversold" in joined


def test_range_bound_in_compression_with_muted_signals():
    agent = SentimentAgent()
    x = make_input(
        wyckoff_phase="B",
        oscillator_score=0.1,
        breadth_score=0.05,
        volatility_regime="compression",
        vol_compression_score=0.8,
        sentiment_energy=0.1,
        regime="sideways",
    )
    out = agent.interpret(x)

    assert out.direction == "range-bound"
    assert any("compression" in n for n in out.notes)


def test_confidence_haircut_in_transition_regime():
    agent = SentimentAgent()
    x = make_input(
        regime="transition",
        confidence=0.9,
    )
    out = agent.interpret(x)

    assert out.confidence < 0.9
    assert any("transition" in n for n in out.notes)


def test_confidence_haircut_on_negative_divergence():
    agent = SentimentAgent()
    x = make_input(
        realized_sentiment_divergence=-0.8,
        confidence=0.9,
    )
    out = agent.interpret(x)

    assert out.confidence < 0.9
    assert any("divergence" in n for n in out.notes)


def test_chaotic_when_confidence_very_low():
    agent = SentimentAgent()
    x = make_input(
        confidence=0.3,
        regime="transition",
        realized_sentiment_divergence=-0.8,
        volatility_regime="expansion",
        oscillator_score=0.0,
    )
    out = agent.interpret(x)

    assert out.confidence <= 0.2
    assert out.direction == "chaotic"


def test_strength_with_expansion_multiplier():
    agent = SentimentAgent()
    x_normal = make_input(
        oscillator_score=0.6,
        breadth_score=0.4,
        flow_bias=0.3,
        sentiment_energy=0.5,
        volatility_regime="normal",
    )
    x_expansion = make_input(
        oscillator_score=0.6,
        breadth_score=0.4,
        flow_bias=0.3,
        sentiment_energy=0.5,
        volatility_regime="expansion",
    )

    out_normal = agent.interpret(x_normal)
    out_expansion = agent.interpret(x_expansion)

    assert out_expansion.strength > out_normal.strength


# Additional comprehensive tests

def test_wyckoff_phase_A_maps_to_range_bound():
    agent = SentimentAgent()
    x = make_input(wyckoff_phase="A")
    out = agent.interpret(x)
    
    assert "range" in out.direction.lower()


def test_wyckoff_phase_B_maps_to_range_bound():
    agent = SentimentAgent()
    x = make_input(wyckoff_phase="B")
    out = agent.interpret(x)
    
    assert "range" in out.direction.lower()


def test_wyckoff_phase_C_maps_to_accumulation():
    agent = SentimentAgent()
    x = make_input(wyckoff_phase="C")
    out = agent.interpret(x)
    
    assert "accumulation" in out.direction.lower()


def test_wyckoff_phase_D_maps_to_bullish():
    agent = SentimentAgent()
    x = make_input(wyckoff_phase="D")
    out = agent.interpret(x)
    
    assert "bullish" in out.direction.lower()


def test_wyckoff_phase_E_maps_to_distribution():
    agent = SentimentAgent()
    x = make_input(wyckoff_phase="E")
    out = agent.interpret(x)
    
    assert "distribution" in out.direction.lower()


def test_strength_bounded_at_one():
    agent = SentimentAgent()
    x = make_input(
        oscillator_score=1.0,
        breadth_score=1.0,
        flow_bias=1.0,
        sentiment_energy=1.0,
        volatility_regime="expansion",
    )
    out = agent.interpret(x)
    
    assert out.strength <= 1.0


def test_confidence_bounded_at_zero():
    agent = SentimentAgent()
    x = make_input(
        confidence=0.5,
        regime="transition",
        realized_sentiment_divergence=-0.8,
        volatility_regime="expansion",
        oscillator_score=0.0,
    )
    out = agent.interpret(x)
    
    assert out.confidence >= 0.0


def test_sideways_regime_haircut():
    agent = SentimentAgent()
    x = make_input(
        regime="sideways",
        confidence=1.0,
    )
    out = agent.interpret(x)
    
    assert out.confidence == pytest.approx(0.85, rel=0.01)
    assert any("sideways" in n for n in out.notes)


def test_expansion_without_strong_oscillator_haircut():
    agent = SentimentAgent()
    x = make_input(
        volatility_regime="expansion",
        oscillator_score=0.1,  # Weak oscillator
        confidence=1.0,
    )
    out = agent.interpret(x)
    
    assert out.confidence == pytest.approx(0.75, rel=0.01)
    assert any("expansion" in n and "oscillator" in n for n in out.notes)


def test_notes_include_regime_information():
    agent = SentimentAgent()
    x = make_input(
        regime="transition",
    )
    out = agent.interpret(x)
    
    notes_text = " ".join(out.notes).lower()
    assert "transition" in notes_text


def test_regime_echoed_in_output():
    agent = SentimentAgent()
    x = make_input(regime="markup")
    out = agent.interpret(x)
    
    assert out.regime == "markup"


def test_output_types_valid():
    agent = SentimentAgent()
    x = make_input()
    out = agent.interpret(x)
    
    assert isinstance(out.direction, str)
    assert isinstance(out.strength, float)
    assert isinstance(out.confidence, float)
    assert isinstance(out.regime, str)
    assert isinstance(out.notes, list)
    assert 0.0 <= out.strength <= 1.0
    assert 0.0 <= out.confidence <= 1.0
