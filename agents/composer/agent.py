"""
Composer Agent
Aggregates suggestions from primary agents
Maps to executable trading strategies
"""
from typing import List, Dict, Any
from datetime import datetime
from schemas import Suggestion, StandardSnapshot
from engines.lookahead.lookahead_engine import LookaheadEngine
from engines.orchestration.logger import get_logger

logger = get_logger(__name__)


class ComposerAgent:
    """
    Composer agent that aggregates primary suggestions
    Maps to executable strategies (spreads, directional, hedges)
    """
    
    def __init__(self, 
                 voting_method: str = "weighted_confidence",
                 min_agreement_score: float = 0.6,
                 lookahead_engine: LookaheadEngine = None):
        self.voting_method = voting_method
        self.min_agreement_score = min_agreement_score
        self.lookahead = lookahead_engine or LookaheadEngine()
        
        # Strategy mapping
        self.strategy_map = {
            "long": "spread:call_debit",
            "short": "spread:put_debit",
            "neutral": "iron_condor",
            "hold": "no_action"
        }
        
        logger.info(f"Composer Agent initialized (voting={voting_method})")
    
    def _vote_majority(self, suggestions: List[Suggestion]) -> str:
        """Simple majority vote"""
        votes = {}
        for s in suggestions:
            votes[s.action] = votes.get(s.action, 0) + 1
        
        return max(votes.items(), key=lambda x: x[1])[0]
    
    def _vote_weighted_confidence(self, suggestions: List[Suggestion]) -> Dict[str, Any]:
        """Confidence-weighted voting"""
        weights = {}
        total_confidence = 0.0
        
        for s in suggestions:
            weights[s.action] = weights.get(s.action, 0.0) + s.confidence
            total_confidence += s.confidence
        
        if not weights:
            return {"action": "hold", "confidence": 0.0}
        
        best_action = max(weights.items(), key=lambda x: x[1])[0]
        action_confidence = weights[best_action] / total_confidence if total_confidence > 0 else 0.0
        
        return {
            "action": best_action,
            "confidence": action_confidence,
            "weights": weights
        }
    
    def _vote_unanimous(self, suggestions: List[Suggestion]) -> Dict[str, Any]:
        """Require unanimous agreement"""
        actions = [s.action for s in suggestions]
        
        if len(set(actions)) == 1:
            # All agree
            avg_confidence = sum(s.confidence for s in suggestions) / len(suggestions)
            return {"action": actions[0], "confidence": avg_confidence}
        else:
            # Disagreement - stay out
            return {"action": "hold", "confidence": 0.5}
    
    def _map_to_strategy(self, action: str, snapshot: StandardSnapshot) -> str:
        """Map action to executable strategy"""
        if action in self.strategy_map:
            return self.strategy_map[action]
        
        # Default mapping
        return "no_action"
    
    def _check_agreement(self, suggestions: List[Suggestion]) -> float:
        """Calculate agreement score across suggestions"""
        if not suggestions:
            return 0.0
        
        # Count how many agree with the most common action
        actions = [s.action for s in suggestions]
        most_common = max(set(actions), key=actions.count)
        agreement_count = sum(1 for a in actions if a == most_common)
        
        return agreement_count / len(actions)
    
    def compose(self, 
                symbol: str,
                suggestions: List[Suggestion],
                snapshot: StandardSnapshot) -> Suggestion:
        """
        Main composition function
        
        Args:
            symbol: Trading symbol
            suggestions: List of primary agent suggestions
            snapshot: Current snapshot for context
        
        Returns:
            Final composed suggestion
        """
        if not suggestions:
            logger.warning("No suggestions provided to composer")
            return Suggestion.create(
                layer="composer",
                symbol=symbol,
                action="hold",
                params={"reason": "no_suggestions"},
                confidence=0.0,
                forecast=self.lookahead.forecast(snapshot, [20])[20],
                reasoning="No primary suggestions available"
            )
        
        # Execute voting
        if self.voting_method == "majority":
            action = self._vote_majority(suggestions)
            confidence = sum(s.confidence for s in suggestions if s.action == action) / len(suggestions)
            vote_info = {"method": "majority"}
        
        elif self.voting_method == "weighted_confidence":
            result = self._vote_weighted_confidence(suggestions)
            action = result["action"]
            confidence = result["confidence"]
            vote_info = {"method": "weighted", "weights": result["weights"]}
        
        elif self.voting_method == "unanimous":
            result = self._vote_unanimous(suggestions)
            action = result["action"]
            confidence = result["confidence"]
            vote_info = {"method": "unanimous"}
        
        else:
            action = "hold"
            confidence = 0.0
            vote_info = {"method": "unknown"}
        
        # Check agreement score
        agreement = self._check_agreement(suggestions)
        
        if agreement < self.min_agreement_score:
            logger.info(f"Low agreement: {agreement:.2f} < {self.min_agreement_score:.2f}, holding")
            action = "hold"
            confidence *= 0.5
        
        # Map to strategy
        strategy = self._map_to_strategy(action, snapshot)
        
        # Inherit best forecast from suggestions
        best_suggestion = max(suggestions, key=lambda s: s.confidence)
        
        # Create final suggestion
        composed = Suggestion.create(
            layer="composer",
            symbol=symbol,
            action=strategy,
            params={
                "base_action": action,
                "num_inputs": len(suggestions),
                "agreement_score": agreement,
                "vote_info": vote_info,
                "source_suggestions": [s.id for s in suggestions]
            },
            confidence=min(0.99, confidence * 1.1),  # Slight boost for aggregation
            forecast=best_suggestion.forecast,
            reasoning=f"Composed from {len(suggestions)} suggestions: {action} -> {strategy} (agreement={agreement:.2f})"
        )
        
        logger.info(f"Composer: {action} -> {strategy} | conf={composed.confidence:.2f} | agreement={agreement:.2f}")
        
        return composed
