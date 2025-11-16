# optimizer/strategy_optimizer.py

"""
Core Optuna-based optimization harness for Trade Agent hyperparameters.

This module orchestrates hyperparameter optimization using Optuna's
Bayesian optimization engine. It's designed to be DI-friendly and
framework-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Any, List, Optional, Protocol, Tuple

import math

try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    optuna = None
    OPTUNA_AVAILABLE = False


class StrategyEvaluator(Protocol):
    """
    Protocol that any strategy evaluator must implement.

    The evaluator is responsible for:
    - Running a backtest given a specific hyperparameter config.
    - Returning a scalar objective (e.g., Sharpe, CAGR, or EV) and rich metrics.
    """

    def __call__(self, params: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate the given strategy parameters.

        Returns:
            objective_value: float
                Scalar to maximize (e.g., Sharpe ratio).
            metrics: Dict[str, Any]
                Arbitrary metrics (win rate, max drawdown, etc.) for logging.
        """
        ...


@dataclass
class OptimizationBounds:
    """
    Encodes search space bounds for a given hyperparameter.

    Attributes:
        name: Name of the hyperparameter.
        low: Lower bound (inclusive).
        high: Upper bound (inclusive).
        step: Optional step size (for int / discrete).
        is_log: Whether to sample in log-space (for positive continuous params).
    """

    name: str
    low: float
    high: float
    step: Optional[float] = None
    is_log: bool = False


@dataclass
class OptimizationConfig:
    """
    Configuration for an Optuna-driven strategy optimization.

    Attributes:
        study_name: Human-readable study name.
        direction: 'maximize' or 'minimize' (almost always 'maximize').
        n_trials: Number of Optuna trials.
        bounds: List of OptimizationBounds describing the search space.
        seed: Optional random seed for reproducibility.
    """

    study_name: str
    direction: str
    n_trials: int
    bounds: List[OptimizationBounds]
    seed: Optional[int] = None


def _suggest_params(trial: "optuna.trial.Trial", bounds: List[OptimizationBounds]) -> Dict[str, Any]:
    """
    Use Optuna trial to sample from the configured bounds.
    """
    params: Dict[str, Any] = {}

    for b in bounds:
        if b.step is not None:
            # Determine if int or float based on step size
            if b.step >= 1.0 and b.low == int(b.low) and b.high == int(b.high):
                # Integer sampling
                params[b.name] = trial.suggest_int(b.name, int(b.low), int(b.high), step=int(b.step))
            else:
                # Float sampling with step
                params[b.name] = trial.suggest_float(b.name, b.low, b.high, step=b.step)
        else:
            # Continuous sampling
            if b.is_log:
                params[b.name] = trial.suggest_float(b.name, b.low, b.high, log=True)
            else:
                params[b.name] = trial.suggest_float(b.name, b.low, b.high)

    return params


def run_optuna_optimization(
    evaluator: StrategyEvaluator,
    config: OptimizationConfig,
    extra_study_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run an Optuna optimization loop over the provided strategy evaluator.

    This function is intentionally DI-based and side-effect-free
    (besides Optuna's internal DB/logging) so it can be easily tested.

    Args:
        evaluator: Callable implementing StrategyEvaluator.
        config: OptimizationConfig describing search space and trial count.
        extra_study_kwargs: Optional additional kwargs for optuna.create_study.

    Returns:
        A dictionary containing:
            - 'best_params': Dict[str, Any]
            - 'best_value': float
            - 'trials': List[Dict[str, Any]] with per-trial results
    """
    if not OPTUNA_AVAILABLE:
        raise RuntimeError(
            "optuna is not installed. Install it with `pip install optuna` to use the optimizer."
        )

    if extra_study_kwargs is None:
        extra_study_kwargs = {}

    # Use seed for reproducibility if provided
    sampler = None
    if config.seed is not None:
        sampler = optuna.samplers.TPESampler(seed=config.seed)
    
    study = optuna.create_study(
        study_name=config.study_name,
        direction=config.direction,
        sampler=sampler,
        **extra_study_kwargs,
    )

    all_trials: List[Dict[str, Any]] = []

    def objective(trial: "optuna.trial.Trial") -> float:
        params = _suggest_params(trial, config.bounds)
        objective_value, metrics = evaluator(params)

        trial.set_user_attr("metrics", metrics)
        all_trials.append(
            {
                "number": trial.number,
                "params": params,
                "objective_value": objective_value,
                "metrics": metrics,
            }
        )
        return objective_value

    study.optimize(objective, n_trials=config.n_trials)

    return {
        "best_params": study.best_params,
        "best_value": study.best_value,
        "trials": all_trials,
    }


def default_trade_hyperparam_bounds() -> List[OptimizationBounds]:
    """
    Provide a canonical set of bounds for trade optimization:
    - profit_target_pct: 10–150%
    - stop_loss_pct: 5–80%
    - dte: 3–60
    - strike_offset_pct: 0–15%
    - min_return_on_risk: 0.05–0.8
    """
    return [
        OptimizationBounds("profit_target_pct", 0.10, 1.50, step=0.05),
        OptimizationBounds("stop_loss_pct", 0.05, 0.80, step=0.05),
        OptimizationBounds("dte", 3, 60, step=1),
        OptimizationBounds("strike_offset_pct", 0.0, 0.15, step=0.01),
        OptimizationBounds("min_return_on_risk", 0.05, 0.80, step=0.05),
    ]
