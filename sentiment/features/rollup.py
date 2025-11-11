"""Rolling statistics computation for sentiment analysis."""

from __future__ import annotations
from typing import Deque, Tuple, Optional
from collections import deque
import math
import numpy as np
import logging

logger = logging.getLogger(__name__)


class RollingStats:
    """Compute rolling statistics on weighted sentiment scores."""
    
    def __init__(self, maxlen: int = 5000):
        """Initialize rolling statistics buffer.
        
        Args:
            maxlen: Maximum buffer size
        """
        self.maxlen = maxlen
        # Store: (timestamp, score, weight, is_unique, source_weight)
        self.buf: Deque[Tuple[float, float, float, bool, float]] = deque(maxlen=maxlen)
        
        # Cache for efficiency
        self._cache_valid = False
        self._cached_arrays = None
    
    def add(
        self,
        ts: float,
        score: float,
        weight: float,
        is_unique: bool,
        source_weight: float
    ):
        """Add a new data point.
        
        Args:
            ts: Timestamp
            score: Sentiment score [-1, 1]
            weight: Combined weight (recency * source * etc.)
            is_unique: Whether this is unique content
            source_weight: Source-specific weight
        """
        self.buf.append((ts, score, weight, is_unique, source_weight))
        self._cache_valid = False
    
    def _get_arrays(self) -> Optional[Tuple[np.ndarray, ...]]:
        """Get numpy arrays from buffer.
        
        Returns:
            Tuple of arrays or None if empty
        """
        if not self.buf:
            return None
        
        if self._cache_valid and self._cached_arrays is not None:
            return self._cached_arrays
        
        arr = np.array(self.buf, dtype=float)
        ts, scores, weights, unique, src_weights = arr.T
        
        self._cached_arrays = (ts, scores, weights, unique, src_weights)
        self._cache_valid = True
        
        return self._cached_arrays
    
    def weighted_mean_std_skew(self) -> Tuple[float, float, float]:
        """Compute weighted mean, std dev, and skewness.
        
        Returns:
            Tuple of (mean, std, skew)
        """
        arrays = self._get_arrays()
        if arrays is None:
            return 0.0, 0.0, 0.0
        
        _, scores, weights, _, _ = arrays
        total_weight = weights.sum()
        
        if total_weight <= 0:
            return 0.0, 0.0, 0.0
        
        # Weighted mean
        mean = float((weights * scores).sum() / total_weight)
        
        # Weighted variance
        variance = float((weights * (scores - mean) ** 2).sum() / total_weight)
        std = math.sqrt(max(variance, 1e-12))
        
        # Weighted skewness
        if std > 1e-9:
            skew = float(
                ((weights * ((scores - mean) / std) ** 3).sum()) / total_weight
            )
        else:
            skew = 0.0
        
        return mean, std, skew
    
    def disagreement(self) -> float:
        """Compute disagreement metric (spread between positive and negative).
        
        Returns:
            Disagreement score [0, 1]
        """
        arrays = self._get_arrays()
        if arrays is None:
            return 0.0
        
        _, scores, weights, _, _ = arrays
        
        # Calculate weighted positive and negative fractions
        pos_weight = weights[scores > 0].sum() if (scores > 0).any() else 0.0
        neg_weight = weights[scores < 0].sum() if (scores < 0).any() else 0.0
        total = pos_weight + neg_weight
        
        if total == 0:
            return 0.0
        
        # Disagreement is the imbalance between positive and negative
        return float(abs(pos_weight / total - neg_weight / total))
    
    def momentum(self, span: int = 20) -> float:
        """Compute momentum (trend) of sentiment.
        
        Args:
            span: EMA span for smoothing
            
        Returns:
            Momentum value
        """
        arrays = self._get_arrays()
        if arrays is None:
            return 0.0
        
        _, scores, weights, _, _ = arrays
        
        if len(scores) < 2:
            return 0.0
        
        # Compute EWMA
        alpha = 2.0 / (span + 1.0)
        ewma = 0.0
        
        for score, weight in zip(scores, weights):
            ewma = alpha * score + (1 - alpha) * ewma
        
        # Momentum is difference from mean
        mean, _, _ = self.weighted_mean_std_skew()
        return float(ewma - mean)
    
    def novelty_ratio(self) -> float:
        """Compute ratio of unique content.
        
        Returns:
            Novelty ratio [0, 1]
        """
        arrays = self._get_arrays()
        if arrays is None:
            return 1.0
        
        _, _, _, unique, _ = arrays
        return float(unique.sum() / len(unique)) if len(unique) > 0 else 1.0
    
    def source_weighted_mean(self) -> float:
        """Compute mean using source weights.
        
        Returns:
            Source-weighted mean sentiment
        """
        arrays = self._get_arrays()
        if arrays is None:
            return 0.0
        
        _, scores, _, _, src_weights = arrays
        
        if len(scores) == 0:
            return 0.0
        
        total_weight = src_weights.sum()
        if total_weight <= 0:
            return 0.0
        
        return float((src_weights * scores).sum() / total_weight)
    
    def entropy(self) -> float:
        """Compute entropy of sentiment distribution.
        
        Returns:
            Normalized entropy [0, 1]
        """
        arrays = self._get_arrays()
        if arrays is None:
            return 0.0
        
        _, scores, weights, _, _ = arrays
        
        # Estimate distribution across pos/neu/neg
        pos_weight = weights[scores > 0.05].sum() if (scores > 0.05).any() else 0.0
        neg_weight = weights[scores < -0.05].sum() if (scores < -0.05).any() else 0.0
        neu_weight = weights[abs(scores) <= 0.05].sum() if (abs(scores) <= 0.05).any() else 0.0
        
        total = pos_weight + neg_weight + neu_weight
        if total <= 0:
            return 0.0
        
        # Calculate Shannon entropy
        probs = [pos_weight / total, neg_weight / total, neu_weight / total]
        entropy = 0.0
        
        for p in probs:
            if p > 1e-12:
                entropy -= p * math.log(p)
        
        # Normalize by max entropy (log 3)
        return float(entropy / math.log(3.0)) if entropy > 0 else 0.0
    
    def sharpe_like(self, drift_span: int = 20) -> float:
        """Compute Sharpe-like ratio (signal to noise).
        
        Args:
            drift_span: Span for momentum calculation
            
        Returns:
            Sharpe-like ratio
        """
        mean, std, _ = self.weighted_mean_std_skew()
        
        if std <= 1e-9:
            return 0.0
        
        mom = self.momentum(span=drift_span)
        return float(mom / std)
    
    def surprise(
        self,
        history_mean: float,
        history_std: float
    ) -> float:
        """Compute surprise (z-score vs historical baseline).
        
        Args:
            history_mean: Historical mean
            history_std: Historical standard deviation
            
        Returns:
            Z-score of current mean vs history
        """
        if history_std <= 1e-9:
            return 0.0
        
        current_mean, _, _ = self.weighted_mean_std_skew()
        return float((current_mean - history_mean) / history_std)
    
    def get_summary_stats(self) -> dict:
        """Get all summary statistics.
        
        Returns:
            Dictionary of all computed statistics
        """
        mean, std, skew = self.weighted_mean_std_skew()
        
        return {
            "n_points": len(self.buf),
            "mean": mean,
            "std": std,
            "skew": skew,
            "disagreement": self.disagreement(),
            "momentum": self.momentum(),
            "novelty_ratio": self.novelty_ratio(),
            "source_weighted_mean": self.source_weighted_mean(),
            "entropy": self.entropy(),
            "sharpe_like": self.sharpe_like(),
        }