"""
Core metrics for Composer backtest validation.

Pure functions for computing directional accuracy, PnL, Sharpe,
and stratified performance by energy buckets.
"""

from typing import Sequence, Tuple, Dict
import math


def compute_directional_accuracy(
    predicted_directions: Sequence[int],
    realized_returns: Sequence[float],
    threshold: float = 0.0,
) -> float:
    """
    Compute directional accuracy: fraction of times predicted direction
    matches realized return direction.
    
    Args:
        predicted_directions: Sequence in {-1, 0, 1}
        realized_returns: Realized returns over chosen horizon
        threshold: Minimum absolute return to count as meaningful move
        
    Returns:
        Accuracy in [0, 1]
        
    Examples:
        >>> compute_directional_accuracy([1, -1, 1, 0], [0.02, -0.01, 0.03, -0.02])
        1.0  # All non-zero predictions correct
    """
    assert len(predicted_directions) == len(realized_returns), \
        "Predictions and returns must have same length"
    
    wins = 0
    total = 0
    
    for direction, return_val in zip(predicted_directions, realized_returns):
        # Skip near-zero moves
        if abs(return_val) <= threshold:
            continue
        
        # Skip neutral predictions
        if direction == 0:
            continue
        
        total += 1
        
        # Check if signs match
        if (direction > 0 and return_val > 0) or (direction < 0 and return_val < 0):
            wins += 1
    
    if total == 0:
        return 0.0
    
    return wins / total


def compute_naive_pnl(
    predicted_directions: Sequence[int],
    realized_returns: Sequence[float],
    notional: float = 1.0,
) -> float:
    """
    Compute toy PnL by going long/short with unit notional according
    to predicted direction.
    
    Args:
        predicted_directions: Sequence in {-1, 0, 1}
        realized_returns: Realized returns (% or log returns)
        notional: Notional exposure per trade
        
    Returns:
        Total PnL over backtest horizon
        
    Examples:
        >>> compute_naive_pnl([1, -1, 0], [0.02, -0.01, 0.03], notional=1.0)
        0.03  # 1*0.02 + (-1)*(-0.01) + 0*0.03
    """
    assert len(predicted_directions) == len(realized_returns), \
        "Predictions and returns must have same length"
    
    pnl = 0.0
    for direction, return_val in zip(predicted_directions, realized_returns):
        pnl += notional * direction * return_val
    
    return pnl


def compute_sharpe_ratio(
    pnl_series: Sequence[float],
    risk_free_rate: float = 0.0,
) -> float:
    """
    Compute Sharpe ratio: mean(excess) / std(excess).
    
    Args:
        pnl_series: Per-period PnL (same horizon as backtest step)
        risk_free_rate: Risk-free per-period rate (usually 0 for intraday)
        
    Returns:
        Sharpe ratio; 0 if variance is zero or no data
        
    Examples:
        >>> compute_sharpe_ratio([0.01, 0.02, -0.01, 0.015])
        # Returns positive Sharpe for profitable series with low vol
    """
    n = len(pnl_series)
    if n == 0:
        return 0.0
    
    # Compute excess returns
    excess = [p - risk_free_rate for p in pnl_series]
    mean_excess = sum(excess) / n
    
    # Compute variance
    var = sum((x - mean_excess) ** 2 for x in excess) / n
    if var < 1e-10:
        return 0.0
    
    std = math.sqrt(var)
    return mean_excess / std


def bucket_accuracy_by_energy(
    predicted_directions: Sequence[int],
    realized_returns: Sequence[float],
    energy_costs: Sequence[float],
    buckets: Tuple[float, ...] = (0.5, 1.0, 2.0, 5.0),
) -> Dict[str, float]:
    """
    Compute directional accuracy stratified by energy_cost buckets.
    
    This tells you whether high-energy (hard-to-move) regimes
    actually behave differently.
    
    Args:
        predicted_directions: Sequence in {-1, 0, 1}
        realized_returns: Realized returns
        energy_costs: Energy cost per prediction
        buckets: Bucket edges for stratification
        
    Returns:
        Dict mapping bucket labels to accuracy values
        
    Examples:
        >>> bucket_accuracy_by_energy(
        ...     [1, 1, -1, 1],
        ...     [0.02, 0.01, -0.02, -0.01],
        ...     [0.3, 0.8, 1.5, 3.0]
        ... )
        {'<= 0.5': 1.0, '0.5 - 1.0': 1.0, '1.0 - 2.0': 1.0, '2.0 - 5.0': 0.0, '> 5.0': 0.0}
    """
    assert len(predicted_directions) == len(realized_returns) == len(energy_costs), \
        "All sequences must have same length"
    
    # Define bucket ranges
    ranges = []
    last = float("-inf")
    for edge in buckets:
        ranges.append((last, edge))
        last = edge
    ranges.append((last, float("inf")))
    
    # Initialize stats for each bucket
    stats: Dict[str, Dict[str, float]] = {}
    labels = []
    
    for low, high in ranges:
        if low == float("-inf"):
            label = f"<= {high}"
        elif high == float("inf"):
            label = f"> {low}"
        else:
            label = f"{low} - {high}"
        labels.append(label)
        stats[label] = {"wins": 0.0, "total": 0.0}
    
    # Accumulate stats
    for direction, return_val, energy in zip(predicted_directions, realized_returns, energy_costs):
        # Skip neutral predictions
        if direction == 0:
            continue
        
        # Find appropriate bucket
        for (low, high), label in zip(ranges, labels):
            if low < energy <= high:
                stats[label]["total"] += 1
                if (direction > 0 and return_val > 0) or (direction < 0 and return_val < 0):
                    stats[label]["wins"] += 1
                break
    
    # Compute accuracies
    out: Dict[str, float] = {}
    for label, s in stats.items():
        if s["total"] == 0:
            out[label] = 0.0
        else:
            out[label] = s["wins"] / s["total"]
    
    return out


def compute_pnl_series(
    predicted_directions: Sequence[int],
    realized_returns: Sequence[float],
    notional: float = 1.0,
) -> list[float]:
    """
    Compute per-period PnL series.
    
    Args:
        predicted_directions: Sequence in {-1, 0, 1}
        realized_returns: Realized returns
        notional: Notional exposure per trade
        
    Returns:
        List of per-period PnL values
        
    Examples:
        >>> compute_pnl_series([1, -1, 0], [0.02, -0.01, 0.03])
        [0.02, 0.01, 0.0]
    """
    assert len(predicted_directions) == len(realized_returns), \
        "Predictions and returns must have same length"
    
    return [notional * d * r for d, r in zip(predicted_directions, realized_returns)]


def compute_max_drawdown(pnl_series: Sequence[float]) -> float:
    """
    Compute maximum drawdown from PnL series.
    
    Args:
        pnl_series: Per-period PnL values
        
    Returns:
        Maximum drawdown as positive value
        
    Examples:
        >>> compute_max_drawdown([0.01, -0.02, 0.01, -0.03])
        0.04  # Max peak-to-trough decline
    """
    if not pnl_series:
        return 0.0
    
    # Compute cumulative PnL
    cumulative = []
    total = 0.0
    for pnl in pnl_series:
        total += pnl
        cumulative.append(total)
    
    # Find max drawdown
    max_dd = 0.0
    peak = cumulative[0]
    
    for value in cumulative:
        if value > peak:
            peak = value
        dd = peak - value
        if dd > max_dd:
            max_dd = dd
    
    return max_dd


def compute_win_rate(
    predicted_directions: Sequence[int],
    realized_returns: Sequence[float],
) -> float:
    """
    Compute fraction of trades that were profitable.
    
    Args:
        predicted_directions: Sequence in {-1, 0, 1}
        realized_returns: Realized returns
        
    Returns:
        Win rate in [0, 1]
    """
    assert len(predicted_directions) == len(realized_returns)
    
    wins = 0
    total = 0
    
    for direction, return_val in zip(predicted_directions, realized_returns):
        if direction == 0:
            continue
        
        total += 1
        pnl = direction * return_val
        if pnl > 0:
            wins += 1
    
    if total == 0:
        return 0.0
    
    return wins / total
