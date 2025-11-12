"""
Reversibility Testing for Causality and Look-Ahead Bias
Tests whether feature -> target relationship is causal (not reversed).

Tests:
- Granger causality: Does past feature predict future target?
- Reverse Granger: Does past target predict future feature? (should be NO)
- Information leak detection via time-reversal
"""

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class ReversibilityResult:
    """Results from reversibility/causality testing."""
    
    granger_pvalue: float
    """P-value for Granger causality test (feature -> target)."""
    
    reverse_granger_pvalue: float
    """P-value for reverse test (target -> feature). Should be > 0.05."""
    
    is_causal: bool
    """Whether feature has predictive power for target."""
    
    is_reversed: bool
    """Whether target predicts feature (indication of look-ahead bias)."""
    
    information_leak_score: float
    """Score indicating potential information leakage (0 = none, 1 = severe)."""


def test_reversibility(
    feature: pd.Series,
    target: pd.Series,
    max_lag: int = 5,
    alpha: float = 0.05,
) -> ReversibilityResult:
    """
    Test feature-target causality and detect look-ahead bias.
    
    Args:
        feature: Feature time series
        target: Target time series
        max_lag: Maximum lag for Granger test
        alpha: Significance level
    
    Returns:
        ReversibilityResult with test statistics
    """
    # Align series
    df = pd.DataFrame({'feature': feature, 'target': target}).dropna()
    
    # Forward Granger: feature -> target
    granger_pval = _granger_causality_test(
        df['feature'], df['target'], max_lag
    )
    
    # Reverse Granger: target -> feature (should NOT be significant)
    reverse_pval = _granger_causality_test(
        df['target'], df['feature'], max_lag
    )
    
    # Information leak detection
    leak_score = _detect_information_leak(df['feature'], df['target'])
    
    is_causal = granger_pval < alpha
    is_reversed = reverse_pval < alpha
    
    return ReversibilityResult(
        granger_pvalue=granger_pval,
        reverse_granger_pvalue=reverse_pval,
        is_causal=is_causal,
        is_reversed=is_reversed,
        information_leak_score=leak_score,
    )


def _granger_causality_test(
    cause: pd.Series,
    effect: pd.Series,
    max_lag: int,
) -> float:
    """Simple Granger causality test using F-statistic."""
    from sklearn.linear_model import LinearRegression
    
    # Create lagged features
    data = []
    for lag in range(1, max_lag + 1):
        data.append(effect.shift(lag).rename(f'effect_lag{lag}'))
        data.append(cause.shift(lag).rename(f'cause_lag{lag}'))
    
    df = pd.concat([effect] + data, axis=1).dropna()
    
    # Restricted model: effect ~ past_effect
    restricted_features = [col for col in df.columns if 'effect_lag' in col]
    X_restricted = df[restricted_features]
    y = df[effect.name]
    
    model_restricted = LinearRegression()
    model_restricted.fit(X_restricted, y)
    rss_restricted = ((y - model_restricted.predict(X_restricted))**2).sum()
    
    # Unrestricted model: effect ~ past_effect + past_cause
    unrestricted_features = [col for col in df.columns if col != effect.name]
    X_unrestricted = df[unrestricted_features]
    
    model_unrestricted = LinearRegression()
    model_unrestricted.fit(X_unrestricted, y)
    rss_unrestricted = ((y - model_unrestricted.predict(X_unrestricted))**2).sum()
    
    # F-statistic
    n = len(df)
    p_restricted = len(restricted_features)
    p_unrestricted = len(unrestricted_features)
    
    if rss_unrestricted == 0:
        return 1.0
    
    f_stat = ((rss_restricted - rss_unrestricted) / (p_unrestricted - p_restricted)) / \
             (rss_unrestricted / (n - p_unrestricted - 1))
    
    # P-value
    pval = 1 - stats.f.cdf(f_stat, p_unrestricted - p_restricted, n - p_unrestricted - 1)
    
    return pval


def _detect_information_leak(
    feature: pd.Series,
    target: pd.Series,
) -> float:
    """
    Detect information leakage via correlation with future values.
    
    Returns score [0, 1] where 1 indicates severe leakage.
    """
    # Correlation with contemporaneous target (should be moderate)
    corr_t0 = abs(feature.corr(target))
    
    # Correlation with future target (should be lower)
    corr_t1 = abs(feature.corr(target.shift(-1)))
    corr_t2 = abs(feature.corr(target.shift(-2)))
    
    # If feature correlates MORE with future than present, likely leak
    future_corr = max(corr_t1, corr_t2)
    
    if future_corr > corr_t0:
        leak_score = (future_corr - corr_t0) / (future_corr + 1e-9)
    else:
        leak_score = 0.0
    
    return min(leak_score, 1.0)


if __name__ == "__main__":
    np.random.seed(42)
    n = 200
    
    # True causal: feature -> target
    feature_causal = np.random.randn(n)
    target = np.zeros(n)
    for t in range(1, n):
        target[t] = 0.5 * feature_causal[t-1] + np.random.randn()
    
    result = test_reversibility(
        pd.Series(feature_causal),
        pd.Series(target),
    )
    
    print("CAUSAL FEATURE:")
    print(f"  Forward Granger p-value: {result.granger_pvalue:.4f}")
    print(f"  Reverse Granger p-value: {result.reverse_granger_pvalue:.4f}")
    print(f"  Is causal: {result.is_causal}")
    print(f"  Is reversed: {result.is_reversed}")
    print(f"  Leak score: {result.information_leak_score:.4f}")
