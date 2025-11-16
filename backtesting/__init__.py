"""
Backtesting module for Composer Agent validation.

Provides tools for walk-forward backtesting of market directives
with calibration metrics and performance analysis.
"""

from backtesting.metrics import (
    compute_directional_accuracy,
    compute_naive_pnl,
    compute_sharpe_ratio,
    bucket_accuracy_by_energy,
)
from backtesting.composer_backtest import (
    BacktestConfig,
    BacktestResult,
    run_composer_backtest,
)

__all__ = [
    "compute_directional_accuracy",
    "compute_naive_pnl",
    "compute_sharpe_ratio",
    "bucket_accuracy_by_energy",
    "BacktestConfig",
    "BacktestResult",
    "run_composer_backtest",
]
