"""
Monte Carlo Permutation Tests (MCPT)
Based on: https://github.com/neurotrader888/MonteCarloPermutation

MCPT tests whether a trading strategy's performance is statistically significant
or just due to random chance. It works by:
1. Computing observed metric (e.g., Sharpe ratio)
2. Randomly shuffling returns many times
3. Computing metric on each shuffle
4. Comparing observed to null distribution

If observed metric exceeds 95% of shuffled metrics, strategy is significant (p < 0.05).

Reference: "Testing Trading Strategies" (Aronson, 2007)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Callable

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class MCPTResult:
    """Results from Monte Carlo Permutation Test."""
    
    observed_metric: float
    """Observed value of test statistic."""
    
    null_distribution: np.ndarray
    """Distribution of metrics under null hypothesis (random shuffling)."""
    
    p_value: float
    """Probability that observed metric could occur by chance."""
    
    is_significant: bool
    """Whether result is statistically significant at given alpha."""
    
    alpha: float
    """Significance level used for test."""
    
    n_permutations: int
    """Number of permutations performed."""
    
    metric_name: str
    """Name of metric tested."""
    
    percentile_rank: float
    """Percentile of observed metric in null distribution."""


def mcpt_validate(
    strategy_returns: pd.Series,
    metric: str = 'sharpe',
    n_permutations: int = 1000,
    alpha: float = 0.05,
    metric_func: Optional[Callable] = None,
) -> MCPTResult:
    """
    Perform Monte Carlo Permutation Test on strategy returns.
    
    Args:
        strategy_returns: Time series of strategy returns
        metric: Metric to test ('sharpe', 'sortino', 'calmar', 'total_return', 'custom')
        n_permutations: Number of random shuffles
        alpha: Significance level (default 0.05 = 95% confidence)
        metric_func: Custom metric function (returns -> float) if metric='custom'
    
    Returns:
        MCPTResult with test statistics
    
    Example:
        >>> strategy_rets = compute_strategy_returns(signals, prices)
        >>> result = mcpt_validate(strategy_rets, metric='sharpe', n_permutations=2000)
        >>> if result.is_significant:
        >>>     print(f"Strategy is significant! p-value: {result.p_value:.4f}")
        >>> else:
        >>>     print("Strategy performance could be due to luck")
    """
    # Remove NaN values
    returns = strategy_returns.dropna()
    
    if len(returns) < 30:
        raise ValueError(f"Insufficient data: need at least 30 returns, got {len(returns)}")
    
    # Select metric function
    if metric == 'custom' and metric_func is None:
        raise ValueError("Must provide metric_func when metric='custom'")
    
    if metric_func is None:
        metric_func = _get_metric_function(metric)
    
    # Compute observed metric
    observed = metric_func(returns)
    
    # Generate null distribution via permutation
    null_distribution = np.zeros(n_permutations)
    
    for i in range(n_permutations):
        # Randomly shuffle returns (destroys time structure)
        shuffled = returns.sample(frac=1.0, replace=False).values
        null_distribution[i] = metric_func(pd.Series(shuffled))
    
    # Compute p-value (two-tailed test)
    if observed >= 0:
        # Right tail: count how many shuffles are >= observed
        p_value = (null_distribution >= observed).sum() / n_permutations
    else:
        # Left tail: count how many shuffles are <= observed
        p_value = (null_distribution <= observed).sum() / n_permutations
    
    # Two-tailed adjustment
    p_value = min(p_value * 2, 1.0)
    
    # Significance test
    is_significant = p_value < alpha
    
    # Percentile rank
    percentile = stats.percentileofscore(null_distribution, observed)
    
    return MCPTResult(
        observed_metric=observed,
        null_distribution=null_distribution,
        p_value=p_value,
        is_significant=is_significant,
        alpha=alpha,
        n_permutations=n_permutations,
        metric_name=metric,
        percentile_rank=percentile,
    )


def _get_metric_function(metric: str) -> Callable:
    """Get metric function by name."""
    
    def sharpe(returns: pd.Series) -> float:
        if returns.std() == 0:
            return 0.0
        return returns.mean() / returns.std() * np.sqrt(252)
    
    def sortino(returns: pd.Series) -> float:
        downside = returns[returns < 0]
        if len(downside) == 0 or downside.std() == 0:
            return 0.0
        return returns.mean() / downside.std() * np.sqrt(252)
    
    def calmar(returns: pd.Series) -> float:
        cumrets = (1 + returns).cumprod()
        running_max = cumrets.cummax()
        drawdown = (cumrets - running_max) / running_max
        max_dd = abs(drawdown.min())
        if max_dd == 0:
            return 0.0
        annual_return = returns.mean() * 252
        return annual_return / max_dd
    
    def total_return(returns: pd.Series) -> float:
        return (1 + returns).prod() - 1.0
    
    def win_rate(returns: pd.Series) -> float:
        if len(returns) == 0:
            return 0.0
        return (returns > 0).mean()
    
    metrics = {
        'sharpe': sharpe,
        'sortino': sortino,
        'calmar': calmar,
        'total_return': total_return,
        'win_rate': win_rate,
    }
    
    if metric not in metrics:
        raise ValueError(f"Unknown metric: {metric}. Choose from {list(metrics.keys())}")
    
    return metrics[metric]


def mcpt_multiple_strategies(
    strategies: Dict[str, pd.Series],
    metric: str = 'sharpe',
    n_permutations: int = 1000,
    alpha: float = 0.05,
    bonferroni_correction: bool = True,
) -> Dict[str, MCPTResult]:
    """
    Test multiple strategies with optional Bonferroni correction for multiple testing.
    
    Args:
        strategies: Dictionary of {strategy_name: returns_series}
        metric: Metric to test
        n_permutations: Number of permutations
        alpha: Base significance level
        bonferroni_correction: Apply Bonferroni correction for multiple comparisons
    
    Returns:
        Dictionary of {strategy_name: MCPTResult}
    
    Example:
        >>> strategies = {
        >>>     'momentum': momentum_returns,
        >>>     'mean_reversion': mr_returns,
        >>>     'breakout': breakout_returns,
        >>> }
        >>> results = mcpt_multiple_strategies(strategies, n_permutations=2000)
        >>> for name, result in results.items():
        >>>     if result.is_significant:
        >>>         print(f"{name}: Significant (p={result.p_value:.4f})")
    """
    # Bonferroni correction
    if bonferroni_correction:
        adjusted_alpha = alpha / len(strategies)
    else:
        adjusted_alpha = alpha
    
    results = {}
    for name, returns in strategies.items():
        results[name] = mcpt_validate(
            returns,
            metric=metric,
            n_permutations=n_permutations,
            alpha=adjusted_alpha,
        )
    
    return results


def compute_confidence_interval(
    result: MCPTResult,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Compute confidence interval from null distribution.
    
    Args:
        result: MCPTResult from mcpt_validate
        confidence: Confidence level (0.95 = 95%)
    
    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    alpha = 1 - confidence
    lower = np.percentile(result.null_distribution, alpha/2 * 100)
    upper = np.percentile(result.null_distribution, (1 - alpha/2) * 100)
    return lower, upper


def bootstrap_metric(
    returns: pd.Series,
    metric: str = 'sharpe',
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
) -> Dict[str, float]:
    """
    Bootstrap confidence interval for a metric (alternative to MCPT).
    
    Bootstrap resamples WITH replacement (vs. MCPT shuffles WITHOUT).
    Use bootstrap for confidence intervals, MCPT for significance testing.
    
    Args:
        returns: Strategy returns
        metric: Metric name
        n_bootstrap: Number of bootstrap samples
        confidence: Confidence level
    
    Returns:
        Dictionary with mean, lower, and upper bounds
    """
    metric_func = _get_metric_function(metric)
    
    bootstrap_dist = np.zeros(n_bootstrap)
    n = len(returns)
    
    for i in range(n_bootstrap):
        # Resample with replacement
        sample = returns.sample(n=n, replace=True)
        bootstrap_dist[i] = metric_func(sample)
    
    alpha = 1 - confidence
    lower = np.percentile(bootstrap_dist, alpha/2 * 100)
    upper = np.percentile(bootstrap_dist, (1 - alpha/2) * 100)
    
    return {
        'mean': bootstrap_dist.mean(),
        'lower': lower,
        'upper': upper,
        'std': bootstrap_dist.std(),
    }


def deflated_sharpe_ratio(
    observed_sharpe: float,
    n_trials: int,
    returns_std: float,
    n_observations: int,
    skew: float = 0.0,
    excess_kurtosis: float = 0.0,
) -> float:
    """
    Compute Deflated Sharpe Ratio (DSR) to account for multiple testing and non-normality.
    
    Reference: "The Deflated Sharpe Ratio" (Bailey & López de Prado, 2014)
    
    Args:
        observed_sharpe: Best Sharpe ratio from multiple trials
        n_trials: Number of strategies tested (multiple testing adjustment)
        returns_std: Standard deviation of returns
        n_observations: Number of return observations
        skew: Skewness of returns
        excess_kurtosis: Excess kurtosis of returns
    
    Returns:
        Deflated Sharpe Ratio (analogous to p-value)
    """
    # Expected maximum Sharpe under null (all strategies are noise)
    # Using extreme value theory
    variance = 1 + (skew**2 / 4) + ((excess_kurtosis - 3) / 24)
    expected_max_sharpe = np.sqrt(variance) * (
        (1 - np.euler_gamma) * stats.norm.ppf(1 - 1/n_trials) +
        np.euler_gamma * stats.norm.ppf(1 - 1/(n_trials * np.e))
    )
    
    # Adjust for finite sample size
    expected_max_sharpe *= np.sqrt(1 - 1/n_observations)
    
    # DSR: probability that observed exceeds expected max
    dsr = stats.norm.cdf(
        (observed_sharpe - expected_max_sharpe) * np.sqrt(n_observations - 1)
    )
    
    return dsr


# Example usage and testing
if __name__ == "__main__":
    # Generate synthetic strategy returns
    np.random.seed(42)
    n = 252  # 1 year of daily returns
    
    # Strategy 1: Positive edge (Sharpe ~1.5)
    good_strategy = np.random.randn(n) * 0.15 + 0.01
    
    # Strategy 2: No edge (Sharpe ~0)
    random_strategy = np.random.randn(n) * 0.15
    
    # Strategy 3: Negative edge
    bad_strategy = np.random.randn(n) * 0.15 - 0.005
    
    strategies = {
        'good': pd.Series(good_strategy),
        'random': pd.Series(random_strategy),
        'bad': pd.Series(bad_strategy),
    }
    
    print("=" * 60)
    print("MONTE CARLO PERMUTATION TESTS")
    print("=" * 60)
    
    # Test each strategy
    for name, returns in strategies.items():
        print(f"\n{name.upper()} STRATEGY:")
        print(f"  Observed Sharpe: {returns.mean() / returns.std() * np.sqrt(252):.2f}")
        
        result = mcpt_validate(returns, metric='sharpe', n_permutations=2000)
        
        print(f"  P-value: {result.p_value:.4f}")
        print(f"  Percentile: {result.percentile_rank:.1f}%")
        print(f"  Significant: {result.is_significant}")
        
        if result.is_significant:
            print("  ✅ PASS: Strategy shows significant skill")
        else:
            print("  ❌ FAIL: Performance could be luck")
        
        # Confidence interval
        ci_low, ci_high = compute_confidence_interval(result)
        print(f"  95% CI of null: [{ci_low:.2f}, {ci_high:.2f}]")
    
    # Multiple testing
    print("\n" + "=" * 60)
    print("MULTIPLE TESTING (with Bonferroni correction)")
    print("=" * 60)
    
    results = mcpt_multiple_strategies(
        strategies,
        n_permutations=2000,
        alpha=0.05,
        bonferroni_correction=True,
    )
    
    for name, result in results.items():
        status = "✅ PASS" if result.is_significant else "❌ FAIL"
        print(f"{name}: {status} (p={result.p_value:.4f}, adjusted α={result.alpha:.4f})")
    
    # Deflated Sharpe Ratio
    print("\n" + "=" * 60)
    print("DEFLATED SHARPE RATIO")
    print("=" * 60)
    
    best_sharpe = strategies['good'].mean() / strategies['good'].std() * np.sqrt(252)
    dsr = deflated_sharpe_ratio(
        observed_sharpe=best_sharpe,
        n_trials=len(strategies),
        returns_std=strategies['good'].std(),
        n_observations=len(strategies['good']),
        skew=strategies['good'].skew(),
        excess_kurtosis=strategies['good'].kurtosis(),
    )
    
    print(f"Observed Sharpe: {best_sharpe:.2f}")
    print(f"Number of trials: {len(strategies)}")
    print(f"DSR: {dsr:.4f}")
    print(f"Interpretation: {dsr*100:.1f}% confidence that performance is real")
