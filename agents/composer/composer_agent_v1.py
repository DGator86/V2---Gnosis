from __future__ import annotations

"""Composer Agent v1.0 implementation skeleton."""

from collections import Counter
from typing import Any, Dict, List
from uuid import uuid4

from agents.base import ComposerAgent
from schemas.core_schemas import StandardSnapshot, Suggestion


class ComposerAgentV1(ComposerAgent):
    """Combine primary suggestions via weighted voting."""

    def __init__(self, weights: Dict[str, float], config: Dict[str, Any]) -> None:
        self.weights = weights
        self.config = config

    def compose(self, snapshot: StandardSnapshot, suggestions: List[Suggestion]) -> Suggestion:
        action_weights: Counter[str] = Counter()
        total_confidence = 0.0

        for suggestion in suggestions:
            weight = self.weights.get(suggestion.layer, 0.0)
            action_weights[suggestion.action] += weight * suggestion.confidence
            total_confidence += weight * suggestion.confidence

        if not action_weights:
            action = "flat"
        else:
            action = action_weights.most_common(1)[0][0]

        confidence = min(1.0, total_confidence)
        tags = ["composer"]
        reasoning = "Weighted consensus"

        return Suggestion(
            id=f"composer-{uuid4()}",
            layer="composer",
            symbol=snapshot.symbol,
            action=action,
            confidence=confidence,
            forecast={},
            reasoning=reasoning,
            tags=tags,
        )
