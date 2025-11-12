"""
Permutation Entropy - Ordinal Pattern Complexity
Based on: https://github.com/neurotrader888/permutation-entropy

Measures complexity via ordinal patterns in time series.
Low entropy = predictable, High entropy = random/complex.

H = -Σ p(π) log p(π) / log(m!)

Reference: "Permutation Entropy: A Natural Complexity Measure" (Bandt & Pompe, 2002)
"""

from dataclasses import dataclass
from typing import Tuple
import itertools
import math

import numpy as np
import pandas as pd


@dataclass
class PermutationEntropyResult:
    """Permutation entropy calculation results."""
    
    entropy: pd.Series
    """Normalized permutation entropy [0, 1]."""
    
    complexity: pd.Series
    """Statistical complexity (entropy × disequilibrium)."""
    
    most_common_pattern: Tuple[int, ...]
    """Most frequently occurring ordinal pattern."""
    
    pattern_distribution: dict
    """Distribution of all patterns."""


def compute_permutation_entropy(
    ts: pd.Series,
    order: int = 3,
    delay: int = 1,
    window: int = None,
    normalize: bool = True,
) -> PermutationEntropyResult:
    """
    Compute permutation entropy of time series.
    
    Args:
        ts: Time series
        order: Embedding dimension (pattern length)
        delay: Time delay between elements
        window: Rolling window size (None = use full series)
        normalize: Normalize to [0, 1]
    
    Returns:
        PermutationEntropyResult
    
    Example:
        >>> prices = pd.Series([100, 101, 99, 102, 98, 103])
        >>> result = compute_permutation_entropy(prices, order=3)
        >>> # Pattern [100, 101, 99] → ranks [1, 2, 0] → permutation (1,2,0)
        >>> if result.entropy.iloc[-1] > 0.8:
        >>>     print("High complexity - difficult to predict")
    """
    if window is None:
        # Single calculation
        entropy_val, complexity_val, patterns = _perm_entropy_single(
            ts.values, order, delay, normalize
        )
        
        entropy_series = pd.Series(entropy_val, index=[ts.index[-1]])
        complexity_series = pd.Series(complexity_val, index=[ts.index[-1]])
        
        most_common = max(patterns, key=patterns.get)
        
        return PermutationEntropyResult(
            entropy=entropy_series,
            complexity=complexity_series,
            most_common_pattern=most_common,
            pattern_distribution=patterns,
        )
    else:
        # Rolling calculation
        entropy_values = []
        complexity_values = []
        
        for i in range(window, len(ts) + 1):
            window_data = ts.iloc[i-window:i].values
            h, c, _ = _perm_entropy_single(window_data, order, delay, normalize)
            entropy_values.append(h)
            complexity_values.append(c)
        
        entropy_series = pd.Series(
            entropy_values,
            index=ts.index[window-1:],
        )
        complexity_series = pd.Series(
            complexity_values,
            index=ts.index[window-1:],
        )
        
        # Get patterns from last window
        _, _, patterns = _perm_entropy_single(
            ts.values[-window:], order, delay, normalize
        )
        most_common = max(patterns, key=patterns.get) if patterns else tuple()
        
        return PermutationEntropyResult(
            entropy=entropy_series,
            complexity=complexity_series,
            most_common_pattern=most_common,
            pattern_distribution=patterns,
        )


def _perm_entropy_single(
    data: np.ndarray,
    order: int,
    delay: int,
    normalize: bool,
) -> Tuple[float, float, dict]:
    """Compute permutation entropy for single window."""
    n = len(data)
    patterns = {}
    
    # Extract all possible ordinal patterns
    for i in range(n - delay * (order - 1)):
        # Get subsequence
        subseq_indices = [i + j * delay for j in range(order)]
        subseq = data[subseq_indices]
        
        # Convert to ordinal pattern (ranks)
        pattern = tuple(np.argsort(np.argsort(subseq)))
        
        patterns[pattern] = patterns.get(pattern, 0) + 1
    
    # Compute entropy
    total = sum(patterns.values())
    if total == 0:
        return 0.0, 0.0, patterns
    
    probs = np.array([count / total for count in patterns.values()])
    entropy = -np.sum(probs * np.log(probs + 1e-10))
    
    # Normalize
    if normalize:
        max_entropy = np.log(math.factorial(order))
        entropy = entropy / max_entropy if max_entropy > 0 else 0.0
    
    # Statistical complexity: entropy × disequilibrium
    # Disequilibrium measures distance from uniform distribution
    uniform_prob = 1.0 / math.factorial(order)
    disequilibrium = np.sum((probs - uniform_prob) ** 2)
    
    complexity = entropy * disequilibrium
    
    return entropy, complexity, patterns


def detect_regime_change_pe(
    ts: pd.Series,
    order: int = 3,
    window: int = 50,
    threshold: float = 0.2,
) -> pd.Series:
    """
    Detect regime changes using permutation entropy.
    
    Args:
        ts: Time series
        order: Pattern order
        window: Window size
        threshold: Threshold for entropy change
    
    Returns:
        Boolean series indicating regime changes
    """
    result = compute_permutation_entropy(ts, order=order, window=window)
    
    # Detect significant changes in entropy
    entropy_change = result.entropy.diff().abs()
    regime_changes = entropy_change > threshold
    
    return regime_changes


# Example
if __name__ == "__main__":
    np.random.seed(42)
    
    # Generate time series with regime change
    n = 300
    ts1 = np.random.randn(n // 2) * 0.5 + 100  # Low volatility
    ts2 = np.random.randn(n // 2) * 2.0 + 100  # High volatility
    ts = pd.Series(np.concatenate([ts1, ts2]))
    
    # Compute permutation entropy
    result = compute_permutation_entropy(ts, order=3, window=50)
    
    print(f"Mean entropy: {result.entropy.mean():.4f}")
    print(f"Mean complexity: {result.complexity.mean():.4f}")
    print(f"Most common pattern: {result.most_common_pattern}")
    
    # Detect regime changes
    changes = detect_regime_change_pe(ts, window=50)
    print(f"Detected regime changes: {changes.sum()}")
