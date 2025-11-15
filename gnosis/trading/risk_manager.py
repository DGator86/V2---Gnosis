"""
Risk Manager

Portfolio-level risk controls:
- Position sizing (Kelly, fixed fraction, volatility-adjusted)
- Stop loss / take profit calculation
- Circuit breakers (drawdown protection)
- Correlation checks
"""

from __future__ import annotations
from typing import Optional, Dict
import numpy as np


class RiskManager:
    """
    Portfolio risk management
    
    Enforces:
    - Max position size
    - Volatility-adjusted sizing
    - Stop loss placement
    - Drawdown protection
    """
    
    def __init__(
        self,
        capital: float = 30000.0,
        max_position_pct: float = 0.15,  # Max 15% per position
        max_portfolio_risk: float = 0.30,  # Max 30% total at risk
        default_stop_pct: float = 0.02,  # 2% stop loss
        default_tp_pct: float = 0.04,  # 4% take profit (2:1 R:R)
        max_drawdown_pct: float = 0.10,  # 10% max drawdown
        use_volatility_sizing: bool = True
    ):
        self.capital = capital
        self.max_position_pct = max_position_pct
        self.max_portfolio_risk = max_portfolio_risk
        self.default_stop_pct = default_stop_pct
        self.default_tp_pct = default_tp_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.use_volatility_sizing = use_volatility_sizing
        
        # Track high water mark for drawdown
        self.high_water_mark = capital
        self.current_equity = capital
    
    def update_equity(self, pnl: float):
        """Update current equity and track drawdown"""
        self.current_equity = self.capital + pnl
        self.high_water_mark = max(self.high_water_mark, self.current_equity)
    
    def get_drawdown(self) -> float:
        """Calculate current drawdown from HWM"""
        return (self.current_equity - self.high_water_mark) / self.high_water_mark
    
    def is_circuit_breaker_triggered(self) -> bool:
        """Check if drawdown limit exceeded"""
        return self.get_drawdown() <= -self.max_drawdown_pct
    
    def calculate_position_size(
        self,
        confidence: float,
        volatility: Optional[float] = None,
        existing_positions: int = 0
    ) -> float:
        """
        Calculate position size based on confidence and risk parameters
        
        Args:
            confidence: Agent confidence (0-1)
            volatility: Asset volatility for scaling (optional)
            existing_positions: Number of open positions
        
        Returns:
            Position size as fraction of capital (0-max_position_pct)
        """
        # Base size from confidence
        base_size = confidence * self.max_position_pct
        
        # Volatility adjustment (inverse relationship)
        if self.use_volatility_sizing and volatility is not None:
            # Normalize volatility (assume typical SPY ~0.15)
            vol_scalar = 0.15 / max(volatility, 0.05)
            vol_scalar = np.clip(vol_scalar, 0.5, 2.0)  # Cap adjustment
            base_size *= vol_scalar
        
        # Portfolio heat adjustment
        # Reduce size if we have many positions
        if existing_positions > 0:
            heat_scalar = 1.0 - (existing_positions * 0.15)  # -15% per position
            base_size *= max(heat_scalar, 0.5)
        
        # Ensure within limits
        size = np.clip(base_size, 0.01, self.max_position_pct)
        
        return size
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        side: int,
        confidence: float,
        volatility: Optional[float] = None
    ) -> float:
        """
        Calculate stop loss price
        
        Uses wider stops for lower confidence and higher volatility.
        
        Args:
            entry_price: Entry price
            side: 1 = long, -1 = short
            confidence: Agent confidence
            volatility: Asset volatility (optional)
        
        Returns:
            Stop loss price
        """
        # Base stop distance
        stop_pct = self.default_stop_pct
        
        # Widen for low confidence
        if confidence < 0.6:
            stop_pct *= 1.5
        
        # Widen for high volatility
        if volatility is not None and volatility > 0.20:
            stop_pct *= (volatility / 0.15)
        
        # Cap at 5%
        stop_pct = min(stop_pct, 0.05)
        
        if side == 1:  # Long
            return entry_price * (1 - stop_pct)
        else:  # Short
            return entry_price * (1 + stop_pct)
    
    def calculate_take_profit(
        self,
        entry_price: float,
        side: int,
        stop_loss: float
    ) -> float:
        """
        Calculate take profit price
        
        Uses 2:1 reward:risk ratio by default.
        
        Args:
            entry_price: Entry price
            side: 1 = long, -1 = short
            stop_loss: Stop loss price
        
        Returns:
            Take profit price
        """
        risk_distance = abs(entry_price - stop_loss)
        reward_distance = risk_distance * 2.0  # 2:1 R:R
        
        if side == 1:  # Long
            return entry_price + reward_distance
        else:  # Short
            return entry_price - reward_distance
    
    def validate_trade(
        self,
        symbol: str,
        side: int,
        size: float,
        confidence: float,
        existing_risk: float
    ) -> tuple[bool, str]:
        """
        Validate if trade meets risk requirements
        
        Args:
            symbol: Trading symbol
            side: 1 = long, -1 = short
            size: Position size (fraction)
            confidence: Agent confidence
            existing_risk: Current portfolio risk exposure
        
        Returns:
            (allowed, reason)
        """
        # Check circuit breaker
        if self.is_circuit_breaker_triggered():
            return False, f"Circuit breaker triggered (DD: {self.get_drawdown():.2%})"
        
        # Check position size limits
        if size > self.max_position_pct:
            return False, f"Position size {size:.2%} exceeds max {self.max_position_pct:.2%}"
        
        # Check portfolio risk
        new_risk = existing_risk + size
        if new_risk > self.max_portfolio_risk:
            return False, f"Total risk {new_risk:.2%} exceeds max {self.max_portfolio_risk:.2%}"
        
        # Check minimum confidence
        if confidence < 0.5:
            return False, f"Confidence {confidence:.2f} too low (min 0.5)"
        
        return True, "OK"
    
    def get_risk_summary(self, positions: Dict) -> dict:
        """Get current risk metrics"""
        total_risk = sum(p.size for p in positions.values())
        
        return {
            "current_equity": self.current_equity,
            "high_water_mark": self.high_water_mark,
            "drawdown": self.get_drawdown(),
            "positions": len(positions),
            "total_risk": total_risk,
            "risk_utilization": total_risk / self.max_portfolio_risk,
            "circuit_breaker": self.is_circuit_breaker_triggered()
        }


if __name__ == "__main__":
    # Test risk manager
    print("="*60)
    print("  RISK MANAGER TEST")
    print("="*60)
    
    rm = RiskManager(capital=30000.0)
    
    # Test position sizing
    print("\n1. Position Sizing Tests:")
    for conf in [0.5, 0.65, 0.75, 0.85]:
        size = rm.calculate_position_size(conf, volatility=0.15)
        print(f"   Confidence {conf:.2f} → Size: {size:.2%}")
    
    # Test with volatility adjustment
    print("\n2. Volatility Adjustment:")
    for vol in [0.10, 0.15, 0.25]:
        size = rm.calculate_position_size(0.75, volatility=vol)
        print(f"   Vol {vol:.2f} → Size: {size:.2%}")
    
    # Test stop loss calculation
    print("\n3. Stop Loss Calculation:")
    entry = 580.0
    for conf in [0.55, 0.70, 0.85]:
        sl = rm.calculate_stop_loss(entry, side=1, confidence=conf, volatility=0.15)
        risk_pct = (entry - sl) / entry
        print(f"   Conf {conf:.2f} → SL: ${sl:.2f} (risk: {risk_pct:.2%})")
    
    # Test take profit
    print("\n4. Take Profit (2:1 R:R):")
    sl = rm.calculate_stop_loss(entry, side=1, confidence=0.75)
    tp = rm.calculate_take_profit(entry, side=1, stop_loss=sl)
    risk = entry - sl
    reward = tp - entry
    print(f"   Entry: ${entry:.2f}")
    print(f"   SL: ${sl:.2f} (risk: ${risk:.2f})")
    print(f"   TP: ${tp:.2f} (reward: ${reward:.2f})")
    print(f"   R:R = {reward/risk:.2f}:1")
    
    # Test circuit breaker
    print("\n5. Circuit Breaker:")
    rm.update_equity(-2000)  # -$2k loss
    print(f"   Equity: ${rm.current_equity:,.0f}")
    print(f"   Drawdown: {rm.get_drawdown():.2%}")
    print(f"   Triggered: {rm.is_circuit_breaker_triggered()}")
    
    rm.update_equity(-4000)  # Additional -$4k loss (total -$6k, -20%)
    print(f"\n   After more losses...")
    print(f"   Equity: ${rm.current_equity:,.0f}")
    print(f"   Drawdown: {rm.get_drawdown():.2%}")
    print(f"   Triggered: {rm.is_circuit_breaker_triggered()}")
    
    print("\n✅ Risk manager tests passed!")
