# agents/trade_agent/risk_analyzer.py

"""
Advanced risk analysis for options strategies.
Computes PnL cones, breakeven points, Greeks evolution, and precise max profit/loss.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from .schemas import OptionLeg, TradeIdea


@dataclass
class PnLPoint:
    """Single point on the PnL curve."""
    underlying_price: float
    profit_loss: float
    delta: float
    gamma: float
    theta: float
    vega: float


@dataclass
class RiskMetrics:
    """Comprehensive risk metrics for a trade idea."""
    max_profit: float
    max_loss: float
    breakeven_points: List[float]
    profit_probability: float  # Rough estimate based on strikes
    risk_reward_ratio: float
    pnl_cone: List[PnLPoint]
    
    # Capital efficiency
    return_on_risk: float  # max_profit / max_loss
    capital_required: float


def analyze_trade_risk(
    idea: TradeIdea,
    underlying_price: float,
    implied_vol: float = 0.30,
    risk_free_rate: float = 0.04,
    price_range_pct: float = 0.20,
    num_points: int = 50,
) -> RiskMetrics:
    """
    Compute comprehensive risk metrics for a trade idea.
    
    Args:
        idea: TradeIdea with legs
        underlying_price: Current underlying price
        implied_vol: Implied volatility (annualized)
        risk_free_rate: Risk-free rate (annualized)
        price_range_pct: % range for PnL cone (e.g., 0.20 = ±20%)
        num_points: Number of points in PnL cone
    
    Returns:
        RiskMetrics with all computed metrics
    """
    
    # Calculate PnL cone
    pnl_cone = _compute_pnl_cone(
        idea.legs,
        underlying_price,
        price_range_pct,
        num_points,
        implied_vol,
        risk_free_rate,
    )
    
    # Find max profit and max loss from PnL cone
    max_profit = max(pt.profit_loss for pt in pnl_cone)
    max_loss = min(pt.profit_loss for pt in pnl_cone)
    
    # Find breakeven points (where PnL crosses zero)
    breakevens = _find_breakeven_points(pnl_cone)
    
    # Estimate profit probability based on position in cone
    profit_prob = _estimate_profit_probability(pnl_cone, underlying_price)
    
    # Risk/reward ratio
    risk_reward = abs(max_profit / max_loss) if max_loss != 0 else float('inf')
    
    # Return on risk (max profit per dollar risked)
    return_on_risk = max_profit / abs(max_loss) if max_loss < 0 else 0.0
    
    # Capital required (sum of debits)
    capital_required = _compute_capital_required(idea.legs)
    
    return RiskMetrics(
        max_profit=max_profit,
        max_loss=max_loss,
        breakeven_points=breakevens,
        profit_probability=profit_prob,
        risk_reward_ratio=risk_reward,
        pnl_cone=pnl_cone,
        return_on_risk=return_on_risk,
        capital_required=capital_required,
    )


def _compute_pnl_cone(
    legs: List[OptionLeg],
    underlying_price: float,
    price_range_pct: float,
    num_points: int,
    implied_vol: float,
    risk_free_rate: float,
) -> List[PnLPoint]:
    """
    Compute PnL at expiration across a range of underlying prices.
    Simplified: assumes holding to expiration (no time decay modeling).
    """
    
    min_price = underlying_price * (1 - price_range_pct)
    max_price = underlying_price * (1 + price_range_pct)
    price_step = (max_price - min_price) / (num_points - 1)
    
    pnl_points: List[PnLPoint] = []
    
    for i in range(num_points):
        price = min_price + i * price_step
        
        # Calculate PnL at this price
        pnl = 0.0
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        
        for leg in legs:
            leg_pnl, leg_greeks = _compute_leg_pnl(
                leg=leg,
                underlying_price=price,
                entry_price=underlying_price,
                implied_vol=implied_vol,
                risk_free_rate=risk_free_rate,
            )
            
            pnl += leg_pnl
            total_delta += leg_greeks['delta']
            total_gamma += leg_greeks['gamma']
            total_theta += leg_greeks['theta']
            total_vega += leg_greeks['vega']
        
        pnl_points.append(PnLPoint(
            underlying_price=price,
            profit_loss=pnl,
            delta=total_delta,
            gamma=total_gamma,
            theta=total_theta,
            vega=total_vega,
        ))
    
    return pnl_points


def _compute_leg_pnl(
    leg: OptionLeg,
    underlying_price: float,
    entry_price: float,
    implied_vol: float,
    risk_free_rate: float,
) -> tuple[float, dict]:
    """
    Compute PnL and Greeks for a single leg at expiration.
    Simplified Black-Scholes approach.
    """
    
    # At expiration, intrinsic value only
    if leg.option_type == "call":
        intrinsic = max(0, underlying_price - leg.strike)
    else:  # put
        intrinsic = max(0, leg.strike - underlying_price)
    
    # Entry cost (simplified: use mid_price or estimate)
    entry_cost = leg.mid_price if leg.mid_price else _estimate_option_price(
        leg, entry_price, implied_vol, risk_free_rate
    )
    
    # PnL = (exit value - entry cost) * quantity * multiplier
    # For long: profit = intrinsic - entry_cost
    # For short: profit = entry_cost - intrinsic
    if leg.side == "long":
        leg_pnl = (intrinsic - entry_cost) * leg.quantity * 100
    else:  # short
        leg_pnl = (entry_cost - intrinsic) * leg.quantity * 100
    
    # Simplified Greeks at expiration (mostly zero except delta)
    greeks = {
        'delta': _compute_delta(leg, underlying_price, implied_vol),
        'gamma': 0.0,  # Zero at expiration
        'theta': 0.0,  # Zero at expiration
        'vega': 0.0,   # Zero at expiration
    }
    
    return leg_pnl, greeks


def _estimate_option_price(
    leg: OptionLeg,
    underlying_price: float,
    implied_vol: float,
    risk_free_rate: float,
    time_to_expiry: float = 0.1,  # Assume 36 days ~ 0.1 year
) -> float:
    """
    Simplified option pricing (not full Black-Scholes).
    For trade generation, we use rough estimates.
    """
    
    # Moneyness
    if leg.option_type == "call":
        moneyness = underlying_price / leg.strike
    else:
        moneyness = leg.strike / underlying_price
    
    # Intrinsic value
    intrinsic = max(0, underlying_price - leg.strike) if leg.option_type == "call" else max(0, leg.strike - underlying_price)
    
    # Time value (very rough approximation)
    base_time_value = underlying_price * implied_vol * math.sqrt(time_to_expiry) * 0.4
    
    # Adjust based on moneyness (distance from ATM affects time value)
    # For calls: moneyness = underlying/strike. OTM when < 1.0, ITM when > 1.0
    # For puts: moneyness = strike/underlying. OTM when < 1.0, ITM when > 1.0
    # ATM (near 1.0) has highest time value
    distance_from_atm = abs(1.0 - moneyness)
    
    if distance_from_atm <= 0.01:  # Within 1% of ATM
        time_value = base_time_value
    elif distance_from_atm <= 0.03:  # 1-3% away from ATM
        time_value = base_time_value * 0.75
    elif distance_from_atm <= 0.07:  # 3-7% away
        time_value = base_time_value * 0.5
    elif distance_from_atm <= 0.15:  # 7-15% away
        time_value = base_time_value * 0.3
    else:  # More than 15% away
        time_value = base_time_value * 0.15
    
    return intrinsic + time_value


def _compute_delta(
    leg: OptionLeg,
    underlying_price: float,
    implied_vol: float,
) -> float:
    """Simplified delta calculation."""
    
    moneyness = underlying_price / leg.strike
    
    if leg.option_type == "call":
        # ATM call: ~0.5 delta, ITM: ~1.0, OTM: ~0
        if moneyness > 1.1:
            delta = 0.9
        elif moneyness > 1.02:
            delta = 0.7
        elif moneyness > 0.98:
            delta = 0.5
        elif moneyness > 0.9:
            delta = 0.3
        else:
            delta = 0.1
    else:  # put
        # ATM put: ~-0.5 delta, ITM: ~-1.0, OTM: ~0
        if moneyness < 0.9:
            delta = -0.9
        elif moneyness < 0.98:
            delta = -0.7
        elif moneyness < 1.02:
            delta = -0.5
        elif moneyness < 1.1:
            delta = -0.3
        else:
            delta = -0.1
    
    # Apply side (long vs short)
    if leg.side == "short":
        delta = -delta
    
    return delta * leg.quantity


def _find_breakeven_points(pnl_cone: List[PnLPoint]) -> List[float]:
    """Find prices where PnL crosses zero."""
    
    breakevens: List[float] = []
    
    for i in range(len(pnl_cone) - 1):
        current = pnl_cone[i]
        next_pt = pnl_cone[i + 1]
        
        # Check if PnL crosses zero between these points
        if (current.profit_loss <= 0 and next_pt.profit_loss >= 0) or \
           (current.profit_loss >= 0 and next_pt.profit_loss <= 0):
            # Linear interpolation to find exact crossover
            if next_pt.profit_loss != current.profit_loss:
                t = -current.profit_loss / (next_pt.profit_loss - current.profit_loss)
                breakeven = current.underlying_price + t * (next_pt.underlying_price - current.underlying_price)
                breakevens.append(breakeven)
    
    return breakevens


def _estimate_profit_probability(
    pnl_cone: List[PnLPoint],
    current_price: float,
) -> float:
    """
    Estimate probability of profit based on position structure.
    Simplified: % of cone that is profitable.
    """
    
    if not pnl_cone:
        return 0.5
    
    profitable_points = sum(1 for pt in pnl_cone if pt.profit_loss > 0)
    return profitable_points / len(pnl_cone)


def _compute_capital_required(legs: List[OptionLeg]) -> float:
    """
    Compute capital required to enter position.
    Sum of all debits (long legs).
    """
    
    capital = 0.0
    
    for leg in legs:
        if leg.side == "long":
            # Debit: we pay premium
            price = leg.mid_price if leg.mid_price else 2.0  # Default estimate
            capital += price * leg.quantity * 100
    
    return capital


def enhance_idea_with_risk_metrics(
    idea: TradeIdea,
    underlying_price: float,
    implied_vol: float = 0.30,
) -> TradeIdea:
    """
    Enhance a TradeIdea with computed risk metrics.
    Updates max_profit, max_loss fields.
    """
    
    metrics = analyze_trade_risk(
        idea=idea,
        underlying_price=underlying_price,
        implied_vol=implied_vol,
    )
    
    # Update the idea with computed metrics
    idea.max_profit = metrics.max_profit
    idea.max_loss = abs(metrics.max_loss)
    idea.breakeven_prices = metrics.breakeven_points
    
    return idea
