# agents/composer/liquidity_adapter.py

from dataclasses import dataclass
from typing import Any, Dict

from engines.liquidity_agent.schemas import LiquidityAgentOutput


@dataclass
class LiquiditySignalForComposer:
    """
    Normalized representation of Liquidity Agent output for the Composer.

    The Composer should think in terms of:
    - direction: semantic label (supportive/fragile/vacuum/balanced/chaotic)
    - strength: [0,1] fragility / cost-to-move-size
    - confidence: [0,1] trust in the microstructure read
    - regime: engine-level liquidity regime label
    - notes: tuple of annotations / warnings
    """
    direction: str
    strength: float
    confidence: float
    regime: str
    notes: tuple[str, ...]


def liquidity_output_to_composer_signal(
    liquidity_output: LiquidityAgentOutput,
) -> LiquiditySignalForComposer:
    """
    Convert LiquidityAgentOutput (Pydantic model) into a lightweight,
    Composer-native dataclass.

    This decouples the Composer from the engine/agent schema internals
    while preserving all semantically important fields.
    """
    return LiquiditySignalForComposer(
        direction=liquidity_output.direction,
        strength=liquidity_output.strength,
        confidence=liquidity_output.confidence,
        regime=liquidity_output.regime,
        notes=tuple(liquidity_output.notes),
    )


def liquidity_signal_to_feature_dict(
    liquidity_signal: LiquiditySignalForComposer,
) -> Dict[str, Any]:
    """
    Flatten the liquidity signal into a feature dictionary suitable for:
    - Fusion with Hedge and Sentiment signals
    - Logging
    - Feeding into ML models down the line

    Keys are intentionally prefixed with 'liquidity_' to avoid namespace
    collisions when merging with other feature sets.
    """
    return {
        "liquidity_direction": liquidity_signal.direction,
        "liquidity_strength": liquidity_signal.strength,
        "liquidity_confidence": liquidity_signal.confidence,
        "liquidity_regime": liquidity_signal.regime,
        "liquidity_notes": list(liquidity_signal.notes),
    }
