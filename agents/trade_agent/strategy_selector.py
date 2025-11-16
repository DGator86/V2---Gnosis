# agents/trade_agent/strategy_selector.py

from __future__ import annotations

from typing import Callable, List

from .options_strategies import (
    build_broken_wing_butterfly,
    build_calendar_spread,
    build_call_debit_spread,
    build_diagonal_spread,
    build_iron_condor,
    build_long_call,
    build_long_put,
    build_put_debit_spread,
    build_reverse_iron_condor,
    build_straddle,
    build_strangle,
    build_synthetic_long,
    build_synthetic_short,
)
from .schemas import ComposerTradeContext, TradeIdea, Direction, VolatilityRegime


StrategyBuilder = Callable[[ComposerTradeContext, float], TradeIdea]


def select_strategy_builders(ctx: ComposerTradeContext) -> List[StrategyBuilder]:
    """
    Map direction + vol regime + confidence → set of option strategy builders.
    Comprehensive strategy selection based on market context.
    """

    builders: list[StrategyBuilder] = []

    # ============================================================
    # DIRECTIONAL STRATEGIES
    # ============================================================
    
    if ctx.direction == Direction.BULLISH:
        # Strong conviction: outright calls
        if ctx.confidence >= 0.7:
            builders.append(build_long_call)
            builders.append(build_synthetic_long)  # For leverage
        
        # Moderate conviction: spreads
        builders.append(build_call_debit_spread)
        
        # Directional with income: diagonals and broken wings
        if ctx.confidence >= 0.5:
            builders.append(build_diagonal_spread)
            builders.append(build_broken_wing_butterfly)

    elif ctx.direction == Direction.BEARISH:
        # Strong conviction: outright puts
        if ctx.confidence >= 0.7:
            builders.append(build_long_put)
            builders.append(build_synthetic_short)  # For leverage
        
        # Moderate conviction: spreads
        builders.append(build_put_debit_spread)
        
        # Directional with income: diagonals and broken wings
        if ctx.confidence >= 0.5:
            builders.append(build_diagonal_spread)
            builders.append(build_broken_wing_butterfly)

    else:  # NEUTRAL / CHOP
        # Range-bound expectations
        builders.append(build_iron_condor)
        
        # Time decay plays
        if ctx.volatility_regime in [VolatilityRegime.LOW, VolatilityRegime.MID]:
            builders.append(build_calendar_spread)

    # ============================================================
    # VOLATILITY-DRIVEN STRATEGIES
    # ============================================================
    
    if ctx.volatility_regime == VolatilityRegime.VOL_EXPANSION:
        # Expecting big move, uncertain direction
        builders.append(build_straddle)
        builders.append(build_strangle)
        builders.append(build_reverse_iron_condor)

    if ctx.volatility_regime == VolatilityRegime.VOL_CRUSH:
        # Sell premium strategies
        if build_iron_condor not in builders:
            builders.append(build_iron_condor)
        builders.append(build_calendar_spread)

    # ============================================================
    # SPECIAL CONDITIONS
    # ============================================================
    
    # High energy + low confidence = expect volatility
    if ctx.confidence < 0.5 and hasattr(ctx, 'energy') and ctx.energy > 1.5:
        if build_straddle not in builders:
            builders.append(build_straddle)

    # De-duplicate while preserving order
    seen = set()
    unique_builders: list[StrategyBuilder] = []
    for b in builders:
        if b not in seen:
            seen.add(b)
            unique_builders.append(b)

    return unique_builders
