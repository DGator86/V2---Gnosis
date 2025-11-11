"""
Performance Metrics Module
Computes Sharpe, Sortino, MAR, max DD, win-rate, profit factor, etc.
"""

import numpy as np
import pandas as pd
from typing import Union


def summarize_metrics(trade_log: pd.DataFrame) -> dict:
    """
    Compute comprehensive performance metrics from trade log.
    
    Parameters
    ----------
    trade_log : pd.DataFrame
        Trade log with columns: ['entry_time', 'exit_time', 'pnl', 'equity']
        
    Returns
    -------
    dict
        Performance metrics
    """
    if trade_log.empty or 'pnl' not in trade_log.columns:
        return {
            'total_trades': 0,
            'sharpe': 0.0,
            'sortino': 0.0,
            'mar': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'total_pnl': 0.0,
        }
    
    pnl = trade_log['pnl'].values
    
    # Basic stats
    total_trades = len(pnl)
    total_pnl = float(np.sum(pnl))
    
    # Win/loss breakdown
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    
    win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
    avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_loss = float(np.mean(np.abs(losses))) if len(losses) > 0 else 0.0
    
    # Profit factor
    gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gross_loss = float(np.sum(np.abs(losses))) if len(losses) > 0 else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
    
    # Equity curve metrics (if equity column exists)
    if 'equity' in trade_log.columns:
        equity = trade_log['equity'].values
        max_dd = calculate_max_drawdown(equity)
        
        # Returns for Sharpe/Sortino
        returns = np.diff(equity) / equity[:-1]
        
        sharpe = calculate_sharpe_ratio(returns)
        sortino = calculate_sortino_ratio(returns)
        
        # MAR ratio (return / max_dd)
        total_return = (equity[-1] - equity[0]) / equity[0]
        mar = total_return / max_dd if max_dd > 0 else 0.0
    else:
        max_dd = 0.0
        sharpe = 0.0
        sortino = 0.0
        mar = 0.0
    
    return {
        'total_trades': int(total_trades),
        'winning_trades': int(len(wins)),
        'losing_trades': int(len(losses)),
        'win_rate': float(win_rate),
        'avg_win': float(avg_win),
        'avg_loss': float(avg_loss),
        'profit_factor': float(profit_factor),
        'total_pnl': float(total_pnl),
        'sharpe': float(sharpe),
        'sortino': float(sortino),
        'mar': float(mar),
        'max_drawdown': float(max_dd),
    }


def calculate_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """
    Calculate annualized Sharpe ratio.
    
    Parameters
    ----------
    returns : np.ndarray
        Array of period returns
    risk_free_rate : float
        Annualized risk-free rate
    periods_per_year : int
        Number of periods per year (252 for daily)
        
    Returns
    -------
    float
        Annualized Sharpe ratio
    """
    if len(returns) == 0 or np.std(returns) == 0:
        return 0.0
    
    excess_returns = returns - (risk_free_rate / periods_per_year)
    sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(periods_per_year)
    
    return float(sharpe)


def calculate_sortino_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """
    Calculate annualized Sortino ratio (uses downside deviation).
    
    Parameters
    ----------
    returns : np.ndarray
        Array of period returns
    risk_free_rate : float
        Annualized risk-free rate
    periods_per_year : int
        Number of periods per year
        
    Returns
    -------
    float
        Annualized Sortino ratio
    """
    if len(returns) == 0:
        return 0.0
    
    excess_returns = returns - (risk_free_rate / periods_per_year)
    
    # Downside deviation (only negative returns)
    downside_returns = excess_returns[excess_returns < 0]
    if len(downside_returns) == 0:
        return 0.0
    
    downside_std = np.std(downside_returns)
    if downside_std == 0:
        return 0.0
    
    sortino = np.mean(excess_returns) / downside_std * np.sqrt(periods_per_year)
    
    return float(sortino)


def calculate_max_drawdown(equity_curve: np.ndarray) -> float:
    """
    Calculate maximum drawdown from equity curve.
    
    Parameters
    ----------
    equity_curve : np.ndarray
        Array of equity values over time
        
    Returns
    -------
    float
        Maximum drawdown as a fraction (e.g., 0.15 for 15%)
    """
    if len(equity_curve) == 0:
        return 0.0
    
    # Running maximum
    running_max = np.maximum.accumulate(equity_curve)
    
    # Drawdown at each point
    drawdown = (equity_curve - running_max) / running_max
    
    # Maximum drawdown
    max_dd = float(np.abs(np.min(drawdown)))
    
    return max_dd


def calculate_calmar_ratio(
    total_return: float,
    max_drawdown: float
) -> float:
    """
    Calculate Calmar ratio (annualized return / max drawdown).
    
    Parameters
    ----------
    total_return : float
        Total return over period
    max_drawdown : float
        Maximum drawdown
        
    Returns
    -------
    float
        Calmar ratio
    """
    if max_drawdown == 0:
        return 0.0
    
    return total_return / max_drawdown
