# tests/optimizer/test_strategy_optimizer.py

"""
Tests for Optuna-based strategy optimization.

Tests cover:
- Mock StrategyEvaluator behavior
- Optuna integration (n_trials, best_params, metrics storage)
- Hyperparameter bound sampling
- Default trade hyperparameter bounds
"""

import pytest
from typing import Dict, Any, Tuple

from optimizer.strategy_optimizer import (
    StrategyEvaluator,
    OptimizationBounds,
    OptimizationConfig,
    run_optuna_optimization,
    default_trade_hyperparam_bounds,
    OPTUNA_AVAILABLE,
)


class MockStrategyEvaluator:
    """Mock evaluator that returns deterministic Sharpe given params."""
    
    def __init__(self, sharpe_formula: callable):
        """
        Initialize with a formula that computes Sharpe from params.
        
        Args:
            sharpe_formula: Function taking params dict and returning float
        """
        self.sharpe_formula = sharpe_formula
        self.call_count = 0
    
    def __call__(self, params: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """Evaluate parameters and return objective + metrics."""
        self.call_count += 1
        
        sharpe = self.sharpe_formula(params)
        
        metrics = {
            "sharpe": sharpe,
            "win_rate": 0.55 + params.get("profit_target_pct", 0) * 0.1,
            "max_drawdown": 0.15,
            "total_trades": 100,
        }
        
        return sharpe, metrics


@pytest.fixture
def simple_evaluator():
    """Create evaluator that prefers high profit targets."""
    def sharpe_fn(params):
        # Simple: Sharpe increases with profit_target_pct
        return params.get("profit_target_pct", 0.5) * 2.0
    
    return MockStrategyEvaluator(sharpe_fn)


@pytest.fixture
def simple_config():
    """Create simple optimization config."""
    return OptimizationConfig(
        study_name="test_study",
        direction="maximize",
        n_trials=5,
        bounds=[
            OptimizationBounds("profit_target_pct", 0.1, 1.0, step=0.1),
            OptimizationBounds("stop_loss_pct", 0.1, 0.5, step=0.1),
        ],
        seed=42,
    )


class TestOptimizationBounds:
    """Test hyperparameter bounds specification."""
    
    def test_bounds_creation(self):
        """Test creating optimization bounds."""
        bounds = OptimizationBounds(
            name="profit_target_pct",
            low=0.1,
            high=1.0,
            step=0.05,
            is_log=False,
        )
        
        assert bounds.name == "profit_target_pct"
        assert bounds.low == 0.1
        assert bounds.high == 1.0
        assert bounds.step == 0.05
        assert bounds.is_log is False
    
    def test_log_scale_bounds(self):
        """Test log-scale bounds for positive parameters."""
        bounds = OptimizationBounds(
            name="learning_rate",
            low=0.001,
            high=0.1,
            is_log=True,
        )
        
        assert bounds.is_log is True
        assert bounds.step is None


class TestOptimizationConfig:
    """Test optimization configuration."""
    
    def test_config_creation(self):
        """Test creating optimization config."""
        config = OptimizationConfig(
            study_name="my_study",
            direction="maximize",
            n_trials=10,
            bounds=[
                OptimizationBounds("param1", 0.0, 1.0),
                OptimizationBounds("param2", 1, 100, step=1),
            ],
            seed=42,
        )
        
        assert config.study_name == "my_study"
        assert config.direction == "maximize"
        assert config.n_trials == 10
        assert len(config.bounds) == 2
        assert config.seed == 42


@pytest.mark.skipif(not OPTUNA_AVAILABLE, reason="Optuna not installed")
class TestOptunaIntegration:
    """Test Optuna optimization integration."""
    
    def test_run_optimization_basic(self, simple_evaluator, simple_config):
        """Test basic optimization run."""
        result = run_optuna_optimization(simple_evaluator, simple_config)
        
        assert "best_params" in result
        assert "best_value" in result
        assert "trials" in result
        
        # Should have run n_trials
        assert len(result["trials"]) == simple_config.n_trials
        
        # Evaluator should have been called n_trials times
        assert simple_evaluator.call_count == simple_config.n_trials
    
    def test_best_params_structure(self, simple_evaluator, simple_config):
        """Test best_params has expected structure."""
        result = run_optuna_optimization(simple_evaluator, simple_config)
        
        best_params = result["best_params"]
        
        # Should have both parameters
        assert "profit_target_pct" in best_params
        assert "stop_loss_pct" in best_params
        
        # Should respect bounds
        assert 0.1 <= best_params["profit_target_pct"] <= 1.0
        assert 0.1 <= best_params["stop_loss_pct"] <= 0.5
    
    def test_trials_contain_metrics(self, simple_evaluator, simple_config):
        """Test trials contain metrics from evaluator."""
        result = run_optuna_optimization(simple_evaluator, simple_config)
        
        for trial in result["trials"]:
            assert "number" in trial
            assert "params" in trial
            assert "objective_value" in trial
            assert "metrics" in trial
            
            metrics = trial["metrics"]
            assert "sharpe" in metrics
            assert "win_rate" in metrics
            assert "max_drawdown" in metrics
    
    def test_optimization_finds_better_params(self, simple_evaluator, simple_config):
        """Test that optimization improves objective over trials."""
        result = run_optuna_optimization(simple_evaluator, simple_config)
        
        # Best value should be positive (our mock always returns positive)
        assert result["best_value"] > 0
        
        # Best params should favor higher profit_target_pct (our mock rewards this)
        assert result["best_params"]["profit_target_pct"] >= 0.5
    
    def test_direction_maximize(self, simple_evaluator):
        """Test maximize direction."""
        config = OptimizationConfig(
            study_name="maximize_test",
            direction="maximize",
            n_trials=3,
            bounds=[OptimizationBounds("param", 0.0, 1.0, step=0.1)],
        )
        
        result = run_optuna_optimization(simple_evaluator, config)
        
        assert result["best_value"] >= 0.0
    
    def test_seed_reproducibility(self, simple_evaluator, simple_config):
        """Test that seed produces reproducible results."""
        # Run twice with same seed
        result1 = run_optuna_optimization(simple_evaluator, simple_config)
        
        # Reset evaluator counter
        simple_evaluator.call_count = 0
        
        result2 = run_optuna_optimization(simple_evaluator, simple_config)
        
        # Should get same best value (deterministic with seed)
        assert result1["best_value"] == result2["best_value"]


class TestDefaultTradeHyperparamBounds:
    """Test default hyperparameter bounds for trade optimization."""
    
    def test_default_bounds_exist(self):
        """Test default bounds are defined."""
        bounds = default_trade_hyperparam_bounds()
        
        assert len(bounds) == 5
        
        param_names = [b.name for b in bounds]
        assert "profit_target_pct" in param_names
        assert "stop_loss_pct" in param_names
        assert "dte" in param_names
        assert "strike_offset_pct" in param_names
        assert "min_return_on_risk" in param_names
    
    def test_profit_target_bounds(self):
        """Test profit target bounds."""
        bounds = default_trade_hyperparam_bounds()
        
        profit_bound = next(b for b in bounds if b.name == "profit_target_pct")
        
        assert profit_bound.low == 0.10
        assert profit_bound.high == 1.50
        assert profit_bound.step == 0.05
    
    def test_stop_loss_bounds(self):
        """Test stop loss bounds."""
        bounds = default_trade_hyperparam_bounds()
        
        stop_bound = next(b for b in bounds if b.name == "stop_loss_pct")
        
        assert stop_bound.low == 0.05
        assert stop_bound.high == 0.80
        assert stop_bound.step == 0.05
    
    def test_dte_bounds(self):
        """Test DTE bounds."""
        bounds = default_trade_hyperparam_bounds()
        
        dte_bound = next(b for b in bounds if b.name == "dte")
        
        assert dte_bound.low == 3
        assert dte_bound.high == 60
        assert dte_bound.step == 1
    
    def test_strike_offset_bounds(self):
        """Test strike offset bounds."""
        bounds = default_trade_hyperparam_bounds()
        
        strike_bound = next(b for b in bounds if b.name == "strike_offset_pct")
        
        assert strike_bound.low == 0.0
        assert strike_bound.high == 0.15
        assert strike_bound.step == 0.01
    
    def test_return_on_risk_bounds(self):
        """Test return on risk bounds."""
        bounds = default_trade_hyperparam_bounds()
        
        ror_bound = next(b for b in bounds if b.name == "min_return_on_risk")
        
        assert ror_bound.low == 0.05
        assert ror_bound.high == 0.80
        assert ror_bound.step == 0.05


class TestMockEvaluator:
    """Test mock evaluator behavior."""
    
    def test_evaluator_call_count(self):
        """Test evaluator tracks calls correctly."""
        def dummy_sharpe(params):
            return 1.0
        
        evaluator = MockStrategyEvaluator(dummy_sharpe)
        
        assert evaluator.call_count == 0
        
        evaluator({"param": 0.5})
        assert evaluator.call_count == 1
        
        evaluator({"param": 0.7})
        assert evaluator.call_count == 2
    
    def test_evaluator_returns_tuple(self):
        """Test evaluator returns (objective, metrics) tuple."""
        def dummy_sharpe(params):
            return 1.5
        
        evaluator = MockStrategyEvaluator(dummy_sharpe)
        
        objective, metrics = evaluator({"param": 0.5})
        
        assert isinstance(objective, float)
        assert isinstance(metrics, dict)
        assert "sharpe" in metrics
