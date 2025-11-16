# agents/trade_agent/strategy_selector.py

from __future__ import annotations

from typing import Callable, List

from .options_strategies import (
    build_call_debit_spread,
    build_iron_condor,
    build_long_call,
    build_long_put,
    build_put_debit_spread,
    build_straddle,
    build_strangle,
)
from .schemas import ComposerTradeContext, TradeIdea, Direction, VolatilityRegime


StrategyBuilder = Callable[[ComposerTradeContext, float], TradeIdea]


def select_strategy_builders(ctx: ComposerTradeContext) -> List[StrategyBuilder]:
    """
    Map direction + vol regime → set of option strategy builders.
    This embodies the rule-based mapping we discussed.
    """

    builders: list[StrategyBuilder] = []

    # Directional bias
    if ctx.direction == Direction.BULLISH:
        builders.append(build_long_call)
        builders.append(build_call_debit_spread)

    elif ctx.direction == Direction.BEARISH:
        builders.append(build_long_put)
        builders.append(build_put_debit_spread)

    else:  # NEUTRAL / CHOP
        builders.append(build_iron_condor)

    # Volatility overlays
    if ctx.volatility_regime == VolatilityRegime.VOL_EXPANSION:
        builders.append(build_straddle)
        builders.append(build_strangle)

    if ctx.volatility_regime == VolatilityRegime.VOL_CRUSH:
        if build_iron_condor not in builders:
            builders.append(build_iron_condor)

    # De-duplicate while preserving order
    seen = set()
    unique_builders: list[StrategyBuilder] = []
    for b in builders:
        if b not in seen:
            seen.add(b)
            unique_builders.append(b)

    return unique_builders
