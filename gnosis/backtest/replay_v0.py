from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

from gnosis.feature_store.store import FeatureStore
from gnosis.agents.agents_v1 import agent1_hedge, agent2_liquidity, agent3_sentiment, compose

@dataclass
class Trade:
    """Represents a completed trade"""
    t_entry: datetime
    direction: int     # +1 long, -1 short
    entry_px: float
    size: float
    time_stop_bars: int
    t_exit: Optional[datetime] = None
    exit_px: Optional[float] = None
    pnl: Optional[float] = None
    exit_reason: Optional[str] = None
    
    def to_dict(self):
        """Convert to dictionary with datetime serialization"""
        d = asdict(self)
        d['t_entry'] = self.t_entry.isoformat() if self.t_entry else None
        d['t_exit'] = self.t_exit.isoformat() if self.t_exit else None
        return d

def _slippage(amihud: float, px: float) -> float:
    """
    Calculate slippage based on market liquidity (Amihud illiquidity)
    Thinner markets = higher slippage
    
    Returns slippage in dollar terms (0-15 bps of price)
    """
    # Map Amihud to bps slippage: 0–15 bps
    # Liquid (1e-11): ~1 bps
    # Illiquid (1e-8): ~15 bps
    if amihud <= 0:
        bps = 1.0
    else:
        # Log scale mapping
        log_amihud = np.log10(max(amihud, 1e-15))
        # -11 → 1 bps, -8 → 15 bps
        bps = max(1.0, min(15.0, 1.0 + 14.0 * (log_amihud + 11) / 3))
    
    return px * (bps / 1e4)

def backtest_day(
    symbol: str, 
    date: str, 
    l1_path: str = "data_l1", 
    feature_set_id: str = "v0.1.0"
) -> Dict[str, Any]:
    """
    Replay a single trading day with event-time logic
    
    Args:
        symbol: Trading symbol (e.g., "SPY")
        date: Date in YYYY-MM-DD format
        l1_path: Path to L1 data directory
        feature_set_id: Feature set version to use
    
    Returns:
        Dictionary with backtest results including trades, P&L, and stats
    """
    fs = FeatureStore(root="data", read_only=True)
    
    # Load L1 data for the day
    l1_fn = Path(l1_path) / f"l1_{date}.parquet"
    if not l1_fn.exists():
        return {
            "error": f"No L1 data found for {date}",
            "path": str(l1_fn)
        }
    
    l1 = pd.read_parquet(l1_fn)
    l1 = l1[l1["symbol"] == symbol].sort_values("t_event").reset_index(drop=True)
    
    if l1.empty:
        return {
            "error": f"No data for {symbol} on {date}"
        }
    
    bars = l1["t_event"].tolist()
    
    # Trading state
    position: Optional[Trade] = None
    trades: List[Trade] = []
    equity_curve = []
    cash = 0.0
    size = 1.0  # 1 share/unit for simplicity
    
    # Replay each bar (except last, since we need next-bar for execution)
    for i, t in enumerate(bars[:-1]):
        try:
            # Read L3 features (point-in-time) for this bar
            row = fs.read_pit(symbol, t, feature_set_id)
        except (FileNotFoundError, ValueError):
            # No features for this bar - skip
            mtm = 0.0
            if position is not None:
                px_now = float(l1.loc[i, "price"])
                mtm = (px_now - position.entry_px) * position.direction * position.size
            equity_curve.append((t, cash + mtm))
            continue
        
        # Unpack features for agents
        hedge = row.get("hedge") or {}
        liq = row.get("liquidity") or {}
        sent = row.get("sentiment") or {}
        
        # Need all three engines to make a decision
        if not (hedge and liq and sent):
            mtm = 0.0
            if position is not None:
                px_now = float(l1.loc[i, "price"])
                mtm = (px_now - position.entry_px) * position.direction * position.size
            equity_curve.append((t, cash + mtm))
            continue
        
        # Build agent views and compose idea
        px_now = float(l1.loc[i, "price"])
        
        v1 = agent1_hedge(symbol, t, hedge["present"], hedge["future"])
        v2 = agent2_liquidity(symbol, t, liq["present"], liq["future"], px_now)
        v3 = agent3_sentiment(symbol, t, sent["present"], sent["future"])
        
        idea = compose(
            symbol, t, [v1, v2, v3],
            amihud=float(liq["present"]["amihud"]),
            reliability={"hedge": 1.0, "liquidity": 1.0, "sentiment": 1.0}
        )
        
        # Get prices and slippage
        px_next = float(l1.loc[i + 1, "price"])
        amihud = float(liq["present"]["amihud"])
        slip = _slippage(amihud, px_now)
        
        # --- Manage open position ---
        if position is not None:
            # Decrement time stop
            position.time_stop_bars -= 1
            exit_reason = None
            
            # Check for direction flip
            if idea.get("take_trade"):
                new_dir = 1 if idea["direction"] == "long" else -1
                if new_dir != position.direction:
                    exit_reason = "direction_flip"
            
            # Check time stop
            if position.time_stop_bars <= 0 and exit_reason is None:
                exit_reason = "time_stop"
            
            # Execute exit if triggered
            if exit_reason:
                # Exit at next bar with slippage
                if position.direction > 0:  # Long exit = sell
                    exit_px = px_next - slip
                else:  # Short exit = buy to cover
                    exit_px = px_next + slip
                
                pnl = (exit_px - position.entry_px) * position.direction * position.size
                
                position.t_exit = l1.loc[i + 1, "t_event"]
                position.exit_px = exit_px
                position.pnl = pnl
                position.exit_reason = exit_reason
                
                cash += pnl
                trades.append(position)
                position = None
        
        # --- Open new position if signal ---
        if position is None and idea.get("take_trade"):
            direction = 1 if idea["direction"] == "long" else -1
            size_mult = float(idea.get("position_sizing_hint", 1.0))
            
            # Entry at next bar with slippage
            if direction > 0:  # Long entry = buy
                entry_px = px_next + slip
            else:  # Short entry = sell
                entry_px = px_next - slip
            
            position = Trade(
                t_entry=l1.loc[i + 1, "t_event"],
                direction=direction,
                entry_px=entry_px,
                size=size * size_mult,
                time_stop_bars=int(idea.get("time_stop_bars", 8))
            )
        
        # Mark-to-market and record equity
        mtm = 0.0
        if position is not None:
            mtm = (px_now - position.entry_px) * position.direction * position.size
        equity_curve.append((t, cash + mtm))
    
    # Close any open position at end of day
    if position is not None:
        last_px = float(l1.iloc[-1]["price"])
        amihud_last = 1e-10  # Use reasonable default
        slip = _slippage(amihud_last, last_px)
        
        if position.direction > 0:
            exit_px = last_px - slip
        else:
            exit_px = last_px + slip
        
        pnl = (exit_px - position.entry_px) * position.direction * position.size
        
        position.t_exit = l1.iloc[-1]["t_event"]
        position.exit_px = exit_px
        position.pnl = pnl
        position.exit_reason = "end_of_day"
        
        cash += pnl
        trades.append(position)
    
    # Calculate statistics
    eq = pd.DataFrame(equity_curve, columns=["t", "equity"])
    
    if len(eq) > 10:
        ret = eq["equity"].diff().fillna(0.0)
        sharpe = (ret.mean() / (ret.std() + 1e-9)) * np.sqrt(390)  # Annualized intraday
        max_dd = float((eq["equity"].cummax() - eq["equity"]).max())
        
        # Win rate
        winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
        win_rate = len(winning_trades) / len(trades) if trades else 0.0
        
        # Average win/loss
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0.0
        losing_trades = [t for t in trades if t.pnl and t.pnl < 0]
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0.0
    else:
        sharpe = 0.0
        max_dd = 0.0
        win_rate = 0.0
        avg_win = 0.0
        avg_loss = 0.0
    
    return {
        "symbol": symbol,
        "date": date,
        "pnl": float(cash),
        "num_trades": len(trades),
        "win_rate": float(win_rate),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "sharpe_like_intraday": float(sharpe),
        "max_drawdown": max_dd,
        "equity_curve": eq.to_dict(orient="records") if not eq.empty else [],
        "trades": [t.to_dict() for t in trades]
    }