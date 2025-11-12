"""
Feedback and learning engine
Computes rewards and updates agent learning signals
Implements per-agent and per-regime learning
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..orchestration.logger import get_logger

logger = get_logger(__name__)


class FeedbackEngine:
    """
    Engine for feedback loops and learning
    Computes rewards and maintains learning state
    """
    
    def __init__(self, 
                 reward_metric: str = "sharpe",
                 learning_rate: float = 0.2,
                 window_size: int = 100):
        self.reward_metric = reward_metric
        self.learning_rate = learning_rate
        self.window_size = window_size
        
        # Learning state per agent
        self.agent_scores: Dict[str, float] = {}
        
        # Regime-specific learning
        self.regime_scores: Dict[str, Dict[str, float]] = {}
        
        logger.info(f"Feedback engine initialized (metric={reward_metric}, lr={learning_rate})")
    
    def compute_reward(self, result: Dict[str, Any], metric: str = None) -> float:
        """
        Compute reward from result
        
        Args:
            result: Result dict with pnl, horizon, etc.
            metric: Override default metric (pnl, sharpe, hit_rate, sortino)
        
        Returns:
            Scalar reward
        """
        metric = metric or self.reward_metric
        
        if metric == "pnl":
            return float(result.get("pnl", 0.0))
        
        elif metric == "hit_rate":
            return 1.0 if result.get("pnl", 0.0) > 0 else 0.0
        
        elif metric == "sharpe":
            # Simplified sharpe: pnl / risk
            pnl = result.get("pnl", 0.0)
            risk = result.get("risk", 1.0)
            return pnl / risk if risk > 0 else 0.0
        
        elif metric == "sortino":
            # Simplified sortino: pnl / downside_risk
            pnl = result.get("pnl", 0.0)
            if pnl >= 0:
                return pnl
            else:
                downside = abs(pnl)
                return -downside * 1.5  # Penalize losses more
        
        else:
            logger.warning(f"Unknown reward metric: {metric}, using pnl")
            return float(result.get("pnl", 0.0))
    
    def update_agent_score(self, agent_name: str, reward: float) -> float:
        """
        Update agent learning score with exponential moving average
        
        Args:
            agent_name: Name of agent (e.g., 'primary_hedge')
            reward: Reward signal
        
        Returns:
            Updated score
        """
        if agent_name not in self.agent_scores:
            self.agent_scores[agent_name] = 0.0
        
        # Exponential moving average
        old_score = self.agent_scores[agent_name]
        new_score = self.learning_rate * reward + (1 - self.learning_rate) * old_score
        
        self.agent_scores[agent_name] = new_score
        
        logger.debug(f"Updated {agent_name} score: {old_score:.4f} -> {new_score:.4f}")
        
        return new_score
    
    def update_regime_score(self, agent_name: str, regime: str, reward: float) -> float:
        """
        Update regime-specific learning score
        
        Args:
            agent_name: Name of agent
            regime: Market regime
            reward: Reward signal
        
        Returns:
            Updated regime score
        """
        if agent_name not in self.regime_scores:
            self.regime_scores[agent_name] = {}
        
        if regime not in self.regime_scores[agent_name]:
            self.regime_scores[agent_name][regime] = 0.0
        
        old_score = self.regime_scores[agent_name][regime]
        new_score = self.learning_rate * reward + (1 - self.learning_rate) * old_score
        
        self.regime_scores[agent_name][regime] = new_score
        
        logger.debug(f"Updated {agent_name}/{regime} score: {old_score:.4f} -> {new_score:.4f}")
        
        return new_score
    
    def get_agent_confidence(self, agent_name: str) -> float:
        """
        Get confidence multiplier for agent based on learning
        Returns value in [0.5, 1.5] range
        """
        if agent_name not in self.agent_scores:
            return 1.0
        
        score = self.agent_scores[agent_name]
        
        # Map score to confidence multiplier
        # Positive scores increase confidence, negative decrease
        confidence = 1.0 + (score * 0.5)
        
        # Clamp to reasonable range
        return max(0.5, min(1.5, confidence))
    
    def get_regime_confidence(self, agent_name: str, regime: str) -> float:
        """Get regime-specific confidence for agent"""
        if agent_name not in self.regime_scores:
            return 1.0
        
        if regime not in self.regime_scores[agent_name]:
            return 1.0
        
        score = self.regime_scores[agent_name][regime]
        confidence = 1.0 + (score * 0.5)
        
        return max(0.5, min(1.5, confidence))
    
    def get_best_agent(self, regime: str = None) -> Optional[str]:
        """
        Get best-performing agent
        
        Args:
            regime: Optional regime filter
        
        Returns:
            Agent name with highest score
        """
        if regime:
            # Find best agent for this regime
            best_agent = None
            best_score = float('-inf')
            
            for agent, regimes in self.regime_scores.items():
                if regime in regimes:
                    score = regimes[regime]
                    if score > best_score:
                        best_score = score
                        best_agent = agent
            
            return best_agent
        else:
            # Find overall best agent
            if not self.agent_scores:
                return None
            
            return max(self.agent_scores.items(), key=lambda x: x[1])[0]
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of learning state"""
        return {
            "agent_scores": dict(self.agent_scores),
            "regime_scores": dict(self.regime_scores),
            "best_agent": self.get_best_agent(),
            "reward_metric": self.reward_metric,
            "learning_rate": self.learning_rate
        }
