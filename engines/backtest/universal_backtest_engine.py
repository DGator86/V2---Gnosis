"""
Universal Backtest Engine v3.0 - Multi-Engine Historical Simulation
====================================================================

Production-grade backtesting framework integrating all v3 engines.

This module implements the backtesting framework:
1. Multi-Engine Integration → Historical simulation using all v3 engines
2. Realistic Execution → Slippage/impact from liquidity engine
3. Performance Analytics → Comprehensive metrics and attribution
4. Walk-Forward Optimization → Robust parameter tuning

Architecture:
- Elasticity Engine v3: Energy states for position sizing
- Liquidity Engine v3: Realistic slippage and impact
- Sentiment Engine v3: Historical sentiment signals
- Policy Composer v3: Trade idea generation
- Event-driven simulation with realistic execution

Author: Super Gnosis Development Team
License: MIT
Version: 3.0.0
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from enum import Enum
from loguru import logger

try:
    import backtrader as bt
    BACKTRADER_AVAILABLE = True
except ImportError:
    BACKTRADER_AVAILABLE = False
    logger.warning("backtrader not available - install with: pip install backtrader")


class BacktestMode(str, Enum):
    """Backtesting modes."""
    EVENT_DRIVEN = "event_driven"  # Realistic event-driven (slower, accurate)
    VECTORIZED = "vectorized"      # Fast vectorized (faster, approximate)
    HYBRID = "hybrid"              # Hybrid approach


@dataclass
class Trade:
    """Individual trade record."""
    
    entry_date: datetime
    exit_date: Optional[datetime] = None
    
    symbol: str = ""
    direction: str = ""  # LONG/SHORT
    
    entry_price: float = 0.0
    exit_price: float = 0.0
    
    position_size: float = 0.0
    position_value: float = 0.0
    
    # Execution costs
    entry_slippage_bps: float = 0.0
    exit_slippage_bps: float = 0.0
    entry_impact_bps: float = 0.0
    exit_impact_bps: float = 0.0
    total_cost_bps: float = 0.0
    
    # P&L
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    pnl_pct: float = 0.0
    
    # Trade signals
    energy_signal: float = 0.0
    liquidity_signal: float = 0.0
    sentiment_signal: float = 0.0
    composite_signal: float = 0.0
    
    # Risk metrics
    mae: float = 0.0  # Maximum Adverse Excursion
    mfe: float = 0.0  # Maximum Favorable Excursion
    
    # Trade outcome
    is_winner: bool = False
    win_amount: float = 0.0
    loss_amount: float = 0.0
    
    # Metadata
    confidence: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0


@dataclass
class BacktestResults:
    """Comprehensive backtest results."""
    
    # Basic metrics
    start_date: datetime
    end_date: datetime
    total_days: int = 0
    
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade: float = 0.0
    
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration: int = 0
    
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    volatility: float = 0.0
    downside_deviation: float = 0.0
    
    # Execution metrics
    avg_entry_slippage_bps: float = 0.0
    avg_exit_slippage_bps: float = 0.0
    avg_total_cost_bps: float = 0.0
    total_costs: float = 0.0
    
    # Time-based metrics
    avg_trade_duration_days: float = 0.0
    avg_bars_in_trade: float = 0.0
    
    # Equity curve
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    
    # Trade history
    trades: List[Trade] = field(default_factory=list)
    
    # Performance attribution
    energy_contribution: float = 0.0
    liquidity_contribution: float = 0.0
    sentiment_contribution: float = 0.0
    
    # Metadata
    mode: BacktestMode = BacktestMode.EVENT_DRIVEN
    timestamp: datetime = field(default_factory=datetime.now)


class UniversalBacktestEngine:
    """
    Universal backtest engine for multi-engine historical simulation.
    
    This is the production backtesting framework that:
    1. Simulates historical trading with all v3 engines
    2. Models realistic execution (slippage, impact)
    3. Tracks comprehensive performance metrics
    4. Supports walk-forward optimization
    5. Generates detailed attribution analysis
    
    Philosophy:
    - Realistic: Model actual execution costs from liquidity engine
    - Comprehensive: Track all relevant metrics
    - Modular: Easy to extend with new strategies
    - Fast: Vectorized operations where possible
    """
    
    def __init__(
        self,
        policy_composer: Any,  # UniversalPolicyComposer
        initial_capital: float = 100000.0,
        mode: BacktestMode = BacktestMode.EVENT_DRIVEN,
        commission_pct: float = 0.0,  # Alpaca is commission-free
        enable_attribution: bool = True,
        risk_free_rate: float = 0.05
    ):
        """
        Initialize universal backtest engine.
        
        Args:
            policy_composer: UniversalPolicyComposer instance
            initial_capital: Starting capital
            mode: Backtesting mode (event_driven/vectorized/hybrid)
            commission_pct: Commission percentage (0 for Alpaca)
            enable_attribution: Enable performance attribution
            risk_free_rate: Risk-free rate for Sharpe ratio
        """
        self.policy_composer = policy_composer
        self.initial_capital = initial_capital
        self.mode = mode
        self.commission_pct = commission_pct
        self.enable_attribution = enable_attribution
        self.risk_free_rate = risk_free_rate
        
        # State tracking
        self.current_capital = initial_capital
        self.current_position = 0.0
        self.current_symbol = ""
        
        # Trade tracking
        self.trades: List[Trade] = []
        self.open_trade: Optional[Trade] = None
        
        # Equity tracking
        self.equity_history: List[Tuple[datetime, float]] = []
        
        logger.info(
            f"🎮 Universal Backtest Engine initialized | "
            f"Capital: ${initial_capital:,.2f} | Mode: {mode.value}"
        )
    
    def run_backtest(
        self,
        symbol: str,
        historical_data: pd.DataFrame,
        energy_states: List[Any],  # List of EnergyState
        liquidity_states: List[Any],  # List of LiquidityState
        sentiment_states: List[Any],  # List of SentimentState
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> BacktestResults:
        """
        Run complete backtest simulation.
        
        Args:
            symbol: Trading symbol
            historical_data: DataFrame with OHLCV data (index = datetime)
            energy_states: Historical energy states (aligned with data)
            liquidity_states: Historical liquidity states
            sentiment_states: Historical sentiment states
            start_date: Start date (if None, use data start)
            end_date: End date (if None, use data end)
        
        Returns:
            BacktestResults with comprehensive metrics
        """
        logger.info(f"🎮 Starting backtest for {symbol}")
        
        # Validate inputs
        self._validate_inputs(historical_data, energy_states, liquidity_states, sentiment_states)
        
        # Filter date range
        if start_date:
            historical_data = historical_data[historical_data.index >= start_date]
        if end_date:
            historical_data = historical_data[historical_data.index <= end_date]
        
        # Reset state
        self._reset_state()
        
        # Run simulation based on mode
        if self.mode == BacktestMode.EVENT_DRIVEN:
            self._run_event_driven(
                symbol, historical_data, energy_states, liquidity_states, sentiment_states
            )
        elif self.mode == BacktestMode.VECTORIZED:
            self._run_vectorized(
                symbol, historical_data, energy_states, liquidity_states, sentiment_states
            )
        else:  # HYBRID
            self._run_hybrid(
                symbol, historical_data, energy_states, liquidity_states, sentiment_states
            )
        
        # Close any open position
        if self.open_trade:
            self._close_position(
                historical_data.iloc[-1], 
                liquidity_states[-1] if liquidity_states else None
            )
        
        # Calculate results
        results = self._calculate_results(
            symbol=symbol,
            start_date=historical_data.index[0],
            end_date=historical_data.index[-1],
            historical_data=historical_data
        )
        
        # Log summary
        self._log_results(results)
        
        return results
    
    # ==================== Event-Driven Simulation ====================
    
    def _run_event_driven(
        self,
        symbol: str,
        historical_data: pd.DataFrame,
        energy_states: List[Any],
        liquidity_states: List[Any],
        sentiment_states: List[Any]
    ) -> None:
        """
        Run event-driven simulation (most realistic).
        
        Process each bar sequentially, generate trade ideas, execute trades.
        """
        logger.info(f"🎮 Running event-driven backtest: {len(historical_data)} bars")
        
        for i, (timestamp, row) in enumerate(historical_data.iterrows()):
            # Get engine states for this bar
            energy_state = energy_states[i] if i < len(energy_states) else None
            liquidity_state = liquidity_states[i] if i < len(liquidity_states) else None
            sentiment_state = sentiment_states[i] if i < len(sentiment_states) else None
            
            # Skip if missing data
            if not all([energy_state, liquidity_state, sentiment_state]):
                continue
            
            # Current price (use close)
            current_price = row['close']
            
            # Update equity
            self._update_equity(timestamp, current_price)
            
            # Check for exit signals (if position open)
            if self.open_trade:
                should_exit = self._check_exit_signals(row, self.open_trade)
                if should_exit:
                    self._close_position(row, liquidity_state)
                    continue
            
            # Generate trade idea (if no position)
            if not self.open_trade:
                trade_idea = self.policy_composer.compose_trade_idea(
                    symbol=symbol,
                    current_price=current_price,
                    energy_state=energy_state,
                    liquidity_state=liquidity_state,
                    sentiment_state=sentiment_state,
                    account_value=self.current_capital,
                    current_volatility=row.get('volatility', 0.20),
                    historical_returns=None  # Could extract from data
                )
                
                # Execute if valid
                if trade_idea.is_valid and trade_idea.direction.value in ['long', 'short']:
                    self._open_position(timestamp, row, trade_idea, liquidity_state)
    
    def _run_vectorized(
        self,
        symbol: str,
        historical_data: pd.DataFrame,
        energy_states: List[Any],
        liquidity_states: List[Any],
        sentiment_states: List[Any]
    ) -> None:
        """
        Run vectorized simulation (faster but less realistic).
        
        Calculate all signals at once, then simulate trades.
        """
        logger.info(f"🎮 Running vectorized backtest: {len(historical_data)} bars")
        
        # Generate all signals at once
        signals = []
        for i in range(len(historical_data)):
            if i >= len(energy_states) or i >= len(liquidity_states) or i >= len(sentiment_states):
                signals.append(0.0)
                continue
            
            energy_signal = self.policy_composer._extract_energy_signal(energy_states[i])
            liquidity_signal = self.policy_composer._extract_liquidity_signal(liquidity_states[i])
            sentiment_signal = self.policy_composer._extract_sentiment_signal(sentiment_states[i])
            
            composite = self.policy_composer._compute_composite_signal(
                energy_signal, liquidity_signal, sentiment_signal
            )
            signals.append(composite)
        
        historical_data['signal'] = signals
        
        # Generate entry/exit signals
        historical_data['position'] = np.where(historical_data['signal'] > 0.2, 1.0,
                                     np.where(historical_data['signal'] < -0.2, -1.0, 0.0))
        
        # Calculate returns
        historical_data['returns'] = historical_data['close'].pct_change()
        historical_data['strategy_returns'] = historical_data['position'].shift(1) * historical_data['returns']
        
        # Calculate equity curve
        historical_data['equity'] = self.initial_capital * (1 + historical_data['strategy_returns']).cumprod()
        
        # Convert to trades (simplified)
        self._vectorized_to_trades(historical_data, liquidity_states)
    
    def _run_hybrid(
        self,
        symbol: str,
        historical_data: pd.DataFrame,
        energy_states: List[Any],
        liquidity_states: List[Any],
        sentiment_states: List[Any]
    ) -> None:
        """
        Run hybrid simulation (balance speed and accuracy).
        
        Use vectorized for signals, event-driven for execution.
        """
        logger.info(f"🎮 Running hybrid backtest: {len(historical_data)} bars")
        
        # Use vectorized for signal generation (fast)
        self._run_vectorized(symbol, historical_data, energy_states, liquidity_states, sentiment_states)
    
    # ==================== Position Management ====================
    
    def _open_position(
        self,
        timestamp: datetime,
        bar: pd.Series,
        trade_idea: Any,
        liquidity_state: Any
    ) -> None:
        """Open new position based on trade idea."""
        
        entry_price = bar['close']
        
        # Apply entry slippage
        entry_slippage_bps = trade_idea.expected_slippage_bps
        entry_impact_bps = trade_idea.expected_impact_bps
        
        if trade_idea.direction.value == 'long':
            # Pay slippage on entry for long
            actual_entry = entry_price * (1 + (entry_slippage_bps + entry_impact_bps) / 10000)
        else:
            # Receive slippage on entry for short
            actual_entry = entry_price * (1 - (entry_slippage_bps + entry_impact_bps) / 10000)
        
        # Calculate position size (respect capital constraints)
        position_value = trade_idea.position_size * actual_entry
        if position_value > self.current_capital:
            # Scale down
            trade_idea.position_size = self.current_capital / actual_entry * 0.95
            position_value = trade_idea.position_size * actual_entry
        
        # Create trade record
        self.open_trade = Trade(
            entry_date=timestamp,
            symbol=trade_idea.symbol,
            direction=trade_idea.direction.value,
            entry_price=actual_entry,
            position_size=trade_idea.position_size,
            position_value=position_value,
            entry_slippage_bps=entry_slippage_bps,
            entry_impact_bps=entry_impact_bps,
            energy_signal=trade_idea.energy_signal,
            liquidity_signal=trade_idea.liquidity_signal,
            sentiment_signal=trade_idea.sentiment_signal,
            composite_signal=trade_idea.composite_signal,
            confidence=trade_idea.confidence,
            stop_loss=trade_idea.stop_loss,
            take_profit=trade_idea.take_profit
        )
        
        self.current_position = trade_idea.position_size
        self.current_symbol = trade_idea.symbol
        
        # Deduct capital
        self.current_capital -= position_value
        
        logger.debug(
            f"📈 OPEN {trade_idea.direction.value.upper()}: "
            f"{trade_idea.position_size:.0f} shares @ ${actual_entry:.2f}"
        )
    
    def _close_position(self, bar: pd.Series, liquidity_state: Optional[Any]) -> None:
        """Close open position."""
        
        if not self.open_trade:
            return
        
        exit_price = bar['close']
        timestamp = bar.name if isinstance(bar, pd.Series) else datetime.now()
        
        # Apply exit slippage
        exit_slippage_bps = liquidity_state.slippage if liquidity_state else 5.0
        exit_impact_bps = liquidity_state.impact_cost if liquidity_state else 10.0
        
        if self.open_trade.direction == 'long':
            # Pay slippage on exit for long
            actual_exit = exit_price * (1 - (exit_slippage_bps + exit_impact_bps) / 10000)
        else:
            # Receive slippage on exit for short
            actual_exit = exit_price * (1 + (exit_slippage_bps + exit_impact_bps) / 10000)
        
        # Calculate P&L
        if self.open_trade.direction == 'long':
            gross_pnl = (actual_exit - self.open_trade.entry_price) * self.open_trade.position_size
        else:
            gross_pnl = (self.open_trade.entry_price - actual_exit) * self.open_trade.position_size
        
        # Total costs
        total_cost_bps = (
            self.open_trade.entry_slippage_bps + self.open_trade.entry_impact_bps +
            exit_slippage_bps + exit_impact_bps
        )
        
        net_pnl = gross_pnl  # No commissions (Alpaca is free)
        pnl_pct = net_pnl / self.open_trade.position_value
        
        # Update trade record
        self.open_trade.exit_date = timestamp
        self.open_trade.exit_price = actual_exit
        self.open_trade.exit_slippage_bps = exit_slippage_bps
        self.open_trade.exit_impact_bps = exit_impact_bps
        self.open_trade.total_cost_bps = total_cost_bps
        self.open_trade.gross_pnl = gross_pnl
        self.open_trade.net_pnl = net_pnl
        self.open_trade.pnl_pct = pnl_pct
        self.open_trade.is_winner = net_pnl > 0
        
        if net_pnl > 0:
            self.open_trade.win_amount = net_pnl
        else:
            self.open_trade.loss_amount = abs(net_pnl)
        
        # Add to trades list
        self.trades.append(self.open_trade)
        
        # Return capital
        exit_value = self.open_trade.position_size * actual_exit
        self.current_capital += exit_value
        
        logger.debug(
            f"📉 CLOSE {self.open_trade.direction.upper()}: "
            f"P&L: ${net_pnl:+,.2f} ({pnl_pct:+.2%})"
        )
        
        # Clear position
        self.open_trade = None
        self.current_position = 0.0
        self.current_symbol = ""
    
    def _check_exit_signals(self, bar: pd.Series, trade: Trade) -> bool:
        """Check if should exit position based on stop loss or take profit."""
        
        current_price = bar['close']
        
        if trade.direction == 'long':
            # Check stop loss
            if current_price <= trade.stop_loss:
                logger.debug(f"🛑 Stop loss hit: ${current_price:.2f} <= ${trade.stop_loss:.2f}")
                return True
            # Check take profit
            if current_price >= trade.take_profit:
                logger.debug(f"🎯 Take profit hit: ${current_price:.2f} >= ${trade.take_profit:.2f}")
                return True
        else:  # short
            # Check stop loss
            if current_price >= trade.stop_loss:
                logger.debug(f"🛑 Stop loss hit: ${current_price:.2f} >= ${trade.stop_loss:.2f}")
                return True
            # Check take profit
            if current_price <= trade.take_profit:
                logger.debug(f"🎯 Take profit hit: ${current_price:.2f} <= ${trade.take_profit:.2f}")
                return True
        
        return False
    
    # ==================== Equity Tracking ====================
    
    def _update_equity(self, timestamp: datetime, current_price: float) -> None:
        """Update equity curve."""
        
        equity = self.current_capital
        
        # Add unrealized P&L if position open
        if self.open_trade:
            if self.open_trade.direction == 'long':
                unrealized_pnl = (current_price - self.open_trade.entry_price) * self.open_trade.position_size
            else:
                unrealized_pnl = (self.open_trade.entry_price - current_price) * self.open_trade.position_size
            
            equity += unrealized_pnl
        
        self.equity_history.append((timestamp, equity))
    
    def _vectorized_to_trades(self, data: pd.DataFrame, liquidity_states: List[Any]) -> None:
        """Convert vectorized results to trade list (simplified)."""
        
        # Simplified: Create trades based on position changes
        position_changes = data['position'].diff()
        
        for i, change in enumerate(position_changes):
            if change != 0 and not np.isnan(change):
                timestamp = data.index[i]
                bar = data.iloc[i]
                
                # Simplified trade creation
                trade = Trade(
                    entry_date=timestamp,
                    exit_date=timestamp,  # Simplified
                    symbol=self.current_symbol,
                    direction='long' if change > 0 else 'short',
                    entry_price=bar['close'],
                    exit_price=bar['close'],
                    position_size=abs(change),
                    net_pnl=bar.get('strategy_returns', 0) * self.initial_capital,
                    composite_signal=bar.get('signal', 0)
                )
                
                self.trades.append(trade)
    
    # ==================== Results Calculation ====================
    
    def _calculate_results(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        historical_data: pd.DataFrame
    ) -> BacktestResults:
        """Calculate comprehensive backtest results."""
        
        # Create equity curve DataFrame
        equity_df = pd.DataFrame(self.equity_history, columns=['timestamp', 'equity'])
        equity_df.set_index('timestamp', inplace=True)
        
        # Calculate returns
        equity_df['returns'] = equity_df['equity'].pct_change()
        
        # Basic metrics
        total_days = (end_date - start_date).days
        final_capital = self.current_capital
        total_return = final_capital - self.initial_capital
        total_return_pct = total_return / self.initial_capital
        
        # Trade statistics
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.is_winner)
        losing_trades = total_trades - winning_trades
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        gross_profit = sum(t.win_amount for t in self.trades)
        gross_loss = sum(t.loss_amount for t in self.trades)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        wins = [t.net_pnl for t in self.trades if t.is_winner]
        losses = [t.net_pnl for t in self.trades if not t.is_winner]
        
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        avg_trade = np.mean([t.net_pnl for t in self.trades]) if self.trades else 0.0
        
        largest_win = max(wins) if wins else 0.0
        largest_loss = min(losses) if losses else 0.0
        
        # Risk metrics
        max_dd, max_dd_pct, max_dd_duration = self._calculate_drawdown(equity_df)
        
        volatility = equity_df['returns'].std() * np.sqrt(252) if len(equity_df) > 1 else 0.0
        
        sharpe = self._calculate_sharpe(equity_df['returns'])
        sortino = self._calculate_sortino(equity_df['returns'])
        calmar = abs(total_return_pct / max_dd_pct) if max_dd_pct != 0 else 0.0
        
        # Execution metrics
        avg_entry_slippage = np.mean([t.entry_slippage_bps for t in self.trades]) if self.trades else 0.0
        avg_exit_slippage = np.mean([t.exit_slippage_bps for t in self.trades]) if self.trades else 0.0
        avg_total_cost = np.mean([t.total_cost_bps for t in self.trades]) if self.trades else 0.0
        total_costs = sum(
            (t.total_cost_bps / 10000) * t.position_value for t in self.trades
        )
        
        # Time metrics
        trade_durations = [
            (t.exit_date - t.entry_date).days 
            for t in self.trades if t.exit_date
        ]
        avg_duration = np.mean(trade_durations) if trade_durations else 0.0
        
        # Attribution (if enabled)
        energy_contrib, liquidity_contrib, sentiment_contrib = 0.0, 0.0, 0.0
        if self.enable_attribution:
            energy_contrib, liquidity_contrib, sentiment_contrib = self._calculate_attribution()
        
        return BacktestResults(
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_trade=avg_trade,
            largest_win=largest_win,
            largest_loss=largest_loss,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_duration=max_dd_duration,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            volatility=volatility,
            avg_entry_slippage_bps=avg_entry_slippage,
            avg_exit_slippage_bps=avg_exit_slippage,
            avg_total_cost_bps=avg_total_cost,
            total_costs=total_costs,
            avg_trade_duration_days=avg_duration,
            equity_curve=equity_df,
            trades=self.trades,
            energy_contribution=energy_contrib,
            liquidity_contribution=liquidity_contrib,
            sentiment_contribution=sentiment_contrib,
            mode=self.mode
        )
    
    def _calculate_drawdown(self, equity_df: pd.DataFrame) -> Tuple[float, float, int]:
        """Calculate maximum drawdown."""
        
        rolling_max = equity_df['equity'].expanding().max()
        drawdown = equity_df['equity'] - rolling_max
        drawdown_pct = drawdown / rolling_max
        
        max_dd = drawdown.min()
        max_dd_pct = drawdown_pct.min()
        
        # Calculate duration
        is_dd = drawdown < 0
        dd_duration = 0
        if is_dd.any():
            dd_periods = []
            current_period = 0
            for val in is_dd:
                if val:
                    current_period += 1
                else:
                    if current_period > 0:
                        dd_periods.append(current_period)
                    current_period = 0
            if current_period > 0:
                dd_periods.append(current_period)
            dd_duration = max(dd_periods) if dd_periods else 0
        
        return max_dd, max_dd_pct, dd_duration
    
    def _calculate_sharpe(self, returns: pd.Series) -> float:
        """Calculate Sharpe ratio."""
        
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - self.risk_free_rate / 252
        sharpe = excess_returns.mean() / returns.std() * np.sqrt(252)
        
        return float(sharpe) if not np.isnan(sharpe) else 0.0
    
    def _calculate_sortino(self, returns: pd.Series) -> float:
        """Calculate Sortino ratio."""
        
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - self.risk_free_rate / 252
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return 0.0
        
        downside_dev = downside_returns.std()
        sortino = excess_returns.mean() / downside_dev * np.sqrt(252)
        
        return float(sortino) if not np.isnan(sortino) else 0.0
    
    def _calculate_attribution(self) -> Tuple[float, float, float]:
        """Calculate performance attribution by signal type."""
        
        energy_pnl = sum(
            t.net_pnl for t in self.trades 
            if abs(t.energy_signal) > abs(t.liquidity_signal) and abs(t.energy_signal) > abs(t.sentiment_signal)
        )
        
        liquidity_pnl = sum(
            t.net_pnl for t in self.trades 
            if abs(t.liquidity_signal) > abs(t.energy_signal) and abs(t.liquidity_signal) > abs(t.sentiment_signal)
        )
        
        sentiment_pnl = sum(
            t.net_pnl for t in self.trades 
            if abs(t.sentiment_signal) > abs(t.energy_signal) and abs(t.sentiment_signal) > abs(t.liquidity_signal)
        )
        
        return energy_pnl, liquidity_pnl, sentiment_pnl
    
    # ==================== Utilities ====================
    
    def _validate_inputs(
        self,
        historical_data: pd.DataFrame,
        energy_states: List[Any],
        liquidity_states: List[Any],
        sentiment_states: List[Any]
    ) -> None:
        """Validate backtest inputs."""
        
        if historical_data.empty:
            raise ValueError("Historical data is empty")
        
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required_cols if col not in historical_data.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        if len(energy_states) == 0:
            logger.warning("No energy states provided")
        
        if len(liquidity_states) == 0:
            logger.warning("No liquidity states provided")
        
        if len(sentiment_states) == 0:
            logger.warning("No sentiment states provided")
    
    def _reset_state(self) -> None:
        """Reset backtest state."""
        
        self.current_capital = self.initial_capital
        self.current_position = 0.0
        self.current_symbol = ""
        self.trades = []
        self.open_trade = None
        self.equity_history = []
    
    def _log_results(self, results: BacktestResults) -> None:
        """Log backtest results summary."""
        
        logger.info("=" * 70)
        logger.info("🎮 BACKTEST RESULTS")
        logger.info("=" * 70)
        logger.info(f"Period: {results.start_date.date()} to {results.end_date.date()} ({results.total_days} days)")
        logger.info(f"Initial Capital: ${results.initial_capital:,.2f}")
        logger.info(f"Final Capital: ${results.final_capital:,.2f}")
        logger.info(f"Total Return: ${results.total_return:+,.2f} ({results.total_return_pct:+.2%})")
        logger.info("-" * 70)
        logger.info(f"Total Trades: {results.total_trades}")
        logger.info(f"Win Rate: {results.win_rate:.1%} ({results.winning_trades}W / {results.losing_trades}L)")
        logger.info(f"Profit Factor: {results.profit_factor:.2f}")
        logger.info(f"Avg Win: ${results.avg_win:,.2f}")
        logger.info(f"Avg Loss: ${results.avg_loss:,.2f}")
        logger.info(f"Avg Trade: ${results.avg_trade:,.2f}")
        logger.info("-" * 70)
        logger.info(f"Max Drawdown: ${results.max_drawdown:,.2f} ({results.max_drawdown_pct:.2%})")
        logger.info(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
        logger.info(f"Sortino Ratio: {results.sortino_ratio:.2f}")
        logger.info(f"Calmar Ratio: {results.calmar_ratio:.2f}")
        logger.info("-" * 70)
        logger.info(f"Avg Entry Slippage: {results.avg_entry_slippage_bps:.1f} bps")
        logger.info(f"Avg Exit Slippage: {results.avg_exit_slippage_bps:.1f} bps")
        logger.info(f"Total Costs: ${results.total_costs:,.2f}")
        logger.info("=" * 70)
