"""
Composer backtesting harness with walk-forward validation.

Pure dependency injection pattern: you provide data loaders and engine runners,
this module orchestrates the backtest and computes metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Dict, Any, Sequence
from datetime import datetime

import pandas as pd

from agents.hedge_agent_v3 import HedgeAgentV3
from agents.liquidity_agent_v1 import LiquidityAgentV1
from agents.sentiment_agent_v1 import SentimentAgentV1
from agents.composer.composer_agent import ComposerAgent
from agents.composer.schemas import CompositeMarketDirective
from backtesting.metrics import (
    compute_directional_accuracy,
    compute_naive_pnl,
    compute_sharpe_ratio,
    bucket_accuracy_by_energy,
    compute_pnl_series,
    compute_max_drawdown,
    compute_win_rate,
)


@dataclass
class BacktestConfig:
    """
    Configuration for Composer backtest.
    
    Attributes:
        symbol: Ticker symbol to backtest
        horizon_steps: How many bars ahead to measure return
        notional: Notional exposure per trade for PnL calculation
        return_threshold: Minimum absolute return to count as meaningful move
        energy_buckets: Bucket edges for energy stratification
    """
    symbol: str
    horizon_steps: int = 1
    notional: float = 1.0
    return_threshold: float = 0.0
    energy_buckets: tuple[float, ...] = (0.5, 1.0, 2.0, 5.0)


@dataclass
class BacktestResult:
    """
    Aggregated backtest results with full per-step log.
    
    Attributes:
        config: Backtest configuration used
        log: DataFrame with per-timestamp results
        directional_accuracy: Fraction of correct directional predictions
        naive_pnl: Total PnL from naive long/short strategy
        sharpe: Sharpe ratio of PnL series
        max_drawdown: Maximum peak-to-trough decline
        win_rate: Fraction of profitable trades
        energy_bucket_accuracy: Accuracy stratified by energy cost
        total_trades: Number of non-zero directional predictions
        neutral_count: Number of neutral (0) predictions
    """
    config: BacktestConfig
    log: pd.DataFrame
    directional_accuracy: float
    naive_pnl: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    energy_bucket_accuracy: Dict[str, float]
    total_trades: int = 0
    neutral_count: int = 0
    
    def summary(self) -> Dict[str, Any]:
        """Return summary statistics as dict."""
        return {
            "symbol": self.config.symbol,
            "horizon_steps": self.config.horizon_steps,
            "total_trades": self.total_trades,
            "neutral_count": self.neutral_count,
            "directional_accuracy": round(self.directional_accuracy, 4),
            "win_rate": round(self.win_rate, 4),
            "naive_pnl": round(self.naive_pnl, 6),
            "sharpe_ratio": round(self.sharpe, 4),
            "max_drawdown": round(self.max_drawdown, 6),
            "energy_bucket_accuracy": {
                k: round(v, 4) for k, v in self.energy_bucket_accuracy.items()
            },
        }


def run_composer_backtest(
    config: BacktestConfig,
    timestamps: Sequence[pd.Timestamp],
    price_getter: Callable[[str, pd.Timestamp], float],
    hedge_engine_runner: Callable[[str, pd.Timestamp], Any],
    liquidity_engine_runner: Callable[[str, pd.Timestamp], Any],
    sentiment_engine_runner: Callable[[str, pd.Timestamp], Any],
    agent_configs: Dict[str, Any] | None = None,
) -> BacktestResult:
    """
    Run walk-forward backtest over sequence of timestamps.
    
    For each timestamp t_i:
    1. Run all three engines for (symbol, t_i)
    2. Feed results into agents via .set_engine_output() / .set_sentiment_envelope()
    3. Compose directive
    4. Compute realized return over (t_i -> t_{i+horizon})
    
    Args:
        config: Backtest configuration
        timestamps: Monotonic increasing sequence of bar timestamps
        price_getter: Function (symbol, timestamp) -> price
        hedge_engine_runner: Function (symbol, timestamp) -> hedge_engine_output
        liquidity_engine_runner: Function (symbol, timestamp) -> liquidity_engine_output
        sentiment_engine_runner: Function (symbol, timestamp) -> sentiment_envelope
        agent_configs: Optional agent-specific configs
        
    Returns:
        BacktestResult with full log and aggregate metrics
        
    Example:
        >>> config = BacktestConfig(symbol="SPY", horizon_steps=1)
        >>> result = run_composer_backtest(
        ...     config=config,
        ...     timestamps=historical_timestamps,
        ...     price_getter=my_price_loader,
        ...     hedge_engine_runner=my_hedge_runner,
        ...     liquidity_engine_runner=my_liquidity_runner,
        ...     sentiment_engine_runner=my_sentiment_runner,
        ... )
        >>> print(f"Accuracy: {result.directional_accuracy:.3f}")
        >>> print(f"Sharpe: {result.sharpe:.3f}")
    """
    symbol = config.symbol
    horizon = config.horizon_steps
    
    # Initialize agent configs
    if agent_configs is None:
        agent_configs = {
            "hedge": {},
            "liquidity": {},
            "sentiment": {},
        }
    
    # Initialize agents once
    hedge_agent = HedgeAgentV3(config=agent_configs.get("hedge", {}))
    liquidity_agent = LiquidityAgentV1(config=agent_configs.get("liquidity", {}))
    sentiment_agent = SentimentAgentV1(config=agent_configs.get("sentiment", {}))
    
    # Mutable cell to share current price into composer
    _current_price: List[float] = [0.0]
    
    # Build composer
    composer = ComposerAgent(
        hedge_agent=hedge_agent,
        liquidity_agent=liquidity_agent,
        sentiment_agent=sentiment_agent,
        reference_price_getter=lambda: _current_price[0],
    )
    
    records: List[Dict[str, Any]] = []
    n = len(timestamps)
    
    for i, t in enumerate(timestamps):
        # Ensure we have horizon target
        j = i + horizon
        if j >= n:
            break  # Cannot compute realized future return for last horizon steps
        
        t_next = timestamps[j]
        
        # 1. Get current + future prices
        try:
            p_now = price_getter(symbol, t)
            p_future = price_getter(symbol, t_next)
        except Exception as e:
            # Skip if price data unavailable
            continue
        
        if p_now <= 0 or p_future <= 0 or pd.isna(p_now) or pd.isna(p_future):
            # Skip bad data
            continue
        
        # Simple percent return (use log return if preferred)
        realized_return = (p_future - p_now) / p_now
        _current_price[0] = p_now  # Feed into composer via closure
        
        # 2. Run engines via provided runners
        try:
            hedge_output = hedge_engine_runner(symbol, t)
            liquidity_output = liquidity_engine_runner(symbol, t)
            sentiment_envelope = sentiment_engine_runner(symbol, t)
        except Exception as e:
            # Skip if engine execution fails
            continue
        
        # 3. Set agent outputs
        try:
            hedge_agent.set_engine_output(hedge_output)
            liquidity_agent.set_engine_output(liquidity_output)
            sentiment_agent.set_sentiment_envelope(sentiment_envelope)
        except Exception as e:
            # Skip if agent setup fails
            continue
        
        # 4. Compose directive
        try:
            directive: CompositeMarketDirective = composer.compose()
        except Exception as e:
            # Skip if composition fails
            continue
        
        # 5. Store record
        records.append(
            {
                "timestamp": t,
                "price": p_now,
                "future_price": p_future,
                "realized_return": realized_return,
                "direction": directive.direction,
                "strength": directive.strength,
                "confidence": directive.confidence,
                "energy_cost": directive.energy_cost,
                "trade_style": directive.trade_style,
                "volatility": directive.volatility,
                "rationale": directive.rationale[:100] if directive.rationale else "",  # Truncate
            }
        )
    
    # Handle empty results
    if not records:
        empty_df = pd.DataFrame(
            columns=[
                "timestamp",
                "price",
                "future_price",
                "realized_return",
                "direction",
                "strength",
                "confidence",
                "energy_cost",
                "trade_style",
                "volatility",
                "rationale",
            ]
        )
        return BacktestResult(
            config=config,
            log=empty_df,
            directional_accuracy=0.0,
            naive_pnl=0.0,
            sharpe=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            energy_bucket_accuracy={},
            total_trades=0,
            neutral_count=0,
        )
    
    # Build results DataFrame
    log = pd.DataFrame.from_records(records)
    log = log.set_index("timestamp").sort_index()
    
    # Extract sequences for metrics
    dirs = log["direction"].astype(int).tolist()
    rets = log["realized_return"].astype(float).tolist()
    energies = log["energy_cost"].astype(float).tolist()
    
    # Count trades
    total_trades = sum(1 for d in dirs if d != 0)
    neutral_count = sum(1 for d in dirs if d == 0)
    
    # Compute metrics
    directional_acc = compute_directional_accuracy(
        dirs, rets, threshold=config.return_threshold
    )
    naive_pnl = compute_naive_pnl(dirs, rets, notional=config.notional)
    pnl_series = compute_pnl_series(dirs, rets, notional=config.notional)
    sharpe = compute_sharpe_ratio(pnl_series)
    max_dd = compute_max_drawdown(pnl_series)
    win_rate = compute_win_rate(dirs, rets)
    energy_bucket_acc = bucket_accuracy_by_energy(
        dirs, rets, energies, buckets=config.energy_buckets
    )
    
    return BacktestResult(
        config=config,
        log=log,
        directional_accuracy=directional_acc,
        naive_pnl=naive_pnl,
        sharpe=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        energy_bucket_accuracy=energy_bucket_acc,
        total_trades=total_trades,
        neutral_count=neutral_count,
    )
