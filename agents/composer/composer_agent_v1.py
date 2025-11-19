from __future__ import annotations

"""Composer Agent v1.0 implementation skeleton."""

from collections import Counter
from typing import Any, Dict, List
from uuid import uuid4

from agents.base import ComposerAgent
from schemas.core_schemas import StandardSnapshot, Suggestion


class ComposerAgentV1(ComposerAgent):
    """Combine primary suggestions via weighted voting."""

    def __init__(self, weights: Dict[str, float], config: Dict[str, Any], learning_orchestrator=None) -> None:
        self.weights = weights
        self.config = config
        self.learning_orchestrator = learning_orchestrator

    def compose(self, snapshot: StandardSnapshot, suggestions: List[Suggestion]) -> Suggestion:
        action_weights: Counter[str] = Counter()
        total_confidence = 0.0

        for suggestion in suggestions:
            weight = self.weights.get(suggestion.layer, 0.0)
            action_weights[suggestion.action] += weight * suggestion.confidence
            total_confidence += weight * suggestion.confidence

        # 🧠 ADAPTIVE LEARNING: Add Transformer lookahead prediction as weighted vote
        # Weight: 0.3 (configurable via adaptation.lookahead.prediction_weight)
        lookahead_contribution = ""
        if self.learning_orchestrator and self.learning_orchestrator.enabled:
            prediction_result = self.learning_orchestrator.get_lookahead_prediction(
                symbol=snapshot.symbol
            )
            
            if prediction_result and 'predicted_direction' in prediction_result:
                direction = prediction_result['predicted_direction']  # 'up', 'down', 'neutral'
                confidence_score = prediction_result.get('confidence', 0.5)
                prediction_weight = self.config.get('lookahead_weight', 0.3)
                
                # Map direction to action
                if direction == 'up':
                    lookahead_action = 'long'
                elif direction == 'down':
                    lookahead_action = 'short'
                else:
                    lookahead_action = 'flat'
                
                # Add lookahead vote with configured weight
                action_weights[lookahead_action] += prediction_weight * confidence_score
                total_confidence += prediction_weight * confidence_score
                
                lookahead_contribution = f" + Lookahead({direction}, w={prediction_weight:.2f})"

        if not action_weights:
            action = "flat"
        else:
            action = action_weights.most_common(1)[0][0]

        confidence = min(1.0, total_confidence)
        tags = ["composer"]
        reasoning = f"Weighted consensus{lookahead_contribution}"

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
