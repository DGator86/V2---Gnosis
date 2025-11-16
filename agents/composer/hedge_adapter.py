"""
Composer Hedge Adapter

Glue layer between Hedge Agent output and Composer Agent.
Converts HedgeAgentOutput into Composer-friendly format.
"""

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from engines.hedge_agent.schemas import HedgeAgentOutput


@dataclass
class HedgeSignalForComposer:
    """
    Minimal, normalized representation of the Hedge Agent's output
    as seen by the Composer.
    
    This avoids coupling the Composer directly to the HedgeAgentOutput
    schema, while still preserving all critical information.
    
    Attributes:
        direction: Directional classification (strong/weak bull/bear, neutral, chaotic)
        strength: Field strength [0-1] - energy cost to move price
        confidence: Agent confidence [0-1]
        regime: Market regime (quadratic, cubic, double_well, jump, etc.)
        notes: Interpretation notes/flags
    """
    direction: str
    strength: float
    confidence: float
    regime: str
    notes: Tuple[str, ...]


def hedge_output_to_composer_signal(
    hedge_output: HedgeAgentOutput,
) -> HedgeSignalForComposer:
    """
    Convert HedgeAgentOutput into a Composer-friendly hedge signal object.
    
    This is the primary adapter function for the Composer integration.
    
    Args:
        hedge_output: Raw output from HedgeAgent.interpret()
        
    Returns:
        HedgeSignalForComposer with normalized fields
    
    Example:
        ```python
        from engines.hedge_agent import HedgeAgent, HedgeAgentInput
        from agents.composer.hedge_adapter import hedge_output_to_composer_signal
        
        agent = HedgeAgent()
        hedge_input = HedgeAgentInput(...)
        hedge_output = agent.interpret(hedge_input)
        
        composer_signal = hedge_output_to_composer_signal(hedge_output)
        print(f"Direction: {composer_signal.direction}")
        print(f"Strength: {composer_signal.strength}")
        ```
    """
    return HedgeSignalForComposer(
        direction=hedge_output.direction,
        strength=hedge_output.strength,
        confidence=hedge_output.confidence,
        regime=hedge_output.regime,
        notes=tuple(hedge_output.notes),
    )


def hedge_signal_to_feature_dict(
    hedge_signal: HedgeSignalForComposer,
) -> Dict[str, Any]:
    """
    Convert the hedge signal into a flat feature dictionary for fusion
    with Liquidity and Sentiment signals.
    
    This is what the Composer will typically consume when building its
    full feature vector for decision-making.
    
    Args:
        hedge_signal: Normalized hedge signal from adapter
        
    Returns:
        Flat dictionary with hedge_ prefixed features
    
    Example:
        ```python
        features = hedge_signal_to_feature_dict(composer_signal)
        
        # Features ready for fusion
        assert "hedge_direction" in features
        assert "hedge_strength" in features
        assert "hedge_confidence" in features
        ```
    """
    return {
        "hedge_direction": hedge_signal.direction,
        "hedge_strength": hedge_signal.strength,
        "hedge_confidence": hedge_signal.confidence,
        "hedge_regime": hedge_signal.regime,
        "hedge_notes": list(hedge_signal.notes),
    }


def fuse_hedge_with_other_agents(
    hedge_output: HedgeAgentOutput,
    liquidity_features: Dict[str, Any],
    sentiment_features: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Example fusion function showing how to combine hedge signals
    with liquidity and sentiment signals at the Composer level.
    
    This is illustrative - actual Composer fusion logic will be more sophisticated.
    
    Args:
        hedge_output: Raw Hedge Agent output
        liquidity_features: Features from Liquidity Engine
        sentiment_features: Features from Sentiment Engine
        
    Returns:
        Consolidated feature dictionary for strategy selection
    
    Example:
        ```python
        fused_features = fuse_hedge_with_other_agents(
            hedge_output=hedge_agent.interpret(hedge_input),
            liquidity_features={"liquidity_score": 0.8, ...},
            sentiment_features={"sentiment_bias": "bullish", ...},
        )
        
        # Fused features ready for Composer decision-making
        assert "hedge_direction" in fused_features
        assert "liquidity_score" in fused_features
        assert "sentiment_bias" in fused_features
        ```
    """
    # Convert hedge output to normalized signal
    hedge_signal = hedge_output_to_composer_signal(hedge_output)
    hedge_features = hedge_signal_to_feature_dict(hedge_signal)
    
    # Merge all feature sets
    fused = {
        **hedge_features,
        **liquidity_features,
        **sentiment_features,
    }
    
    return fused


def calculate_composite_confidence(
    hedge_confidence: float,
    liquidity_confidence: float,
    sentiment_confidence: float,
    weights: Tuple[float, float, float] = (0.4, 0.3, 0.3),
) -> float:
    """
    Calculate composite confidence from all three agents.
    
    Uses weighted geometric mean to ensure low confidence in any
    agent significantly reduces overall confidence.
    
    Args:
        hedge_confidence: Hedge Agent confidence [0-1]
        liquidity_confidence: Liquidity Engine confidence [0-1]
        sentiment_confidence: Sentiment Engine confidence [0-1]
        weights: Weight tuple (hedge, liquidity, sentiment), must sum to 1.0
        
    Returns:
        Composite confidence [0-1]
    
    Example:
        ```python
        composite = calculate_composite_confidence(
            hedge_confidence=0.8,
            liquidity_confidence=0.7,
            sentiment_confidence=0.9,
        )
        
        # Composite confidence will be geometric-weighted average
        assert 0.0 <= composite <= 1.0
        ```
    """
    # Geometric mean with weights
    w_hedge, w_liq, w_sent = weights
    
    geometric_mean = (
        hedge_confidence ** w_hedge *
        liquidity_confidence ** w_liq *
        sentiment_confidence ** w_sent
    )
    
    return float(geometric_mean)
