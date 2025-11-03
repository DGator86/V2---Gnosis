from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Literal, Optional
from collections import deque

MarketState = Literal["accumulation", "trending_up", "distribution", "trending_down", "ranging"]

class SimpleHMM:
    """
    Simple Hidden Markov Model for market regime detection
    
    States: 5 market regimes (accumulation, trending_up, distribution, trending_down, ranging)
    Observations: (price_momentum, volume_change, volatility)
    
    This is a simplified HMM using heuristic transition probabilities.
    For production, consider using hmmlearn library for proper EM training.
    """
    
    def __init__(self):
        # State labels
        self.states = ["accumulation", "trending_up", "distribution", "trending_down", "ranging"]
        
        # Transition probability matrix (from → to)
        # Rows: current state, Columns: next state
        self.transition_matrix = np.array([
            # From: accum,  trend_up, distrib,  trend_dn, ranging
            [0.70, 0.25, 0.02, 0.01, 0.02],  # From accumulation
            [0.05, 0.75, 0.15, 0.02, 0.03],  # From trending_up
            [0.02, 0.10, 0.70, 0.15, 0.03],  # From distribution
            [0.10, 0.02, 0.03, 0.75, 0.10],  # From trending_down
            [0.20, 0.20, 0.20, 0.20, 0.20],  # From ranging (uniform)
        ])
        
        # Initial state probabilities (start in ranging)
        self.initial_probs = np.array([0.1, 0.2, 0.1, 0.2, 0.4])
        
        # Current belief (state probabilities)
        self.belief = self.initial_probs.copy()
        
        # History for Viterbi algorithm
        self.observation_history = deque(maxlen=50)
        
    def _emission_probability(
        self, 
        state: str, 
        momo: float, 
        vol_change: float, 
        volatility: float
    ) -> float:
        """
        Calculate P(observation | state)
        
        Args:
            state: Current market state
            momo: Price momentum z-score (-3 to +3)
            vol_change: Volume change ratio (0 to 2+)
            volatility: Volatility z-score (-3 to +3)
        
        Returns:
            Probability of observation given state
        """
        # Accumulation: Low momentum, high volume, moderate vol
        if state == "accumulation":
            momo_score = self._gaussian_score(momo, mu=0.0, sigma=0.5)
            vol_score = self._gaussian_score(vol_change, mu=1.5, sigma=0.3)
            vola_score = self._gaussian_score(volatility, mu=0.5, sigma=0.5)
            return momo_score * 0.3 + vol_score * 0.5 + vola_score * 0.2
        
        # Trending Up: Positive momentum, declining volume, moderate vol
        elif state == "trending_up":
            momo_score = self._gaussian_score(momo, mu=1.5, sigma=0.8)
            vol_score = self._gaussian_score(vol_change, mu=0.8, sigma=0.3)
            vola_score = self._gaussian_score(volatility, mu=-0.5, sigma=0.5)
            return momo_score * 0.6 + vol_score * 0.2 + vola_score * 0.2
        
        # Distribution: Low momentum, high volume, moderate vol
        elif state == "distribution":
            momo_score = self._gaussian_score(momo, mu=0.0, sigma=0.5)
            vol_score = self._gaussian_score(vol_change, mu=1.5, sigma=0.3)
            vola_score = self._gaussian_score(volatility, mu=0.5, sigma=0.5)
            return momo_score * 0.3 + vol_score * 0.5 + vola_score * 0.2
        
        # Trending Down: Negative momentum, declining volume, high vol
        elif state == "trending_down":
            momo_score = self._gaussian_score(momo, mu=-1.5, sigma=0.8)
            vol_score = self._gaussian_score(vol_change, mu=0.8, sigma=0.3)
            vola_score = self._gaussian_score(volatility, mu=1.0, sigma=0.7)
            return momo_score * 0.6 + vol_score * 0.2 + vola_score * 0.2
        
        # Ranging: Near-zero momentum, low volume, low vol
        elif state == "ranging":
            momo_score = self._gaussian_score(momo, mu=0.0, sigma=0.3)
            vol_score = self._gaussian_score(vol_change, mu=0.7, sigma=0.2)
            vola_score = self._gaussian_score(volatility, mu=-0.5, sigma=0.3)
            return momo_score * 0.4 + vol_score * 0.3 + vola_score * 0.3
        
        return 0.2  # Uniform fallback
    
    def _gaussian_score(self, x: float, mu: float, sigma: float) -> float:
        """Gaussian likelihood (unnormalized)"""
        return max(0.01, np.exp(-0.5 * ((x - mu) / sigma) ** 2))
    
    def update(
        self, 
        momo: float, 
        vol_change: float, 
        volatility: float
    ) -> tuple[str, np.ndarray]:
        """
        Update belief state with new observation (forward algorithm)
        
        Args:
            momo: Price momentum z-score
            vol_change: Volume change ratio
            volatility: Volatility z-score
        
        Returns:
            (most_likely_state, state_probabilities)
        """
        # Store observation
        self.observation_history.append((momo, vol_change, volatility))
        
        # Calculate emission probabilities for all states
        emission_probs = np.array([
            self._emission_probability(state, momo, vol_change, volatility)
            for state in self.states
        ])
        
        # Prediction step: P(state_t | obs_1:t-1)
        predicted = self.transition_matrix.T @ self.belief
        
        # Update step: P(state_t | obs_1:t)
        likelihood = predicted * emission_probs
        self.belief = likelihood / (likelihood.sum() + 1e-9)
        
        # Get most likely state
        best_idx = np.argmax(self.belief)
        best_state = self.states[best_idx]
        
        return best_state, self.belief.copy()
    
    def get_transition_probabilities(self, current_state: str) -> dict[str, float]:
        """
        Get transition probabilities from current state to all others
        
        Args:
            current_state: Current market state
        
        Returns:
            Dictionary mapping next_state → probability
        """
        state_idx = self.states.index(current_state)
        probs = self.transition_matrix[state_idx]
        
        return {
            state: float(prob)
            for state, prob in zip(self.states, probs)
        }
    
    def reset(self):
        """Reset to initial belief"""
        self.belief = self.initial_probs.copy()
        self.observation_history.clear()

def _compute_features(df: pd.DataFrame) -> tuple[float, float, float]:
    """
    Extract HMM observation features from price/volume data
    
    Returns:
        (momentum_z, volume_change, volatility_z)
    """
    if len(df) < 20:
        return 0.0, 1.0, 0.0
    
    df = df.tail(50).copy()
    
    # 1. Momentum z-score (20-bar)
    returns = np.log(df["price"]).diff()
    recent_ret = returns.tail(20)
    momo_z = recent_ret.mean() / (recent_ret.std() + 1e-8)
    momo_z = float(np.clip(momo_z, -3, 3))
    
    # 2. Volume change ratio (recent 10 bars vs baseline 20 bars)
    vol_recent = df["volume"].tail(10).mean()
    vol_baseline = df["volume"].tail(30).head(20).mean()
    vol_change = vol_recent / (vol_baseline + 1e-8)
    vol_change = float(np.clip(vol_change, 0, 3))
    
    # 3. Volatility z-score (comparing recent to baseline)
    vol_recent_std = returns.tail(10).std()
    vol_baseline_std = returns.tail(50).std()
    vola_z = (vol_recent_std - vol_baseline_std) / (vol_baseline_std + 1e-8)
    vola_z = float(np.clip(vola_z, -3, 3))
    
    return momo_z, vol_change, vola_z

def compute_markov_regime_v0(
    symbol: str, 
    now: datetime, 
    df: pd.DataFrame,
    hmm: Optional[SimpleHMM] = None
) -> dict:
    """
    Compute Hidden Markov Model regime features
    
    Args:
        symbol: Trading symbol
        now: Current timestamp
        df: DataFrame with columns: t_event, price, volume
        hmm: Optional existing HMM instance (for stateful updates)
    
    Returns:
        Dictionary with HMM regime features
    """
    if df.empty or len(df) < 20:
        return {
            "current_state": "ranging",
            "state_probabilities": {
                "accumulation": 0.2,
                "trending_up": 0.2,
                "distribution": 0.2,
                "trending_down": 0.2,
                "ranging": 0.2
            },
            "confidence": 0.0,
            "transition_probs": {},
            "momentum_z": 0.0,
            "volume_change": 1.0,
            "volatility_z": 0.0
        }
    
    # Initialize HMM if not provided
    if hmm is None:
        hmm = SimpleHMM()
    
    # Extract observation features
    momo_z, vol_change, vola_z = _compute_features(df)
    
    # Update HMM
    current_state, state_probs = hmm.update(momo_z, vol_change, vola_z)
    
    # Get confidence (max probability)
    confidence = float(state_probs.max())
    
    # Get transition probabilities from current state
    transition_probs = hmm.get_transition_probabilities(current_state)
    
    return {
        "current_state": current_state,
        "state_probabilities": {
            state: float(prob)
            for state, prob in zip(hmm.states, state_probs)
        },
        "confidence": confidence,
        "transition_probs": transition_probs,
        "momentum_z": momo_z,
        "volume_change": vol_change,
        "volatility_z": vola_z,
        "hmm_instance": hmm  # Return instance for stateful updates
    }

# Global HMM instance for stateful tracking (optional)
_global_hmms = {}

def get_or_create_hmm(symbol: str) -> SimpleHMM:
    """Get or create HMM instance for a symbol"""
    if symbol not in _global_hmms:
        _global_hmms[symbol] = SimpleHMM()
    return _global_hmms[symbol]

def compute_markov_regime_stateful(
    symbol: str, 
    now: datetime, 
    df: pd.DataFrame
) -> dict:
    """
    Compute HMM regime with persistent state per symbol
    
    This maintains HMM state across multiple calls for same symbol.
    Useful for real-time streaming data.
    """
    hmm = get_or_create_hmm(symbol)
    return compute_markov_regime_v0(symbol, now, df, hmm)
