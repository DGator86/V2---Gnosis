# agents/trade_agent/exit_manager.py

"""
Exit management system for options trades.
Defines target, stop, and time-based exit rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from .schemas import TradeIdea, StrategyType


class ExitTrigger(str, Enum):
    """Type of exit signal."""
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIME_DECAY = "time_decay"
    GREEKS_THRESHOLD = "greeks_threshold"
    TRAILING_STOP = "trailing_stop"
    BREAKEVEN_STOP = "breakeven_stop"


@dataclass
class ExitRule:
    """
    Defines conditions for exiting a trade.
    """
    
    # Profit targets
    profit_target_pct: Optional[float] = None  # % of max profit
    profit_target_dollars: Optional[float] = None  # Absolute $
    
    # Stop losses
    stop_loss_pct: Optional[float] = None  # % of max loss
    stop_loss_dollars: Optional[float] = None  # Absolute $
    
    # Time-based exits
    max_days_to_expiry: Optional[int] = None  # Exit N days before expiry
    max_holding_days: Optional[int] = None  # Max calendar days to hold
    
    # Greeks-based exits
    theta_threshold: Optional[float] = None  # Exit if theta decay exceeds
    delta_threshold: Optional[float] = None  # Exit if delta changes
    
    # Trailing stop
    trailing_stop_pct: Optional[float] = None  # Trail by % of max profit
    
    # Breakeven management
    move_to_breakeven_at_pct: Optional[float] = None  # Move stop to BE at X% profit


@dataclass
class ExitSignal:
    """Signal to exit a position."""
    trigger: ExitTrigger
    reason: str
    should_exit: bool
    suggested_action: str  # "close_full", "close_partial", "adjust_stop"


def create_default_exit_rules(
    strategy_type: StrategyType,
    confidence: float,
) -> ExitRule:
    """
    Create default exit rules based on strategy type and confidence.
    
    Higher confidence → wider stops, longer holding period.
    Lower confidence → tighter stops, quicker exits.
    """
    
    # Base rules by strategy family
    if strategy_type in [
        StrategyType.LONG_CALL,
        StrategyType.LONG_PUT,
        StrategyType.CALL_DEBIT_SPREAD,
        StrategyType.PUT_DEBIT_SPREAD,
    ]:
        # Directional debit strategies
        base_profit_target = 0.50  # 50% of max profit
        base_stop_loss = 0.50  # 50% of max loss
        max_dte = 5  # Exit 5 days before expiry
        
    elif strategy_type in [
        StrategyType.IRON_CONDOR,
        StrategyType.CALENDAR_SPREAD,
        StrategyType.BROKEN_WING_BUTTERFLY,
    ]:
        # Income/theta strategies
        base_profit_target = 0.50  # Take profit at 50%
        base_stop_loss = 1.00  # Full stop at max loss
        max_dte = 3  # Exit 3 days before expiry
        
    elif strategy_type in [
        StrategyType.STRADDLE,
        StrategyType.STRANGLE,
        StrategyType.REVERSE_IRON_CONDOR,
    ]:
        # Volatility strategies
        base_profit_target = 0.75  # Let runners run
        base_stop_loss = 0.75  # Wider stop for vol plays
        max_dte = 7  # Exit 1 week before expiry
        
    else:
        # Default for synthetics and others
        base_profit_target = 0.50
        base_stop_loss = 0.50
        max_dte = 5
    
    # Adjust based on confidence
    # High confidence → wider stops, higher targets
    confidence_multiplier = 0.5 + confidence  # Range: 0.5 to 1.5
    
    profit_target = min(1.0, base_profit_target * confidence_multiplier)
    stop_loss = base_stop_loss / confidence_multiplier  # Tighter stop with low confidence
    
    # Trailing stop: activate after reaching 25% profit
    trailing_stop = 0.15  # Trail by 15% of peak profit
    
    # Move to breakeven after reaching 30% profit
    breakeven_trigger = 0.30
    
    return ExitRule(
        profit_target_pct=profit_target,
        stop_loss_pct=stop_loss,
        max_days_to_expiry=max_dte,
        max_holding_days=int(30 / confidence_multiplier),  # 20-60 days
        trailing_stop_pct=trailing_stop,
        move_to_breakeven_at_pct=breakeven_trigger,
        theta_threshold=-50.0,  # Exit if losing $50/day to theta
        delta_threshold=None,  # Not used for now
    )


def check_exit_conditions(
    idea: TradeIdea,
    current_price: float,
    current_pnl: float,
    days_held: int,
    days_to_expiry: int,
    current_theta: float,
    peak_pnl: float,
    exit_rule: ExitRule,
) -> ExitSignal:
    """
    Check if any exit conditions are met.
    
    Args:
        idea: Original trade idea
        current_price: Current underlying price
        current_pnl: Current profit/loss
        days_held: Days since entry
        days_to_expiry: Days until expiration
        current_theta: Current theta value
        peak_pnl: Highest PnL achieved (for trailing stop)
        exit_rule: Exit rules to apply
    
    Returns:
        ExitSignal indicating whether to exit and why
    """
    
    # ============================================================
    # PROFIT TARGET
    # ============================================================
    
    if exit_rule.profit_target_pct and idea.max_profit:
        target_pnl = idea.max_profit * exit_rule.profit_target_pct
        if current_pnl >= target_pnl:
            return ExitSignal(
                trigger=ExitTrigger.PROFIT_TARGET,
                reason=f"Profit target hit: ${current_pnl:.2f} >= ${target_pnl:.2f}",
                should_exit=True,
                suggested_action="close_full",
            )
    
    if exit_rule.profit_target_dollars:
        if current_pnl >= exit_rule.profit_target_dollars:
            return ExitSignal(
                trigger=ExitTrigger.PROFIT_TARGET,
                reason=f"Profit target hit: ${current_pnl:.2f}",
                should_exit=True,
                suggested_action="close_full",
            )
    
    # ============================================================
    # STOP LOSS
    # ============================================================
    
    if exit_rule.stop_loss_pct and idea.max_loss:
        stop_pnl = -idea.max_loss * exit_rule.stop_loss_pct
        if current_pnl <= stop_pnl:
            return ExitSignal(
                trigger=ExitTrigger.STOP_LOSS,
                reason=f"Stop loss hit: ${current_pnl:.2f} <= ${stop_pnl:.2f}",
                should_exit=True,
                suggested_action="close_full",
            )
    
    if exit_rule.stop_loss_dollars:
        if current_pnl <= -exit_rule.stop_loss_dollars:
            return ExitSignal(
                trigger=ExitTrigger.STOP_LOSS,
                reason=f"Stop loss hit: ${current_pnl:.2f}",
                should_exit=True,
                suggested_action="close_full",
            )
    
    # ============================================================
    # TIME-BASED EXITS
    # ============================================================
    
    if exit_rule.max_days_to_expiry:
        if days_to_expiry <= exit_rule.max_days_to_expiry:
            return ExitSignal(
                trigger=ExitTrigger.TIME_DECAY,
                reason=f"Approaching expiry: {days_to_expiry} DTE",
                should_exit=True,
                suggested_action="close_full",
            )
    
    if exit_rule.max_holding_days:
        if days_held >= exit_rule.max_holding_days:
            return ExitSignal(
                trigger=ExitTrigger.TIME_DECAY,
                reason=f"Max holding period reached: {days_held} days",
                should_exit=True,
                suggested_action="close_full",
            )
    
    # ============================================================
    # GREEKS-BASED EXITS
    # ============================================================
    
    if exit_rule.theta_threshold:
        if current_theta < exit_rule.theta_threshold:
            return ExitSignal(
                trigger=ExitTrigger.GREEKS_THRESHOLD,
                reason=f"Theta decay excessive: ${current_theta:.2f}/day",
                should_exit=True,
                suggested_action="close_full",
            )
    
    # ============================================================
    # TRAILING STOP
    # ============================================================
    
    if exit_rule.trailing_stop_pct and peak_pnl > 0:
        # Trail stop from peak
        trailing_stop_level = peak_pnl * (1 - exit_rule.trailing_stop_pct)
        if current_pnl < trailing_stop_level:
            return ExitSignal(
                trigger=ExitTrigger.TRAILING_STOP,
                reason=f"Trailing stop hit: ${current_pnl:.2f} < ${trailing_stop_level:.2f} "
                       f"(peak was ${peak_pnl:.2f})",
                should_exit=True,
                suggested_action="close_full",
            )
    
    # ============================================================
    # BREAKEVEN STOP ADJUSTMENT
    # ============================================================
    
    if exit_rule.move_to_breakeven_at_pct and idea.max_profit:
        breakeven_trigger = idea.max_profit * exit_rule.move_to_breakeven_at_pct
        if current_pnl >= breakeven_trigger and peak_pnl >= breakeven_trigger:
            # Don't exit, but signal to adjust stop to breakeven
            return ExitSignal(
                trigger=ExitTrigger.BREAKEVEN_STOP,
                reason=f"Move stop to breakeven (hit ${breakeven_trigger:.2f})",
                should_exit=False,
                suggested_action="adjust_stop",
            )
    
    # No exit conditions met
    return ExitSignal(
        trigger=ExitTrigger.PROFIT_TARGET,  # Placeholder
        reason="No exit conditions met",
        should_exit=False,
        suggested_action="hold",
    )


def apply_exit_rules_to_idea(
    idea: TradeIdea,
    confidence: float,
) -> TradeIdea:
    """
    Attach default exit rules to a trade idea.
    Stores rules in idea metadata for later use.
    """
    
    exit_rules = create_default_exit_rules(
        strategy_type=idea.strategy_type,
        confidence=confidence,
    )
    
    # Store in idea (would need to add exit_rules field to TradeIdea schema)
    # For now, this is a placeholder showing the integration pattern
    
    return idea
