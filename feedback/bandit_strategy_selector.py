"""
Multi-Armed Bandit for Options Strategy Selection

Implements Thompson Sampling with 28 arms (one per strategy).
Learns which strategies perform best in real-time using realized P&L as reward.

Author: Super Gnosis AI Developer
Created: 2025-11-19
"""

from __future__ import annotations
import numpy as np
from typing import Dict, Tuple, Optional
from collections import defaultdict
import json


class BanditStrategySelector:
    """
    Thompson Sampling bandit for selecting among 28 options strategies.
    
    Each arm represents one strategy. Reward is realized P&L percentage.
    Maintains both per-symbol and global statistics.
    """
    
    def __init__(
        self,
        num_strategies: int = 28,
        alpha_prior: float = 1.0,
        beta_prior: float = 1.0,
        per_symbol: bool = True
    ):
        """
        Initialize bandit with Beta priors.
        
        Args:
            num_strategies: Number of strategies (28)
            alpha_prior: Beta distribution alpha (success prior)
            beta_prior: Beta distribution beta (failure prior)
            per_symbol: Track separate statistics per symbol
        """
        self.num_strategies = num_strategies
        self.alpha_prior = alpha_prior
        self.beta_prior = beta_prior
        self.per_symbol = per_symbol
        
        # Global statistics: strategy_id -> (alpha, beta, total_reward, count)
        self.global_stats = {
            i: {
                'alpha': alpha_prior,
                'beta': beta_prior,
                'total_reward': 0.0,
                'count': 0
            }
            for i in range(1, num_strategies + 1)
        }
        
        # Per-symbol statistics: symbol -> strategy_id -> (alpha, beta, total_reward, count)
        self.symbol_stats: Dict[str, Dict[int, Dict]] = defaultdict(
            lambda: {
                i: {
                    'alpha': alpha_prior,
                    'beta': beta_prior,
                    'total_reward': 0.0,
                    'count': 0
                }
                for i in range(1, num_strategies + 1)
            }
        )
    
    def sample_strategy(
        self,
        symbol: Optional[str] = None,
        deterministic_strategy: Optional[int] = None
    ) -> Tuple[int, float]:
        """
        Sample a strategy using Thompson Sampling.
        
        Args:
            symbol: Symbol to get per-symbol stats (if enabled)
            deterministic_strategy: The strategy picked by deterministic logic
        
        Returns:
            (strategy_number, probability) tuple
        """
        # Choose which stats to use
        if self.per_symbol and symbol:
            stats = self.symbol_stats[symbol]
        else:
            stats = self.global_stats
        
        # Sample from Beta distribution for each arm
        samples = {}
        for strategy_id in range(1, self.num_strategies + 1):
            alpha = stats[strategy_id]['alpha']
            beta = stats[strategy_id]['beta']
            samples[strategy_id] = np.random.beta(alpha, beta)
        
        # Select arm with highest sample
        best_strategy = max(samples.keys(), key=lambda k: samples[k])
        best_probability = samples[best_strategy]
        
        return best_strategy, best_probability
    
    def get_strategy_probabilities(
        self,
        symbol: Optional[str] = None
    ) -> Dict[int, float]:
        """
        Get mean probability for each strategy (for dashboard display).
        
        Args:
            symbol: Symbol for per-symbol stats
        
        Returns:
            Dict mapping strategy_id -> mean probability
        """
        if self.per_symbol and symbol:
            stats = self.symbol_stats[symbol]
        else:
            stats = self.global_stats
        
        probabilities = {}
        for strategy_id in range(1, self.num_strategies + 1):
            alpha = stats[strategy_id]['alpha']
            beta = stats[strategy_id]['beta']
            # Mean of Beta distribution
            probabilities[strategy_id] = alpha / (alpha + beta)
        
        return probabilities
    
    def update(
        self,
        strategy_id: int,
        pnl_pct: float,
        symbol: Optional[str] = None
    ):
        """
        Update bandit statistics after trade closes.
        
        Args:
            strategy_id: Strategy number (1-28)
            pnl_pct: Realized P&L as percentage of capital risked
            symbol: Symbol for per-symbol tracking
        """
        if strategy_id < 1 or strategy_id > self.num_strategies:
            return
        
        # Convert P&L to success/failure for Beta distribution
        # Winning trade: success
        # Losing trade: failure
        # Scale by magnitude for partial updates
        
        success = max(0, pnl_pct / 100.0)  # Normalize to 0-1
        failure = max(0, -pnl_pct / 100.0)
        
        # Ensure at least some update
        if success == 0 and failure == 0:
            failure = 0.1  # Small loss for break-even
        
        # Update global stats
        self.global_stats[strategy_id]['alpha'] += success
        self.global_stats[strategy_id]['beta'] += failure
        self.global_stats[strategy_id]['total_reward'] += pnl_pct
        self.global_stats[strategy_id]['count'] += 1
        
        # Update per-symbol stats
        if self.per_symbol and symbol:
            self.symbol_stats[symbol][strategy_id]['alpha'] += success
            self.symbol_stats[symbol][strategy_id]['beta'] += failure
            self.symbol_stats[symbol][strategy_id]['total_reward'] += pnl_pct
            self.symbol_stats[symbol][strategy_id]['count'] += 1
    
    def get_top_strategies(
        self,
        top_n: int = 10,
        symbol: Optional[str] = None
    ) -> list[Tuple[int, float, int]]:
        """
        Get top N strategies by probability.
        
        Args:
            top_n: Number of top strategies to return
            symbol: Symbol for per-symbol stats
        
        Returns:
            List of (strategy_id, probability, count) tuples
        """
        probabilities = self.get_strategy_probabilities(symbol)
        
        if self.per_symbol and symbol:
            stats = self.symbol_stats[symbol]
        else:
            stats = self.global_stats
        
        # Sort by probability
        sorted_strategies = sorted(
            probabilities.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        
        # Add count information
        result = [
            (strategy_id, prob, stats[strategy_id]['count'])
            for strategy_id, prob in sorted_strategies
        ]
        
        return result
    
    def get_strategy_stats(
        self,
        strategy_id: int,
        symbol: Optional[str] = None
    ) -> Dict:
        """
        Get detailed statistics for a strategy.
        
        Args:
            strategy_id: Strategy number (1-28)
            symbol: Symbol for per-symbol stats
        
        Returns:
            Dict with alpha, beta, mean, count, avg_reward
        """
        if self.per_symbol and symbol:
            stats = self.symbol_stats[symbol][strategy_id]
        else:
            stats = self.global_stats[strategy_id]
        
        alpha = stats['alpha']
        beta = stats['beta']
        mean_prob = alpha / (alpha + beta)
        count = stats['count']
        avg_reward = stats['total_reward'] / max(1, count)
        
        return {
            'alpha': alpha,
            'beta': beta,
            'mean_probability': mean_prob,
            'count': count,
            'avg_reward_pct': avg_reward
        }
    
    def to_dict(self) -> Dict:
        """
        Serialize bandit state for persistence.
        
        Returns:
            Dict with all state
        """
        return {
            'num_strategies': self.num_strategies,
            'alpha_prior': self.alpha_prior,
            'beta_prior': self.beta_prior,
            'per_symbol': self.per_symbol,
            'global_stats': self.global_stats,
            'symbol_stats': dict(self.symbol_stats)
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BanditStrategySelector':
        """
        Deserialize bandit state from persistence.
        
        Args:
            data: Dict with state
        
        Returns:
            Restored BanditStrategySelector instance
        """
        bandit = cls(
            num_strategies=data.get('num_strategies', 28),
            alpha_prior=data.get('alpha_prior', 1.0),
            beta_prior=data.get('beta_prior', 1.0),
            per_symbol=data.get('per_symbol', True)
        )
        
        bandit.global_stats = data.get('global_stats', bandit.global_stats)
        bandit.symbol_stats = defaultdict(
            lambda: {
                i: {
                    'alpha': bandit.alpha_prior,
                    'beta': bandit.beta_prior,
                    'total_reward': 0.0,
                    'count': 0
                }
                for i in range(1, bandit.num_strategies + 1)
            },
            data.get('symbol_stats', {})
        )
        
        return bandit
    
    def reset_strategy(
        self,
        strategy_id: int,
        symbol: Optional[str] = None
    ):
        """
        Reset a strategy's statistics to prior.
        
        Args:
            strategy_id: Strategy to reset
            symbol: Symbol to reset (None = global)
        """
        if symbol and self.per_symbol:
            self.symbol_stats[symbol][strategy_id] = {
                'alpha': self.alpha_prior,
                'beta': self.beta_prior,
                'total_reward': 0.0,
                'count': 0
            }
        else:
            self.global_stats[strategy_id] = {
                'alpha': self.alpha_prior,
                'beta': self.beta_prior,
                'total_reward': 0.0,
                'count': 0
            }
