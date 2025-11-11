"""
Evaluation package initialization.
Provides backtesting and performance metrics functions.
"""

from .backtest import backtest, walk_forward_validation, replay_historical_snapshot
from .metrics import (
    summarize_metrics,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_calmar_ratio,
)

__all__ = [
    'backtest',
    'walk_forward_validation',
    'replay_historical_snapshot',
    'summarize_metrics',
    'calculate_sharpe_ratio',
    'calculate_sortino_ratio',
    'calculate_max_drawdown',
    'calculate_calmar_ratio',
]
