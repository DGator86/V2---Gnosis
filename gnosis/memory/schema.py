"""
Memory Schema for Trading Episodes

Stores each trade as an episode with:
- Context: market conditions, features, agent views
- Decision: what was chosen, why
- Outcome: PnL, hit rate, regime fit
- Reflection: post-mortem analysis

Enables retrieval of similar past contexts to inform future decisions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List
import json


@dataclass
class AgentView:
    """Single agent's view at decision time"""
    agent_name: str
    signal: int  # -1, 0, 1
    confidence: float
    reasoning: str
    key_features: Dict[str, float]  # Top features that drove decision


@dataclass
class Episode:
    """
    A complete trade episode from idea to exit
    
    Lifecycle:
    1. Created at decision time with open context
    2. Updated at exit with outcome and critique
    3. Embedded and indexed for future retrieval
    """
    # Identity
    episode_id: str
    symbol: str
    
    # Entry context
    t_open: datetime
    price_open: float
    features_digest: Dict[str, float]  # Key L3 features at entry
    agent_views: List[AgentView]
    
    # Decision
    decision: int  # -1 (short), 0 (pass), 1 (long)
    decision_confidence: float
    position_size: float  # Fraction of capital
    consensus_logic: str  # "2-of-3 agree" or "unanimous high conf"
    
    # Exit (filled at close)
    t_close: Optional[datetime] = None
    price_close: Optional[float] = None
    exit_reason: Optional[str] = None  # "TP", "SL", "time_stop", "signal_reverse"
    
    # Outcome
    pnl: Optional[float] = None
    return_pct: Optional[float] = None
    duration_bars: Optional[int] = None
    hit_target: Optional[bool] = None  # Did TP hit?
    
    # Reflection (auto-generated at exit)
    critique: Optional[str] = None  # "Why it worked/failed"
    regime_label: Optional[str] = None  # "trending_up", "ranging", etc.
    key_lesson: Optional[str] = None  # One-liner takeaway
    
    # Metadata for retrieval
    embedding: Optional[List[float]] = None  # Vector representation
    similar_episodes: List[str] = field(default_factory=list)  # IDs of similar past
    retrieval_score: float = 0.0  # Recency + outcome weighting
    
    def to_dict(self) -> dict:
        """Serialize for storage"""
        return {
            "episode_id": self.episode_id,
            "symbol": self.symbol,
            "t_open": self.t_open.isoformat(),
            "price_open": self.price_open,
            "features_digest": self.features_digest,
            "agent_views": [
                {
                    "agent_name": av.agent_name,
                    "signal": av.signal,
                    "confidence": av.confidence,
                    "reasoning": av.reasoning,
                    "key_features": av.key_features
                }
                for av in self.agent_views
            ],
            "decision": self.decision,
            "decision_confidence": self.decision_confidence,
            "position_size": self.position_size,
            "consensus_logic": self.consensus_logic,
            "t_close": self.t_close.isoformat() if self.t_close else None,
            "price_close": self.price_close,
            "exit_reason": self.exit_reason,
            "pnl": self.pnl,
            "return_pct": self.return_pct,
            "duration_bars": self.duration_bars,
            "hit_target": self.hit_target,
            "critique": self.critique,
            "regime_label": self.regime_label,
            "key_lesson": self.key_lesson,
            "embedding": self.embedding,
            "similar_episodes": self.similar_episodes,
            "retrieval_score": self.retrieval_score
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> Episode:
        """Deserialize from storage"""
        agent_views = [
            AgentView(
                agent_name=av["agent_name"],
                signal=av["signal"],
                confidence=av["confidence"],
                reasoning=av["reasoning"],
                key_features=av["key_features"]
            )
            for av in d["agent_views"]
        ]
        
        return cls(
            episode_id=d["episode_id"],
            symbol=d["symbol"],
            t_open=datetime.fromisoformat(d["t_open"]),
            price_open=d["price_open"],
            features_digest=d["features_digest"],
            agent_views=agent_views,
            decision=d["decision"],
            decision_confidence=d["decision_confidence"],
            position_size=d["position_size"],
            consensus_logic=d["consensus_logic"],
            t_close=datetime.fromisoformat(d["t_close"]) if d.get("t_close") else None,
            price_close=d.get("price_close"),
            exit_reason=d.get("exit_reason"),
            pnl=d.get("pnl"),
            return_pct=d.get("return_pct"),
            duration_bars=d.get("duration_bars"),
            hit_target=d.get("hit_target"),
            critique=d.get("critique"),
            regime_label=d.get("regime_label"),
            key_lesson=d.get("key_lesson"),
            embedding=d.get("embedding"),
            similar_episodes=d.get("similar_episodes", []),
            retrieval_score=d.get("retrieval_score", 0.0)
        )
    
    def to_text(self) -> str:
        """
        Convert to natural language description for embedding
        
        This text will be embedded and used for similarity search.
        Focus on the context and decision, not the outcome.
        """
        agent_summary = ", ".join([
            f"{av.agent_name}: {av.signal} ({av.confidence:.2f})"
            for av in self.agent_views
        ])
        
        features_summary = ", ".join([
            f"{k}: {v:.3f}"
            for k, v in list(self.features_digest.items())[:5]
        ])
        
        text = (
            f"Symbol {self.symbol} at {self.t_open.strftime('%Y-%m-%d %H:%M')}. "
            f"Price: ${self.price_open:.2f}. "
            f"Features: {features_summary}. "
            f"Agents: {agent_summary}. "
            f"Decision: {self.decision} (confidence {self.decision_confidence:.2f}), "
            f"size {self.position_size:.2%}. "
            f"Logic: {self.consensus_logic}."
        )
        
        return text
    
    def update_outcome(
        self,
        t_close: datetime,
        price_close: float,
        exit_reason: str,
        pnl: float,
        hit_target: bool
    ):
        """Update episode with exit information"""
        self.t_close = t_close
        self.price_close = price_close
        self.exit_reason = exit_reason
        self.pnl = pnl
        self.return_pct = (price_close - self.price_open) / self.price_open
        if self.decision == -1:  # Short position
            self.return_pct *= -1
        self.duration_bars = int((t_close - self.t_open).total_seconds() / 3600)  # Assume hourly
        self.hit_target = hit_target
    
    def compute_retrieval_score(self, current_time: datetime, decay_days: float = 30.0) -> float:
        """
        Compute score for retrieval ranking
        
        Formula: score = recency_weight * outcome_weight
        - Recency: exponential decay (half-life = decay_days)
        - Outcome: 
            - Win: 2.0
            - Neutral: 1.0
            - Loss: 0.5
        
        Args:
            current_time: Current datetime for recency calculation
            decay_days: Half-life in days
        
        Returns:
            Retrieval score (higher = more relevant)
        """
        if self.t_close is None:
            return 0.0  # Don't retrieve unclosed episodes
        
        # Recency weight (exponential decay)
        days_old = (current_time - self.t_close).total_days
        recency_weight = 0.5 ** (days_old / decay_days)
        
        # Outcome weight
        if self.pnl is None:
            outcome_weight = 1.0
        elif self.pnl > 0:
            outcome_weight = 2.0  # Boost winners
        elif self.pnl < 0:
            outcome_weight = 0.5  # Downweight losers
        else:
            outcome_weight = 1.0
        
        self.retrieval_score = recency_weight * outcome_weight
        return self.retrieval_score


@dataclass
class MemoryRecall:
    """
    Result of a memory retrieval query
    
    Contains K most similar past episodes with their similarity scores.
    """
    query_text: str
    episodes: List[Episode]
    similarities: List[float]
    aggregate_signal: Optional[int] = None  # Weighted consensus of recalls
    aggregate_confidence: Optional[float] = None
    
    def compute_aggregate(self):
        """
        Compute aggregate signal from recalled episodes
        
        Weighted by similarity * retrieval_score
        """
        if not self.episodes:
            self.aggregate_signal = 0
            self.aggregate_confidence = 0.0
            return
        
        total_weight = 0.0
        weighted_signal = 0.0
        
        for ep, sim in zip(self.episodes, self.similarities):
            weight = sim * ep.retrieval_score
            weighted_signal += ep.decision * weight
            total_weight += weight
        
        if total_weight > 0:
            self.aggregate_signal = int(round(weighted_signal / total_weight))
            self.aggregate_confidence = min(1.0, total_weight / len(self.episodes))
        else:
            self.aggregate_signal = 0
            self.aggregate_confidence = 0.0
    
    def to_summary(self) -> str:
        """Human-readable summary of recall"""
        if not self.episodes:
            return "No similar episodes found."
        
        lines = [f"Found {len(self.episodes)} similar episodes:"]
        
        for i, (ep, sim) in enumerate(zip(self.episodes[:3], self.similarities[:3]), 1):
            outcome = "WIN" if ep.pnl and ep.pnl > 0 else "LOSS" if ep.pnl and ep.pnl < 0 else "NEUTRAL"
            lines.append(
                f"  {i}. {ep.symbol} on {ep.t_close.strftime('%Y-%m-%d') if ep.t_close else 'Open'} "
                f"(sim: {sim:.3f}, {outcome}, {ep.decision})"
            )
        
        if self.aggregate_signal is not None:
            lines.append(
                f"\nAggregate: signal={self.aggregate_signal}, confidence={self.aggregate_confidence:.3f}"
            )
        
        return "\n".join(lines)
