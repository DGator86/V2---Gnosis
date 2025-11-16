# agents/trade_agent/options_strategies.py

from __future__ import annotations

from typing import List

from .expiration_selector import select_expiry
from .schemas import (
    ComposerTradeContext,
    Direction,
    OptionLeg,
    StrategyGreeks,
    StrategyType,
    TradeIdea,
)


# --------- Core directional strategies --------- #


def build_long_call(ctx: ComposerTradeContext, underlying_price: float) -> TradeIdea:
    expiry = select_expiry(ctx)
    strike = _choose_directional_strike(
        underlying_price=underlying_price,
        direction="call",
        ctx=ctx,
    )

    leg = OptionLeg(
        side="long",
        option_type="call",
        strike=strike,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        f"Long call targeting {ctx.expected_move.value} move in a "
        f"{ctx.volatility_regime.value} regime. "
        f"Expiry={expiry}, strike≈{strike:.2f}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.LONG_CALL,
        description=desc,
        legs=[leg],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.6,
            gamma=0.3,
            theta=-0.6,
            vega=0.7,
        ),
    )


def build_long_put(ctx: ComposerTradeContext, underlying_price: float) -> TradeIdea:
    expiry = select_expiry(ctx)
    strike = _choose_directional_strike(
        underlying_price=underlying_price,
        direction="put",
        ctx=ctx,
    )

    leg = OptionLeg(
        side="long",
        option_type="put",
        strike=strike,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        f"Long put targeting {ctx.expected_move.value} downside move in "
        f"{ctx.volatility_regime.value} regime. Expiry={expiry}, strike≈{strike:.2f}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.LONG_PUT,
        description=desc,
        legs=[leg],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=-0.6,
            gamma=0.3,
            theta=-0.6,
            vega=0.7,
        ),
    )


def build_call_debit_spread(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    expiry = select_expiry(ctx)

    lower, upper = _vertical_strikes(underlying_price, "call", ctx)

    long_leg = OptionLeg(
        side="long",
        option_type="call",
        strike=lower,
        expiry=expiry,
        quantity=1,
    )
    short_leg = OptionLeg(
        side="short",
        option_type="call",
        strike=upper,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        "Bullish call debit spread to capture upside while capping risk. "
        f"Long {lower:.2f}C / Short {upper:.2f}C, expiry={expiry}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.CALL_DEBIT_SPREAD,
        description=desc,
        legs=[long_leg, short_leg],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.35,
            gamma=0.2,
            theta=-0.2,
            vega=0.3,
        ),
    )


def build_put_debit_spread(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    expiry = select_expiry(ctx)

    lower, upper = _vertical_strikes(underlying_price, "put", ctx)

    long_leg = OptionLeg(
        side="long",
        option_type="put",
        strike=upper,
        expiry=expiry,
        quantity=1,
    )
    short_leg = OptionLeg(
        side="short",
        option_type="put",
        strike=lower,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        "Bearish put debit spread to capture downside with defined risk. "
        f"Long {upper:.2f}P / Short {lower:.2f}P, expiry={expiry}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.PUT_DEBIT_SPREAD,
        description=desc,
        legs=[long_leg, short_leg],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=-0.35,
            gamma=0.2,
            theta=-0.2,
            vega=0.3,
        ),
    )


# --------- Neutral / vol strategies --------- #


def build_iron_condor(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    expiry = select_expiry(ctx)

    wings = _iron_condor_wings(underlying_price, ctx)

    short_put, long_put, short_call, long_call = wings

    desc = (
        "Market-neutral iron condor targeting range-bound price action. "
        f"Short {short_put.strike:.2f}P / Long {long_put.strike:.2f}P / "
        f"Short {short_call.strike:.2f}C / Long {long_call.strike:.2f}C, "
        f"expiry={expiry}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.IRON_CONDOR,
        description=desc,
        legs=[short_put, long_put, short_call, long_call],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.0,
            gamma=-0.1,
            theta=0.6,
            vega=-0.4,
        ),
    )


def build_straddle(ctx: ComposerTradeContext, underlying_price: float) -> TradeIdea:
    expiry = select_expiry(ctx)
    k = round(underlying_price)  # ATM approximation

    long_call = OptionLeg(
        side="long",
        option_type="call",
        strike=k,
        expiry=expiry,
        quantity=1,
    )
    long_put = OptionLeg(
        side="long",
        option_type="put",
        strike=k,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        "Long straddle for large move in either direction under vol expansion. "
        f"ATM strikes at {k:.2f}, expiry={expiry}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.STRADDLE,
        description=desc,
        legs=[long_call, long_put],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.0,
            gamma=0.5,
            theta=-0.9,
            vega=0.9,
        ),
    )


def build_strangle(ctx: ComposerTradeContext, underlying_price: float) -> TradeIdea:
    expiry = select_expiry(ctx)

    call_strike = underlying_price * 1.02
    put_strike = underlying_price * 0.98

    long_call = OptionLeg(
        side="long",
        option_type="call",
        strike=call_strike,
        expiry=expiry,
        quantity=1,
    )
    long_put = OptionLeg(
        side="long",
        option_type="put",
        strike=put_strike,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        "Long strangle: OTM call and put to capture large move with lower premium "
        f"than straddle. Expiry={expiry}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.STRANGLE,
        description=desc,
        legs=[long_call, long_put],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.0,
            gamma=0.4,
            theta=-0.7,
            vega=0.8,
        ),
    )


# --------- Helpers --------- #


def _choose_directional_strike(
    underlying_price: float,
    direction: str,
    ctx: ComposerTradeContext,
) -> float:
    # Simple heuristic: higher confidence → closer to ATM
    moneyness = 0.02 * (1.0 - ctx.confidence)  # 0–2% OTM by default

    if direction == "call":
        return underlying_price * (1.0 + moneyness)
    else:
        return underlying_price * (1.0 - moneyness)


def _vertical_strikes(
    underlying_price: float,
    option_kind: str,
    ctx: ComposerTradeContext,
) -> tuple[float, float]:
    """
    Returns (lower_strike, upper_strike) for verticals.
    For calls: lower=long, upper=short.
    For puts: lower=short, upper=long.
    """
    width = 0.02  # 2% wide spread baseline; can be tuned by vol later

    if option_kind == "call":
        lower = underlying_price * 1.0
        upper = underlying_price * (1.0 + width)
    else:
        lower = underlying_price * (1.0 - width)
        upper = underlying_price * 1.0

    return lower, upper


def _iron_condor_wings(
    underlying_price: float,
    ctx: ComposerTradeContext,
) -> tuple[OptionLeg, OptionLeg, OptionLeg, OptionLeg]:
    expiry = select_expiry(ctx)

    wing_width = 0.04
    body_width = 0.02

    short_put_k = underlying_price * (1.0 - body_width)
    long_put_k = underlying_price * (1.0 - wing_width)
    short_call_k = underlying_price * (1.0 + body_width)
    long_call_k = underlying_price * (1.0 + wing_width)

    short_put = OptionLeg(
        side="short",
        option_type="put",
        strike=short_put_k,
        expiry=expiry,
        quantity=1,
    )
    long_put = OptionLeg(
        side="long",
        option_type="put",
        strike=long_put_k,
        expiry=expiry,
        quantity=1,
    )
    short_call = OptionLeg(
        side="short",
        option_type="call",
        strike=short_call_k,
        expiry=expiry,
        quantity=1,
    )
    long_call = OptionLeg(
        side="long",
        option_type="call",
        strike=long_call_k,
        expiry=expiry,
        quantity=1,
    )

    return short_put, long_put, short_call, long_call


# --------- Advanced time-based strategies --------- #


def build_calendar_spread(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    """
    Calendar spread (horizontal spread): Same strike, different expiries.
    Profits from time decay differential between near and far months.
    Best in low vol, neutral market expecting vol expansion near expiry.
    """
    from datetime import datetime, timedelta
    
    near_expiry = select_expiry(ctx)
    # Far expiry: typically 2-3x the near expiry DTE
    # Parse near expiry and add more time
    near_date = datetime.fromisoformat(near_expiry).date()
    from datetime import date
    today = date.today()
    days_to_near = (near_date - today).days
    far_date = near_date + timedelta(days=days_to_near)  # Double the time
    far_expiry = far_date.isoformat()
    
    strike = round(underlying_price)  # ATM
    
    short_leg = OptionLeg(
        side="short",
        option_type="call",
        strike=strike,
        expiry=near_expiry,
        quantity=1,
    )
    long_leg = OptionLeg(
        side="long",
        option_type="call",
        strike=strike,
        expiry=far_expiry,
        quantity=1,
    )
    
    desc = (
        f"Calendar spread at {strike:.2f} strike. "
        f"Short {near_expiry} / Long {far_expiry}. "
        "Profits from theta decay and potential vol expansion."
    )
    
    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.CALENDAR_SPREAD,
        description=desc,
        legs=[short_leg, long_leg],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.05,  # Near neutral
            gamma=0.1,
            theta=0.4,  # Positive theta from short near-term
            vega=0.3,   # Benefits from vol increase
        ),
    )


def build_diagonal_spread(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    """
    Diagonal spread: Different strikes AND different expiries.
    Directional bias with time decay component.
    Long far OTM + short near ATM/ITM.
    """
    from datetime import datetime, timedelta, date
    
    near_expiry = select_expiry(ctx)
    # Far expiry: typically 2-3x the near expiry DTE
    near_date = datetime.fromisoformat(near_expiry).date()
    today = date.today()
    days_to_near = (near_date - today).days
    far_date = near_date + timedelta(days=days_to_near)  # Double the time
    far_expiry = far_date.isoformat()
    
    # Bullish diagonal example: lower strike long, higher strike short
    long_strike = underlying_price * 0.98  # Slightly ITM long-term
    short_strike = underlying_price * 1.02  # Slightly OTM short-term
    
    long_leg = OptionLeg(
        side="long",
        option_type="call",
        strike=long_strike,
        expiry=far_expiry,
        quantity=1,
    )
    short_leg = OptionLeg(
        side="short",
        option_type="call",
        strike=short_strike,
        expiry=near_expiry,
        quantity=1,
    )
    
    desc = (
        f"Bullish diagonal spread: Long {long_strike:.2f}C {far_expiry} / "
        f"Short {short_strike:.2f}C {near_expiry}. "
        "Directional upside with income generation."
    )
    
    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.DIAGONAL_SPREAD,
        description=desc,
        legs=[long_leg, short_leg],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.25,  # Moderate bullish
            gamma=0.15,
            theta=0.2,   # Positive theta from short near leg
            vega=0.2,
        ),
    )


def build_broken_wing_butterfly(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    """
    Broken wing butterfly: Asymmetric butterfly with directional bias.
    Body shifted toward expected move direction.
    Higher probability, defined risk, directional play.
    """
    expiry = select_expiry(ctx)
    
    # Bullish broken wing: shift body higher
    # Standard butterfly: 1 lower, 2 middle, 1 upper
    # Broken wing: shift upper wing further out for directional bias
    
    if ctx.direction == Direction.BULLISH:  # Bullish
        lower_strike = underlying_price * 0.98
        middle_strike = underlying_price * 1.00
        upper_strike = underlying_price * 1.05  # Wider upper wing
    else:  # Bearish
        lower_strike = underlying_price * 0.95  # Wider lower wing
        middle_strike = underlying_price * 1.00
        upper_strike = underlying_price * 1.02
    
    long_lower = OptionLeg(
        side="long",
        option_type="call",
        strike=lower_strike,
        expiry=expiry,
        quantity=1,
    )
    short_middle = OptionLeg(
        side="short",
        option_type="call",
        strike=middle_strike,
        expiry=expiry,
        quantity=2,
    )
    long_upper = OptionLeg(
        side="long",
        option_type="call",
        strike=upper_strike,
        expiry=expiry,
        quantity=1,
    )
    
    desc = (
        f"Broken wing butterfly: {lower_strike:.2f}/{middle_strike:.2f}/{upper_strike:.2f} "
        f"calls, expiry={expiry}. "
        "Asymmetric risk/reward with directional bias."
    )
    
    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.BROKEN_WING_BUTTERFLY,
        description=desc,
        legs=[long_lower, short_middle, long_upper],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.15 if ctx.direction == Direction.BULLISH else -0.15,
            gamma=-0.05,
            theta=0.3,
            vega=-0.2,
        ),
    )


def build_synthetic_long(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    """
    Synthetic long stock: Long call + short put at same strike.
    Replicates long stock position with options.
    Used when stock is hard to borrow or for leverage.
    """
    expiry = select_expiry(ctx)
    strike = round(underlying_price)  # ATM
    
    long_call = OptionLeg(
        side="long",
        option_type="call",
        strike=strike,
        expiry=expiry,
        quantity=1,
    )
    short_put = OptionLeg(
        side="short",
        option_type="put",
        strike=strike,
        expiry=expiry,
        quantity=1,
    )
    
    desc = (
        f"Synthetic long at {strike:.2f}: Long call + short put, expiry={expiry}. "
        "Replicates 100 shares long stock exposure."
    )
    
    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.SYNTHETIC_LONG,
        description=desc,
        legs=[long_call, short_put],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=1.0,   # Equivalent to 100 delta (long stock)
            gamma=0.0,   # Offsetting gamma
            theta=0.0,   # Offsetting theta
            vega=0.0,    # Offsetting vega
        ),
    )


def build_synthetic_short(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    """
    Synthetic short stock: Long put + short call at same strike.
    Replicates short stock position with options.
    Used when stock is hard to borrow or expensive to short.
    """
    expiry = select_expiry(ctx)
    strike = round(underlying_price)  # ATM
    
    long_put = OptionLeg(
        side="long",
        option_type="put",
        strike=strike,
        expiry=expiry,
        quantity=1,
    )
    short_call = OptionLeg(
        side="short",
        option_type="call",
        strike=strike,
        expiry=expiry,
        quantity=1,
    )
    
    desc = (
        f"Synthetic short at {strike:.2f}: Long put + short call, expiry={expiry}. "
        "Replicates short stock exposure."
    )
    
    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.SYNTHETIC_SHORT,
        description=desc,
        legs=[long_put, short_call],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=-1.0,  # Equivalent to -100 delta (short stock)
            gamma=0.0,
            theta=0.0,
            vega=0.0,
        ),
    )


def build_reverse_iron_condor(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    """
    Reverse iron condor: Opposite of iron condor.
    Long inner wings, short outer wings.
    Profits from large move (breakout) in either direction.
    Best in low vol expecting vol expansion.
    """
    expiry = select_expiry(ctx)
    
    # Reverse IC structure: opposite of standard IC
    body_width = 0.02
    wing_width = 0.04
    
    # Long the body (expecting price to move outside)
    long_put_k = underlying_price * (1.0 - body_width)
    long_call_k = underlying_price * (1.0 + body_width)
    
    # Short the wings (protection)
    short_put_k = underlying_price * (1.0 - wing_width)
    short_call_k = underlying_price * (1.0 + wing_width)
    
    long_put = OptionLeg(
        side="long",
        option_type="put",
        strike=long_put_k,
        expiry=expiry,
        quantity=1,
    )
    short_put = OptionLeg(
        side="short",
        option_type="put",
        strike=short_put_k,
        expiry=expiry,
        quantity=1,
    )
    long_call = OptionLeg(
        side="long",
        option_type="call",
        strike=long_call_k,
        expiry=expiry,
        quantity=1,
    )
    short_call = OptionLeg(
        side="short",
        option_type="call",
        strike=short_call_k,
        expiry=expiry,
        quantity=1,
    )
    
    desc = (
        "Reverse iron condor expecting breakout. "
        f"Long {long_put_k:.2f}P / Short {short_put_k:.2f}P / "
        f"Long {long_call_k:.2f}C / Short {short_call_k:.2f}C, "
        f"expiry={expiry}. Profits from large move either direction."
    )
    
    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.REVERSE_IRON_CONDOR,
        description=desc,
        legs=[long_put, short_put, long_call, short_call],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.0,    # Market neutral
            gamma=0.4,    # Positive gamma
            theta=-0.5,   # Negative theta (long premium)
            vega=0.6,     # Positive vega (benefits from vol increase)
        ),
    )
