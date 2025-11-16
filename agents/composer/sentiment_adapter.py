# agents/composer/sentiment_adapter.py

from dataclasses import dataclass
from typing import Any, Dict

from engines.sentiment_agent.schemas import SentimentAgentOutput


@dataclass
class SentimentSignalForComposer:
    """
    Normalized representation of Sentiment Agent output for the Composer.
    """
    direction: str
    strength: float
    confidence: float
    regime: str
    notes: tuple[str, ...]


def sentiment_output_to_composer_signal(
    sentiment_output: SentimentAgentOutput,
) -> SentimentSignalForComposer:
    """
    Convert SentimentAgentOutput into a Composer-native dataclass.
    """
    return SentimentSignalForComposer(
        direction=sentiment_output.direction,
        strength=sentiment_output.strength,
        confidence=sentiment_output.confidence,
        regime=sentiment_output.regime,
        notes=tuple(sentiment_output.notes),
    )


def sentiment_signal_to_feature_dict(
    sentiment_signal: SentimentSignalForComposer,
) -> Dict[str, Any]:
    """
    Flatten the sentiment signal for downstream fusion with Hedge and Liquidity.
    """
    return {
        "sentiment_direction": sentiment_signal.direction,
        "sentiment_strength": sentiment_signal.strength,
        "sentiment_confidence": sentiment_signal.confidence,
        "sentiment_regime": sentiment_signal.regime,
        "sentiment_notes": list(sentiment_signal.notes),
    }
