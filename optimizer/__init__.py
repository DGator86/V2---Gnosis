# optimizer/__init__.py

"""
Super Gnosis Strategy Optimizer (Trade Agent Self-Optimization Brain)

ML-driven optimization layer that enables self-improving strategy selection.

Key Components:
- Strategy Optimizer: Optuna-based hyperparameter tuning
- Historical Evaluator: Regime-based win-rate tables
- ML Integration: Prediction model interface
- Kelly Refinement: Dynamic position sizing with empirical edge

This layer sits on top of Trade Agent v2/v2.5/v3 and provides:
1. Automated hyperparameter optimization (profit %, stop %, DTE, strikes)
2. Regime-aware performance statistics (VIX, trend, dealer, liquidity)
3. ML prediction integration (direction, volatility, trend persistence)
4. Empirical Kelly fraction refinement (win rate, avg win/loss)
"""

__version__ = "1.0.0"
__all__ = [
    "StrategyOptimizer",
    "HistoricalEvaluator",
    "MLIntegration",
    "KellyRefinement",
]
