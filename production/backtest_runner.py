"""
Comprehensive Backtesting Framework
Tests strategy performance on historical data with detailed metrics.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats

from integrations.validation.mcpt import mcpt_validate


logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Complete backtest results with all metrics."""
    
    # Basic metrics
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    
    # Trading metrics
    n_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    
    # Advanced metrics
    sharpe_p_value: float  # MCPT p-value
    is_significant: bool
    
    # Time series
    equity_curve: pd.Series
    returns: pd.Series
    positions: pd.Series
    
    # Metadata
    start_date: datetime
    end_date: datetime
    days: int


class BacktestRunner:
    """
    Run comprehensive backtests with detailed performance analysis.
    
    Features:
    - Complete performance metrics
    - Statistical validation (MCPT)
    - Transaction costs
    - Slippage modeling
    - Position sizing
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        transaction_cost: float = 0.001,  # 0.1%
        slippage: float = 0.0005,  # 0.05%
    ):
        """
        Initialize backtest runner.
        
        Args:
            initial_capital: Starting capital
            transaction_cost: Transaction cost as fraction
            slippage: Slippage as fraction
        """
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.slippage = slippage
        
        logger.info(f"BacktestRunner initialized with ${initial_capital:,.0f}")
    
    def run(
        self,
        signals: pd.Series,
        prices: pd.Series,
        position_sizes: Optional[pd.Series] = None,
        validate: bool = True,
    ) -> BacktestResult:
        """
        Run backtest on signals.
        
        Args:
            signals: Series of {-1, 0, 1} for short/neutral/long
            prices: Price series
            position_sizes: Optional position sizing (0-1), default = 1.0
            validate: Whether to run MCPT validation
        
        Returns:
            BacktestResult with all metrics
        """
        logger.info("Running backtest...")
        
        # Align data
        signals, prices = signals.align(prices, join='inner')
        
        if position_sizes is not None:
            position_sizes = position_sizes.reindex(signals.index, fill_value=1.0)
        else:
            position_sizes = pd.Series(1.0, index=signals.index)
        
        # Compute returns
        price_returns = prices.pct_change()
        
        # Apply position sizing and costs
        positions = signals * position_sizes
        position_changes = positions.diff().fillna(positions)
        
        # Transaction costs (pay on position changes)
        costs = np.abs(position_changes) * (self.transaction_cost + self.slippage)
        
        # Strategy returns
        strategy_returns = positions.shift(1) * price_returns - costs
        strategy_returns = strategy_returns.fillna(0)
        
        # Equity curve
        equity_curve = (1 + strategy_returns).cumprod() * self.initial_capital
        
        # Compute metrics
        metrics = self._compute_metrics(
            strategy_returns,
            equity_curve,
            positions,
            prices.index[0],
            prices.index[-1],
        )
        
        # Statistical validation
        if validate and len(strategy_returns) > 30:
            logger.info("Running MCPT validation...")
            mcpt_result = mcpt_validate(strategy_returns, metric='sharpe', n_permutations=1000)
            sharpe_p_value = mcpt_result.p_value
            is_significant = mcpt_result.is_significant
        else:
            sharpe_p_value = np.nan
            is_significant = False
        
        result = BacktestResult(
            **metrics,
            sharpe_p_value=sharpe_p_value,
            is_significant=is_significant,
            equity_curve=equity_curve,
            returns=strategy_returns,
            positions=positions,
            start_date=prices.index[0],
            end_date=prices.index[-1],
            days=len(prices),
        )
        
        logger.info(f"Backtest complete: Return={result.total_return:.2%}, Sharpe={result.sharpe_ratio:.2f}")
        
        return result
    
    def _compute_metrics(
        self,
        returns: pd.Series,
        equity: pd.Series,
        positions: pd.Series,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict:
        """Compute all performance metrics."""
        # Basic returns metrics
        total_return = (equity.iloc[-1] / self.initial_capital) - 1
        
        # Sharpe ratio (annualized)
        if returns.std() > 0:
            sharpe = returns.mean() / returns.std() * np.sqrt(252)
        else:
            sharpe = 0.0
        
        # Sortino ratio (annualized)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            sortino = returns.mean() / downside_returns.std() * np.sqrt(252)
        else:
            sortino = 0.0
        
        # Drawdown
        running_max = equity.cummax()
        drawdown = (equity - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Calmar ratio
        if max_drawdown < 0:
            calmar = (returns.mean() * 252) / abs(max_drawdown)
        else:
            calmar = 0.0
        
        # Trading metrics
        position_changes = positions.diff().fillna(positions)
        trades = position_changes[position_changes != 0]
        n_trades = len(trades)
        
        # Win rate
        winning_trades = returns[returns > 0]
        losing_trades = returns[returns < 0]
        
        win_rate = len(winning_trades) / max(len(returns[returns != 0]), 1)
        avg_win = winning_trades.mean() if len(winning_trades) > 0 else 0.0
        avg_loss = losing_trades.mean() if len(losing_trades) > 0 else 0.0
        
        # Profit factor
        total_wins = winning_trades.sum()
        total_losses = abs(losing_trades.sum())
        profit_factor = total_wins / total_losses if total_losses > 0 else np.inf
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'max_drawdown': max_drawdown,
            'n_trades': n_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
        }
    
    def compare_strategies(
        self,
        strategies: Dict[str, Tuple[pd.Series, pd.Series]],  # {name: (signals, prices)}
        validate: bool = True,
    ) -> pd.DataFrame:
        """
        Compare multiple strategies.
        
        Args:
            strategies: Dict of {strategy_name: (signals, prices)}
            validate: Whether to validate with MCPT
        
        Returns:
            DataFrame comparing all strategies
        """
        logger.info(f"Comparing {len(strategies)} strategies...")
        
        results = []
        
        for name, (signals, prices) in strategies.items():
            logger.info(f"Backtesting {name}...")
            result = self.run(signals, prices, validate=validate)
            
            results.append({
                'strategy': name,
                'total_return': result.total_return,
                'sharpe_ratio': result.sharpe_ratio,
                'sortino_ratio': result.sortino_ratio,
                'calmar_ratio': result.calmar_ratio,
                'max_drawdown': result.max_drawdown,
                'n_trades': result.n_trades,
                'win_rate': result.win_rate,
                'profit_factor': result.profit_factor,
                'is_significant': result.is_significant,
                'p_value': result.sharpe_p_value,
            })
        
        df = pd.DataFrame(results).sort_values('sharpe_ratio', ascending=False)
        
        logger.info("Strategy comparison complete")
        
        return df
    
    def generate_report(self, result: BacktestResult) -> str:
        """Generate comprehensive backtest report."""
        report_lines = [
            "=" * 80,
            "BACKTEST REPORT",
            "=" * 80,
            f"Period: {result.start_date.date()} to {result.end_date.date()}",
            f"Days: {result.days}",
            f"Initial Capital: ${self.initial_capital:,.0f}",
            f"Final Capital: ${result.equity_curve.iloc[-1]:,.0f}",
            "",
            "PERFORMANCE METRICS",
            "-" * 80,
            f"Total Return: {result.total_return:.2%}",
            f"Sharpe Ratio: {result.sharpe_ratio:.2f}",
            f"Sortino Ratio: {result.sortino_ratio:.2f}",
            f"Calmar Ratio: {result.calmar_ratio:.2f}",
            f"Max Drawdown: {result.max_drawdown:.2%}",
            "",
            "TRADING STATISTICS",
            "-" * 80,
            f"Total Trades: {result.n_trades}",
            f"Win Rate: {result.win_rate:.2%}",
            f"Average Win: {result.avg_win:.4f}",
            f"Average Loss: {result.avg_loss:.4f}",
            f"Profit Factor: {result.profit_factor:.2f}",
            "",
            "STATISTICAL VALIDATION",
            "-" * 80,
            f"MCPT P-value: {result.sharpe_p_value:.4f}",
            f"Statistically Significant: {'✅ YES' if result.is_significant else '❌ NO'}",
            "",
        ]
        
        if result.is_significant:
            report_lines.append("✅ Strategy shows statistically significant performance!")
        else:
            report_lines.append("⚠️  Performance could be due to random chance")
        
        report_lines.extend([
            "",
            "=" * 80,
        ])
        
        return "\n".join(report_lines)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Generate sample data
    np.random.seed(42)
    n = 252  # 1 year of daily data
    dates = pd.date_range('2023-01-01', periods=n, freq='D')
    
    # Simulate prices
    returns = np.random.randn(n) * 0.02 + 0.0005
    prices = pd.Series(100 * np.exp(np.cumsum(returns)), index=dates)
    
    # Generate signals (simple momentum strategy)
    momentum = prices.pct_change(20)
    signals = pd.Series(0, index=dates)
    signals[momentum > 0.05] = 1
    signals[momentum < -0.05] = -1
    
    # Run backtest
    runner = BacktestRunner(initial_capital=100000)
    result = runner.run(signals, prices, validate=True)
    
    # Print report
    report = runner.generate_report(result)
    print(report)
    
    # Plot equity curve
    print("\nEquity Curve:")
    print(result.equity_curve.tail(10))
