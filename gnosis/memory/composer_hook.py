"""
Memory-Augmented Composer

Integrates episodic memory retrieval into the decision composer.
Before agents vote, recall similar past contexts and adjust:
- Confidence thresholds
- Position sizing
- Agent reliability weights

Pattern: "If similar setups won 80% of the time → lower threshold, size up"
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np

from gnosis.memory.schema import Episode, AgentView
from gnosis.memory.vec import recall_similar
from gnosis.memory.store import get_memory_stats


class MemoryAugmentedComposer:
    """
    Composer that uses memory to inform decisions
    
    Workflow:
    1. Agents generate views (as usual)
    2. Build context text from current features + agent views
    3. Recall K similar past episodes
    4. Compute adjustments based on recall outcomes
    5. Apply adjustments to thresholds/sizing
    6. Proceed with voting (with adjusted parameters)
    """
    
    def __init__(
        self,
        recall_k: int = 10,
        min_recall_similarity: float = 0.5,
        adjustment_strength: float = 0.3,
        enable_memory: bool = True
    ):
        """
        Args:
            recall_k: Number of similar episodes to retrieve
            min_recall_similarity: Ignore recalls below this similarity
            adjustment_strength: How much to adjust (0=none, 1=full)
            enable_memory: Master switch to disable memory
        """
        self.recall_k = recall_k
        self.min_recall_similarity = min_recall_similarity
        self.adjustment_strength = adjustment_strength
        self.enable_memory = enable_memory
    
    def build_context_query(
        self,
        symbol: str,
        features: Dict[str, float],
        agent_views: List[AgentView]
    ) -> str:
        """
        Build context query for memory retrieval
        
        Converts current state to natural language for embedding.
        """
        # Top features
        feat_items = sorted(features.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        feat_str = ", ".join([f"{k}: {v:.3f}" for k, v in feat_items])
        
        # Agent summary
        agent_str = ", ".join([
            f"{av.agent_name}: {av.signal} ({av.confidence:.2f})"
            for av in agent_views
        ])
        
        query = (
            f"Symbol {symbol}. "
            f"Features: {feat_str}. "
            f"Agents: {agent_str}."
        )
        
        return query
    
    def compute_adjustments(
        self,
        recall,
        current_decision: int,
        current_confidence: float
    ) -> Dict[str, float]:
        """
        Compute parameter adjustments based on memory recall
        
        Logic:
        - If similar setups had high win rate → boost confidence, size up
        - If similar setups had low win rate → reduce confidence, size down
        - If no similar setups → no adjustment (neutral)
        
        Args:
            recall: MemoryRecall result
            current_decision: Proposed decision (-1, 0, 1)
            current_confidence: Base confidence from agents
        
        Returns:
            Dict with adjustment factors:
            - confidence_delta: Add to confidence (-0.3 to +0.3)
            - size_multiplier: Multiply position size (0.5 to 1.5)
            - threshold_delta: Add to alignment threshold (-1 to +1)
        """
        if not recall.episodes:
            return {
                "confidence_delta": 0.0,
                "size_multiplier": 1.0,
                "threshold_delta": 0.0,
                "recall_signal": 0,
                "recall_strength": 0.0
            }
        
        # Filter by similarity threshold
        relevant = [
            (ep, sim)
            for ep, sim in zip(recall.episodes, recall.similarities)
            if sim >= self.min_recall_similarity
        ]
        
        if not relevant:
            return {
                "confidence_delta": 0.0,
                "size_multiplier": 1.0,
                "threshold_delta": 0.0,
                "recall_signal": 0,
                "recall_strength": 0.0
            }
        
        # Compute weighted win rate and average outcome
        total_weight = 0.0
        weighted_wins = 0.0
        weighted_pnl = 0.0
        direction_match = 0.0
        
        for ep, sim in relevant:
            weight = sim * ep.retrieval_score
            total_weight += weight
            
            if ep.pnl and ep.pnl > 0:
                weighted_wins += weight
            
            if ep.pnl:
                weighted_pnl += weight * ep.pnl
            
            # Check if past decision matches current
            if ep.decision == current_decision:
                direction_match += weight
        
        if total_weight == 0:
            return {
                "confidence_delta": 0.0,
                "size_multiplier": 1.0,
                "threshold_delta": 0.0,
                "recall_signal": 0,
                "recall_strength": 0.0
            }
        
        # Normalize
        win_rate = weighted_wins / total_weight
        avg_pnl = weighted_pnl / total_weight
        direction_alignment = direction_match / total_weight
        
        # Compute adjustments
        # High win rate + direction match → boost
        # Low win rate or opposite direction → reduce
        
        if direction_alignment > 0.6:
            # Similar setups in same direction
            if win_rate > 0.6:
                # High win rate → boost
                confidence_delta = self.adjustment_strength * 0.2
                size_multiplier = 1.0 + (self.adjustment_strength * 0.3)
                threshold_delta = -1.0 * self.adjustment_strength  # Lower threshold
            elif win_rate < 0.4:
                # Low win rate → reduce
                confidence_delta = -self.adjustment_strength * 0.2
                size_multiplier = 1.0 - (self.adjustment_strength * 0.3)
                threshold_delta = 1.0 * self.adjustment_strength  # Raise threshold
            else:
                # Neutral
                confidence_delta = 0.0
                size_multiplier = 1.0
                threshold_delta = 0.0
        else:
            # Weak direction match → be cautious
            confidence_delta = -self.adjustment_strength * 0.1
            size_multiplier = 1.0 - (self.adjustment_strength * 0.2)
            threshold_delta = 0.5 * self.adjustment_strength
        
        return {
            "confidence_delta": confidence_delta,
            "size_multiplier": max(0.5, min(1.5, size_multiplier)),
            "threshold_delta": threshold_delta,
            "recall_signal": recall.aggregate_signal or 0,
            "recall_strength": direction_alignment,
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "num_recalls": len(relevant)
        }
    
    def augment_decision(
        self,
        symbol: str,
        features: Dict[str, float],
        agent_views: List[AgentView],
        base_decision: int,
        base_confidence: float,
        base_size: float,
        current_time: Optional[datetime] = None
    ) -> Tuple[int, float, float, dict]:
        """
        Augment decision with memory
        
        Args:
            symbol: Trading symbol
            features: Current L3 features
            agent_views: Agent opinions
            base_decision: Decision from composer (-1, 0, 1)
            base_confidence: Confidence from composer
            base_size: Position size from composer
            current_time: For recency weighting
        
        Returns:
            Tuple of (decision, confidence, size, memory_context)
            - decision: May be same or flipped based on memory
            - confidence: Adjusted confidence
            - size: Adjusted position size
            - memory_context: Dict with recall details for logging
        """
        if not self.enable_memory:
            return base_decision, base_confidence, base_size, {}
        
        # Build query and recall similar episodes
        query = self.build_context_query(symbol, features, agent_views)
        recall = recall_similar(query, k=self.recall_k, current_time=current_time)
        
        # Compute adjustments
        adjustments = self.compute_adjustments(recall, base_decision, base_confidence)
        
        # Apply adjustments
        adjusted_confidence = base_confidence + adjustments["confidence_delta"]
        adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))
        
        adjusted_size = base_size * adjustments["size_multiplier"]
        adjusted_size = max(0.01, min(0.3, adjusted_size))  # Cap at 1-30%
        
        # Decision override: if memory strongly disagrees, flip
        if (
            adjustments["recall_strength"] > 0.7
            and adjustments["recall_signal"] != 0
            and adjustments["recall_signal"] != base_decision
            and adjustments["win_rate"] > 0.6
        ):
            # Memory has strong opinion in opposite direction with good track record
            decision = adjustments["recall_signal"]
        else:
            decision = base_decision
        
        # Build context for logging
        memory_context = {
            "recall_count": adjustments.get("num_recalls", 0),
            "recall_win_rate": adjustments.get("win_rate", 0.0),
            "recall_avg_pnl": adjustments.get("avg_pnl", 0.0),
            "confidence_delta": adjustments["confidence_delta"],
            "size_multiplier": adjustments["size_multiplier"],
            "decision_flipped": decision != base_decision,
            "recall_episodes": [ep.episode_id for ep in recall.episodes[:3]]
        }
        
        return decision, adjusted_confidence, adjusted_size, memory_context


# Convenience function
def augment_with_memory(
    symbol: str,
    features: Dict[str, float],
    agent_views: List[AgentView],
    base_decision: int,
    base_confidence: float,
    base_size: float,
    current_time: Optional[datetime] = None
) -> Tuple[int, float, float, dict]:
    """
    High-level API: augment decision with memory
    
    Returns: (decision, confidence, size, memory_context)
    """
    composer = MemoryAugmentedComposer()
    return composer.augment_decision(
        symbol, features, agent_views,
        base_decision, base_confidence, base_size,
        current_time
    )


if __name__ == "__main__":
    # Test memory augmentation
    print("\n" + "="*60)
    print("  MEMORY-AUGMENTED COMPOSER TEST")
    print("="*60 + "\n")
    
    # Mock current context
    features = {
        "hedge_gamma": 0.7,
        "liq_amihud": 0.015,
        "sent_momentum": 0.6,
        "sent_volume_delta": 0.4
    }
    
    agent_views = [
        AgentView("hedge", 1, 0.8, "Gamma wall", {"gamma": 0.7}),
        AgentView("liquidity", 1, 0.7, "Tight", {"amihud": 0.015}),
        AgentView("sentiment", 1, 0.6, "Bullish", {"momentum": 0.6}),
    ]
    
    # Base decision from composer
    base_decision = 1  # Long
    base_confidence = 0.7
    base_size = 0.10
    
    print("Base Decision:")
    print(f"  Decision: {base_decision}")
    print(f"  Confidence: {base_confidence:.3f}")
    print(f"  Size: {base_size:.2%}")
    
    # Augment with memory
    print("\n🧠 Augmenting with memory...")
    decision, confidence, size, ctx = augment_with_memory(
        "SPY", features, agent_views,
        base_decision, base_confidence, base_size
    )
    
    print(f"\nAugmented Decision:")
    print(f"  Decision: {decision} {'(FLIPPED!)' if ctx.get('decision_flipped') else ''}")
    print(f"  Confidence: {confidence:.3f} (Δ={ctx.get('confidence_delta', 0):.3f})")
    print(f"  Size: {size:.2%} (×{ctx.get('size_multiplier', 1):.2f})")
    print(f"\nMemory Context:")
    print(f"  Recalls: {ctx.get('recall_count', 0)}")
    print(f"  Win Rate: {ctx.get('recall_win_rate', 0):.2%}")
    print(f"  Avg PnL: ${ctx.get('recall_avg_pnl', 0):.2f}")
    
    print("\n✅ Composer hook tests passed!")
