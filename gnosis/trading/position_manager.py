"""
Position Manager

Tracks open positions and manages lifecycle:
- Entry: Create position from agent decision
- Updates: Track P&L, time in position
- Exit: Close on TP/SL/time/signal
- Persistence: Survive restarts
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path
import json


@dataclass
class Position:
    """Open trading position"""
    position_id: str
    symbol: str
    side: int  # 1 = long, -1 = short
    size: float  # Position size (fraction of capital)
    entry_price: float
    entry_time: datetime
    entry_confidence: float
    
    # Risk parameters
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_bars: int = 24  # Auto-exit after N bars
    
    # State
    current_price: float = 0.0
    bars_held: int = 0
    unrealized_pnl: float = 0.0
    
    # Memory tracking
    episode_id: Optional[str] = None
    
    def update(self, current_price: float):
        """Update position with latest price"""
        self.current_price = current_price
        self.bars_held += 1
        
        # Calculate unrealized P&L
        if self.side == 1:  # Long
            pnl_pct = (current_price - self.entry_price) / self.entry_price
        else:  # Short
            pnl_pct = (self.entry_price - current_price) / self.entry_price
        
        self.unrealized_pnl = pnl_pct * self.size
    
    def check_exit_conditions(self) -> Optional[str]:
        """
        Check if position should exit
        
        Returns:
            Exit reason string or None
        """
        if self.stop_loss and self.current_price <= self.stop_loss:
            return "stop_loss"
        
        if self.take_profit and self.current_price >= self.take_profit:
            return "take_profit"
        
        if self.bars_held >= self.max_bars:
            return "time_stop"
        
        return None
    
    def to_dict(self) -> dict:
        """Serialize for storage"""
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side,
            "size": self.size,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "entry_confidence": self.entry_confidence,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "max_bars": self.max_bars,
            "current_price": self.current_price,
            "bars_held": self.bars_held,
            "unrealized_pnl": self.unrealized_pnl,
            "episode_id": self.episode_id
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> Position:
        """Deserialize from storage"""
        return cls(
            position_id=d["position_id"],
            symbol=d["symbol"],
            side=d["side"],
            size=d["size"],
            entry_price=d["entry_price"],
            entry_time=datetime.fromisoformat(d["entry_time"]),
            entry_confidence=d["entry_confidence"],
            stop_loss=d.get("stop_loss"),
            take_profit=d.get("take_profit"),
            max_bars=d.get("max_bars", 24),
            current_price=d.get("current_price", 0.0),
            bars_held=d.get("bars_held", 0),
            unrealized_pnl=d.get("unrealized_pnl", 0.0),
            episode_id=d.get("episode_id")
        )


class PositionManager:
    """
    Manages all open positions
    
    Features:
    - Track multiple positions
    - Risk checks (max positions, daily loss)
    - State persistence (JSON file)
    - P&L aggregation
    """
    
    def __init__(
        self,
        state_file: str = "trading_state.json",
        max_positions: int = 3,
        max_daily_loss: float = -0.05  # -5% daily loss limit
    ):
        self.state_file = Path(state_file)
        self.max_positions = max_positions
        self.max_daily_loss = max_daily_loss
        
        self.positions: Dict[str, Position] = {}
        self.daily_pnl: float = 0.0
        self.daily_trades: int = 0
        self.last_reset: datetime = datetime.now()
        
        self.load_state()
    
    def can_open_position(self, symbol: str) -> tuple[bool, str]:
        """
        Check if we can open a new position
        
        Returns:
            (allowed, reason)
        """
        # Check position limit
        if len(self.positions) >= self.max_positions:
            return False, f"Max positions ({self.max_positions}) reached"
        
        # Check if already have position in this symbol
        if symbol in self.positions:
            return False, f"Already have open position in {symbol}"
        
        # Check daily loss limit
        if self.daily_pnl <= self.max_daily_loss:
            return False, f"Daily loss limit hit ({self.daily_pnl:.2%})"
        
        return True, "OK"
    
    def open_position(
        self,
        symbol: str,
        side: int,
        size: float,
        entry_price: float,
        confidence: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        episode_id: Optional[str] = None
    ) -> Optional[Position]:
        """
        Open new position
        
        Returns:
            Position object or None if rejected
        """
        can_open, reason = self.can_open_position(symbol)
        if not can_open:
            print(f"⚠️  Cannot open {symbol}: {reason}")
            return None
        
        position_id = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        position = Position(
            position_id=position_id,
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            entry_time=datetime.now(),
            entry_confidence=confidence,
            stop_loss=stop_loss,
            take_profit=take_profit,
            episode_id=episode_id
        )
        
        self.positions[symbol] = position
        self.daily_trades += 1
        self.save_state()
        
        print(f"✅ Opened {symbol} {'LONG' if side == 1 else 'SHORT'}: "
              f"size={size:.2%}, entry=${entry_price:.2f}")
        
        return position
    
    def update_positions(self, prices: Dict[str, float]):
        """Update all positions with current prices"""
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update(prices[symbol])
    
    def check_exits(self) -> List[tuple[str, str]]:
        """
        Check all positions for exit conditions
        
        Returns:
            List of (symbol, exit_reason) tuples
        """
        to_exit = []
        
        for symbol, position in self.positions.items():
            exit_reason = position.check_exit_conditions()
            if exit_reason:
                to_exit.append((symbol, exit_reason))
        
        return to_exit
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str
    ) -> Optional[dict]:
        """
        Close position and return trade summary
        
        Returns:
            Trade summary dict or None
        """
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        # Calculate final P&L
        if position.side == 1:  # Long
            pnl_pct = (exit_price - position.entry_price) / position.entry_price
        else:  # Short
            pnl_pct = (position.entry_price - exit_price) / position.entry_price
        
        realized_pnl = pnl_pct * position.size
        
        # Update daily P&L
        self.daily_pnl += realized_pnl
        
        # Create trade summary
        trade = {
            "position_id": position.position_id,
            "symbol": symbol,
            "side": position.side,
            "size": position.size,
            "entry_price": position.entry_price,
            "entry_time": position.entry_time,
            "exit_price": exit_price,
            "exit_time": datetime.now(),
            "exit_reason": exit_reason,
            "bars_held": position.bars_held,
            "pnl_pct": pnl_pct,
            "realized_pnl": realized_pnl,
            "episode_id": position.episode_id
        }
        
        # Remove position
        del self.positions[symbol]
        self.save_state()
        
        outcome = "WIN" if realized_pnl > 0 else "LOSS"
        print(f"🔔 Closed {symbol} {outcome}: "
              f"PnL={realized_pnl:+.2%} ({exit_reason})")
        
        return trade
    
    def get_portfolio_summary(self) -> dict:
        """Get current portfolio state"""
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        
        return {
            "positions": len(self.positions),
            "symbols": list(self.positions.keys()),
            "unrealized_pnl": total_unrealized,
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
            "total_pnl": self.daily_pnl + total_unrealized
        }
    
    def reset_daily(self):
        """Reset daily counters (call at market open)"""
        today = datetime.now().date()
        if self.last_reset.date() < today:
            print(f"📅 New trading day: Yesterday PnL = {self.daily_pnl:+.2%}")
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.last_reset = datetime.now()
            self.save_state()
    
    def save_state(self):
        """Persist state to disk"""
        state = {
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
            "last_reset": self.last_reset.isoformat()
        }
        
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self):
        """Load state from disk"""
        if not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            self.positions = {
                k: Position.from_dict(v)
                for k, v in state.get("positions", {}).items()
            }
            self.daily_pnl = state.get("daily_pnl", 0.0)
            self.daily_trades = state.get("daily_trades", 0)
            self.last_reset = datetime.fromisoformat(state.get("last_reset", datetime.now().isoformat()))
            
            print(f"📂 Loaded state: {len(self.positions)} open positions")
        except Exception as e:
            print(f"⚠️  Could not load state: {e}")


if __name__ == "__main__":
    # Test position manager
    pm = PositionManager(state_file="test_state.json")
    
    # Test opening position
    pos = pm.open_position(
        symbol="SPY",
        side=1,
        size=0.10,
        entry_price=580.0,
        confidence=0.75,
        stop_loss=575.0,
        take_profit=585.0
    )
    
    # Simulate price updates
    print("\n📊 Simulating price movement...")
    for i, price in enumerate([580.5, 581.0, 582.0, 583.0, 585.5]):
        pm.update_positions({"SPY": price})
        exits = pm.check_exits()
        
        print(f"Bar {i+1}: SPY=${price:.2f}, "
              f"Unrealized PnL={pos.unrealized_pnl:+.2%}")
        
        if exits:
            symbol, reason = exits[0]
            trade = pm.close_position(symbol, price, reason)
            break
    
    # Show summary
    summary = pm.get_portfolio_summary()
    print(f"\n📈 Portfolio Summary:")
    print(f"   Total PnL: {summary['total_pnl']:+.2%}")
    print(f"   Daily Trades: {summary['daily_trades']}")
    
    print("\n✅ Position manager test passed!")
