# optimizer/historical_evaluator.py

"""
Regime-based performance evaluation for strategy optimization.

Compiles win-rate tables segmented by market regime (VIX, trend, dealer, liquidity)
to enable regime-aware strategy selection and position sizing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Hashable
import math
from collections import defaultdict


@dataclass(frozen=True)
class RegimeKey:
    """
    Represents a single regime bucket in which performance is evaluated.

    Example fields:
        vix_bucket: e.g., 'low', 'medium', 'high'
        trend_bucket: e.g., 'up', 'down', 'sideways'
        dealer_bucket: e.g., 'short_gamma', 'long_gamma', 'neutral'
        liquidity_bucket: e.g., 'thin', 'normal', 'deep'
    """
    vix_bucket: str
    trend_bucket: str
    dealer_bucket: str
    liquidity_bucket: str


@dataclass
class TradeOutcome:
    """
    Single trade outcome used for regime statistics.

    Attributes:
        regime: RegimeKey at the time of entry.
        pnl: Realized PnL for the trade (in account currency or R units).
        is_win: Whether trade is considered a 'win' (pnl > 0 or threshold).
        max_drawdown: Optional per-trade drawdown measure (for distributional stats).
    """
    regime: RegimeKey
    pnl: float
    is_win: bool
    max_drawdown: float = 0.0


@dataclass
class RegimeStats:
    """
    Aggregated performance statistics for a given regime.

    Attributes:
        count: Number of trades in this regime.
        win_rate: Wins / total.
        avg_pnl: Mean PnL.
        pnl_std: Standard deviation of PnL.
        avg_max_drawdown: Mean per-trade max drawdown.
    """
    count: int
    win_rate: float
    avg_pnl: float
    pnl_std: float
    avg_max_drawdown: float


def compute_regime_stats(trades: List[TradeOutcome]) -> Dict[RegimeKey, RegimeStats]:
    """
    Aggregate trade outcomes into regime-based statistics.

    Args:
        trades: List of TradeOutcome entries from historical backtests.

    Returns:
        Mapping from RegimeKey to RegimeStats.
    """
    buckets: Dict[RegimeKey, List[TradeOutcome]] = defaultdict(list)

    for t in trades:
        buckets[t.regime].append(t)

    regime_stats: Dict[RegimeKey, RegimeStats] = {}

    for regime, items in buckets.items():
        n = len(items)
        if n == 0:
            continue

        wins = sum(1 for t in items if t.is_win)
        pnl_values = [t.pnl for t in items]
        m = sum(pnl_values) / n
        var = sum((x - m) ** 2 for x in pnl_values) / n if n > 1 else 0.0
        std = math.sqrt(var)
        avg_dd = sum(t.max_drawdown for t in items) / n

        regime_stats[regime] = RegimeStats(
            count=n,
            win_rate=wins / n,
            avg_pnl=m,
            pnl_std=std,
            avg_max_drawdown=avg_dd,
        )

    return regime_stats


def pick_best_regimes(
    regime_stats: Dict[RegimeKey, RegimeStats],
    min_trades: int = 20,
    sort_by: str = "avg_pnl",
) -> List[Tuple[RegimeKey, RegimeStats]]:
    """
    Filter and rank regimes.

    Args:
        regime_stats: Computed regime statistics.
        min_trades: Minimum number of trades required to consider a regime.
        sort_by: Metric to sort by ('avg_pnl', 'win_rate', 'count').

    Returns:
        Sorted list of (RegimeKey, RegimeStats) tuples.
    """
    filtered = [
        (k, v) for k, v in regime_stats.items()
        if v.count >= min_trades
    ]

    if sort_by == "win_rate":
        key_fn = lambda kv: kv[1].win_rate
    elif sort_by == "count":
        key_fn = lambda kv: kv[1].count
    else:
        key_fn = lambda kv: kv[1].avg_pnl

    return sorted(filtered, key=key_fn, reverse=True)
