# optimizer/kelly_refinement.py

"""
Dynamic Kelly fraction refinement based on empirical edge.

Converts regime-based win-rate statistics and ML predictions into
optimal position sizes using the Kelly Criterion with risk constraints.
"""

from __future__ import annotations

from typing import Optional


def compute_kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> float:
    """
    Compute the raw Kelly fraction.

    Kelly formula: f* = (bp - q) / b
    where:
        b = avg_win / avg_loss (win/loss ratio)
        p = win_rate (probability of win)
        q = 1 - p (probability of loss)

    Args:
        win_rate: Probability of a winning trade (0–1).
        avg_win: Average gain per winning trade (in R or %).
        avg_loss: Average loss per losing trade (positive number in same units as avg_win).

    Returns:
        Kelly fraction (can be negative if edge < 0).
    """
    if avg_loss <= 0:
        raise ValueError("avg_loss must be positive")

    if win_rate <= 0 or win_rate >= 1:
        # Degenerate cases: near certain loss or gain
        # Caller should clamp outside.
        return 0.0

    b = avg_win / avg_loss
    q = 1.0 - win_rate

    # Kelly formula: f* = (bp - q) / b
    numerator = b * win_rate - q
    if b == 0:
        return 0.0

    return numerator / b


def clamp_kelly_fraction(
    kelly: float,
    max_fraction: float = 0.25,
    min_fraction: float = -0.25,
) -> float:
    """
    Clamp Kelly fraction into a risk-tolerant band.

    Typical usage: cap at 25% and floor at -25%.
    Negative Kelly implies no trade or a small contrarian overlay.

    Args:
        kelly: Raw Kelly fraction from compute_kelly_fraction
        max_fraction: Maximum allowed fraction (e.g., 0.25 = 25%)
        min_fraction: Minimum allowed fraction (e.g., -0.25 = -25%)

    Returns:
        Clamped Kelly fraction
    """
    return max(min(kelly, max_fraction), min_fraction)


def recommended_risk_fraction(
    empirical_win_rate: float,
    avg_win: float,
    avg_loss: float,
    confidence: float,
    global_risk_cap: float = 0.02,
) -> float:
    """
    Convert empirical stats + model confidence into a final risk fraction
    of account equity to allocate to a single trade.

    This function combines:
    1. Kelly Criterion (based on empirical edge)
    2. Confidence scaling (from Trade Agent/Composer)
    3. Global risk cap (max % of account per trade)

    Args:
        empirical_win_rate: Observed win rate in similar regimes.
        avg_win: Average win in same units as avg_loss.
        avg_loss: Average loss (positive).
        confidence: 0–1 score from your engines/composer/trade agent.
        global_risk_cap: Max risk per trade as share of account equity (e.g., 0.02 = 2%).

    Returns:
        Final fraction of account equity to risk on this trade.

    Example:
        If clamped Kelly = 0.4, confidence = 0.5, cap = 0.02:
        risk_fraction = 0.4 * 0.5 * 0.02 = 0.004 (0.4% of equity)
    """
    raw_kelly = compute_kelly_fraction(empirical_win_rate, avg_win, avg_loss)
    clamped = clamp_kelly_fraction(raw_kelly)

    # Downscale by confidence and global risk cap
    # This ensures that:
    # 1. Low confidence trades get smaller size
    # 2. No single trade risks more than global_risk_cap
    # 3. Kelly's edge is respected but constrained
    return clamped * confidence * global_risk_cap
