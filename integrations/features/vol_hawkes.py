"""
Hawkes Process for Volatility Clustering
Based on: https://github.com/neurotrader888/VolatilityHawkesProcess

Hawkes processes are self-exciting point processes that model clustering:
λ(t) = μ + α Σ exp(-β(t - tᵢ))

Where:
- λ(t): Intensity (probability of event at time t)
- μ: Baseline intensity
- α: Self-excitation (how much each event triggers others)
- β: Decay rate (how quickly excitement fades)
- Branching ratio n = α/β: Expected number of children per event

Applied to volatility: events = large price moves (|return| > threshold)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass
class HawkesParams:
    """Estimated Hawkes process parameters."""
    
    mu: float
    """Baseline intensity (background rate of volatility events)."""
    
    alpha: float
    """Self-excitation parameter (impact of past events)."""
    
    beta: float
    """Decay rate (how quickly excitement fades)."""
    
    branching_ratio: float
    """n = α/β. If n > 1, process is explosive. If n < 1, stable."""
    
    log_likelihood: float
    """Final log-likelihood of the fitted model."""
    
    convergence: bool
    """Whether optimization converged successfully."""
    
    lambda_history: Optional[np.ndarray] = None
    """Conditional intensity λ(t) over time (if computed)."""


def fit_hawkes_volatility(
    returns: pd.Series,
    threshold_percentile: float = 90.0,
    max_iter: int = 500,
    compute_intensity: bool = True,
) -> HawkesParams:
    """
    Fit univariate Hawkes process to volatility events.
    
    Args:
        returns: Price returns time series
        threshold_percentile: Percentile for defining volatility events
        max_iter: Maximum optimization iterations
        compute_intensity: Whether to compute λ(t) history
    
    Returns:
        HawkesParams with fitted parameters
    
    Example:
        >>> returns = prices.pct_change()
        >>> params = fit_hawkes_volatility(returns)
        >>> if params.branching_ratio > 0.9:
        >>>     print("High clustering - expect volatility continuation")
    """
    # Identify volatility events (absolute returns above threshold)
    threshold = np.percentile(np.abs(returns.dropna()), threshold_percentile)
    vol_events = np.abs(returns) > threshold
    
    # Extract event times (in units of bars)
    event_times = np.where(vol_events)[0].astype(float)
    
    if len(event_times) < 10:
        # Not enough events for reliable fitting
        return HawkesParams(
            mu=0.01,
            alpha=0.0,
            beta=1.0,
            branching_ratio=0.0,
            log_likelihood=-np.inf,
            convergence=False,
        )
    
    # Time span
    T = len(returns)
    
    # Negative log-likelihood function
    def neg_log_likelihood(params):
        mu_p, alpha_p, beta_p = params
        
        # Constraints
        if mu_p <= 0 or alpha_p < 0 or beta_p <= 0:
            return 1e10
        
        # Compute compensator (integral of intensity)
        compensator = mu_p * T
        
        # Compute sum of intensities at event times
        log_intensity_sum = 0.0
        
        for i, t_i in enumerate(event_times):
            # Compute λ(t_i) = μ + α Σ_{j<i} exp(-β(t_i - t_j))
            if i == 0:
                intensity = mu_p
            else:
                past_contribution = np.sum(np.exp(-beta_p * (t_i - event_times[:i])))
                intensity = mu_p + alpha_p * past_contribution
            
            if intensity <= 0:
                return 1e10
            
            log_intensity_sum += np.log(intensity)
            
            # Add to compensator
            if i > 0:
                compensator += (alpha_p / beta_p) * (1 - np.exp(-beta_p * (T - t_i)))
        
        # Negative log-likelihood
        neg_ll = compensator - log_intensity_sum
        
        return neg_ll
    
    # Initial guess
    x0 = np.array([
        len(event_times) / T,  # mu: average rate
        0.5,                    # alpha
        1.0,                    # beta
    ])
    
    # Optimize
    bounds = [(1e-6, None), (0, None), (1e-3, None)]
    result = minimize(
        neg_log_likelihood,
        x0,
        method='L-BFGS-B',
        bounds=bounds,
        options={'maxiter': max_iter},
    )
    
    mu_opt, alpha_opt, beta_opt = result.x
    branching = alpha_opt / beta_opt
    
    # Compute intensity history if requested
    lambda_hist = None
    if compute_intensity and result.success:
        lambda_hist = _compute_intensity_history(
            event_times, T, mu_opt, alpha_opt, beta_opt
        )
    
    return HawkesParams(
        mu=mu_opt,
        alpha=alpha_opt,
        beta=beta_opt,
        branching_ratio=branching,
        log_likelihood=-result.fun,
        convergence=result.success,
        lambda_history=lambda_hist,
    )


def _compute_intensity_history(
    event_times: np.ndarray,
    T: int,
    mu: float,
    alpha: float,
    beta: float,
) -> np.ndarray:
    """
    Compute conditional intensity λ(t) for all time points.
    
    Args:
        event_times: Array of event occurrence times
        T: Total time span
        mu, alpha, beta: Hawkes parameters
    
    Returns:
        Array of intensities at each time point
    """
    lambda_t = np.full(T, mu)
    
    # For each time point, compute contribution from past events
    for t in range(T):
        past_events = event_times[event_times < t]
        if len(past_events) > 0:
            excitement = alpha * np.sum(np.exp(-beta * (t - past_events)))
            lambda_t[t] += excitement
    
    return lambda_t


def compute_hawkes_features(
    returns: pd.Series,
    params: HawkesParams,
    lookback: int = 20,
) -> pd.DataFrame:
    """
    Extract trading features from fitted Hawkes process.
    
    Args:
        returns: Price returns
        params: Fitted HawkesParams
        lookback: Window for rolling features
    
    Returns:
        DataFrame with Hawkes-based features
    """
    if params.lambda_history is None:
        raise ValueError("Must fit with compute_intensity=True")
    
    lambda_series = pd.Series(params.lambda_history, index=returns.index)
    
    features = pd.DataFrame(index=returns.index)
    
    # Raw intensity
    features['lambda'] = lambda_series
    
    # Normalized intensity (z-score)
    features['lambda_zscore'] = (
        (lambda_series - lambda_series.rolling(lookback).mean()) /
        lambda_series.rolling(lookback).std()
    )
    
    # Jump probability: high intensity = high probability of next event
    # Normalize to [0, 1]
    features['jump_prob'] = lambda_series / (lambda_series.max() + 1e-9)
    
    # Clustering regime: branching ratio stability
    features['branching_ratio'] = params.branching_ratio
    
    # Excitement level: ratio of current to baseline
    features['excitement'] = lambda_series / (params.mu + 1e-9)
    
    # Regime flag: high clustering if branching > threshold
    features['high_clustering'] = (params.branching_ratio > 0.8).astype(int)
    
    # Expected decay time: 1/β
    features['decay_time'] = 1.0 / (params.beta + 1e-9)
    
    return features


def detect_volatility_regime_change(
    returns: pd.Series,
    window: int = 100,
    step: int = 20,
    branching_threshold: float = 0.8,
) -> pd.DataFrame:
    """
    Detect changes in volatility clustering regime over time.
    
    Args:
        returns: Price returns
        window: Window size for fitting
        step: Step size for rolling estimation
        branching_threshold: Threshold for high clustering regime
    
    Returns:
        DataFrame with regime indicators
    """
    results = []
    
    for i in range(window, len(returns), step):
        window_returns = returns.iloc[i-window:i]
        
        # Fit Hawkes to window
        params = fit_hawkes_volatility(
            window_returns,
            compute_intensity=False,
        )
        
        if params.convergence:
            results.append({
                'timestamp': returns.index[i],
                'mu': params.mu,
                'alpha': params.alpha,
                'beta': params.beta,
                'branching_ratio': params.branching_ratio,
                'high_clustering': params.branching_ratio > branching_threshold,
            })
    
    df = pd.DataFrame(results)
    if len(df) > 0:
        df = df.set_index('timestamp')
    
    return df


def simulate_hawkes(
    mu: float,
    alpha: float,
    beta: float,
    T: float,
    max_events: int = 10000,
) -> np.ndarray:
    """
    Simulate Hawkes process using Ogata's thinning algorithm.
    
    Args:
        mu: Baseline intensity
        alpha: Self-excitation
        beta: Decay rate
        T: Time horizon
        max_events: Maximum number of events to generate
    
    Returns:
        Array of event times
    """
    events = []
    t = 0.0
    lambda_star = mu
    
    while t < T and len(events) < max_events:
        # Generate next potential event
        u = np.random.uniform()
        t = t - np.log(u) / lambda_star
        
        if t > T:
            break
        
        # Compute actual intensity at t
        if len(events) == 0:
            lambda_t = mu
        else:
            past_contribution = np.sum(np.exp(-beta * (t - np.array(events))))
            lambda_t = mu + alpha * past_contribution
        
        # Accept/reject
        u = np.random.uniform()
        if u <= lambda_t / lambda_star:
            events.append(t)
            lambda_star = lambda_t + alpha
        
    return np.array(events)


# Example usage and testing
if __name__ == "__main__":
    # Generate sample returns with volatility clustering
    np.random.seed(42)
    n = 500
    dates = pd.date_range('2024-01-01', periods=n, freq='1h')
    
    # Simulate returns with GARCH-like clustering
    returns = np.zeros(n)
    sigma = np.zeros(n)
    sigma[0] = 0.01
    
    for t in range(1, n):
        # GARCH(1,1)
        sigma[t] = np.sqrt(0.00001 + 0.1 * returns[t-1]**2 + 0.85 * sigma[t-1]**2)
        returns[t] = sigma[t] * np.random.randn()
    
    returns_series = pd.Series(returns, index=dates)
    
    # Fit Hawkes process
    print("Fitting Hawkes process to volatility...")
    params = fit_hawkes_volatility(returns_series, threshold_percentile=85)
    
    print(f"\nFitted Parameters:")
    print(f"  μ (baseline): {params.mu:.6f}")
    print(f"  α (excitation): {params.alpha:.6f}")
    print(f"  β (decay): {params.beta:.6f}")
    print(f"  Branching ratio: {params.branching_ratio:.4f}")
    print(f"  Convergence: {params.convergence}")
    print(f"  Log-likelihood: {params.log_likelihood:.2f}")
    
    if params.branching_ratio > 1:
        print("\n⚠️  WARNING: Explosive process (branching > 1)")
    elif params.branching_ratio > 0.8:
        print("\n📈 High clustering detected (branching > 0.8)")
    else:
        print("\n✅ Stable clustering regime")
    
    # Extract features
    if params.lambda_history is not None:
        features = compute_hawkes_features(returns_series, params)
        print(f"\nFeature Statistics:")
        print(f"  Mean intensity: {features['lambda'].mean():.6f}")
        print(f"  Max jump prob: {features['jump_prob'].max():.4f}")
        print(f"  High clustering periods: {features['high_clustering'].sum()} / {len(features)}")
    
    # Detect regime changes
    print("\nDetecting regime changes...")
    regimes = detect_volatility_regime_change(returns_series, window=100, step=50)
    if len(regimes) > 0:
        print(f"  Detected {len(regimes)} regime estimates")
        print(f"  Mean branching: {regimes['branching_ratio'].mean():.4f}")
        print(f"  High clustering periods: {regimes['high_clustering'].sum()} / {len(regimes)}")
